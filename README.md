# Pico - AI Home Assistant for Raspberry Pi

Pico is a lightweight, intelligent home assistant designed for Raspberry Pi. It integrates system monitoring, SMS management, and AI chat capabilities into a unified Telegram bot interface.

## 🌟 Features

*   **AI Agent**:
    *   Supports **Google Gemini** (default), **OpenAI**, and **Ollama**.
    *   **Stateless Architecture**: Ensures privacy and simplicity for single-turn interactions.
    - **Tools**: Can read system logs, check CPU temperature, and manage SMS.
*   **USCIS Monitor**:
    - Automated check for USCIS case status updates.
    - Support for TOTP-based multi-factor authentication.
*   **SMS Management**:
    - Forward incoming SMS to Telegram or Bark.
    - Interactive Telegram UI to view recent messages.
    - Powered by `gammu-smsd`.
*   **System Monitoring**:
    - Real-time CPU temperature alerts.
    - Remote system control (Restart Service/Pi).
*   **Notifications**:
    - Multi-channel alerts via Telegram and Bark.

## 📋 Prerequisites

*   **Hardware**: Raspberry Pi (Zero 2W, 3, 4, or 5 recommended).
*   **OS**: Linux (Raspberry Pi OS).
*   **Software**:
    *   Python 3.13+
    *   `gammu-smsd` (for SMS features)
    *   `uv` (for dependency management)

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
    Copy the example configuration file:
    ```bash
    cp sdk/config.py.example sdk/config.py
    ```
    Edit `sdk/config.py` with your credentials:
    *   `TELEGRAM_BOT_TOKEN`: Your BotFather token.
    *   `GOOGLE_API_KEY`: Your Gemini API key.
    *   `TELEGRAM_ALLOWED_USERS`: A list of numeric Telegram IDs authorized to use the bot.

    > [!IMPORTANT]
    > `sdk/config.py` is ignored by git to keep your secrets safe. Always keep a backup of this file.

## 🏃 Usage

### Run Locally
Pico consists of three main services. You can run them individually:

```bash
# Telegram Bot
uv run python -m services.bot

# Scheduler (USCIS/Temp Monitor)
uv run python -m services.scheduler

# SMS Forwarder
uv run python -m services.sms
```

### Deploy as Services
1.  Review the unit files in the `systemd/` directory and ensure the paths are correct for your environment.
2.  Install and enable the services:
    ```bash
    sudo cp systemd/pico-*.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now pico-bot pico-scheduler pico-sms
    ```

## 🤖 Commands

*   `/start`: Welcome message.
*   `/model`: Switch between available AI models.
*   `/sms [N]`: View last N SMS messages.
*   `/log pico [N]`: View Pico bot logs.
*   `/log sys [N]`: View system logs.
*   `/restart pico`: Restart the Pico bot service.
*   `/restart pi`: Reboot the Raspberry Pi.

## 📄 License
MIT
