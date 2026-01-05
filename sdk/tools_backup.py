import asyncio
import os
import json
import aiofiles
import sdk.config as config
from loguru import logger
from sdk.system import get_cpu_temperature

async def get_system_temperature_tool():
    """
    Get the current CPU temperature of the system.
    
    Returns:
        str: The current CPU temperature formatted as a string (e.g. "45.0 C").
    """
    logger.info("TOOL EXECUTION: get_system_temperature_tool() started")
    temp = await get_cpu_temperature()
    logger.info(f"TOOL EXECUTION: get_system_temperature_tool() result: {temp}")
    return f"{temp:.1f} C"

async def get_system_logs_tool(lines: int = 20):
    """
    Get the last N lines of the system logs (pico service).
    
    Args:
        lines (int): Number of lines to retrieve (default 20, max 100).
        
    Returns:
        str: The log content.
    """
    logger.info(f"TOOL EXECUTION: get_system_logs_tool({lines}) started")
    lines = min(lines, 100)
    try:
        proc = await asyncio.create_subprocess_shell(
            f"journalctl -u pico* -n {lines} --no-pager", # Match pico-bot, pico-sms etc
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        logs = stdout.decode().strip()
        logger.info(f"TOOL EXECUTION: get_system_logs_tool() result length: {len(logs)}")
        return logs or "No logs found."
    except Exception as e:
        return f"Error reading logs: {e}"

async def restart_pico_tool():
    """
    Restart the pico services.
    
    Returns:
        str: Status message.
    """
    logger.info("TOOL EXECUTION: restart_pico_tool() started")
    # Trigger restart in background
    asyncio.create_task(asyncio.sleep(2))
    asyncio.create_task(asyncio.create_subprocess_shell("sudo systemctl restart pico-bot pico-sms pico-scheduler"))
    return "Restarting Pico services in 2 seconds..."

async def restart_system_tool():
    """
    Restart the entire system (Raspberry Pi).
    
    Returns:
        str: Status message.
    """
    logger.info("TOOL EXECUTION: restart_system_tool() started")
    asyncio.create_task(asyncio.sleep(2))
    asyncio.create_task(asyncio.create_subprocess_shell("sudo reboot"))
    return "Rebooting system in 2 seconds..."

async def get_sys_logs_tool(lines: int = 20):
    """
    Get the last N lines of the general system logs (journalctl).
    
    Args:
        lines (int): Number of lines to retrieve (default 20, max 100).
        
    Returns:
        str: The log content.
    """
    logger.info(f"TOOL EXECUTION: get_sys_logs_tool({lines}) started")
    lines = min(lines, 100)
    try:
        proc = await asyncio.create_subprocess_shell(
            f"journalctl -n {lines} --no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        logs = stdout.decode().strip()
        logger.info(f"TOOL EXECUTION: get_sys_logs_tool() result length: {len(logs)}")
        return logs or "No logs found."
    except Exception as e:
        return f"Error reading system logs: {e}"

async def read_inbox_tool(limit: int = 5):
    """
    Read the latest SMS messages by scanning the inbox directory.
    Merges multi-part messages automatically.
    
    Args:
        limit (int): Number of messages to retrieve (default 5).
        
    Returns:
        str: List of messages with sender and content.
    """
    from sdk.sms import get_inbox_messages
    logger.info(f"TOOL EXECUTION: read_inbox_tool({limit}) started")
    
    msgs = await get_inbox_messages(limit)
    if not msgs:
        return "Inbox is empty or directory not found."
    
    # Return as JSON for the agent
    return json.dumps(msgs)

async def check_uscis_tool():
    """
    Check the status of USCIS cases for the user.
    
    Returns:
        str: Status report for all configured cases.
    """
    from sdk.uscis import UscisClient
    logger.info("TOOL EXECUTION: check_uscis_tool() started")
    client = UscisClient()
    try:
        results = await client.check_all()
        # Format the result nicely for Telegram
        report = "📋 **USCIS Case Status Report**\n\n"
        for cn, status in results.items():
            if "error" in status:
                report += f"❌ `{cn}`: {status['error']}\n"
            else:
                text = status.get("case_status_content_chinese", "Unknown status").strip()
                date = status.get("case_status_date", "Unknown date")
                report += f"🔹 `{cn}`: **{text}** ({date})\n"
        return report
    except Exception as e:
        return f"Error checking USCIS: {e}"
    finally:
        await client.close()

def get_tools():
    return [
        get_system_temperature_tool,
        get_system_logs_tool,
        get_sys_logs_tool,
        read_inbox_tool,
        check_uscis_tool,
        restart_pico_tool,
        restart_system_tool
    ]
