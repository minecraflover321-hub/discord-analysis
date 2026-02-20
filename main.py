import os
import asyncio
import sqlite3
import random
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
CHECK_INTERVAL = 300  # 5 minutes

if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment.")

# ================= DATABASE =================
conn = sqlite3.connect("monitor.db")
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
]

def get_proxy():
    proxy = random.choice(PROXIES)
    if proxy:
        return {"http": proxy, "https": proxy}
    return None

# ================= INSTAGRAM CHECK =================
def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, proxies=get_proxy(), timeout=10)

        if r.status_code == 200:
            if "Sorry, this page isn't available" in r.text:
                return "BANNED"
            return "ACTIVE"

        if r.status_code == 404:
            return "BANNED"

    except:
        return "UNKNOWN"

    return "UNKNOWN"

# ================= COMMANDS =================
async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch username")
        return

    username = context.args[0].lower()
    chat_id = update.effective_chat.id

    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
        (username, "UNKNOWN", chat_id)
    )
    conn.commit()

    await update.message.reply_text(f"🔍 Now monitoring: {username}")

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unwatch username")
        return

    username = context.args[0].lower()
    cursor.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()

    await update.message.reply_text(f"❌ Stopped monitoring: {username}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute(
        "SELECT username, status FROM users WHERE chat_id=?",
        (update.effective_chat.id,)
    )
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("No usernames added.")
        return

    msg = "📊 Monitoring List:\n\n"
    for u, s in rows:
        msg += f"• {u} → {s}\n"

    await update.message.reply_text(msg)

# ================= MONITOR LOOP =================
async def monitor_loop(app):
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
                await app.bot.send_message(chat_id=chat_id, text=alert)

        await asyncio.sleep(CHECK_INTERVAL)

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("list", list_users))

    app.create_task(monitor_loop(app))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
