import discord
from discord.ext import commands
import re

from log_utils import send_mod_log

# Matches URLs (http/https/www and bare domains like discord.gg/xxx)
LINK_PATTERN = re.compile(
    r"(https?://|www\.|\bdiscord\.gg/)[^\s]+",
    re.IGNORECASE,
)

# Allowed domains — obliveyon.com is permitted
ALLOWED_DOMAINS = [
    "obliveyon.com",
    # GIF providers
    "tenor.com",
    "giphy.com",
    "klipy.com",
    "imgur.com",
    "gfycat.com",
    "redgifs.com",
    "media.discordapp.net",
    "cdn.discordapp.com",
]

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

    def _has_wanderer_role(self, member: discord.Member) -> bool:
        return discord.utils.get(member.roles, name="The Wanderer") is not None

    def _is_privileged(self, member: discord.Member) -> bool:
        has_owner = discord.utils.get(member.roles, name="Owner") is not None
        has_mod = discord.utils.get(member.roles, name="Moderator") is not None
        return has_owner or has_mod or member.guild_permissions.administrator

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self._is_privileged(message.author):
            return

        text = message.content.lower().strip()

        # Slur filter
        for pattern in COMPILED_PATTERNS:
            if pattern.search(text):
                await message.delete()
                warning = await message.channel.send(
                    f"{message.author.mention}, that language is not allowed here."
                )
                await warning.delete(delay=5)
                print(f"Deleted message from {message.author} in {message.guild.name}: slur detected")
                await send_mod_log(
                    message.guild,
                    "SLUR_DELETE",
                    target=message.author,
                    moderator=None,
                    details=f"Channel: #{message.channel.name}",
                )
                return

        # Link filter — only applies to members with The Wanderer role
        # Skip if the message has direct file attachments (uploaded GIFs/images)
        if self._has_wanderer_role(message.author) and not message.attachments:
            links = LINK_PATTERN.findall(message.content)
            if links:
                # Check if all links are from allowed domains
                blocked = False
                for match in re.finditer(r"(https?://|www\.|\bdiscord\.gg/)([^\s]+)", message.content, re.IGNORECASE):
                    full = match.group(0).lower()
                    if not any(domain in full for domain in ALLOWED_DOMAINS):
                        blocked = True
                        break

                if blocked:
                    await message.delete()
                    await message.channel.send(
                        f"Hey {message.author.mention}, we don't allow links in this server to keep everyone safe — no worries though, it happens! 🖤",
                        delete_after=8,
                    )
                    # Log to #bot-dm-logs
                    log_channel = discord.utils.get(message.guild.text_channels, name="bot-dm-logs")
                    if log_channel:
                        await log_channel.send(
                            f"🔗 **Link blocked** — {message.author.mention} (`{message.author}`) "
                            f"in #{message.channel.name}\n"
                            f">>> {message.content[:500]}"
                        )
                    return

    @commands.command(name="purge", hidden=True)
    async def purge(self, ctx: commands.Context, first=None, second: int = None):
        """Delete messages. Usage: ?purge <number> or ?purge @user <number>"""
        has_owner_role = discord.utils.get(ctx.author.roles, name="Owner") is not None
        if not has_owner_role and not ctx.author.guild_permissions.administrator:
            return

        target = None
        amount = None

        if first is None:
            return await ctx.send("Usage: `?purge <number>` or `?purge @user <number>`", delete_after=5)

        try:
            amount = int(first)
        except (ValueError, TypeError):
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
            to_delete = []
            async for msg in ctx.channel.history(limit=None):
                if len(to_delete) >= amount:
                    break
                if msg.author == target:
                    to_delete.append(msg)
            count = 0
            for msg in to_delete:
                await msg.delete()
                count += 1
            await ctx.author.send(f"Deleted **{count}** messages from {target.name} in #{ctx.channel.name}.")
            await send_mod_log(
                ctx.guild, "PURGE", target=target, moderator=ctx.author,
                details=f"Deleted {count} messages from {target} in #{ctx.channel.name}"
            )
        else:
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.author.send(f"Deleted **{len(deleted)}** messages in #{ctx.channel.name}.")
            await send_mod_log(
                ctx.guild, "PURGE", target=None, moderator=ctx.author,
                details=f"Bulk deleted {len(deleted)} messages in #{ctx.channel.name}"
            )

    @purge.error
    async def purge_error(self, ctx, error):
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            await ctx.send("Usage: `?purge <number>` or `?purge @user <number>`", delete_after=5)
