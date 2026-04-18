import discord
from discord.ext import commands
import asyncio
import random
import yt_dlp

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": "cookies.txt",
    "extractor_args": {"youtube": {"player_client": ["tv"]}},
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class MusicCog(commands.Cog):
    """Music playback commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> list of (title, url, requester_name)
        self.queues: dict[int, list[tuple[str, str, str]]] = {}
        # guild_id -> (title, url, requester_name) | None
        self.current: dict[int, tuple[str, str, str] | None] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Leave voice channel if the bot is alone."""
        if member.bot:
            return

        if before.channel is None:
            return

        guild = member.guild
        if not guild.voice_client or guild.voice_client.channel != before.channel:
            return

        real_members = [m for m in before.channel.members if not m.bot]
        if len(real_members) == 0:
            self._get_queue(guild.id).clear()
            self.current[guild.id] = None
            if guild.voice_client.is_playing():
                guild.voice_client.stop()
            await guild.voice_client.disconnect()

    def _get_queue(self, guild_id: int) -> list:
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    async def _search(self, query: str) -> tuple[str, str] | None:
        """Search YouTube and return (title, stream_url)."""
        loop = asyncio.get_running_loop()
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

        def extract():
            info = ytdl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            url = info.get("url")
            if not url:
                formats = info.get("formats", [])
                for f in reversed(formats):
                    if f.get("url"):
                        url = f["url"]
                        break
            return info["title"], url

        try:
            return await loop.run_in_executor(None, extract)
        except Exception as e:
            print(f"yt-dlp error: {e}")
            return None

    def _play_next(self, guild: discord.Guild):
        """Play the next song in the queue."""
        queue = self._get_queue(guild.id)
        if not queue:
            self.current[guild.id] = None
            return

        title, url, requester = queue.pop(0)
        self.current[guild.id] = (title, url, requester)
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)

        def after(error):
            if error:
                print(f"Playback error: {error}")
            self._play_next(guild)

        if guild.voice_client:
            guild.voice_client.play(source, after=after)

    @commands.command(name="join")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def join(self, ctx: commands.Context):
        """Join your voice channel."""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel.")

        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"Joined **{channel.name}**")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song from YouTube. Usage: ?play <song name or URL>"""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel.")

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        await ctx.send(f"Searching for **{query}**...")
        result = await self._search(query)
        if not result:
            return await ctx.send("Could not find that track.")

        title, url = result
        requester = ctx.author.display_name
        vc = ctx.voice_client

        if vc.is_playing() or vc.is_paused():
            self._get_queue(ctx.guild.id).append((title, url, requester))
            await ctx.send(f"Queued: **{title}** (requested by {requester})")
        else:
            self.current[ctx.guild.id] = (title, url, requester)
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: self._play_next(ctx.guild))
            await ctx.send(f"Now playing: **{title}** (requested by {requester})")

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        """Skip the current song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        """Show the current queue."""
        q = self._get_queue(ctx.guild.id)
        if not q:
            return await ctx.send("The queue is empty.")

        lines = [f"**{i+1}.** {title} — *{req}*" for i, (title, _, req) in enumerate(q[:10])]
        if len(q) > 10:
            lines.append(f"...and {len(q) - 10} more")
        await ctx.send("\n".join(lines))

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Show the currently playing song."""
        entry = self.current.get(ctx.guild.id)
        if not entry:
            return await ctx.send("Nothing is currently playing.")
        title, _, requester = entry
        await ctx.send(f"Now playing: **{title}** (requested by {requester})")

    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue."""
        q = self._get_queue(ctx.guild.id)
        if len(q) < 2:
            return await ctx.send("Not enough songs in the queue to shuffle.")
        random.shuffle(q)
        await ctx.send("Queue shuffled.")

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, position: int):
        """Remove a song from the queue by position. Usage: ?remove <number>"""
        q = self._get_queue(ctx.guild.id)
        if not q:
            return await ctx.send("The queue is empty.")
        if position < 1 or position > len(q):
            return await ctx.send(f"Invalid position. Queue has {len(q)} song(s).")
        title, _, _ = q.pop(position - 1)
        await ctx.send(f"Removed **{title}** from the queue.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause playback."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Paused.")
        else:
            await ctx.send("Nothing is playing.")

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        """Resume playback."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Resumed.")
        else:
            await ctx.send("Nothing is paused.")

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue."""
        self._get_queue(ctx.guild.id).clear()
        self.current[ctx.guild.id] = None
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send("Stopped and cleared the queue.")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def leave(self, ctx: commands.Context):
        """Leave the voice channel."""
        if not ctx.voice_client:
            return await ctx.send("I'm not in a voice channel.")

        is_admin = ctx.author.guild_permissions.administrator
        has_owner_role = discord.utils.get(ctx.author.roles, name="Owner") is not None
        in_same_vc = (
            ctx.author.voice
            and ctx.author.voice.channel == ctx.voice_client.channel
        )

        if not (in_same_vc or is_admin or has_owner_role):
            return await ctx.send(
                "You must be in the same voice channel to use this.", delete_after=5
            )

        self._get_queue(ctx.guild.id).clear()
        self.current[ctx.guild.id] = None
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected.")

    @join.error
    @leave.error
    async def cooldown_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"Slow down! Try again in {error.retry_after:.0f}s.",
                delete_after=5,
            )

    @remove.error
    async def remove_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Usage: `?remove <number>`", delete_after=5)
