# bot.py
import discord
from discord.ext import commands, tasks
import requests, json, os, threading
from flask import Flask

# ================= CONFIG =================
TOKEN = os.environ.get("TOKEN")  # Discord bot token
OWNER_ID = os.environ.get("OWNER_ID")  # Discord numeric ID
if OWNER_ID is None:
    raise ValueError("OWNER_ID environment variable not set!")
OWNER_ID = int(OWNER_ID)
DATA_FILE = "data.json"
CHECK_INTERVAL_MINUTES = 5
DEFAULT_CHANNEL_NAME = "general"

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= FLASK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is alive ✅"

# ================= DATA HANDLING =================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
alert_channel_name = DEFAULT_CHANNEL_NAME

# ================= INSTAGRAM FUNCTIONS =================
def instagram_exists(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        # Reliable check: user exists if not "page isn't available"
        if r.status_code == 200:
            if "Sorry, this page isn't available" in r.text:
                return False
            return True
        return False
    except requests.exceptions.RequestException:
        return False

def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            if "Sorry, this page isn't available" in r.text:
                return "BANNED"
            return "ACTIVE"
        return "ERROR"
    except requests.exceptions.RequestException:
        return "ERROR"

# ================= WATCHER TASK =================
@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def watcher():
    for username, info in data.items():
        if not info.get("watch"):
            continue
        old_status = info.get("status", "UNKNOWN")
        new_status = check_instagram(username)
        if new_status == "ERROR":
            continue
        if new_status != old_status:
            info["status"] = new_status
            save_data(data)
            # Send alert in selected channel
            channel = discord.utils.get(bot.get_all_channels(), name=alert_channel_name)
            if not channel:
                continue
            if new_status == "BANNED":
                await channel.send(f"❌ Account Banned!\nUsername: {username}")
            elif new_status == "ACTIVE" and old_status == "BANNED":
                await channel.send(f"✅ Account Unbanned!\nUsername: {username}")

# ================= BOT EVENTS =================
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not watcher.is_running():
        watcher.start()

# ================= BOT COMMANDS =================
@bot.command()
async def watch(ctx, username: str):
    username = username.lower()
    if not instagram_exists(username):
        await ctx.send(f"❌ Username '{username}' does not exist or is invalid.")
        return
    status = check_instagram(username)
    if username not in data:
        data[username] = {"status": status, "watch": True}
    else:
        data[username]["watch"] = True
        data[username]["status"] = status
    save_data(data)
    await ctx.send(f"✅ Now watching: {username} (Status: {status})")

@bot.command()
async def unwatch(ctx, username: str):
    username = username.lower()
    if username in data:
        data[username]["watch"] = False
        save_data(data)
        await ctx.send(f"Stopped watching: {username}")
    else:
        await ctx.send("Username not found in watch list.")

@bot.command()
async def status(ctx, username: str):
    username = username.lower()
    info = data.get(username)
    if not info:
        await ctx.send("No record found")
    else:
        await ctx.send(
            f"Username: {username}\nStatus: {info['status']}\nWatching: {info['watch']}"
        )

@bot.command()
async def list(ctx):
    msg = "Watched accounts:\n"
    for i, (username, info) in enumerate(data.items(), 1):
        msg += f"{i}. {username} - {info['status']} - Watching: {info['watch']}\n"
    await ctx.send(msg or "No accounts being watched.")

@bot.command()
async def admin(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("You are not authorized to use this command.")
        return
    msg = f"Admin Panel\nTotal accounts watched: {len(data)}"
    await ctx.send(msg)

@bot.command()
async def setchannel(ctx, channel_name: str):
    global alert_channel_name
    if ctx.author.id != OWNER_ID:
        await ctx.send("You are not authorized to set the alert channel.")
        return
    alert_channel_name = channel_name
    await ctx.send(f"Alert channel set to: {alert_channel_name}")

# Optional: Check your own Discord ID
@bot.command()
async def myid(ctx):
    await ctx.send(f"Your Discord ID: {ctx.author.id}")

# ================= RUN FLASK + BOT =================
def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

threading.Thread(target=run_flask).start()
bot.run(TOKEN)
