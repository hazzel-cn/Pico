import asyncio
import os
import re
import aiofiles
from typing import Dict, Tuple, Optional, AsyncGenerator
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger

# Regex for standard Gammu filename
# IN20251210_001000_00_123456789_00.txt
FILENAME_PATTERN = re.compile(r"^IN(\d{8})_(\d{6})_(\d{2})_(.*)_(\d{2})\.txt$")
INBOX_PATH = "/var/spool/gammu/inbox"

def parse_filename(filename: str) -> Optional[dict]:
    """
    Pure utility: Parse a Gammu filename into components.
    Returns dict or None.
    """
    match = FILENAME_PATTERN.match(filename)
    if not match:
        return None
        
    date_str, time_str, serial, phone, seq_str = match.groups()
    return {
        "date": date_str,
        "time": time_str,
        "serial": serial,
        "phone": phone,
        "seq": int(seq_str)
    }

class SMSAssembler:
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.buffer: Dict[Tuple[str, str], dict] = {} # (phone, serial) -> {parts: [], timer: handle}
        self.queue = queue
        self.loop = loop
        self.timeout = 5.0

    async def _flush_buffer(self, key):
        if key not in self.buffer: return
        data = self.buffer.pop(key)
        
        parts = sorted(data['parts'], key=lambda x: x[0])
        full_text = "".join([p[1] for p in parts])
        phone, _ = key
        
        logger.info(f"SMS assembled from {phone}, yielding to generator.")
        await self.queue.put((phone, full_text))

    def add_part(self, phone: str, serial: str, seq: int, text: str):
        key = (phone, serial)
        if key not in self.buffer:
            self.buffer[key] = {'parts': [], 'timer': None}
        
        self.buffer[key]['parts'].append((seq, text))
        
        # Debounce logic
        if self.buffer[key]['timer']:
            self.buffer[key]['timer'].cancel()
            
        self.buffer[key]['timer'] = self.loop.call_later(
            self.timeout, 
            lambda: asyncio.create_task(self._flush_buffer(key))
        )

async def _read_and_assemble(filepath: str, assembler: SMSAssembler):
    filename = os.path.basename(filepath)
    meta = parse_filename(filename)
    if not meta: return

    try:
        async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = await f.read()
            
        assembler.add_part(
            phone=meta['phone'],
            serial=meta['serial'],
            seq=meta['seq'],
            text=content
        )
    except Exception as e:
        logger.error(f"Failed to process {filename}: {e}")

class _WatchdogHandler(FileSystemEventHandler):
    def __init__(self, loop, assembler):
        self.loop = loop
        self.assembler = assembler

    def on_created(self, event):
        if not event.is_directory:
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(_read_and_assemble(event.src_path, self.assembler))
            )

async def monitor_inbox() -> AsyncGenerator[Tuple[str, str], None]:
    """
    Async Generator that yields (phone, text) tuples as SMS messages are received.
    Manages its own Watchdog Observer.
    """
    if not os.path.exists(INBOX_PATH):
        try:
            os.makedirs(INBOX_PATH)
        except OSError:
            logger.error(f"Could not create inbox: {INBOX_PATH}")
            return

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    assembler = SMSAssembler(queue, loop)
    
    observer = Observer()
    handler = _WatchdogHandler(loop, assembler)
    observer.schedule(handler, INBOX_PATH, recursive=False)
    observer.start()
    logger.info(f"Started SMS Watchdog on {INBOX_PATH}")

    try:
        while True:
            # Wait for assembled messages
            phone, text = await queue.get()
            yield phone, text
            queue.task_done()
    finally:
        observer.stop()
        observer.join()
        logger.info("Stopped SMS Watchdog")

async def get_inbox_messages(limit: int = 5) -> list[dict]:
    """Public API: Read recent SMS from inbox directory."""
    if not os.path.exists(INBOX_PATH): return []
    
    messages_map = {}
    try:
        for filename in os.listdir(INBOX_PATH):
            meta = parse_filename(filename)
            if not meta: continue
            
            filepath = os.path.join(INBOX_PATH, filename)
            try:
                async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                     content = await f.read()
                
                key = (meta['date'], meta['time'], meta['phone'], meta['serial'])
                if key not in messages_map: messages_map[key] = {}
                messages_map[key][meta['seq']] = content
            except: continue
            
        final_msgs = []
        for (d, t, p, s), parts in messages_map.items():
            text = "".join([v for k,v in sorted(parts.items())])
            ts = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"
            final_msgs.append({"ts": ts, "sender": p, "text": text})
            
        return sorted(final_msgs, key=lambda x: x["ts"], reverse=True)[:limit]
    except Exception as e:
        logger.error(f"Error scanning inbox: {e}")
        return []
