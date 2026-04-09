import discord
from discord.ext import commands
import asyncio
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
        # guild_id -> list of (title, url)
        self.queues: dict[int, list[tuple[str, str]]] = {}

    def _get_queue(self, guild_id: int) -> list:
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    async def _search(self, query: str) -> tuple[str, str] | None:
        """Search YouTube and return (title, stream_url)."""
        loop = asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

        def extract():
            info = ytdl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            # Try to get a direct URL, fall back to formats list
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
            return

        title, url = queue.pop(0)
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
        """Play a song from YouTube. Usage: !play <song name or URL>"""
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel.")

        # Auto-join if not connected
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        await ctx.send(f"Searching for **{query}**...")
        result = await self._search(query)
        if not result:
            return await ctx.send("Could not find that track.")

        title, url = result
        vc = ctx.voice_client

        if vc.is_playing() or vc.is_paused():
            self._get_queue(ctx.guild.id).append((title, url))
            await ctx.send(f"Queued: **{title}**")
        else:
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: self._play_next(ctx.guild))
            await ctx.send(f"Now playing: **{title}**")

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

        lines = [f"**{i+1}.** {title}" for i, (title, _) in enumerate(q[:10])]
        if len(q) > 10:
            lines.append(f"...and {len(q) - 10} more")
        await ctx.send("\n".join(lines))

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
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send("Stopped and cleared the queue.")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def leave(self, ctx: commands.Context):
        """Leave the voice channel."""
        if ctx.voice_client:
            self._get_queue(ctx.guild.id).clear()
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected.")
        else:
            await ctx.send("I'm not in a voice channel.")

    @join.error
    @leave.error
    async def cooldown_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"Slow down! Try again in {error.retry_after:.0f}s.",
                delete_after=5,
            )
