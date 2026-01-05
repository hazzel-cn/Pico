import os
import json
from loguru import logger
from sdk.uscis import UscisClient
from sdk.bark import bark

STATE_FILE = "data/uscis_state.json"

async def monitor_uscis():
    """Check USCIS status and notify if changed."""
    client = UscisClient()
    try:
        new_statuses = await client.check_all()
        if not new_statuses:
            return

        old_statuses = {}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    old_statuses = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load USCIS state: {e}")

        changes = []
        # We will merge new results into the global state
        merged_state = old_statuses.copy()
        for case_num, status in new_statuses.items():
            if not status or status.get("error") is not None:
                continue
            
            # Extract data safely
            new_data = status.get("data")
            if not new_data:
                continue

            # Update merged state only on success
            merged_state[case_num] = status

            # Check for existing data
            old_entry = old_statuses.get(case_num) or {}
            old_data = old_entry.get("data") if isinstance(old_entry, dict) else None
            
            new_update_at = new_data.get("updatedAt")
            old_update_at = old_data.get("updatedAt") if old_data else None
            
            # Simple change detection based on 'updatedAt' field
            if old_update_at and old_update_at != new_update_at:
                form_type = new_data.get("formType", "Case")
                changes.append(f"USCIS Update for {case_num} ({form_type}):\nDate: {new_update_at}")
            elif not old_update_at and new_data:
                 logger.info(f"First status capture for {case_num}")

        # Save merged state
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(merged_state, f, indent=2, ensure_ascii=False)

        if changes:
            msg = "\n\n".join(changes)
            logger.info(f"USCIS Change Detected! Sending notification: {msg}")
            await bark.send(msg, title="🇺🇸 USCIS Status Update", group="USCIS")
            
    except Exception as e:
        logger.error(f"USCIS Scheduler Job Error: {e}")
    finally:
        await client.close()
