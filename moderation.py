import discord
from discord.ext import commands
import re

# Slurs and variations to filter (kept minimal and hashed-out for code readability)
# Each entry is a regex pattern to catch common evasion attempts
SLUR_PATTERNS = [
    # N-word variations
    r"n+[\W_]*[i1!|l]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[e3a]+[\W_]*[r]+",
    r"n+[\W_]*[i1!|l]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[a@]+",
    # F-slur variations
    r"f+[\W_]*[a@4]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[o0]+[\W_]*[t7]+",
    r"f+[\W_]*[a@4]+[\W_]*[gq9]+[\W_]*[gq9]+[\W_]*[o0]+[\W_]*[t7]+[\W_]*[s\$]+",
    r"f+[\W_]*[a@4]+[\W_]*[gq9]+[\W_]*[s\$]*$",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SLUR_PATTERNS]


class ModerationCog(commands.Cog):
    """Filters slurs and offensive language."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.guild_permissions.administrator:
            return

        text = message.content.lower().strip()

        for pattern in COMPILED_PATTERNS:
            if pattern.search(text):
                await message.delete()
                warning = await message.channel.send(
                    f"{message.author.mention}, that language is not allowed here."
                )
                # Auto-delete the warning after 5 seconds
                await warning.delete(delay=5)
                print(f"Deleted message from {message.author} in {message.guild.name}: slur detected")
                return
