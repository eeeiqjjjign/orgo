import discord
from discord.ext import commands, tasks
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
import re
import json
import dateutil.parser

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
BOT_LOG_CHANNEL_ID = 1470532226209812539
DEMOTE_GUILD_ID = 1347804635989016617

MANAGED_ROLES = [
    1417986455296278538,
    1417959557719654550,
    1417968485031608443,
    1427466045324787742,
    1418029602735128586,
    1417970206990532730,
    1417970527250677821
]

USER_MAPPING = {
    1086571236160708709: "FunwithBg",
    1157663612115107981: "Snipzy-AZ",
    1444845857701630094: "Jay",
    1210942252264857673: "RINGTA EMPIRE",
    1423018852761079829: "yassin_L",
    1121372530238836738: "Raccoon",  # Replaced Zeki with Raccoon new id
}
DISCORD_USERNAMES = {
    1086571236160708709: "life4x",
    1157663612115107981: ".snipzy_",
    1444845857701630094: "jiyansu",
    1210942252264857673: "vsxwexe",
    1423018852761079829: "unknown057908",
    1121372530238836738: "darthsae_", # Replaced zeki4life with darthsae_
}

DEMOTED_USERS_FILE = "demoted_users.json"
CONFIG_FILE = "config.json"
USER_VIDEO_FILE = "user_video_config.json"

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

