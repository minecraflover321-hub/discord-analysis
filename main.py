import os
import telebot
import requests
import threading
import time
from flask import Flask

# --- CONFIGURATION FROM ENV ---
# Render pe "BOT_TOKEN" naam se variable banayein
API_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# Credits
CREDITS = "@proxyfxc"
monitoring_users = {} # Format: { 'username': 'status' }

@app.route('/')
def home():
    return f"🔥 Bot is Active! | Powered by {CREDITS}"

# --- CORE LOGIC ---
def check_status(username):
    """Instagram status checker with proper headers"""
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return "ACTIVE"
        elif response.status_code == 404:
            return "BANNED"
        else:
            return "LIMIT" # Instagram rate limit
    except:
        return "ERROR"

def monitor_loop(chat_id):
    while True:
        for username in list(monitoring_users.keys()):
            old_status = monitoring_users[username]
            new_status = check_status(username)

            if new_status == "BANNED" and old_status != "BANNED":
                bot.send_message(chat_id, f"🚫 **BANNED SUCCESSFULLY**\n👤 User: @{username}\n⚡ Credits: {CREDITS}", parse_mode="Markdown")
                monitoring_users[username] = "BANNED"
            
            elif new_status == "ACTIVE" and old_status == "BANNED":
                bot.send_message(chat_id, f"✅ **UNBANNED SUCCESSFULLY**\n👤 User: @{username}\n⚡ Credits: {CREDITS}", parse_mode="Markdown")
                monitoring_users[username] = "ACTIVE"
            
            # Rate limit se bachne ke liye delay
            time.sleep(10) 
        
        time.sleep(60) # Har cycle ke baad 1 min ka gap

# --- BOT COMMANDS ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, f"✨ **Instagram Monitor Bot**\n\nSend `/watch username` to start.\n\nOwner: {CREDITS}", parse_mode="Markdown")

@bot.message_handler(commands=['watch'])
def watch(message):
    try:
        user = message.text.split()[1].replace('@', '')
        current = check_status(user)
        monitoring_users[user] = current
        
        bot.send_message(message.chat.id, f"👀 Monitoring started for @{user}\nInitial Status: {current}\n\nCredits: {CREDITS}")
        
        # Start loop in background if not already running
        if len(monitoring_users) == 1:
            threading.Thread(target=monitor_loop, args=(message.chat.id,), daemon=True).start()
    except IndexError:
        bot.reply_to(message, "❌ Please provide a username: `/watch username`")

# --- EXECUTION ---
if __name__ == "__main__":
    # Flask for Render Port Binding
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)).start()
    
    print("Bot is polling...")
    bot.infinity_polling()
