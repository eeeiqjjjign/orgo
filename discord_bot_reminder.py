import discord
from discord.ext import commands, tasks
import os
import logging
from datetime import datetime, timedelta, timezone
import re

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
REMINDER_USERS = [1086571236160708709, 1444845857701630094, 1210942252264857673, 1458104862834167824]

STAFF_ROLES = [
    1417970527250677821,
    1417986455296278538,
    1417959557719654550,
    1417968485031608443,
    1427419553029423324
]

LEADERBOARD_CHANNELS = [1417960723363008722, 1417961665902940332]
REMINDER_INTERVAL_MINS = 60

def is_owner(ctx):
    return ctx.author.id == 608461552034643992

@tasks.loop(minutes=60)
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
        await ctx.send(f"✅ Added {user.mention} to the reminder list.")
    else:
        await ctx.send(f"ℹ️ {user.mention} is already in the list.")

@bot.command()
@commands.check(is_owner)
async def removeuser(ctx, user: discord.User):
    global REMINDER_USERS
    if user.id in REMINDER_USERS:
        REMINDER_USERS.remove(user.id)
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

@bot.command()
@commands.check(is_owner)
async def save(ctx):
    source_channel = bot.get_channel(SOURCE_CHANNEL_ID)
    if not source_channel:
        try:
            source_channel = await bot.fetch_channel(SOURCE_CHANNEL_ID)
        except:
            await ctx.send(f"Error: Could not find source channel with ID {SOURCE_CHANNEL_ID}")
            return

    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    if not log_channel:
        try:
            log_channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except:
            await ctx.send(f"Error: Could not find log channel with ID {LOG_CHANNEL_ID}")
            return

    await log_channel.send(f"🚀 Starting backup for channel: **#{source_channel.name}** ({source_channel.id})")

    messages = []
    count = 0

    try:
        async for msg in source_channel.history(limit=None, oldest_first=True):
            content = msg.content if msg.content else "[No text content]"
            if msg.embeds:
                for embed in msg.embeds:
                    parts = []
                    if embed.title: parts.append(f"Title: {embed.title}")
                    if embed.description: parts.append(f"Desc: {embed.description}")
                    for field in embed.fields:
                        parts.append(f"{field.name}: {field.value}")
                    if parts:
                        content += " [Embed: " + " | ".join(parts) + "]"
            author_name = msg.author.name
            if msg.webhook_id:
                author_name = f"[Webhook] {author_name}"
            messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {author_name}: {content}")
            count += 1
            if count % 1000 == 0:
                try:
                    await log_channel.send(f"⏳ Progress: **{count}** messages fetched...")
                except discord.errors.HTTPException as e:
                    if e.status == 429:
                        await asyncio.sleep(e.retry_after if hasattr(e, 'retry_after') else 10)
                        await log_channel.send(f"⏳ Progress: **{count}** messages fetched...")
                await asyncio.sleep(0.05)

        await log_channel.send(f"✅ Finished fetching all **{count}** messages. Generating file...")

        filename = f"messages_{source_channel.id}.txt"
        with open(filename, "w", encoding='utf-8') as f:
            f.write('\n'.join(messages))

        if len(messages) > 0:
            try:
                await log_channel.send(content=f"📦 Backup complete for **#{source_channel.name}**", file=discord.File(filename))
                await ctx.send(f"Done! Check <#{LOG_CHANNEL_ID}> for the file.")
            except Exception as e:
                await log_channel.send(f"⚠️ File too large to upload! Saved locally as `{filename}`.")
                await ctx.send(f"Done! File too large, saved locally.")
        else:
            await log_channel.send("No messages found.")
            await ctx.send("No messages found.")

    except discord.errors.HTTPException as e:
        if e.status == 429:
            await ctx.send("Critical Rate Limit. Try again later.")
        else:
            raise e

