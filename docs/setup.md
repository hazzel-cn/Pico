# Pico Project Setup Guide

## 1. Installation

### Requirements
- Raspberry Pi (Linux)
- Python 3.10+
- `uv` package manager

### Steps
1. Navigate to the project directory:
   ```bash
   cd /home/pi/pico
   ```
2. Install dependencies:
   ```bash
   uv sync
   ```

## 2. Configuration (`.env`)

Create a `.env` file in the project root:

```ini
# Bark Notification Configuration
# Full URL from your Bark App
BARK_URL=https://bark.hazzel.cn/your_key_here

# Ollama Server URL (Optional, default shown)
OLLAMA_URL=http://localhost:11434

# System Temperature Monitoring
# Alert if temp exceeds this Celsius value
TEMP_THRESHOLD=80.0
```

## 3. Services Overview

- **Web Server**: Runs FastAPI.
- **Scheduler**: Runs separate status checks (e.g., Temperature Monitor).
- **Monitoring**: Located in `services/monitoring/`.
- **SMS Forwarder**: Integrates with Gammu.

## 4. Gammu SMSD Setup

To forward incoming SMS messages to Bark, use `gammu-smsd` with the provided handler script.

### Gammu Configuration

Pico's `SMSService` monitors `/var/spool/gammu/inbox` by default (configurable in `.env`).

**Critical Perparations:**
Since `/var/spool/gammu/inbox` is a system directory, you **must** ensure the `pi` user has permissions to read and delete files there.

```bash
# Create directory (if not exists)
sudo mkdir -p /var/spool/gammu/inbox

# Grant ownership to the current user
sudo chown -R pi:pi /var/spool/gammu/inbox
```

### Configure `gammu-smsdrc`

Edit `/etc/gammu-smsdrc`:

```ini
[smsd]
service = files
# Path to the inbox folder
inboxpath = /var/spool/gammu/inbox/
# ... other settings ...
```

### Testing SMS

You can simulate an incoming SMS using environment variables:

```bash
export SMS_MESSAGES=1
export SMS_1_NUMBER="+123456789"
export SMS_1_TEXT="Hello World"
uv run scripts/sms_handler.py
```

## Deployment (Systemd)

To run Pico as a background service:

1.  **Install and Start Service**:
    ```bash
    # Copy service file
    sudo cp /home/pi/pico/systemd/pico.service /etc/systemd/system/pico.service
    
    # Reload and Start
    sudo systemctl daemon-reload
    sudo systemctl enable pico
    sudo systemctl start pico
    
    # Check Status
    sudo systemctl status pico
    ```

2.  **View Logs**:
    ```bash
    tail -f /home/pi/pico/logs/pico.log
    ```
