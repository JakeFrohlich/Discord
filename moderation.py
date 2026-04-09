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

    @commands.command(name="purge", hidden=True)
    async def purge(self, ctx: commands.Context, first=None, second: int = None):
        """Delete messages. Usage: ?purge <number> or ?purge @user <number>"""
        has_owner_role = discord.utils.get(ctx.author.roles, name="Owner") is not None
        if not has_owner_role and not ctx.author.guild_permissions.administrator:
            return

        target = None
        amount = None

        # Parse arguments: ?purge 10 or ?purge @user 10
        if first is None:
            return await ctx.send("Usage: `?purge <number>` or `?purge @user <number>`", delete_after=5)

        try:
            amount = int(first)
        except (ValueError, TypeError):
            # first arg is a user mention
            converter = commands.MemberConverter()
            try:
                target = await converter.convert(ctx, first)
            except commands.MemberNotFound:
                return await ctx.send("User not found.", delete_after=5)
            amount = second

        if amount is None or amount < 1 or amount > 500:
            return await ctx.send("Please specify a number between 1 and 500.", delete_after=5)

        await ctx.message.delete()

        if target:
            count = 0
            async for msg in ctx.channel.history(limit=1000):
                if count >= amount:
                    break
                if msg.author == target:
                    await msg.delete()
                    count += 1
            await ctx.author.send(f"Deleted **{count}** messages from {target.name} in #{ctx.channel.name}.")
        else:
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.author.send(f"Deleted **{len(deleted)}** messages in #{ctx.channel.name}.")

    @purge.error
    async def purge_error(self, ctx, error):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send("Usage: `?purge <number>` or `?purge @user <number>`", delete_after=5)