@bot.command()
@commands.check(is_owner)
async def log_uploads(ctx):
    source_channel = bot.get_channel(SOURCE_CHANNEL_ID)
    if not source_channel:
        try: source_channel = await bot.fetch_channel(SOURCE_CHANNEL_ID)
        except: return
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        try: log_channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except: return

    await ctx.send("⏳ Fetching uploads...")
    two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
    user_uploads = {}

    try:
        async for msg in source_channel.history(limit=None, after=two_weeks_ago):
            match = re.search(r"New video by\s+(.+)", msg.content, re.IGNORECASE)
            if match:
                uploader = re.sub(r'http[s]?://\S+', '', match.group(1)).strip()
                if uploader:
                    date_str = msg.created_at.strftime('%B %-d')
                    if uploader not in user_uploads: user_uploads[uploader] = []
                    user_uploads[uploader].append(date_str)

        if user_uploads:
            lines = [f"- **{u}** ({', '.join(d)})" for u, d in user_uploads.items()]
            report = "📋 **Uploads:**\n" + "\n".join(lines)
            if len(report) > 2000:
                for i in range(0, len(report), 1900): await log_channel.send(report[i:i+1900])
            else: await log_channel.send(report)
        else: await ctx.send("No uploads found.")
    except Exception as e: await ctx.send(f"Error: {e}")

@bot.command()
@commands.check(is_owner)
async def leaderboard(ctx, days: int = 7):
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not leaderboard_channel:
        try: leaderboard_channel = await bot.fetch_channel(LEADERBOARD_CHANNEL_ID)
        except: return
    await ctx.send(f"⏳ Generating leaderboard ({days} days)...")
    staff_members = set()
    for guild in bot.guilds:
        for r_id in STAFF_ROLES:
            role = guild.get_role(r_id)
            if role:
                for m in role.members: staff_members.add(m)
    if not staff_members: return
    stats = {m.id: {'messages': 0, 'thanks': 0, 'links': 0, 'member': m} for m in staff_members}
    since = datetime.now(timezone.utc) - timedelta(days=days)
    for cid in LEADERBOARD_CHANNELS:
        ch = bot.get_channel(cid) or await bot.fetch_channel(cid)
        if ch:
            async for msg in ch.history(limit=None, after=since):
                if msg.author.id in stats:
                    stats[msg.author.id]['messages'] += 1
                    if "here" in msg.content.lower() and "discord.com/channels/" in msg.content.lower():
                        stats[msg.author.id]['links'] += 1
                content_lower = msg.content.lower()
                if any(k in content_lower for k in ["thanks", "thank you", "ty ", "ty!", "tysm"]):
                    for u in msg.mentions:
                        if u.id in stats: stats[u.id]['thanks'] += 1
                    if msg.reference and msg.reference.resolved and isinstance(msg.reference.resolved, discord.Message):
                        if msg.reference.resolved.author.id in stats:
                            stats[msg.reference.resolved.author.id]['thanks'] += 1
    for uid in stats:
        stats[uid]['staff_score'] = (stats[uid]['thanks'] * 5) + (stats[uid]['links'] * 10)
        stats[uid]['activity_score'] = stats[uid]['messages']
    s_best = sorted(stats.values(), key=lambda x: x['staff_score'], reverse=True)
    report = f"🏆 **LEADERBOARD**\n\n✨ **BEST STAFF**\n" + "\n".join([f"{i+1}. {u['member'].mention} — **{u['staff_score']}**" for i, u in enumerate(s_best) if u['staff_score'] > 0])
    await leaderboard_channel.send(report[:2000])

@bot.command()
@commands.check(is_owner)
async def track_user(ctx, user_id: int = 1332944514322792518, log_channel_id: int = 1424442417381380106):
    log_channel = bot.get_channel(log_channel_id) or await bot.fetch_channel(log_channel_id)
    await ctx.send(f"⏳ Tracking `{user_id}`...")
    user_messages = []
    for channel in ctx.guild.text_channels:
        try:
            async for msg in channel.history(limit=1000):
                if msg.author.id == user_id:
                    user_messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] #{channel.name}: {msg.content or '[Embed/Media]'}")
        except: continue
    if user_messages:
        filename = f"track_{user_id}.txt"
        with open(filename, "w", encoding='utf-8') as f: f.write('\n'.join(user_messages))
        await log_channel.send(content=f"👤 Track Report for `{user_id}`", file=discord.File(filename))
        await ctx.send("✅ Done.")
    else: await ctx.send("No messages found.")

token = os.environ.get('DISCORD_BOT_TOKEN')
if token: bot.run(token)
else: print("Token not set.")
