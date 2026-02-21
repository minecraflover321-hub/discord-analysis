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

# --- FLASK FOR RENDER (To keep it alive) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running and healthy!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
TOKEN = os.getenv("BOT_TOKEN")
CHECK_INTERVAL = 300 

if not TOKEN:
    print("❌ Error: BOT_TOKEN not found in environment variables!")
    exit(1)

# --- DATABASE ---
def init_db():
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
    return conn

db_conn = init_db()

# --- INSTAGRAM LOGIC ---
def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # No proxy used here by default, add if needed
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            if "Sorry, this page isn't available" in r.text:
                return "BANNED"
            return "ACTIVE"
        if r.status_code == 404:
            return "BANNED"
    except Exception as e:
        print(f"Check Error for {username}: {e}")
    return "UNKNOWN"

# --- BOT COMMANDS ---
async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch username")
        return
    user_to_watch = context.args[0].lower().replace("@", "")
    cursor = db_conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (username, status, chat_id) VALUES (?, ?, ?)", 
                   (user_to_watch, "UNKNOWN", update.effective_chat.id))
    db_conn.commit()
    await update.message.reply_text(f"✅ Monitoring started for: @{user_to_watch}")

async def list_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = db_conn.cursor()
    cursor.execute("SELECT username, status FROM users WHERE chat_id=?", (update.effective_chat.id,))
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("List is empty.")
        return
    msg = "📊 **Monitoring List:**\n\n" + "\n".join([f"• @{u} -> {s}" for u, s in rows])
    await update.message.reply_text(msg)

# --- BACKGROUND MONITOR ---
async def monitor_loop(application):
    while True:
        cursor = db_conn.cursor()
        cursor.execute("SELECT username, status, chat_id FROM users")
        users = cursor.fetchall()
        
        for username, old_status, chat_id in users:
            new_status = check_instagram(username)
            if new_status != "UNKNOWN" and new_status != old_status:
                cursor.execute("UPDATE users SET status=? WHERE username=?", (new_status, username))
                db_conn.commit()
                alert = f"🔔 **STATUS CHANGE**\n\n👤 User: @{username}\n📉 New Status: {new_status}\n⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
                try:
                    await application.bot.send_message(chat_id=chat_id, text=alert)
                except Exception as e:
                    print(f"Failed to send alert: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)

# --- MAIN ---
if __name__ == "__main__":
    # 1. Start Flask in background
    Thread(target=run_flask, daemon=True).start()

    # 2. Build Telegram App
    application = ApplicationBuilder().token(TOKEN).build()

    # 3. Add Handlers
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("list", list_all))

    # 4. Start Background Task
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_loop(application))

    # 5. Start Polling
    print("🚀 Bot is starting...")
    application.run_polling()
