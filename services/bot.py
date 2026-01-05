import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import httpx
import os
import json
from loguru import logger

# Project imports
import sdk.telegram as telegram
from sdk.telegram import bot, dp
import sdk.llm

# --- Config ---
# (Environment config imported directly)
# --- Bot & Agent Setup ---

agent = None

# Transient store for pending confirmations: {request_id: ToolRequest}
pending_tools = {}
# Transient store for SMS lists: {user_id: [msg_dicts]}
sms_cache = {}

# Re-import tools (Need to ensure they use Loguru)
from sdk.tools import get_tools
from sdk.sms import get_inbox_messages as get_recent_sms_messages # Alias for compatibility or update usage
from sdk.agents import get_agent, ToolRequest

# --- Helper: Ollama Models ---

# --- Helper: Ollama Models ---
# (Moved to sdk.llm.get_available_models)

# --- Handlers ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Welcome to Pico Agent!**\n\n"
        "I am your home assistant. Use the menu or commands below:\n"
        "🧠 /agent - Switch LLM Engine\n"
        "📩 /sms - View SMS Inbox\n"
        "🇺🇸 /uscis - Check USCIS Status\n"
        "🌡️ /temp - Check System Temperature\n"
        "📄 /logs - View Bot Logs\n"
        "🖥️ /syslogs - View System Logs\n"
        "⚙️ /sys - System Management\n"
        "🧹 /clear - Reset Session",
        parse_mode="Markdown"
    )

@dp.message(F.text == "/clear")
async def cmd_clear(message: types.Message):
    """Clear the current session history."""
    from sdk import memory
    memory.clear_history(message.from_user.id)
    await message.answer("🧹 History cleared.")

@dp.message(F.text == "/temp")
async def cmd_temp(message: types.Message):
    """Check system temperature."""
    if not telegram.is_user_allowed(message.from_user.id): return
    from sdk.system import get_cpu_temperature
    temp = await get_cpu_temperature()
    await message.answer(f"🌡️ **System Temperature**\n\nCPU: {temp:.1f}°C")

@dp.message(F.text == "/agent")
async def cmd_agent(message: types.Message):
    """Change the LLM agent/model."""
    if not telegram.is_user_allowed(message.from_user.id):
        return
        
    models = await sdk.llm.get_available_models()
    if not models:
        await message.answer("Could not fetch models. Check configs.")
        return

    buttons = []
    for m in models:
        cb_data = f"set_model:{m['provider']}:{m['model']}"
        buttons.append([InlineKeyboardButton(text=m['label'], callback_data=cb_data)])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    current_model = agent.model_name if agent else "Default"
    current_provider = type(agent).__name__.replace("Agent", "") if agent else "Unknown"
    
    await message.answer(
        f"🛠️ **Agent Settings**\n"
        f"Current: `{current_model}` ({current_provider})\n\n"
        f"Select a provider/model:", 
        reply_markup=keyboard, 
        parse_mode="Markdown"
    )

@dp.message(F.text == "/sms")
async def cmd_sms(message: types.Message):
    """Show recent SMS messages."""
    if not telegram.is_user_allowed(message.from_user.id): return
    msgs = await get_recent_sms_messages(5)
    if not msgs:
        await message.answer("Inbox is empty.")
        return
    sms_cache[message.from_user.id] = msgs
    await show_sms_list(message, msgs)

@dp.message(F.text == "/uscis")
async def cmd_uscis(message: types.Message):
    """Check USCIS case status."""
    if not telegram.is_user_allowed(message.from_user.id): return
    
    from sdk import config
    case_numbers = config.USCIS_CASE_NUMBERS
    
    if not case_numbers:
        await message.answer("No case numbers configured.")
        return
    
    buttons = []
    for case_num in case_numbers:
        buttons.append([InlineKeyboardButton(text=f"📄 {case_num}", callback_data=f"uscis_check:{case_num}")])
    
    # Add All Cases option
    buttons.append([InlineKeyboardButton(text="🔄 All Cases", callback_data="uscis_check:all")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🇺🇸 **USCIS Status Check**\nSelect a case or check all:", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(F.text == "/sys")
async def cmd_sys(message: types.Message):
    """System management menu."""
    if not telegram.is_user_allowed(message.from_user.id): return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Reboot Raspberry Pi", callback_data="sys:reboot_pi")]
    ])
    await message.answer("⚙️ **System Management**\nChoose an action:", reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("sys:"))
