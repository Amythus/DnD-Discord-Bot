import os
import asyncio
import discord
import sys
from discord.ext import commands
from database.connection import init_database
from config.settings import settings

# Initialize the Bot client
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🎲 Logged in as {bot.user.name} (ID: {bot.user.id})")

async def load_extensions():
    # Sweep your directory and dynamically load your cog segments
    # Path uses standard dot notation relative to the application workspace: cogs.filename
    cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
    
    for filename in os.listdir(cogs_dir):
        if filename.endswith("_cog.py"):
            cog_name = f"cogs.{filename[:-3]}"
            await bot.load_extension(cog_name)
            print(f"✅ Loaded Cog: {cog_name}")

async def main():
    # 1. Boot up the MongoDB & Beanie mapping connection layer
    try:
        db_success = await init_database(settings.mongo_uri)
        if not db_success:
            raise ConnectionError("MongoDB initialization returned False.")
    except Exception as e:
        print(f"❌ CRITICAL BOOT FAILURE: {e}", file=sys.stderr)
        return
    
    # 2. Register all game loop cogs
    await load_extensions()
    
    # 3. Connect to the Discord Gateway
    try:
        await bot.start(settings.discord_bot_token)
    except discord.LoginFailure:
        print("❌ CRITICAL AUTHENTICATION FAILURE: Provided DISCORD_BOT_TOKEN is invalid.", file=sys.stderr)
    except Exception as e:
        print(f"❌ CRITICAL CONNECTIVITY CRASH during bot initialization: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutdown signal intercepted. Closing all network connections cleanly.")
