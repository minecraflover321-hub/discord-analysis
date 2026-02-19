import discord
from discord.ext import commands, tasks
import requests
import json
import os

# ---------- CONFIG ----------
TOKEN = os.getenv("TOKEN")  # Render Environment Variable
DATA_FILE = "data.json"
CHECK_INTERVAL_MINUTES = 5
CHANNEL_NAME = "general"
# ----------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- DATA HANDLING ----------

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ---------- INSTAGRAM CHECK ----------

def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and "Sorry, this page isn't available" not in r.text:
            return "ACTIVE"
        else:
            return "BANNED"
    except:
        return "ERROR"

# ---------- WATCHER TASK ----------

@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def watcher():
    await bot.wait_until_ready()
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

            for guild in bot.guilds:
                channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
                if channel:
                    if new_status == "BANNED":
                        await channel.send(
                            f"🚫 Account Banned Successfully!\nUsername: {username}"
                        )
                    elif new_status == "ACTIVE":
                        await channel.send(
                            f"✅ Account Unbanned Successfully!\nUsername: {username}"
                        )

# ---------- EVENTS ----------

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not watcher.is_running():
        watcher.start()

# ---------- COMMANDS ----------

@bot.command()
async def watch(ctx, username: str):
    username = username.lower()
    if username not in data:
        data[username] = {"status": "UNKNOWN", "watch": True}
    else:
        data[username]["watch"] = True

    save_data(data)
    await ctx.send(f"👀 Now watching: {username}")

@bot.command()
async def unwatch(ctx, username: str):
    username = username.lower()
    if username in data:
        data[username]["watch"] = False
        save_data(data)
        await ctx.send(f"🛑 Stopped watching: {username}")
    else:
        await ctx.send("❌ Username not found")

@bot.command()
async def status(ctx, username: str):
    username = username.lower()
    info = data.get(username)
    if not info:
        await ctx.send("❌ No record found")
    else:
        await ctx.send(
            f"Username: {username}\n"
            f"Status: {info['status']}\n"
            f"Watching: {info['watch']}"
        )

if not TOKEN:
    raise ValueError("TOKEN not found! Set it in Render Environment Variables.")

bot.run(TOKEN)
