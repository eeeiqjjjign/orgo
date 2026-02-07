import discord
from discord.ext import commands, tasks
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
import re
import json

from keep_alive import keep_alive

keep_alive()

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True

bot = commands.Bot(command_prefix='.', intents=intents)

REMINDER_CHANNEL_ID = 1468407822860423273
VIDEO_TRACK_CHANNEL_ID = 1469432714896740474

MANAGED_ROLES = [
    1417986455296278538, 
    1417959557719654550, 
    1417968485031608443, 
    1427466045324787742, 
    1418029602735128586, 
    1417970206990532730
]

USER_MAPPING = {
    1086571236160708709: "FunwithBg",
    1157663612115107981: "Snipzy-AZ",
    1444845857701630094: "Jay",
    1458104862834167824: "Raccoon",
    1210942252264857673: "RINGTA EMPIRE"
}

DEMOTED_USERS_FILE = "demoted_users.json"
CONFIG_FILE = "config.json"

def load_demoted_data():
    if os.path.exists(DEMOTED_USERS_FILE):
        with open(DEMOTED_USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_demoted_data(data):
    with open(DEMOTED_USERS_FILE, "w") as f:
        json.dump(data, f)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"reminder_interval": 60}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

demoted_users = load_demoted_data()
config = load_config()

def is_owner(ctx):
    return ctx.author.id == 608461552034643992

def get_next_deadline():
    now_utc = datetime.now(timezone.utc)
    deadline_utc = now_utc.replace(hour=23, minute=0, second=0, microsecond=0)
    if now_utc > deadline_utc:
        deadline_utc += timedelta(days=1)
    return deadline_utc

async def check_user_restoration(uid_str):
    global demoted_users
    if uid_str not in demoted_users:
        return

    uid = int(uid_str)
    name = USER_MAPPING.get(uid)
    if not name: return

    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try: track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except: return

    deadline_utc = get_next_deadline()
    last_reset = deadline_utc - timedelta(days=1)
    
    guild = track_channel.guild
    data = demoted_users[uid_str]
    
    new_count = 0
    async for msg in track_channel.history(limit=100, after=last_reset):
        pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
        if re.search(pattern, msg.content, re.IGNORECASE):
            new_count += 1
    
    if new_count >= data["missing"]:
        member = guild.get_member(uid)
        if not member:
            try: member = await guild.fetch_member(uid)
            except: return
        
        roles_to_add = [guild.get_role(rid) for rid in data["roles"] if guild.get_role(rid)]
        if roles_to_add:
            await member.add_roles(*roles_to_add)
            
        log_channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ <@{uid}> uploaded their missing videos! Roles restored. Note: You still need to upload 3 more for today!")
        
        del demoted_users[uid_str]
        save_demoted_data(demoted_users)

@bot.command(name='set_interval')
@commands.check(is_owner)
async def set_interval(ctx, minutes: int):
    if minutes < 1:
        await ctx.send("Interval must be at least 1 minute.")
        return
    
    config["reminder_interval"] = minutes
    save_config(config)
    
    reminder_loop.change_interval(minutes=minutes)
    await ctx.send(f"✅ Reminder interval set to {minutes} minutes.")

@set_interval.error
async def set_interval_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Please provide a time in minutes. Example: `.set_interval 20`")

@bot.event
async def on_message(message):
    if message.channel.id == VIDEO_TRACK_CHANNEL_ID:
        # Check if any demoted user just posted
        for uid_str in list(demoted_users.keys()):
            name = USER_MAPPING.get(int(uid_str))
            if name:
                pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
                if re.search(pattern, message.content, re.IGNORECASE):
                    await check_user_restoration(uid_str)
    
    await bot.process_commands(message)

