import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv
from music import MusicCog
from invites import InviteTrackerCog
from moderation import ModerationCog

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.invites = True
intents.voice_states = True

ALLOWED_CHANNEL = "bot-commands"

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.check
async def restrict_to_bot_commands(ctx):
    """Only allow commands in #bot-commands."""
    if ctx.channel.name == ALLOWED_CHANNEL:
        return True
    await ctx.send(f"Commands can only be used in #{ALLOWED_CHANNEL}.", delete_after=5)
    return False


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


@bot.command(name="commands")
async def commands_list(ctx):
    """Show all available bot commands."""
    embed = discord.Embed(
        title="Bot Commands",
        description="All commands must be used in #bot-commands",
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.add_field(
        name="Music",
        value=(
            "**!play <song>** — Play a song from YouTube\n"
            "**!skip** — Skip the current song\n"
            "**!queue** — Show the song queue\n"
            "**!pause** — Pause playback\n"
            "**!resume** — Resume playback\n"
            "**!stop** — Stop and clear the queue\n"
            "**!join** — Join your voice channel\n"
            "**!leave** — Leave the voice channel"
        ),
        inline=False,
    )
    embed.add_field(
        name="Invites",
        value=(
            "**!invites** — Check your invite count\n"
            "**!invites @user** — Check someone else's invites\n"
            "\n*Invite 5 people to earn the **Pink Nametag** role!*"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)


async def main():
    async with bot:
        await bot.add_cog(MusicCog(bot))
        await bot.add_cog(InviteTrackerCog(bot))
        await bot.add_cog(ModerationCog(bot))
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
