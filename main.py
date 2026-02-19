import discord
from discord.ext import commands, tasks
import requests
import json
import os
from flask import Flask
from threading import Thread

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TOKEN")
DATA_FILE = "data.json"
CHECK_INTERVAL_MINUTES = 5
# ----------------------------------------

# ---------------- FLASK -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# ----------------------------------------

# ------------- DISCORD SETUP ------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
# ----------------------------------------

# ---------------- DATA ------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"watchlist": {}, "alert_channel": None}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
# ----------------------------------------

# -------- INSTAGRAM CHECK ---------------
def check_instagram(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200:
            return "ACTIVE"
        elif r.status_code == 404:
            return "NOT_FOUND"
        else:
            return "ERROR"
    except:
        return "ERROR"
# ----------------------------------------

# ------------- EMBED BUILDER ------------
def build_embed(username, status):
    colors = {
        "ACTIVE": discord.Color.green(),
        "BANNED": discord.Color.red(),
        "NOT_FOUND": discord.Color.gold()
    }

    embed = discord.Embed(
        title="Instagram Status Update",
        description=f"Username: **{username}**\nStatus: **{status}**",
        color=colors.get(status, discord.Color.blue())
    )

    return embed
# ----------------------------------------

# ------------- WATCHER LOOP -------------
@tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
async def watcher():
    await bot.wait_until_ready()

    for username, info in data["watchlist"].items():
        old_status = info.get("status", "UNKNOWN")
        new_status = check_instagram(username)

        if new_status in ["ERROR", "NOT_FOUND"]:
            continue

        if new_status != old_status:
            data["watchlist"][username]["status"] = new_status
            save_data(data)

            channel_id = data.get("alert_channel")
            if channel_id:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=build_embed(username, new_status))
# ----------------------------------------

# --------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    if not watcher.is_running():
        watcher.start()
# ----------------------------------------

# -------------- COMMANDS ----------------

# Set alert channel
@bot.command()
async def setchannel(ctx):
    data["alert_channel"] = ctx.channel.id
    save_data(data)
    await ctx.send("✅ This channel is now set for alerts.")

# Watch username
@bot.command()
async def watch(ctx, username: str):
    username = username.lower()
    status = check_instagram(username)

    if status == "NOT_FOUND":
        await ctx.send("❌ Username not found.")
        return

    data["watchlist"][username] = {"status": status}
    save_data(data)

    await ctx.send(embed=build_embed(username, status))

# Instant check
@bot.command()
async def check(ctx, username: str):
    username = username.lower()
    status = check_instagram(username)
    await ctx.send(embed=build_embed(username, status))

# Show watchlist
@bot.command()
async def list(ctx):
    if not data["watchlist"]:
        await ctx.send("Watchlist is empty.")
        return

    desc = ""
    for user, info in data["watchlist"].items():
        desc += f"• {user} - {info['status']}\n"

    embed = discord.Embed(
        title="Watchlist",
        description=desc,
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed)

# ----------------------------------------

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("TOKEN not found!")

    Thread(target=run_flask).start()
    bot.run(TOKEN)
