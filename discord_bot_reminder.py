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

SPECIAL_QUOTA = {1086571236160708709: {"count": 1, "days": 3}}

DEMOTED_USERS_FILE = "demoted_users.json"
CONFIG_FILE = "config.json"

def load_demoted_data():
    if os.path.exists(DEMOTED_USERS_FILE):
        with open(DEMOTED_USERS_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_demoted_data(data):
    with open(DEMOTED_USERS_FILE, "w") as f:
        json.dump(data, f)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {"reminder_interval": 60, "last_demotion_date": "", "last_reminder_date": ""}
    return {"reminder_interval": 60, "last_demotion_date": "", "last_reminder_date": ""}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

demoted_users = load_demoted_data()
config = load_config()

def is_owner(ctx):
    return ctx.author.id == 608461552034643992

def get_deadline_for_now(now=None):
    est_offset = timezone(timedelta(hours=-5))
    now = now or datetime.now(timezone.utc)
    now_est = now.astimezone(est_offset)
    deadline_est = now_est.replace(hour=18, minute=0, second=0, microsecond=0)
    if now_est >= deadline_est:
        deadline_est += timedelta(days=1)
    return deadline_est.astimezone(timezone.utc)

async def check_user_restoration(uid_str):
    global demoted_users
    if uid_str not in demoted_users:
        return

    uid = int(uid_str)
    name = USER_MAPPING.get(uid)
    if not name:
        return

    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try:
            track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except:
            return

    deadline_utc = get_deadline_for_now()
    last_period = deadline_utc - timedelta(days=1)

    guild = track_channel.guild
    data = demoted_users[uid_str]

    new_count = 0
    async for msg in track_channel.history(limit=1000, after=last_period, before=deadline_utc):
        content = msg.content if msg.content else ""
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description: content += f" {embed.description}"
                if embed.author and embed.author.name: content += f" {embed.author.name}"
                if embed.title: content += f" {embed.title}"

        pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
        if re.search(pattern, content, re.IGNORECASE):
            new_count += 1
        elif msg.author.bot and name.lower() in content.lower():
            if any(term in content.lower() for term in ["posted", "new video", "youtu.be", "youtube.com"]):
                if not re.search(pattern, content, re.IGNORECASE):
                    new_count += 1

    if new_count >= data["missing"]:
        member = guild.get_member(uid)
        if not member:
            try:
                member = await guild.fetch_member(uid)
            except:
                return
        roles_to_add = [guild.get_role(rid) for rid in data["roles"] if guild.get_role(rid)]
        if roles_to_add:
            await member.add_roles(*roles_to_add)
        log_channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ <@{uid}> uploaded missing videos! Roles restored. You still need to meet today's regular quota.")
        del demoted_users[uid_str]
        save_demoted_data(demoted_users)

@bot.command(name='set_interval')
@commands.check(is_owner)
async def set_interval(ctx, minutes: int):
    if minutes < 1:
        await ctx.send("Interval must be >= 1 minute.")
        return
    config["reminder_interval"] = minutes
    save_config(config)
    reminder_loop.change_interval(minutes=minutes)
    await ctx.send(f"✅ Interval set to {minutes} minutes.")

@bot.event
async def on_message(message):
    if message.channel.id == VIDEO_TRACK_CHANNEL_ID:
        for uid_str in list(demoted_users.keys()):
            name = USER_MAPPING.get(int(uid_str))
            if name:
                pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
                content = message.content or ""
                if message.embeds:
                    for embed in message.embeds:
                        if embed.description: content += f" {embed.description}"
                if re.search(pattern, content, re.IGNORECASE):
                    await check_user_restoration(uid_str)
    await bot.process_commands(message)

async def run_yesterday_demotion_and_summary():
    global demoted_users
    now = datetime.now(timezone.utc)
    est_offset = timezone(timedelta(hours=-5))
    now_est = now.astimezone(est_offset)
    today_str = now_est.strftime("%Y-%m-%d")
    deadline_utc = get_deadline_for_now(now)
    last_deadline_utc = deadline_utc - timedelta(days=1)
    period_label = f"From <t:{int(last_deadline_utc.timestamp())}:f> to <t:{int(deadline_utc.timestamp())}:f>"
    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try:
            track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except:
            return

    current_counts = {uid: 0 for uid in USER_MAPPING}
    async for msg in track_channel.history(limit=500, after=last_deadline_utc, before=deadline_utc):
        content = msg.content if msg.content else ""
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description: content += f" {embed.description}"
                if embed.author and embed.author.name: content += f" {embed.author.name}"
                if embed.title: content += f" {embed.title}"
        for uid, name in USER_MAPPING.items():
            pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
            if re.search(pattern, content, re.IGNORECASE):
                current_counts[uid] += 1
            elif msg.author.bot and name.lower() in content.lower():
                if any(term in content.lower() for term in ["posted", "new video", "youtu.be", "youtube.com"]):
                    if not re.search(pattern, content, re.IGNORECASE):
                        current_counts[uid] += 1
    guild = track_channel.guild
    demoted_now = []
    for uid in USER_MAPPING:
        if str(uid) in demoted_users:
            continue
        quota = SPECIAL_QUOTA.get(uid, {"count": 3})
        required = quota["count"]
        if current_counts[uid] < required:
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except:
                    continue
            roles_to_remove = [r.id for r in member.roles if r.id in MANAGED_ROLES]
            if roles_to_remove:
                role_objs = [guild.get_role(rid) for rid in roles_to_remove if guild.get_role(rid)]
                if role_objs:
                    await member.remove_roles(*role_objs)
                    demoted_users[str(uid)] = {"roles": roles_to_remove, "missing": required - current_counts[uid]}
                    save_demoted_data(demoted_users)
                    demoted_now.append(f"<@{uid}> ({current_counts[uid]}/{required})")

    # ALWAYS send summary embed for visibility!
    log_channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="Video Uploads – Yesterday's Results",
            description=period_label,
            color=discord.Color.red() if demoted_now else discord.Color.green()
        )
        lines = []
        for uid, name in USER_MAPPING.items():
            quota = SPECIAL_QUOTA.get(uid, {"count": 3})
            required = quota["count"]
            lines.append(f"<@{uid}>: {current_counts[uid]}/{required}")
        embed.add_field(name="Status", value="\n".join(lines), inline=False)
        if demoted_now:
            embed.add_field(name="Demoted", value="\n".join(demoted_now), inline=False)
            embed.set_footer(text="Demoted users need to upload missing videos to get roles back.")
        else:
            embed.set_footer(text="All users met their quota for yesterday!")
        await log_channel.send(embed=embed)

@tasks.loop(minutes=5)
async def check_restores():
    global demoted_users
    if not demoted_users:
        return
    for uid_str in list(demoted_users.keys()):
        await check_user_restoration(uid_str)

@tasks.loop(minutes=60)
async def reminder_loop():
    est_offset = timezone(timedelta(hours=-5))
    now_est = datetime.now(est_offset)
    today_str = now_est.strftime("%Y-%m-%d")
    # Always run at exactly or after 6PM EST
    if now_est.hour == 18 and (config.get("last_reminder_date") != today_str):
        config["last_reminder_date"] = today_str
        save_config(config)
        await run_yesterday_demotion_and_summary()

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user.name}')
    if not check_restores.is_running():
        check_restores.start()
    if not reminder_loop.is_running():
        reminder_loop.start()

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        bot.run(token)
    else:
        logging.error("No DISCORD_BOT_TOKEN found in environment.")