def load_user_video_config():
    if os.path.exists(USER_VIDEO_FILE):
        with open(USER_VIDEO_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_user_video_config(data):
    with open(USER_VIDEO_FILE, "w") as f:
        json.dump(data, f)

demoted_users = load_demoted_data()
config = load_config()
user_video_config = load_user_video_config()

def is_owner(ctx):
    return ctx.author.id == 608461552034643992

def get_required_videos(uid):
    # Check custom config else fallback to default 3
    return user_video_config.get(str(uid), {}).get("restore", 3)

def get_daily_required_videos(uid):
    return user_video_config.get(str(uid), {}).get("daily", 3)

async def send_bot_log(msg):
    print(f"[BOT LOG] {msg}")
    log_channel = bot.get_channel(BOT_LOG_CHANNEL_ID)
    if not log_channel:
        try:
            log_channel = await bot.fetch_channel(BOT_LOG_CHANNEL_ID)
        except Exception as e:
            print(f"[BOTLOG-ERROR] Could not fetch BOT LOG channel: {e}")
            return
    try:
        await log_channel.send(str(msg))
    except Exception as e:
        print(f"[BOTLOG-ERROR] Could not send log to Discord: {e}")

async def recover_demoted_users_from_logs():
    global demoted_users
    if demoted_users:
        return
    log_channel = bot.get_channel(BOT_LOG_CHANNEL_ID)
    if not log_channel:
        try:
            log_channel = await bot.fetch_channel(BOT_LOG_CHANNEL_ID)
        except:
            print("[BOTLOG-ERROR] Could not fetch recovery log channel")
            return
    temp_demoted = {}
    async for msg in log_channel.history(limit=250):
        text = msg.content
        m = re.search(r"DEMOTED\s+<@(\d+)>\s+\([^)]+\)\s+-- Removed roles: (\[[^\]]*\]).*Missing: (\d+)", text)
        if m:
            uid = m.group(1)
            roles_str = m.group(2)
            missing = int(m.group(3))
            try:
                roles = json.loads(roles_str.replace("'", ""))
                temp_demoted[uid] = {
                    "roles": roles,
                    "missing": missing,
                    "demoted_date": datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                print(f"Failed to parse demote line: {e}")
    if temp_demoted:
        demoted_users.update(temp_demoted)
        save_demoted_data(demoted_users)
        print(f"Recovered {len(temp_demoted)} demoted users from logs.")

async def check_user_restoration(uid_str):
    global demoted_users
    if uid_str not in demoted_users:
        await send_bot_log(f"User {uid_str} not in demoted_users, skipping restoration.")
        return
    uid = int(uid_str)
    name = USER_MAPPING.get(uid)
    if not name:
        await send_bot_log(f"No name in USER_MAPPING for UID {uid}, skipping restoration.")
        return
    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try:
            track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except:
            await send_bot_log(f"Could not fetch track_channel {VIDEO_TRACK_CHANNEL_ID} (restoration).")
            return
    # Use demoted_date
    data = demoted_users[uid_str]
    demoted_date = dateutil.parser.parse(data.get('demoted_date', datetime.now(timezone.utc).isoformat()))
    new_count = 0
    async for msg in track_channel.history(limit=1000, after=demoted_date):
        content = ""
        if msg.content:
            content += msg.content
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description:
                    content += f" {embed.description}"
                if embed.author and embed.author.name:
                    content += f" {embed.author.name}"
                if embed.title:
                    content += f" {embed.title}"
        pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
        if re.search(pattern, content, re.IGNORECASE):
            new_count += 1
        elif msg.author.bot and name.lower() in content.lower():
            if any(term in content.lower() for term in ["posted", "new video", "youtu.be", "youtube.com"]):
                if not re.search(pattern, content, re.IGNORECASE):
                    new_count += 1
    await send_bot_log(f"Restoration check for {uid}: found {new_count} new (needed {data['missing']}).")
    if new_count >= data["missing"]:
        guild = bot.get_guild(DEMOTE_GUILD_ID)
        member = guild.get_member(uid)
        if not member:
            try:
                member = await guild.fetch_member(uid)
            except Exception as e:
                await send_bot_log(f"Could not fetch member {uid} (restoration) in demote guild. Error: {e}")
                return
        roles_to_add = [guild.get_role(rid) for rid in data["roles"] if guild.get_role(rid)]
        if roles_to_add:
            await member.add_roles(*roles_to_add)
        log_channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"✅ <@{uid}> uploaded enough missing videos! Roles restored. Note: You must upload your daily quota for tomorrow or you will be demoted again."
            )
        del demoted_users[uid_str]
        save_demoted_data(demoted_users)
        await send_bot_log(f"Roles restored for <@{uid}> after uploading missing videos.")

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

@bot.command(name='set_video_restore')
@commands.check(is_owner)
async def set_video_restore(ctx, user_id: int, num: int):
    if num < 0:
        await ctx.send("❌ Amount must be >= 0.")
        return
    user_video_config.setdefault(str(user_id), {})
    user_video_config[str(user_id)]["restore"] = num
    save_user_video_config(user_video_config)
    await ctx.send(f"✅ <@{user_id}> restore requirement set to {num} videos.")

@set_video_restore.error
async def set_video_restore_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `.set_video_restore <user_id> <amount>`")

@bot.command(name='set_video_daily')
@commands.check(is_owner)
async def set_video_daily(ctx, user_id: int, num: int):
    if num < 0:
        await ctx.send("❌ Amount must be >= 0.")
        return
    user_video_config.setdefault(str(user_id), {})
    user_video_config[str(user_id)]["daily"] = num
    save_user_video_config(user_video_config)
    await ctx.send(f"✅ <@{user_id}> daily requirement set to {num} videos.")

@set_video_daily.error
async def set_video_daily_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `.set_video_daily <user_id> <amount>`")

@bot.command(name='add_video_restore')
@commands.check(is_owner)
async def add_video_restore(ctx, user_id: int, num: int):
    user_video_config.setdefault(str(user_id), {})
    restore = user_video_config[str(user_id)].get("restore", 3)
    restore += num
    user_video_config[str(user_id)]["restore"] = restore
    save_user_video_config(user_video_config)
    await ctx.send(f"✅ Added {num} videos. <@{user_id}> now needs {restore} videos to restore.")

@add_video_restore.error
async def add_video_restore_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `.add_video_restore <user_id> <amount>`")

@bot.command(name='remove_video_restore')
@commands.check(is_owner)
async def remove_video_restore(ctx, user_id: int, num: int):
    user_video_config.setdefault(str(user_id), {})
    restore = user_video_config[str(user_id)].get("restore", 3)
    restore = max(0, restore - num)
    user_video_config[str(user_id)]["restore"] = restore
    save_user_video_config(user_video_config)
    await ctx.send(f"✅ Removed {num} videos. <@{user_id}> now needs {restore} videos to restore.")

@remove_video_restore.error
async def remove_video_restore_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `.remove_video_restore <user_id> <amount>`")

@bot.command(name='add_video_daily')
@commands.check(is_owner)
async def add_video_daily(ctx, user_id: int, num: int):
    user_video_config.setdefault(str(user_id), {})
    daily = user_video_config[str(user_id)].get("daily", 3)
    daily += num
    user_video_config[str(user_id)]["daily"] = daily
    save_user_video_config(user_video_config)
    await ctx.send(f"✅ Added {num} videos. <@{user_id}> now must post {daily} videos daily.")

@add_video_daily.error
async def add_video_daily_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `.add_video_daily <user_id> <amount>`")

@bot.command(name='remove_video_daily')
@commands.check(is_owner)
async def remove_video_daily(ctx, user_id: int, num: int):
    user_video_config.setdefault(str(user_id), {})
    daily = user_video_config[str(user_id)].get("daily", 3)
    daily = max(0, daily - num)
    user_video_config[str(user_id)]["daily"] = daily
    save_user_video_config(user_video_config)
    await ctx.send(f"✅ Removed {num} videos. <@{user_id}> now must post {daily} videos daily.")

@remove_video_daily.error
async def remove_video_daily_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ Only the owner can use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `.remove_video_daily <user_id> <amount>`")

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
                        if embed.description:
                            content += f" {embed.description}"
                if re.search(pattern, content, re.IGNORECASE):
                    await check_user_restoration(uid_str)
    await bot.process_commands(message)

async def run_demotion_check():
    global demoted_users
    est = timezone(timedelta(hours=-5))
    now_est = datetime.now(est)
    period_end_est = now_est.replace(hour=18, minute=0, second=0, microsecond=0)
    if now_est < period_end_est:
        period_end_est -= timedelta(days=1)
    period_start_est = period_end_est - timedelta(days=1)
    period_start = period_start_est.astimezone(timezone.utc)
    period_end = period_end_est.astimezone(timezone.utc)
    await send_bot_log(f"DEMOTION CHECK (YESTERDAY): from={period_start} to={period_end}")

    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try:
            track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except Exception as e:
            await send_bot_log(f"FAILED TO FIND TRACK CHANNEL: {VIDEO_TRACK_CHANNEL_ID} | {e}")
            return

    guild = bot.get_guild(DEMOTE_GUILD_ID)
    if not guild:
        await send_bot_log(f"FAILED TO FIND DEMOTION SERVER (Guild ID: {DEMOTE_GUILD_ID})!")
        return

    current_counts = {uid: 0 for uid in USER_MAPPING}
    async for msg in track_channel.history(limit=2000, after=period_start, before=period_end):
        content = ""
        if msg.content:
            content += msg.content
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description:
                    content += f" {embed.description}"
                if embed.author and embed.author.name:
                    content += f" {embed.author.name}"
                if embed.title:
                    content += f" {embed.title}"
        for uid, name in USER_MAPPING.items():
            pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
            if re.search(pattern, content, re.IGNORECASE):
                current_counts[uid] += 1
            elif msg.author.bot and name.lower() in content.lower():
                if any(term in content.lower() for term in ["posted", "new video", "youtu.be", "youtube.com"]):
                    if not re.search(pattern, content, re.IGNORECASE):
                        current_counts[uid] += 1

    demotion_details = []
    for uid, count in current_counts.items():
        required = get_daily_required_videos(uid)
        missing_today = required - count
        await send_bot_log(f"Checking user: {uid} ({DISCORD_USERNAMES.get(uid,'?')}) -- count: {count}, required: {required}")
        if str(uid) in demoted_users:
            demoted_users[str(uid)]["missing"] += max(0, missing_today)
            if "demoted_date" not in demoted_users[str(uid)]:
                demoted_users[str(uid)]["demoted_date"] = datetime.now(timezone.utc).isoformat()
            roles_to_show = demoted_users[str(uid)]["roles"]
            missing_videos = demoted_users[str(uid)]["missing"]
            demotion_details.append(
                f"<@{uid}> ({count}/{required} videos) — You need {missing_videos} more videos to restore your roles! (Roles lost: {', '.join(str(r) for r in roles_to_show)})"
            )
            await send_bot_log(f"Already demoted: {uid} (missing={missing_videos})")
            save_demoted_data(demoted_users)
            continue
        if missing_today > 0:
            member = guild.get_member(uid)
            if not member:
                try:
                    member = await guild.fetch_member(uid)
                except Exception as e:
                    await send_bot_log(
                        f"Could not fetch member {uid} ({DISCORD_USERNAMES.get(uid,'?')}) in demotion server. Error: {e}"
                    )
                    continue
            roles_before = [role.id for role in member.roles]
            managed_roles = [role for role in member.roles if role.id in MANAGED_ROLES]
            managed_roles_ids = [role.id for role in managed_roles]
            await send_bot_log(
                f"{uid} ({DISCORD_USERNAMES.get(uid,'?')}): Current roles: {roles_before} | Managed roles to remove: {managed_roles_ids} (server: {DEMOTE_GUILD_ID})"
            )
            if not managed_roles:
                await send_bot_log(f"{uid} ({DISCORD_USERNAMES.get(uid,'?')}) has no managed roles to remove!")
                continue
            try:
                await member.remove_roles(*managed_roles, reason="Did not meet quota")
                roles_after = [role.id for role in member.roles if role.id not in managed_roles_ids]
                demoted_users[str(uid)] = {
                    "roles": managed_roles_ids,
                    "missing": missing_today,
                    "demoted_date": datetime.now(timezone.utc).isoformat()
                }
                save_demoted_data(demoted_users)
                demotion_details.append(
                    f"<@{uid}> ({count}/{required} videos) — You need {missing_today} more videos to restore your roles! (Roles lost: {', '.join(str(r) for r in managed_roles_ids)})"
                )
                await send_bot_log(
                    f"DEMOTED <@{uid}> ({DISCORD_USERNAMES.get(uid, '?')}) -- Removed roles: {managed_roles_ids} | "
                    f"Roles before: {roles_before} | Roles after demotion: {roles_after} | Missing: {missing_today} (server: {DEMOTE_GUILD_ID})"
                )
            except Exception as e:
                await send_bot_log(f"Failed to demote user {uid}: {e}")

    log_channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if demotion_details and log_channel:
        msg = "**YESTERDAY videos posted:**\n" + "\n".join(demotion_details)
        msg += "\n\n⚠️ These users have been demoted. Upload your missing videos to get your roles back!"
        await log_channel.send(msg)
        await send_bot_log(f"Demotion log posted to reminder channel.")

@tasks.loop(minutes=1)
async def check_demotion_loop():
    est_offset = timezone(timedelta(hours=-5))
    now_est = datetime.now(est_offset)
    if now_est.hour == 18 and now_est.minute == 0:
        today_str = now_est.strftime("%Y-%m-%d")
        if config.get("last_demotion_date") != today_str:
            await run_demotion_check()
            config["last_demotion_date"] = today_str
            save_config(config)

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
        try:
            channel = await bot.fetch_channel(REMINDER_CHANNEL_ID)
        except:
            return
    est_offset = timezone(timedelta(hours=-5))
    now_est = datetime.now(est_offset)
    today_str = now_est.strftime("%Y-%m-%d")
    if config.get("last_reminder_date") != today_str:
        config["last_reminder_date"] = today_str
        save_config(config)
        await run_demotion_check()
    now_utc = datetime.now(timezone.utc)
    period_start = now_utc - timedelta(days=1)
    track_channel = bot.get_channel(VIDEO_TRACK_CHANNEL_ID)
    if not track_channel:
        try:
            track_channel = await bot.fetch_channel(VIDEO_TRACK_CHANNEL_ID)
        except:
            return
    current_counts = {uid: 0 for uid in USER_MAPPING}
    for uid in USER_MAPPING:
        current_counts[uid] = 0
    async for msg in track_channel.history(limit=2000, after=period_start, before=now_utc):
        content = ""
        if msg.content:
            content += msg.content
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description:
                    content += f" {embed.description}"
                if embed.author and embed.author.name:
                    content += f" {embed.author.name}"
                if embed.title:
                    content += f" {embed.title}"
        for uid, name in USER_MAPPING.items():
            pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
            if re.search(pattern, content, re.IGNORECASE):
                current_counts[uid] += 1
            elif msg.author.bot and name.lower() in content.lower():
                if any(term in content.lower() for term in ["posted", "new video", "youtu.be", "youtube.com"]):
                    if not re.search(pattern, content, re.IGNORECASE):
                        current_counts[uid] += 1
    yesterday_end_est = now_est.replace(hour=18, minute=0, second=0, microsecond=0)
    if now_est < yesterday_end_est:
        yesterday_end_est -= timedelta(days=1)
    yesterday_start_est = yesterday_end_est - timedelta(days=1)
    yesterday_start = yesterday_start_est.astimezone(timezone.utc)
    yesterday_end = yesterday_end_est.astimezone(timezone.utc)
    yesterday_counts = {uid: 0 for uid in USER_MAPPING}
    for uid in USER_MAPPING:
        yesterday_counts[uid] = 0
    async for msg in track_channel.history(limit=2000, after=yesterday_start, before=yesterday_end):
        content = ""
        if msg.content:
            content += msg.content
        if msg.embeds:
            for embed in msg.embeds:
                if embed.description:
                    content += f" {embed.description}"
                if embed.author and embed.author.name:
                    content += f" {embed.author.name}"
                if embed.title:
                    content += f" {embed.title}"
        for uid, name in USER_MAPPING.items():
            pattern = rf"{re.escape(name)}\s+just\s+posted\s+a\s+new\s+video!"
            if re.search(pattern, content, re.IGNORECASE):
                yesterday_counts[uid] += 1
            elif msg.author.bot and name.lower() in content.lower():
                if any(term in content.lower() for term in ["posted", "new video", "youtu.be", "youtube.com"]):
                    if not re.search(pattern, content, re.IGNORECASE):
                        yesterday_counts[uid] += 1
    mentions_list = []
    completed_list = []
    for uid, name in USER_MAPPING.items():
        count = current_counts[uid]
        required_count = get_daily_required_videos(uid)
        missing = demoted_users.get(str(uid), {}).get("missing", max(0, get_required_videos(uid) - count))
        if count >= required_count and str(uid) not in demoted_users:
            completed_list.append(f"<@{uid}> ({count}/{required_count})")
        else:
            lost_roles = demoted_users.get(str(uid), {}).get("roles", [])
            if lost_roles:
                lost_roles_str = ", ".join(str(r) for r in lost_roles)
                mentions_list.append(
                    f"<@{uid}> ({count}/{required_count}) — You need **{missing}** more videos to restore your roles! (Roles lost: {lost_roles_str})"
                )
            else:
                mentions_list.append(
                    f"<@{uid}> ({count}/{required_count}) — You need **{missing}** more videos today!"
                )
    yesterday_summary = [
        f"<@{uid}>: {yesterday_counts[uid]}/{get_daily_required_videos(uid)}"
        for uid in USER_MAPPING
    ]
    # Fixed to always use the specified static built-in timestamp
    fixed_ts = 1769900400  # Your requested UNIX timestamp for 6 PM EST
    msg = ""
    if mentions_list or completed_list:
        msg += "**YESTERDAY videos posted:**\n"
        msg += "\n".join(mentions_list)
        msg += "\n"
        msg += "\n".join(completed_list)
        msg += "\n\n📊 Yesterday's Uploads\n"
        msg += "\n".join(yesterday_summary)
        msg += f"\n\nTime remaining until next deadline (<t:{fixed_ts}:t>):"
        msg += "\n\n⚠️ These users have been demoted. Upload your missing videos to get your roles back!"
    await channel.send(msg)

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user.name}')
    await recover_demoted_users_from_logs()
    if not check_demotion_loop.is_running():
        check_demotion_loop.start()
    if not track_restoration_loop.is_running():
        track_restoration_loop.start()
    if not reminder_loop.is_running():
        reminder_loop.start()

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if token:
        bot.run(token)
    else:
        logging.error("No DISCORD_BOT_TOKEN found in environment.")
