import discord
from discord.ext import commands, tasks
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
import re
from keep_alive import keep_alive

keep_alive()

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True

bot = commands.Bot(command_prefix='.', intents=intents)

SOURCE_CHANNEL_ID = 1463707650037645455
LOG_CHANNEL_ID = 1383649215321870407
LEADERBOARD_CHANNEL_ID = 1419533221925752964
REMINDER_CHANNEL_ID = 1468407822860423273

STAFF_ROLES = [
    1417970527250677821,
    1417986455296278538,
    1417959557719654550,
    1417968485031608443,
    1427419553029423324
]

LEADERBOARD_CHANNELS = [1417960723363008722, 1417961665902940332]
REMINDER_INTERVAL_MINS = 60

REMINDER_USERS_FILE = "reminder_users.txt"

def load_reminder_users():
    if os.path.exists(REMINDER_USERS_FILE):
        with open(REMINDER_USERS_FILE, "r") as f:
            return [int(line.strip()) for line in f if line.strip().isdigit()]
    else:
        default_users = [1086571236160708709, 1444845857701630094, 1210942252264857673, 1458104862834167824]
        with open(REMINDER_USERS_FILE, "w") as f:
            for uid in default_users:
                f.write(f"{uid}\n")
        return default_users

def save_reminder_users(users):
    with open(REMINDER_USERS_FILE, "w") as f:
        for uid in users:
            f.write(f"{uid}\n")

REMINDER_USERS = load_reminder_users()

def is_owner(ctx):
    return ctx.author.id == 608461552034643992

@tasks.loop(minutes=REMINDER_INTERVAL_MINS)
async def reminder_loop():
    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot.fetch_channel(REMINDER_CHANNEL_ID)
        except:
            return

    now_utc = datetime.now(timezone.utc)
    deadline_utc = now_utc.replace(hour=23, minute=0, second=0, microsecond=0)
    if now_utc > deadline_utc:
        deadline_utc += timedelta(days=1)

    diff = deadline_utc - now_utc
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    mentions = " ".join([f"<@{uid}>" for uid in REMINDER_USERS])

    if hours == 23 and minutes > 50:
        time_str = "23 hours"
        message = f"🔔 {mentions}\n**Upload the video!**\n{time_str} left till your schedule, make sure to post 3 shorts by then!"
    else:
        if hours > 0:
            time_str = f"**{hours} hours and {minutes} minutes**" if minutes > 0 else f"**{hours} hours**"
        else:
            time_str = f"**{minutes} minutes**"
        message = f"🔔 {mentions}\n**Upload the video!**\nYou have {time_str} left till deadline to post 3 shorts every day (<t:1769900400:t>)."
    await channel.send(message)

@bot.event
async def on_ready():
    print(f'Bot is logged in as {bot.user}')
    if not reminder_loop.is_running():
        reminder_loop.start()

@bot.command()
@commands.check(is_owner)
async def adduser(ctx, user: discord.User):
    global REMINDER_USERS
    if user.id not in REMINDER_USERS:
        REMINDER_USERS.append(user.id)
        save_reminder_users(REMINDER_USERS)
        await ctx.send(f"✅ Added {user.mention} to the reminder list.")
    else:
        await ctx.send(f"ℹ️ {user.mention} is already in the list.")

@bot.command()
@commands.check(is_owner)
async def removeuser(ctx, user: discord.User):
    global REMINDER_USERS
    if user.id in REMINDER_USERS:
        REMINDER_USERS.remove(user.id)
        save_reminder_users(REMINDER_USERS)
        await ctx.send(f"✅ Removed {user.mention} from the reminder list.")
    else:
        await ctx.send(f"ℹ️ {user.mention} is not in the list.")

@bot.command()
@commands.check(is_owner)
async def set_interval(ctx, minutes: int):
    global REMINDER_INTERVAL_MINS
    if minutes < 1:
        await ctx.send("❌ Interval must be at least 1 minute.")
        return

    REMINDER_INTERVAL_MINS = minutes
    reminder_loop.change_interval(minutes=minutes)
    await ctx.send(f"✅ Reminder interval set to **{minutes} minutes**.")

token = os.environ.get('DISCORD_BOT_TOKEN')
if token: bot.run(token)
else: print("Token not set.")
