# Pico - AI Home Assistant for Raspberry Pi

Pico is a lightweight, intelligent home assistant designed for Raspberry Pi. It integrates system monitoring, SMS management, and AI chat capabilities into a unified Telegram bot interface.

## 🌟 Features

*   **AI Agent**:
    *   Supports **OpenAI** (via `gpt-*` models) and **Ollama** (local models).
    *   **Stateless Architecture**: Ensures privacy and simplicity for single-turn interactions.
    *   **Tools**: Can read system logs, check CPU temperature, and manage SMS.
*   **SMS Management**:
    *   Forward incoming SMS to Telegram or Bark.
    *   Interactive Telegram UI to view recent messages.
    *   Powered by `gammu-smsd`.
*   **System Monitoring**:
    *   Real-time CPU temperature alerts.
    *   Remote system control (Restart Service/Pi).
*   **Notifications**:
    *   Multi-channel alerts via Telegram and Bark.

## 📋 Prerequisites

*   **Hardware**: Raspberry Pi (Zero 2W, 3, 4, or 5 recommended).
*   **OS**: Linux (Raspberry Pi OS).
*   **Software**:
    *   Python 3.11+
    *   `gammu-smsd` (for SMS features)
    *   `uv` (recommended for dependency management)

## 🚀 Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/pico.git
    cd pico
    ```

2.  **Install Dependencies**
    Using `uv`:
    ```bash
    uv sync
    ```

3.  **Configuration**
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` with your API keys and preferences:
    *   `TELEGRAM_BOT_TOKEN`: Your BotFather token.
    *   `OPENAI_API_KEY`: For GPT-5.2/4o support.
    *   `TELEGRAM_ALLOWED_USERS`: Your numeric Telegram ID (get it from @userinfobot).
    *   `GAMMU_INBOX_PATH`: Path to Gammu inbox (default: `/var/spool/gammu/inbox`).

## 🏃 Usage

### Run Locally
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Deploy as Service
1.  Edit `systemd/pico.service` to match your paths and user.
2.  Install the service:
    ```bash
    sudo cp systemd/pico.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable pico
    sudo systemctl start pico
    ```

## 🤖 Commands

*   `/start`: Welcome message.
*   `/model`: Switch between available AI models (OpenAI/Ollama).
*   `/sms [N]`: View last N SMS messages.
*   `/log pico [N]`: View Pico service logs.
*   `/log sys [N]`: View system logs.
*   `/restart pico`: Restart the Pico service.
*   `/restart pi`: Reboot the Raspberry Pi.

## 📄 License
MIT