async def handle_sys_action(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    if action == "reboot_pi":
        await callback.message.edit_text("⚠️ Rebooting system now...")
        await asyncio.create_subprocess_shell("sudo reboot")

@dp.message(F.text == "/logs")
async def cmd_logs(message: types.Message):
    """Show last 30 lines of Pico Bot logs."""
    if not telegram.is_user_allowed(message.from_user.id): return
    log_file = "logs/pico.log" 
    if not os.path.exists(log_file):
        await message.answer("Log file not found.")
        return
    proc = await asyncio.create_subprocess_shell(f"tail -n 30 {log_file}", stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    logs = stdout.decode().strip() or "No logs found."
    await message.answer(f"📄 **Pico Logs**\n```\n{logs[-4000:]}\n```", parse_mode="Markdown")

@dp.message(F.text == "/syslogs")
async def cmd_syslogs(message: types.Message):
    """Show last 30 lines of system logs."""
    if not telegram.is_user_allowed(message.from_user.id): return
    proc = await asyncio.create_subprocess_shell("journalctl -n 30 --no-pager", stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    logs = stdout.decode().strip() or "No logs found."
    await message.answer(f"🖥️ **System Logs**\n```\n{logs[-4000:]}\n```", parse_mode="Markdown")

@dp.callback_query(F.data.startswith("set_model:"))
async def handle_set_model(callback: CallbackQuery):
    global agent
    # Data is "set_model:provider:model_name"
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Invalid model selection format.")
        return
        
    provider = parts[1]
    model_name = ":".join(parts[2:]) # In case model name has colons (like ollama)

    try:
        logger.info(f"Switching to {provider} / {model_name}")
        agent = get_agent(tools=get_tools(), provider=provider, model_name=model_name)
        await callback.message.edit_text(
            f"✅ **Agent Updated**\n"
            f"Provider: `{provider.upper()}`\n"
            f"Model: `{model_name}`\n"
            f"Type: `{type(agent).__name__}`", 
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to switch agent: {e}")
        await callback.message.edit_text(f"❌ Failed to switch: {e}")

@dp.callback_query(F.data.startswith("confirm_tool:"))
async def handle_tool_confirm(callback: CallbackQuery):
    req_id = callback.data.split(":")[1]
    
    if req_id in pending_tools:
        req = pending_tools.pop(req_id)
        
        # Special Handling for Interactive SMS Tool
        if req.name == "read_inbox_tool":
             await callback.message.edit_text(f"Scanning Inbox ({req.args.get('limit', 5)})...")
             
             # Execute tool (it returns JSON string)
             if hasattr(agent, "execute_tool"):
                 import sdk.memory as memory
                 raw_json = await agent.execute_tool(req.name, req.args)
                 memory.add_message(callback.from_user.id, "user", f"[Tool Result: {raw_json}]")
                 try:
                     msgs = json.loads(raw_json)
                     if isinstance(msgs, dict) and "error" in msgs:
                         await callback.message.answer(f"Error: {msgs['error']}")
                         return
                         
                     if not msgs or (isinstance(msgs, str) and "empty" in msgs.lower()):
                          await callback.message.answer("Inbox is empty.")
                          return

                     # Cache messages
                     sms_cache[callback.from_user.id] = msgs
                     
                     # Render List UI
                     await show_sms_list(callback.message, msgs)
                     return # Handled
                     
                 except json.JSONDecodeError:
                     pass
                 except Exception as e:
                     logger.error(f"Error rendering SMS UI: {e}")
        
        # Standard Tool Execution
        await callback.message.edit_text(f"Running `{req.name}`...", parse_mode="Markdown")
        
        if hasattr(agent, "execute_tool"):
             result = await agent.execute_tool(req.name, req.args)
             import sdk.memory as memory
             memory.add_message(callback.from_user.id, "user", f"[Tool Result: {result}]")
        else:
             result = "Error: Agent does not support direct execution."
             
        # Direct Output
        if len(result) > 4000:
            result = result[:4000] + "\n...(truncated)"
            
        # Special Handling for Sensitive Data
        if req.name == "check_uscis_tool":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑️ Delete Now", callback_data="delete_msg")]
            ])
            await callback.message.answer(result, reply_markup=keyboard, parse_mode="HTML")
            return

        try:
            await callback.message.answer(result, parse_mode="Markdown")
        except TelegramBadRequest:
             await callback.message.answer(result, parse_mode=None)
    else:
        await callback.message.edit_text("Confirmation expired or invalid.")

async def show_sms_list(message: types.Message, msgs: list):
    """Render the list of SMS buttons."""
    buttons = []
    for idx, m in enumerate(msgs):
        sender = m['sender']
        # ts: "2024-12-10 22:00:00"
        ts_parts = m['ts'].split(" ")
        date_part = ts_parts[0][5:] if len(ts_parts) > 0 else "?"
        time_part = ts_parts[1][:5] if len(ts_parts) > 1 else "?"
        
        label = f"{sender} ({date_part} {time_part})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"view_sms:{idx}")])
    
    buttons.append([InlineKeyboardButton(text="❌ Close", callback_data="close_inbox")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

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
            # Wrap content in a code block to handle special characters safely
            text = (
                f"📱 **Message Details**\n\n"
                f"**From:** `{m['sender']}`\n"
                f"**Time:** `{m['ts']}`\n\n"
                f"**Content:**\n```\n{m['text']}\n```"
            )
            buttons = [[InlineKeyboardButton(text="🔙 Back to List", callback_data="back_to_sms_list")]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
            except TelegramBadRequest:
                # Fallback to plain text if Markdown fails
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=None)
        else:
            await callback.message.edit_text("Has expired details.")
    except Exception as e:
        logger.error(f"Error viewing SMS: {e}")
        await callback.message.edit_text(f"Error viewing message: {e}")

@dp.callback_query(F.data == "back_to_sms_list")
async def handle_back_sms(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in sms_cache:
        await show_sms_list(callback.message, sms_cache[user_id])
    else:
        await callback.message.edit_text("Session expired.")

@dp.callback_query(F.data == "close_inbox")
async def handle_close_inbox(callback: CallbackQuery):
    await callback.message.delete()

@dp.callback_query(F.data.startswith("uscis_check:"))
async def handle_uscis_check(callback: CallbackQuery):
    """Handle USCIS case status check with self-destruct notice."""
    case_num = callback.data.split(":", 1)[1]
    
    target_name = "**all cases**" if case_num == "all" else f"`{case_num}`"
    await callback.message.edit_text(f"🔍 Fetching status for {target_name}...", parse_mode="Markdown")
    
    try:
        from sdk.uscis import get_formatted_report
        case_list = None if case_num == "all" else [case_num]
        report = await get_formatted_report(case_list=case_list, show_diff=True)
        
        # Add manual delete button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Delete Now", callback_data="delete_msg")]
        ])
        
        await callback.message.edit_text(report, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"USCIS check failed: {e}")
        await callback.message.edit_text(f"❌ Error: {str(e)}")

@dp.callback_query(F.data == "delete_msg")
async def handle_delete_msg(callback: CallbackQuery):
    """Manual message deletion."""
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer("Message already deleted or too old.")

@dp.callback_query(F.data.startswith("cancel_tool:"))
async def handle_tool_cancel(callback: CallbackQuery):
    req_id = callback.data.split(":")[1]
    if req_id in pending_tools:
        del pending_tools[req_id]
        import sdk.memory as memory
        memory.add_message(callback.from_user.id, "user", "[Tool Request Cancelled by User]")
    
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_text("Tool execution cancelled.")

@dp.message(F.text)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"Telegram Message from {user_id} (@{username}): {message.text}")
    
    if not telegram.is_user_allowed(user_id):
        logger.warning(f"Unauthorized access attempt from {user_id} (@{username})")
        # Silently ignore - no response to unauthorized users
        return

    if not agent:
        await message.answer("Agent System is starting up... please wait.")
        return

    processing_msg = await message.answer("Thinking...")
    
    try:
        response = await agent.chat(str(user_id), message.text)
        
        
        if isinstance(response, ToolRequest):
            pending_tools[response.id] = response
            buttons = [[
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"confirm_tool:{response.id}"), 
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel_tool:{response.id}")
            ]]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            args_preview = str(response.args)
            if len(args_preview) > 100: args_preview = args_preview[:100] + "..."
            
            await processing_msg.edit_text(
                f"🛠️ <b>Tool Request</b>\nFunction: <code>{response.name}</code>\nArgs: <tg-spoiler><code>{args_preview}</code></tg-spoiler>\n\nRun this?", 
                reply_markup=keyboard, 
                parse_mode="HTML"
            )
            return

        try:
            await processing_msg.edit_text(response, parse_mode="Markdown")
        except TelegramBadRequest:
            await processing_msg.edit_text(response, parse_mode=None)

    except Exception as e:
        logger.error(f"Error in agent processing: {e!s}")
        await processing_msg.edit_text(f"An internal error occurred: {e!s}")

async def main():
    global bot, agent
    
    logger.add("logs/pico.log", rotation="5 MB", level="INFO")
    
    if not bot:
        logger.warning("Bot instance not available (Token missing?). Exiting.")
        return

    try:
        bot_info = await bot.get_me()
        logger.info(f"Telegram Bot connected: @{bot_info.username} (ID: {bot_info.id})")
        
        # Register Commands in UI
        await bot.set_my_commands([
            types.BotCommand(command="start", description="Welcome & Help"),
            types.BotCommand(command="agent", description="Switch LLM Engine"),
            types.BotCommand(command="sms", description="View SMS Inbox"),
            types.BotCommand(command="uscis", description="Check USCIS Status"),
            types.BotCommand(command="temp", description="Check System Temperature"),
            types.BotCommand(command="logs", description="View Bot Logs"),
            types.BotCommand(command="syslogs", description="View System Logs"),
            types.BotCommand(command="sys", description="System Management"),
            types.BotCommand(command="clear", description="Clear History")
        ])
        
        # Initialize Agent
        logger.info("Initializing Default Agent")
        agent = get_agent(tools=get_tools())
        
        logger.info("Starting Telegram Bot Polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Telegram Bot failed to start: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
