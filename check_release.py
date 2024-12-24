import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_URL = "https://www.swisspedose.example/releases"
LAST_DATE_FILE = "last_release_date.txt"

def fetch_release_date(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # Adjust the selector below to match the actual page
    date_element = soup.find("span", class_="release-date")
    if not date_element:
        raise Exception("Release date element not found")

    release_date_str = date_element.text.strip()
    release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
    return release_date

def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        print("Telegram credentials not set. Skipping notification.")
        return
    telegram_api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    r = requests.post(telegram_api_url, data=payload)
    if r.status_code != 200:
        print(f"Failed to send message: {r.text}")
    else:
        print("Notification sent successfully.")

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

def main():
    current_release_date = fetch_release_date(CHECK_URL)
    last_release_date = load_last_date(LAST_DATE_FILE)
    if last_release_date is None or current_release_date > last_release_date:
        message = f"New SwissPedose release published on {current_release_date}!"
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
        save_last_date(LAST_DATE_FILE, current_release_date)
    else:
        print("No new release detected.")

if __name__ == "__main__":
    main()