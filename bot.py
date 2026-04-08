import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv
from music import MusicCog
from invites import InviteTrackerCog

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.invites = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


async def main():
    async with bot:
        await bot.add_cog(MusicCog(bot))
        await bot.add_cog(InviteTrackerCog(bot))
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
