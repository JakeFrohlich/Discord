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

ALLOWED_CHANNELS = ["bot-commands", "ticket-logs"]

bot = commands.Bot(command_prefix="?", intents=intents)


@bot.check
async def restrict_to_allowed_channels(ctx):
    """Only allow commands in approved channels."""
    if ctx.command and ctx.command.name == "purge":
        return True
    if ctx.channel.name in ALLOWED_CHANNELS:
        return True
    await ctx.send("Commands can only be used in #bot-commands.", delete_after=5)
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
        description="Prefix: **?** — All commands must be used in #bot-commands",
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.add_field(
        name="Music",
        value=(
            "**?play <song>** — Play a song from YouTube\n"
            "**?skip** — Skip the current song\n"
            "**?queue** — Show the song queue\n"
            "**?pause** — Pause playback\n"
            "**?resume** — Resume playback\n"
            "**?stop** — Stop and clear the queue\n"
            "**?join** — Join your voice channel\n"
            "**?leave** — Leave the voice channel"
        ),
        inline=False,
    )
    embed.add_field(
        name="Moderation (Admin only)",
        value="**?purge <number>** — Delete messages (works in any channel)",
        inline=False,
    )
    embed.add_field(
        name="Invites",
        value=(
            "**?invites** — Check your invite count\n"
            "**?invites @user** — Check someone else's invites\n"
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