@tasks.loop(minutes=1)
async def check_demotion_loop():
    global demoted_users
    now_utc = datetime.now(timezone.utc)
    
    if now_utc.hour == 23 and now_utc.minute == 0:
        deadline_utc = get_next_deadline()
        last_reset = deadline_utc - timedelta(days=1)
        
        track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
        if not track_channel:
            track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
            
        current_counts = {uid: 0 for uid in USER_MAPPING}
        async for msg in track_channel.history(limit=None, after=last_reset):
            for uid, name in USER_MAPPING.items():
                pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
                if re.search(pattern, msg.content, re.IGNORECASE):
                    current_counts[uid] += 1
        
        guild = track_channel.guild
        for uid, count in current_counts.items():
            if count < 3:
                member = guild.get_member(uid)
                if not member:
                    try: member = await guild.fetch_member(uid)
                    except: continue
                
                roles_to_remove = [r.id for r in member.roles if r.id in MANAGED_ROLES]
                if roles_to_remove:
                    roles_objects = [guild.get_role(rid) for rid in roles_to_remove]
                    await member.remove_roles(*roles_objects)
                    
                    demoted_users[str(uid)] = {
                        "roles": roles_to_remove,
                        "missing": 3 - count
                    }
                    save_demoted_data(demoted_users)
                    
                    log_channel = bot.get_channel(REMINDER_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(f"⚠️ <@{uid}> has been demoted for missing {3-count} videos today.")

@tasks.loop(minutes=5)
async def track_restoration_loop():
    global demoted_users
    if not demoted_users:
        return
    for uid_str in list(demoted_users.keys()):
        await check_user_restoration(uid_str)

@tasks.loop(minutes=60)
async def reminder_loop():
    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if not channel:
        try: channel = await bot.fetch_channel(REMINDER_CHANNEL_ID)
        except: return

    now_utc = datetime.now(timezone.utc)
    deadline_utc = get_next_deadline()
    diff = deadline_utc - now_utc
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    last_reset = deadline_utc - timedelta(days=1)
    
    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try: track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except: return

    current_counts = {uid: 0 for uid in USER_MAPPING}
    async for msg in track_channel.history(limit=None, after=last_reset):
        for uid, name in USER_MAPPING.items():
            pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
            if re.search(pattern, msg.content, re.IGNORECASE):
                current_counts[uid] += 1

    mentions_list = []
    for uid, name in USER_MAPPING.items():
        uid_str = str(uid)
        count = current_counts[uid]
        
        if uid_str in demoted_users:
            missing_from_yesterday = demoted_users[uid_str]["missing"]
            if count < missing_from_yesterday:
                needed = missing_from_yesterday - count
                mentions_list.append(f"<@{uid}> ({name}) needs **{needed}** more shorts (to get roles back)")
            else:
                today_count = count - missing_from_yesterday
                if today_count < 3:
                    needed = 3 - today_count
                    mentions_list.append(f"<@{uid}> ({name}) needs **{needed}** more shorts")
        else:
            if count < 3:
                needed = 3 - count
                mentions_list.append(f"<@{uid}> ({name}) needs **{needed}** more shorts")

    if not mentions_list:
        return

    mentions_str = "\n".join(mentions_list)
    time_str = f"**{hours}h {minutes}m**" if hours > 0 else f"**{minutes}m**"
    
    message = f"🔔 **Upload the video!**\n{mentions_str}\n\nYou have {time_str} left till deadline (<t:1769900400:t>)."
    await channel.send(message)

@bot.event
async def on_ready():
    print(f'Bot is logged in as {bot.user}')
    
    # Set the reminder interval from config
    interval = config.get("reminder_interval", 60)
    reminder_loop.change_interval(minutes=interval)
    
    if not reminder_loop.is_running(): reminder_loop.start()
    if not check_demotion_loop.is_running(): check_demotion_loop.start()
    if not track_restoration_loop.is_running(): track_restoration_loop.start()

token = os.environ.get('DISCORD_BOT_TOKEN')
if token: bot.run(token)
else: print("Token not set.")
