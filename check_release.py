import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
LATEST_CHECK_DATE_FILE = "latest_check_date.txt"

def _make_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        connect=3,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def _http_get(session, url):
    response = session.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SwissPedDoseBot/1.0; +https://github.com/mascot27/swisspeddose-bot-telegram)"
    })
    response.raise_for_status()
    return response


def _parse_release_from_homepage(response):
    """Strategy A: regex on the raw HTML for 'Release YYYY-MM-DD'.

    The site renders the release date in the footer as plain text
    'Release 2026-05-12'. This pattern is layout-independent, so it
    survives DOM restructuring as long as the wording stays the same.
    """
    match = re.search(r"Release\s+(\d{4}-\d{2}-\d{2})", response.text)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%d").date()


def _parse_release_from_footer_xpath(response):
    """Strategy B: XPath into the footer for a span containing the date.

    Targets the current layout (data-flux-footer attribute) but is
    flexible about exact nesting — picks any descendant span/p/div
    whose text matches the release pattern.
    """
    tree = html.fromstring(response.content)
    candidates = tree.xpath(
        "//*[@data-flux-footer]//*[self::span or self::p or self::div]"
        "[contains(normalize-space(text()), 'Release')]"
    )
    for el in candidates:
        text = (el.text_content() or "").strip()
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    return None


def _parse_release_from_changelog(session, base_url):
    """Strategy C: fall back to the changelog page.

    Each entry on /de/changelog is prefixed with 'Veröffentlichung DD-MM-YYYY'.
    We return the most recent one (the entries are listed newest-first).
    """
    changelog_url = base_url.rstrip("/") + "/de/changelog"
    response = _http_get(session, changelog_url)
    matches = re.findall(r"Ver[öo]ffentlichung\s+(\d{2})-(\d{2})-(\d{4})", response.text)
    if not matches:
        return None
    dates = []
    for day, month, year in matches:
        try:
            dates.append(datetime(int(year), int(month), int(day)).date())
        except ValueError:
            continue
    if not dates:
        return None
    return max(dates)


def fetch_release_date(url):
    try:
        session = _make_session()
        response = _http_get(session, url)
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching release date: {e}")
        return None, str(e)

    strategies = (
        ("homepage regex", lambda: _parse_release_from_homepage(response)),
        ("homepage footer xpath", lambda: _parse_release_from_footer_xpath(response)),
        ("changelog page", lambda: _parse_release_from_changelog(session, url)),
    )

    errors = []
    for name, strategy in strategies:
        try:
            result = strategy()
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue
        if result is not None:
            print(f"Release date {result} found via '{name}' strategy.")
            return result, None
        errors.append(f"{name}: no match")

    error_msg = "All parsing strategies failed: " + "; ".join(errors)
    print(f"Error fetching or parsing the release date: {error_msg}")
    return None, error_msg

def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        print("Telegram credentials not set. Skipping Telegram notification.")
        return False
    telegram_api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(telegram_api_url, data=payload, timeout=15)
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
    current_release_date, fetch_error = fetch_release_date(CHECK_URL)
    if current_release_date is None:
        msg = f"Could not fetch release date from {CHECK_URL}: {fetch_error}"
        print(msg)
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, msg)
        send_email_notification("SwissPedDose Bot Warning", msg)
        return

    # Always write today's date so the repo has activity on every run,
    # preventing GitHub from disabling the scheduled workflow due to inactivity.
    today = datetime.utcnow().date()
    save_last_date(LATEST_CHECK_DATE_FILE, today)

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
