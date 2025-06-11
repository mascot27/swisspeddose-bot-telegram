import os
import requests
import re
from lxml import html
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_URL = "https://db.swisspeddose.ch"
LAST_DATE_FILE = "last_release_date.txt"

def fetch_release_date(url):
    response = requests.get(url)
    response.raise_for_status()

    tree = html.fromstring(response.content)
    date_element_xpath = '//*[@id="app"]/footer/div/div[2]/div/p'

    try:
        date_element_text = tree.xpath(date_element_xpath)[0].text.strip()
        match = re.search(r"\d{4}-\d{2}-\d{2}", date_element_text)
        if not match:
            raise ValueError(f"No valid date found in text: {date_element_text}")
        release_date_str = match.group(0)
        release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        return release_date
    except (IndexError, ValueError) as e:
        print(f"Error fetching or parsing the release date: {e}")
        return None

def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        print("Telegram credentials not set. Skipping Telegram notification.")
        return False
    telegram_api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(telegram_api_url, data=payload)
        if r.status_code != 200:
            print(f"Failed to send Telegram message: {r.text}")
            return False
        print("Telegram notification sent successfully.")
        return True
    except Exception as e:
        print(f"Exception sending Telegram message: {e}")
        return False

def send_email_notification(subject, body):
    smtp_server = "smtp.gmail.com"
    smtp_port = 465  # SSL port
    from_addr = os.getenv("EMAIL_FROM")
    to_addr = os.getenv("EMAIL_TO")
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    if not all([from_addr, to_addr, user, password]):
        print("SMTP credentials not set. Skipping email notification.")
        return
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        print("Email notification sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def load_last_date(file_path):
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r") as f:
        date_str = f.read().strip()
        if not date_str:
            return None
        return datetime.strptime(date_str, "%Y-%m-%d").date()

def save_last_date(file_path, date_obj):
    with open(file_path, "w") as f:
        f.write(date_obj.strftime("%Y-%m-%d"))
    print(f"Last release date saved: {date_obj}")

def main():
    # Determine if notifications should always be sent when no new release
    always_notify_env = os.getenv("ALWAYS_NOTIFY", "false").lower() == "true"
    today_is_monday = datetime.utcnow().weekday() == 0
    always_notify = always_notify_env or today_is_monday
    current_release_date = fetch_release_date(CHECK_URL)
    if current_release_date is None:
        print("Failed to fetch the release date.")
        return

    last_release_date = load_last_date(LAST_DATE_FILE)
    if last_release_date is None or current_release_date > last_release_date:
        message = f"New SwissPedose release published on {current_release_date}!"
        tg_ok = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
        if not tg_ok:
            message += " (Telegram notification failed)"
        send_email_notification("New SwissPedose Release", message)
        save_last_date(LAST_DATE_FILE, current_release_date)
        print("New release detected and notification sent.")
    else:
        if always_notify:
            # Send a notification even when no new release
            info = f"No new SwissPedose release. Latest release date is {current_release_date}."
            tg_ok = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, info)
            if not tg_ok:
                info += " (Telegram notification failed)"
            send_email_notification("SwissPedose Release Status", info)
            print("Notification sent (no new release).")
        else:
            print("No new release detected.")
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_text = f"Workflow failed: {e}"
        tg_ok = send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, error_text)
        if not tg_ok:
            error_text += " (Telegram notification failed)"
        send_email_notification("SwissPedDose Bot Error", error_text)
        raise
