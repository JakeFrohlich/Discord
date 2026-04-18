import discord
from discord.ext import commands
import json
import os
import datetime

from log_utils import send_mod_log

WARNINGS_FILE = "warnings_data.json"
TIMEOUT_THRESHOLD = 3   # warnings before auto-timeout (10 min)
KICK_THRESHOLD = 5      # warnings before auto-kick


class WarningsCog(commands.Cog):
    """Warning system: ?warn, ?warnings, ?clearwarnings with auto-timeout/kick."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data: dict[str, dict[str, list]] = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(WARNINGS_FILE):
            with open(WARNINGS_FILE, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {}

    def _save_data(self):
        with open(WARNINGS_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def _is_privileged(self, member: discord.Member) -> bool:
        has_owner = discord.utils.get(member.roles, name="Owner") is not None
        return has_owner or member.guild_permissions.administrator

    def _get_warnings(self, guild_id: int, user_id: int) -> list:
        return self.data.get(str(guild_id), {}).get(str(user_id), [])

    @commands.command(name="warn")
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Warn a user. Usage: ?warn @user <reason>"""
        if not self._is_privileged(ctx.author):
            return

        guild_key = str(ctx.guild.id)
        user_key = str(member.id)

        if guild_key not in self.data:
            self.data[guild_key] = {}
        if user_key not in self.data[guild_key]:
            self.data[guild_key][user_key] = []

        entry = {
            "reason": reason,
            "moderator_id": ctx.author.id,
            "moderator_name": str(ctx.author),
            "timestamp": discord.utils.utcnow().isoformat(),
        }
        self.data[guild_key][user_key].append(entry)
        self._save_data()

        total = len(self.data[guild_key][user_key])

        # DM the warned user
        try:
            dm_embed = discord.Embed(
                title="You received a warning",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )
            dm_embed.add_field(name="Server", value=ctx.guild.name, inline=True)
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            dm_embed.add_field(name="Total Warnings", value=str(total), inline=True)
            dm_embed.set_footer(text=f"Warned by {ctx.author}")
            await member.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            pass  # DMs disabled

        # Confirm in channel
        await ctx.send(
            f"**{member}** has been warned. Reason: {reason} — Total warnings: **{total}**",
            delete_after=10,
        )

        await send_mod_log(
            ctx.guild, "WARN", target=member, moderator=ctx.author,
            details=f"Reason: {reason} | Total warnings: {total}"
        )

        await self._check_auto_actions(ctx, member, total)

    async def _check_auto_actions(self, ctx: commands.Context, member: discord.Member, total: int):
        if total == KICK_THRESHOLD:
            # DM before kick so it can still be delivered
            try:
                await member.send(
                    f"You have been kicked from **{ctx.guild.name}** for reaching {KICK_THRESHOLD} warnings."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
            try:
                await member.kick(reason=f"Reached {KICK_THRESHOLD} warnings")
                await ctx.send(f"**{member}** has been kicked for reaching {KICK_THRESHOLD} warnings.", delete_after=10)
                await send_mod_log(ctx.guild, "AUTO_KICK", target=member, details=f"Reached {KICK_THRESHOLD} warnings")
            except discord.Forbidden:
                await ctx.send("I don't have permission to kick that user.", delete_after=5)

        elif total == TIMEOUT_THRESHOLD:
            until = discord.utils.utcnow() + datetime.timedelta(minutes=10)
            try:
                await member.timeout(until, reason=f"Reached {TIMEOUT_THRESHOLD} warnings")
                await ctx.send(
                    f"**{member}** has been timed out for 10 minutes for reaching {TIMEOUT_THRESHOLD} warnings.",
                    delete_after=10,
                )
                await send_mod_log(
                    ctx.guild, "AUTO_TIMEOUT", target=member,
                    details=f"Reached {TIMEOUT_THRESHOLD} warnings — timed out 10 min"
                )
            except discord.Forbidden:
                await ctx.send("I don't have permission to timeout that user.", delete_after=5)

    @commands.command(name="warnings")
    async def warnings(self, ctx: commands.Context, member: discord.Member = None):
        """Show warnings for a user. Usage: ?warnings [@user]"""
        if not self._is_privileged(ctx.author):
            return
        member = member or ctx.author
        entries = self._get_warnings(ctx.guild.id, member.id)

        embed = discord.Embed(
            title=f"Warnings for {member}",
            color=discord.Color.orange() if entries else discord.Color.green(),
        )
        if not entries:
            embed.description = "No warnings on record."
        else:
            for i, w in enumerate(entries, 1):
                embed.add_field(
                    name=f"#{i} — {w['timestamp'][:10]}",
                    value=f"**Reason:** {w['reason']}\n**By:** {w['moderator_name']}",
                    inline=False,
                )
        await ctx.send(embed=embed)

    @commands.command(name="clearwarnings")
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member):
        """Clear all warnings for a user. Usage: ?clearwarnings @user"""
        if not self._is_privileged(ctx.author):
            return

        guild_key = str(ctx.guild.id)
        user_key = str(member.id)

        if guild_key in self.data and user_key in self.data[guild_key]:
            self.data[guild_key].pop(user_key)
            self._save_data()

        await ctx.send(f"Cleared all warnings for **{member}**.", delete_after=10)
        await send_mod_log(
            ctx.guild, "CLEAR_WARNS", target=member, moderator=ctx.author,
            details="All warnings cleared"
        )

    @warn.error
    async def warn_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("User not found.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `?warn @user <reason>`", delete_after=5)

    @clearwarnings.error
    async def clearwarnings_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("User not found.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `?clearwarnings @user`", delete_after=5)
