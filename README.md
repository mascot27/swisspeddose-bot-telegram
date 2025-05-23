# swisspeddose-bot-telegram

Automatically notifies a Telegram chat when a new SwissPedDose release is published.

## Overview

This project checks the [SwissPedDose database](https://db.swisspeddose.ch) for new releases and sends a Telegram notification if a new release is detected. It is intended for automated monitoring and alerting of updates to the SwissPedDose platform.

## How it works

1. **Fetch Release Date:**
   - The script scrapes the SwissPedDose website to extract the latest release date from the footer.
2. **Compare Dates:**
   - It compares the fetched release date with the last known release date stored in `last_release_date.txt`.
3. **Send Notification:**
   - If a new release is detected, a message is sent to a specified Telegram chat using a bot.
   - The last known release date is updated.
4. **No Update:**
   - If there is no new release, no notification is sent (unless you uncomment the relevant lines in the code).

## Setup

1. **Clone the repository**
2. **Install dependencies:**
   - Python 3.x
   - `requests`, `lxml`, `bs4`
   - Install with:
     ```bash
     pip install requests lxml beautifulsoup4
     ```
3. **Set environment variables:**
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `TELEGRAM_CHAT_ID`: The chat ID to send notifications to
   - Example (on macOS/Linux):
     ```bash
     export TELEGRAM_BOT_TOKEN=your_token_here
     export TELEGRAM_CHAT_ID=your_chat_id_here
     ```
4. **Run the script:**
   ```bash
   python check_release.py
   ```

## File Descriptions

- `check_release.py`: Main script for checking releases and sending notifications.
- `last_release_date.txt`: Stores the date of the last detected release (auto-updated).

## Workflow

1. The script is intended to be run periodically (e.g., via cron or a scheduler).
2. On each run, it checks for a new release and sends a Telegram message if there is an update.
3. The script is idempotent and safe to run multiple times.

## Example Notification

```
New SwissPedose release published on 2025-05-21!
```

