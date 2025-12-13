import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import httpx
import os

# Project imports
from core.config import settings
from core.logger import logger
from services.monitoring.system import get_cpu_temperature

from core.logger import LOG_FILE
import aiofiles

# Google ADK Imports REMOVED (Handled in agents.py)
from services.agents import get_agent

# --- Tool Definitions ---

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
            f"journalctl -u pico -n {lines} --no-pager",
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
    Restart the pico service.
    
    Returns:
        str: Status message.
    """
    logger.info("TOOL EXECUTION: restart_pico_tool() started")
    # Trigger restart in background to allow response to send
    asyncio.create_task(asyncio.sleep(2))
    asyncio.create_task(asyncio.create_subprocess_shell("sudo systemctl restart pico"))
    return "Restarting Pico service in 2 seconds..."

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

async def get_recent_sms_messages(limit: int = 5):
    """
    Helper to read recent SMS messages from the inbox.
    Returns a list of dicts: {"ts": ..., "sender": ..., "text": ...}
    """
    import re
    
    inbox_dir = settings.GAMMU_INBOX_PATH
    # Regex: IN{Date}_{Time}_{Serial}_{Phone}_{Seq}.txt
    pattern = re.compile(r"^IN(\d{8})_(\d{6})_(\d{2})_(.*)_(\d{2})\.txt$")
    
    messages_map = {}
    
    try:
        if not os.path.exists(inbox_dir):
            return []
            
        # Scan directory
        for filename in os.listdir(inbox_dir):
            match = pattern.match(filename)
            if match:
                date_str, time_str, serial, phone, seq_str = match.groups()
                seq = int(seq_str)
                
                # Read content
                filepath = os.path.join(inbox_dir, filename)
                try:
                    async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                         content = await f.read()
                except Exception as e:
                    logger.error(f"Failed to read {filename}: {e}")
                    continue
                
                key = (date_str, time_str, phone, serial)
                if key not in messages_map:
                    messages_map[key] = {}
                messages_map[key][seq] = content
        
        if not messages_map:
            return []
            
        # Merge and Sort
        final_messages = []
        for key, parts in messages_map.items():
            date_str, time_str, phone, serial = key
            
            # Sort parts by sequence
            sorted_parts = sorted(parts.items()) # [(0, text), (1, text)...]
            full_text = "".join([p[1] for p in sorted_parts])
            
            # Format timestamp
            # Date: YYYYMMDD, Time: HHMMSS
            ts_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
            
            final_messages.append({
                "ts": ts_str,
                "sender": phone,
                "text": full_text
            })
            
        # Sort by timestamp descending
        final_messages.sort(key=lambda x: x["ts"], reverse=True)
        
        # Take limit
        top_msgs = final_messages[:limit]
        
        # Reverse display order (Oldest top -> Newest bottom) ? 
        # Actually the UI usually shows a list top-down. 
        # If we want "recent" at the top of the list, we keep descending order.
        # But `read_inbox_tool` reversed it before. Let's see:
        # "Reverse display order (Oldest top -> Newest bottom) ('Later the lower')"
        # If I get the 5 most recent, they are [Newest, ..., 5th Newest]. 
        # Reversing them makes [5th Newest, ..., Newest].
        # In a chat log, newest is at bottom.
        # In a list of buttons, usually newest is at top. 
        # The previous code reversed it. I will keep consistent behavior.
        # But wait, for the interactive list, maybe newest at top is better?
        # The previous code comments said "Later the lower".
        top_msgs.reverse()
        
        return top_msgs
        
    except Exception as e:
        logger.error(f"Error scanning inbox: {e}")
        return []

async def read_inbox_tool(limit: int = 5):
    """
    Read the latest SMS messages by scanning the inbox directory.
    Merges multi-part messages automatically.
    
    Args:
        limit (int): Number of messages to retrieve (default 5).
        
    Returns:
        str: List of messages with sender and content.
    """
    logger.info(f"TOOL EXECUTION: read_inbox_tool({limit}) started")
    
    msgs = await get_recent_sms_messages(limit)
    if not msgs:
        return "Inbox is empty or directory not found."
    
    # Return as JSON for the agent
    return json.dumps(msgs)

def get_tools():
    # Pass raw functions as per Google ADK docs; LlmAgent handles wrapping/parsing
    return [
        get_system_temperature_tool,
        get_system_logs_tool,
        get_sys_logs_tool,
        read_inbox_tool,
        restart_pico_tool,
        restart_system_tool
    ]

# --- Bot & Agent Setup ---

bot = None
dp = Dispatcher()
# 'agent' is now an instance of BaseAgent (SlimAgent or ADKAgent)
agent = None

# --- Helper: Ollama Models ---

async def get_ollama_models(base_url: str) -> list[str]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error(f"Failed to fetch models: {e}")
    return []

# --- Handlers ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Hello! I am Pico Agent.\nCommands:\n/model - Change LLM Model\n/clear - Clear History")

@dp.message(F.text == "/clear")
async def cmd_clear(message: types.Message):
    """Clear the current session history."""
    # For now, simplistic clear (Simulated by renaming session? Or just doing nothing if stateless)
    # If we are using ADK, we can call delete.
    # But 'agent' might abstract this?
    # For SlimAgent, it's stateless anyway.
    # For ADKAgent, we should expose 'clear_session'.
    # TODO: Add clear_session to BaseAgent
    await message.answer("History cleared (if applicable).")

@dp.message(F.text.startswith("/model"))
async def cmd_model(message: types.Message):
    """Change the LLM model."""
    if not settings.TELEGRAM_ALLOWED_USERS or message.from_user.id in settings.TELEGRAM_ALLOWED_USERS:
        models = await get_ollama_models(settings.OLLAMA_URL)
        
        # Add OpenAI models if configured
        # Add OpenAI models if configured
        if settings.OPENAI_API_KEY:
            models.append(settings.OPENAI_MODEL)
            
        if not models:
            await message.answer("Could not fetch models.")
            return

        buttons = []
        for m in models:
            buttons.append([InlineKeyboardButton(text=m, callback_data=f"set_model:{m}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        current = agent.model_name if agent else "Unknown"
            
        await message.answer(f"Current Model: `{current}`\nSelect a new model:", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(F.text.startswith("/sms"))
async def cmd_sms(message: types.Message):
    """Show recent SMS messages."""
    if settings.TELEGRAM_ALLOWED_USERS and message.from_user.id not in settings.TELEGRAM_ALLOWED_USERS:
        return

    try:
        args = message.text.split()
        limit = 1
        if len(args) > 1:
            limit = int(args[1])
    except ValueError:
        limit = 1
        
    # Reuse the global cache system for consistent UX? 
    # Yes, show_sms_list relies on sms_cache for "view details"
    user_id = message.from_user.id
    
    msgs = await get_recent_sms_messages(limit)
    if not msgs:
        await message.answer("Inbox is empty.")
        return

    # Cache for interactivity
    sms_cache[user_id] = msgs
    
    # Show List
    await show_sms_list(message, msgs)

@dp.message(F.text == "/restart pi")
async def cmd_restart_pi(message: types.Message):
    """Restart the Raspberry Pi."""
    if settings.TELEGRAM_ALLOWED_USERS and message.from_user.id not in settings.TELEGRAM_ALLOWED_USERS:
        return

    await message.answer("⚠️ Restarting system in 5 seconds...")
    await asyncio.sleep(2) # Give time to send message
    
    try:
        # Use sudo reboot. Assumes passwordless sudo for the user.
        # 'sudo' is redundant if running as root, but safe if pi user has sudoers.
        # Run in background to let the process return?
        # Actually, once reboot starts, this process dies.
        proc = await asyncio.create_subprocess_shell("sudo reboot")
        await proc.wait()
    except Exception as e:
        await message.answer(f"Failed to restart: {e}")

@dp.message(F.text == "/restart pico")
async def cmd_restart_pico(message: types.Message):
    """Restart the Pico service."""
    if settings.TELEGRAM_ALLOWED_USERS and message.from_user.id not in settings.TELEGRAM_ALLOWED_USERS:
        return

    await message.answer("⚠️ Restarting Pico service in 2 seconds...")
    await asyncio.sleep(2)
    
    try:
        await asyncio.create_subprocess_shell("sudo systemctl restart pico")
    except Exception as e:
        await message.answer(f"Failed to restart: {e}")

@dp.message(F.text.startswith("/log pico"))
async def cmd_log_pico(message: types.Message):
    """Show last N lines of Pico service logs."""
    if settings.TELEGRAM_ALLOWED_USERS and message.from_user.id not in settings.TELEGRAM_ALLOWED_USERS:
        return

    try:
        args = message.text.split()
        lines = 30
        if len(args) > 2: # /log pico N
            lines = int(args[2])
    except ValueError:
        lines = 30
    
    log_file = LOG_FILE
    if not os.path.exists(log_file):
        await message.answer("Log file not found.")
        return

    try:
        # Simple tail implementation using 'tail' command is robust
        proc = await asyncio.create_subprocess_shell(
            f"tail -n {lines} {log_file}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        logs = stdout.decode().strip()
        
        if not logs:
            logs = "No logs found."
        
        # Chunk if too long
        if len(logs) > 4000:
            logs = logs[-4000:]
            
        await message.answer(f"📄 **Pico Logs (Last {lines})**\n```\n{logs}\n```", parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"Error reading logs: {e}")

@dp.message(F.text.startswith("/log sys"))
async def cmd_log_sys(message: types.Message):
    """Show last N lines of system logs."""
    if settings.TELEGRAM_ALLOWED_USERS and message.from_user.id not in settings.TELEGRAM_ALLOWED_USERS:
        return

    try:
        args = message.text.split()
        lines = 30
        if len(args) > 2: # /log sys N
            lines = int(args[2])
    except ValueError:
        lines = 30

    try:
        proc = await asyncio.create_subprocess_shell(
            f"journalctl -n {lines} --no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        logs = stdout.decode().strip()
        
        if not logs:
            logs = "No logs found."
            
        if len(logs) > 4000:
            logs = logs[-4000:]
            
        await message.answer(f"🖥️ **System Logs (Last {lines})**\n```\n{logs}\n```", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"Error reading system logs: {e}")

@dp.callback_query(F.data.startswith("set_model:"))
async def handle_set_model(callback: CallbackQuery):
    global agent
    model_name = callback.data.split(":", 1)[1]
    
    try:
        logger.info(f"Switching model to {model_name}")
        agent = get_agent(model_name, get_tools())
        await callback.message.edit_text(f"Model switched to: `{model_name}`\nAgent Type: {type(agent).__name__}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        await callback.message.edit_text(f"Failed to switch model: {e}")

# ...
from services.agents import get_agent, ToolRequest

# Transient store for pending confirmations: {user_id: ToolRequest}
pending_tools = {}
# Transient store for SMS lists: {user_id: [msg_dicts]}
sms_cache = {}

# ... (Previous handlers)

@dp.callback_query(F.data == "confirm_tool")
async def handle_tool_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_tools:
        req = pending_tools.pop(user_id)
        
        # Special Handling for Interactive SMS Tool
        if req.name == "read_inbox_tool":
             await callback.message.edit_text(f"Scanning Inbox ({req.args.get('limit', 5)})...")
             if hasattr(agent, "execute_tool"):
                 raw_json = await agent.execute_tool(req.name, req.args)
                 try:
                     msgs = json.loads(raw_json)
                     if isinstance(msgs, dict) and "error" in msgs:
                         await callback.message.reply(f"Error: {msgs['error']}")
                         return
                         
                     if not msgs or (isinstance(msgs, str) and "empty" in msgs.lower()):
                          await callback.message.reply("Inbox is empty.")
                          return

                     # Cache messages
                     sms_cache[user_id] = msgs
                     
                     # Render List UI
                     await show_sms_list(callback.message, msgs)
                     return # Handled
                     
                 except json.JSONDecodeError:
                     # Fallback to raw text if JSON fails
                     pass
                     
                 except Exception as e:
                     logger.error(f"Error rendering SMS UI: {e}")
                     # Fallback to raw output
        
        # Standard Tool Execution
        await callback.message.edit_text(f"Running `{req.name}`...", parse_mode="Markdown")
        
        if hasattr(agent, "execute_tool"):
             result = await agent.execute_tool(req.name, req.args)
        else:
             result = "Error: Agent does not support direct execution."
             
        # Direct Output (No LLM Re-ingestion)
        if len(result) > 4000:
            result = result[:4000] + "\n...(truncated)"
            
        try:
            await callback.message.reply(f"```\n{result}\n```", parse_mode="Markdown")
        except TelegramBadRequest:
             await callback.message.reply(result, parse_mode=None)
    else:
        await callback.message.edit_text("Confirmation expired or invalid.")

async def show_sms_list(message: types.Message, msgs: list):
    """Render the list of SMS buttons."""
    buttons = []
    for idx, m in enumerate(msgs):
        # Button Text: "+123456789 (12-10 22:00)"
        # ts format: YYYY-MM-DD HH:MM:SS
        ts_parts = m['ts'].split(" ")
        date_part = ts_parts[0][5:] # MM-DD
        time_part = ts_parts[1][:5] # HH:MM
        
        sender = m['sender']
        label = f"{sender} ({date_part} {time_part})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"view_sms:{idx}")])
    
    # Add Cancel/Close
    buttons.append([InlineKeyboardButton(text="❌ Close", callback_data="cancel_tool")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    # We edit the message if possible, or reply?
    # Context suggests we are coming from "Scanning Inbox..." edit state.
    # But `message` object might need `edit_text` or `reply`.
    # Let's try `edit_text` on the message passed (which is callback.message)
    try:
        await message.edit_text("📩 **Inbox**", reply_markup=keyboard, parse_mode="Markdown")
    except:
        await message.answer("📩 **Inbox**", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_sms:"))
async def handle_view_sms(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        idx = int(callback.data.split(":")[1])
        if user_id in sms_cache and 0 <= idx < len(sms_cache[user_id]):
            m = sms_cache[user_id][idx]
            
            text = f"📱 **Message Details**\n\n" \
                   f"**From:** `{m['sender']}`\n" \
                   f"**Time:** `{m['ts']}`\n" \
                   f"**Content:**\n{m['text']}"
            
            buttons = [[InlineKeyboardButton(text="🔙 Back to List", callback_data="back_to_sms_list")]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await callback.message.edit_text("Has expired details.")
    except Exception as e:
        logger.error(f"Error viewing SMS: {e}")
        await callback.message.edit_text("Error viewing message.")

@dp.callback_query(F.data == "back_to_sms_list")
async def handle_back_sms(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in sms_cache:
        await show_sms_list(callback.message, sms_cache[user_id])
    else:
        await callback.message.edit_text("Session expired.")

@dp.callback_query(F.data == "cancel_tool")
async def handle_tool_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_tools:
        del pending_tools[user_id]
    await callback.message.edit_text("Tool execution cancelled.")

@dp.message(F.text)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Telegram Message from {user_id} (@{username}): {message.text}")
    
    if settings.TELEGRAM_ALLOWED_USERS and user_id not in settings.TELEGRAM_ALLOWED_USERS:
        logger.warning(f"Unauthorized access attempt from {user_id}")
        # Reply so they know which message was unauthorized
        await message.reply(f"Unauthorized. Your ID is {user_id}.")
        return

    if not agent:
        # Reply
        await message.reply("Agent System is starting up... please wait.")
        return

    # Reply to acknowledge receipt
    # await message.reply(f"Thinking...") 
    # Actually "Thinking..." might be spammy if we keep it. 
    # But let's keep it for now as a reply.
    processing_msg = await message.reply("Thinking...")
    
    try:
        response = await agent.chat(str(user_id), message.text)
        
        # Check if response is a ToolRequest
        if isinstance(response, ToolRequest):
            # Store for confirmation
            pending_tools[user_id] = response
            
            # Send Confirmation UI
            buttons = [
                [
                    InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_tool"),
                    InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_tool")
                ]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            args_preview = str(response.args)
            if len(args_preview) > 100: args_preview = args_preview[:100] + "..."
            
            # Edit the "Thinking..." message to become the tool request? 
            # Or just send a new reply? 
            # Editing is cleaner.
            await processing_msg.edit_text(
                f"🛠️ **Tool Request**\nFunction: `{response.name}`\nArgs: `{args_preview}`\n\nRun this?", 
                reply_markup=keyboard, 
                parse_mode="Markdown"
            )
            return

        # Normal text response - Edit the thinking message or reply?
        # Editing "Thinking..." is best UX.
        try:
            await processing_msg.edit_text(response, parse_mode="Markdown")
        except TelegramBadRequest:
            # Fallback for broken markdown
            await processing_msg.edit_text(response, parse_mode=None)

    except Exception as e:
        logger.error(f"Error in agent processing: {e!s}", exc_info=True)
        await processing_msg.edit_text(f"An internal error occurred: {e!s}")

async def start_telegram_bot():
    global bot, agent
    
    # Ensure logging is set up for aiogram
    logging.basicConfig(level=logging.INFO)
    
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram bot disabled.")
        return

    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        bot_info = await bot.get_me()
        logger.info(f"Telegram Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Initialize Agent using Factory
        model_name = settings.OPENAI_MODEL
        logger.info(f"Initializing Default Agent for {model_name}")
        agent = get_agent(model_name, get_tools())
        
        logger.info("Starting Telegram Bot Polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Telegram Bot failed to start: {e}", exc_info=True)
