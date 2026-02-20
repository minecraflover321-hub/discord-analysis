import os
import time
import sqlite3
import random
import requests
import threading
from datetime import datetime
from telegram.ext import Updater, CommandHandler

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
CHECK_INTERVAL = 300  # 5 minutes
# ==========================================

if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment variables.")

# ================= DATABASE =================
conn = sqlite3.connect("monitor.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    status TEXT,
    chat_id INTEGER
)
""")
conn.commit()

# ================= PROXY POOL =================
PROXIES = [
    None,
    # "http://user:pass@ip:port"
]

def get_proxy():
    proxy = random.choice(PROXIES)
    if proxy:
        return {"http": proxy, "https": proxy}
    return None

# ================= INSTAGRAM CHECK =================
def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        r = requests.get(
            url,
            headers=headers,
            proxies=get_proxy(),
            timeout=10
        )

        if r.status_code == 200:
            if "Sorry, this page isn't available" in r.text:
                return "BANNED"
            return "ACTIVE"

        if r.status_code == 404:
            return "BANNED"

    except requests.RequestException:
        return "UNKNOWN"

    return "UNKNOWN"

# ================= COMMANDS =================
def watch(update, context):
    if not context.args:
        update.message.reply_text("Usage: /watch username")
        return

    username = context.args[0].lower()
    chat_id = update.effective_chat.id

    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
        (username, "UNKNOWN", chat_id)
    )
    conn.commit()

    update.message.reply_text(f"🔍 Now monitoring: {username}")

def unwatch(update, context):
    if not context.args:
        update.message.reply_text("Usage: /unwatch username")
        return

    username = context.args[0].lower()

    cursor.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()

    update.message.reply_text(f"❌ Stopped monitoring: {username}")

def list_users(update, context):
    cursor.execute("SELECT username, status FROM users WHERE chat_id=?",
                   (update.effective_chat.id,))
    rows = cursor.fetchall()

    if not rows:
        update.message.reply_text("No usernames added.")
        return

    msg = "📊 Monitoring List:\n\n"
    for u, s in rows:
        msg += f"• {u} → {s}\n"

    update.message.reply_text(msg)

# ================= MONITOR LOOP =================
def monitor_loop(bot):
    while True:
        cursor.execute("SELECT username, status, chat_id FROM users")
        rows = cursor.fetchall()

        for username, old_status, chat_id in rows:
            new_status = check_instagram(username)

            if new_status == "UNKNOWN":
                continue

            if new_status != old_status:
                cursor.execute(
                    "UPDATE users SET status=? WHERE username=?",
                    (new_status, username)
                )
                conn.commit()

                alert = f"""
🚨 INSTAGRAM STATUS CHANGE

👤 Username: {username}
📊 Previous: {old_status}
📌 Current: {new_status}
⏰ {datetime.now().strftime('%d %b %Y | %I:%M %p')}

━━━━━━━━━━━━━━━━
⚡ Powered by @proxyfxc
"""
                try:
                    bot.send_message(chat_id=chat_id, text=alert)
                except:
                    pass

        time.sleep(CHECK_INTERVAL)

# ================= MAIN =================
def main():
    print("Bot starting on Render...")

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("watch", watch))
    dp.add_handler(CommandHandler("unwatch", unwatch))
    dp.add_handler(CommandHandler("list", list_users))

    threading.Thread(
        target=monitor_loop,
        args=(updater.bot,),
        daemon=True
    ).start()

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
