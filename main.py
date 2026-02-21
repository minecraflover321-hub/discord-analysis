import os
import asyncio
import sqlite3
import random
import requests
from datetime import datetime
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Flask setup for Render (Health Check)
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

TOKEN = os.getenv("BOT_TOKEN")
CHECK_INTERVAL = 300  

if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment.")

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect("monitor.db", check_same_thread=False)
    return conn

conn = get_db()
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
PROXIES = [None]

def get_proxy():
    proxy = random.choice(PROXIES)
    return {"http": proxy, "https": proxy} if proxy else None

# ================= INSTAGRAM CHECK =================
def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        r = requests.get(url, headers=headers, proxies=get_proxy(), timeout=15)
        if r.status_code == 200:
            if "Sorry, this page isn't available" in r.text:
                return "BANNED"
            return "ACTIVE"
        if r.status_code == 404:
            return "BANNED"
    except Exception as e:
        print(f"Error checking {username}: {e}")
        return "UNKNOWN"
    return "UNKNOWN"

# ================= COMMANDS =================
async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch username")
        return
    username = context.args[0].lower().replace("@", "")
    chat_id = update.effective_chat.id
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (username, "UNKNOWN", chat_id))
    conn.commit()
    await update.message.reply_text(f"🔍 Now monitoring: {username}")

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unwatch username")
        return
    username = context.args[0].lower().replace("@", "")
    cursor.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    await update.message.reply_text(f"❌ Stopped monitoring: {username}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, status FROM users WHERE chat_id=?", (update.effective_chat.id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("No usernames added.")
        return
    msg = "📊 Monitoring List:\n\n" + "\n".join([f"• {u} → {s}" for u, s in rows])
    await update.message.reply_text(msg)

# ================= MONITOR LOOP =================
async def monitor_loop(app_tg):
    while True:
        try:
            cursor.execute("SELECT username, status, chat_id FROM users")
            rows = cursor.fetchall()
            for username, old_status, chat_id in rows:
                new_status = check_instagram(username)
                if new_status == "UNKNOWN" or new_status == old_status:
                    continue
                
                cursor.execute("UPDATE users SET status=? WHERE username=?", (new_status, username))
                conn.commit()
                
                alert = f"🚨 STATUS CHANGE\n\n👤: {username}\n📊: {old_status} ➔ {new_status}\n⏰: {datetime.now().strftime('%d %b | %I:%M %p')}"
                await app_tg.bot.send_message(chat_id=chat_id, text=alert)
            
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(10)

# ================= MAIN =================
if __name__ == "__main__":
    # Start Flask in a separate thread
    Thread(target=run_flask, daemon=True).start()

    # Start Telegram Bot
    app_tg = ApplicationBuilder().token(TOKEN).build()
    app_tg.add_handler(CommandHandler("watch", watch))
    app_tg.add_handler(CommandHandler("unwatch", unwatch))
    app_tg.add_handler(CommandHandler("list", list_users))

    # Run monitor loop using the app's event loop
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_loop(app_tg))
    
    print("Bot is starting...")
    app_tg.run_polling()
