import discord
from discord.ext import commands
import json
import os

INVITE_DATA_FILE = "invite_data.json"
ROLE_NAME = "Pink Nametag"
REQUIRED_INVITES = 5


class InviteTrackerCog(commands.Cog):
    """Tracks invites and assigns a role when a user reaches 5 successful invites."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> {invite_code: uses}
        self.invite_cache: dict[int, dict[str, int]] = {}
        # guild_id -> {inviter_id: count}
        self.invite_counts: dict[str, dict[str, int]] = {}
        self._load_data()

    def _load_data(self):
        if os.path.exists(INVITE_DATA_FILE):
            with open(INVITE_DATA_FILE, "r") as f:
                self.invite_counts = json.load(f)
        else:
            self.invite_counts = {}

    def _save_data(self):
        with open(INVITE_DATA_FILE, "w") as f:
            json.dump(self.invite_counts, f, indent=2)

    @commands.Cog.listener()
    async def on_ready(self):
        """Cache all guild invites on startup."""
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
            except discord.Forbidden:
                print(f"Missing permissions to fetch invites in {guild.name}")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Update cache when a new invite is created."""
        guild_id = invite.guild.id
        if guild_id not in self.invite_cache:
            self.invite_cache[guild_id] = {}
        self.invite_cache[guild_id][invite.code] = invite.uses

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Remove invite from cache when deleted."""
        guild_id = invite.guild.id
        if guild_id in self.invite_cache:
            self.invite_cache[guild_id].pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Detect which invite was used and credit the inviter."""
        guild = member.guild
        guild_id = guild.id
        guild_key = str(guild_id)

        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return

        old_cache = self.invite_cache.get(guild_id, {})
        inviter = None

        for invite in current_invites:
            old_uses = old_cache.get(invite.code, 0)
            if invite.uses > old_uses and invite.inviter:
                inviter = invite.inviter
                break

        # Update cache
        self.invite_cache[guild_id] = {inv.code: inv.uses for inv in current_invites}

        if inviter is None or inviter.bot:
            return

        # Update invite count
        inviter_key = str(inviter.id)
        if guild_key not in self.invite_counts:
            self.invite_counts[guild_key] = {}
        current = self.invite_counts[guild_key].get(inviter_key, 0) + 1
        self.invite_counts[guild_key][inviter_key] = current
        self._save_data()

        print(f"{inviter.name} now has {current} invite(s) in {guild.name}")

        # Check if they hit the threshold
        if current >= REQUIRED_INVITES:
            await self._assign_role(guild, inviter)

    async def _assign_role(self, guild: discord.Guild, user: discord.User):
        """Assign the Pink Nametag role to a user."""
        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if role is None:
            try:
                role = await guild.create_role(
                    name=ROLE_NAME,
                    color=discord.Color.from_rgb(255, 105, 180),
                    reason="Auto-created for invite tracker",
                )
                print(f"Created role '{ROLE_NAME}' in {guild.name}")
            except discord.Forbidden:
                print(f"Missing permissions to create role in {guild.name}")
                return

        member = guild.get_member(user.id)
        if member is None:
            return

        if role not in member.roles:
            try:
                await member.add_roles(role, reason=f"Reached {REQUIRED_INVITES} invites")
                print(f"Assigned '{ROLE_NAME}' to {member.name}")

                # Try to notify in system channel
                channel = guild.system_channel
                if channel:
                    await channel.send(
                        f"Congrats {member.mention}! You've invited {REQUIRED_INVITES} "
                        f"people and earned the **{ROLE_NAME}** role!"
                    )
            except discord.Forbidden:
                print(f"Missing permissions to assign role to {member.name}")

    @commands.command(name="invites")
    async def check_invites(self, ctx: commands.Context, member: discord.Member = None):
        """Check how many invites a user has. Usage: !invites [@user]"""
        member = member or ctx.author
        guild_key = str(ctx.guild.id)
        member_key = str(member.id)
        count = self.invite_counts.get(guild_key, {}).get(member_key, 0)
        remaining = max(0, REQUIRED_INVITES - count)

        embed = discord.Embed(
            title="Invite Tracker",
            color=discord.Color.from_rgb(255, 105, 180),
        )
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Invites", value=str(count), inline=True)

        if remaining > 0:
            embed.add_field(
                name="Until Pink Nametag",
                value=f"{remaining} more invite(s) needed",
                inline=False,
            )
        else:
            embed.add_field(name="Status", value="Earned Pink Nametag!", inline=False)

        await ctx.send(embed=embed)
