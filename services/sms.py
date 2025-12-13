import asyncio
import os
import re
from typing import Dict, List, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from core.config import settings
from core.bark import bark
from core.logger import logger

# --- Sender & Assembler ---

class SMSAssembler:
    def __init__(self):
        # Key: (phone, serial) -> {'parts': [(seq, text)], 'timer': TimerHandle}
        self.buffer: Dict[Tuple[str, str], dict] = {}
        self.loop = None
        self.timeout = 5.0 # Seconds to wait for other parts

    def set_loop(self, loop):
        self.loop = loop

    def add_part(self, phone: str, serial: str, seq: int, text: str):
        key = (phone, serial)
        
        if key not in self.buffer:
            self.buffer[key] = {'parts': [], 'timer': None}
        
        # Add part
        self.buffer[key]['parts'].append((seq, text))
        
        # Cancel existing timer
        if self.buffer[key]['timer']:
            self.buffer[key]['timer'].cancel()
        
        # Schedule new processing
        if self.loop:
            self.buffer[key]['timer'] = self.loop.call_later(
                self.timeout, 
                lambda: asyncio.create_task(self.process_buffer(key))
            )

    async def process_buffer(self, key):
        if key not in self.buffer:
            return
            
        data = self.buffer.pop(key)
        parts = data['parts']
        phone, serial = key
        
        # Sort by sequence
        parts.sort(key=lambda x: x[0])
        
        # Join text
        full_text = "".join([p[1] for p in parts])
        
        # Log (Redacted)
        logger.info(f"Processing SMS from {phone} (Parts: {len(parts)})")
        
        try:
            # 1. Send Notification (Bark)
            await bark.send(
                title=phone,
                body=full_text,
                group="sms_forwarder",
                level="timeSensitive",
            )
                 
        except Exception as e:
            logger.error(f"Failed to process SMS (Send/Save): {e}")

assembler = SMSAssembler()

# --- Watchdog Handling ---

class SMSHandler(FileSystemEventHandler):
    # Regex for standard Gammu filename
    # IN20251210_001000_00_123456789_00.txt
    # Capture: 1=Date, 2=Time, 3=Serial, 4=Phone, 5=Seq
    FILENAME_PATTERN = re.compile(r"^IN(\d{8})_(\d{6})_(\d{2})_(.*)_(\d{2})\.txt$")

    def __init__(self, loop=None):
        self.loop = loop

    def on_created(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        match = self.FILENAME_PATTERN.match(filename)
        if not match:
            logger.warning(f"Ignored file with unknown format: {filename}")
            return

        serial = match.group(3)
        phone = match.group(4)
        seq_str = match.group(5)
        
        try:
            seq = int(seq_str)
            
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Bridge to Main Loop safely
            if self.loop:
                # assembler.add_part must be run in the loop context or we call it here?
                # Actually assembler.add_part uses call_later which is not threadsafe.
                # So we must schedule add_part to run on the loop.
                self.loop.call_soon_threadsafe(assembler.add_part, phone, serial, seq, content)
            else:
                logger.error("Event loop not available for SMS processing.")
            
            # User requested to keep files in inbox for on-demand scanning.
            # We do NOT delete or archive them here.
            pass

        except Exception as e:
            logger.error(f"Error processing SMS file {filename}: {e}")

class SMSService:
    def __init__(self):
        self.observer = Observer()
        self.handler = None # Will init on start with loop
        self.directory = settings.GAMMU_INBOX_PATH

    def start(self):
        if not os.path.exists(self.directory):
            try:
                os.makedirs(self.directory)
            except PermissionError:
                logger.error(f"Cannot create {self.directory}. Permission denied.")
                return
        
        if not os.access(self.directory, os.R_OK | os.W_OK):
            logger.error(f"Permission denied: {self.directory}")
            return
        
        # Capture the running loop here (Main Thread)
        try:
            loop = asyncio.get_running_loop()
            assembler.set_loop(loop)
            self.handler = SMSHandler(loop) # Pass loop to handler
        except RuntimeError:
            logger.error("Could not get running event loop for SMS Service.")
            return

        logger.info(f"Starting SMS Watcher on {self.directory}")
        self.observer.schedule(self.handler, self.directory, recursive=False)
        self.observer.start()

    def stop(self):
        logger.info("Stopping SMS Watcher...")
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

sms_service = SMSService()
