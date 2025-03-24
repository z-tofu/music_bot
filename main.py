import discord
from discord.ext import commands
from music_player import MusicPlayer
from bot_commands import BotCommands
import dotenv
import os
import signal
import sys
import asyncio

# Load environment variables from .env file
dotenv.load_dotenv()

# Get the token from environment variables
bot_token = os.getenv("DISCORD_BOT_TOKEN")
if not bot_token:
    raise ValueError("Missing DISCORD_BOT_TOKEN environment variable")

# Set up the bot with required intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix="mao!", intents=intents)

# Create a dictionary to store music players for each guild
music_players = {}


# Event for when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        # Global sync for all commands
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands globally.")

        # Remove the guild-specific sync to avoid permission conflicts
    except Exception as e:
        print(f"Error syncing commands: {e}")


# Get or create music player for a guild
def get_music_player(guild):
    guild_id = guild.id
    if guild_id not in music_players:
        music_players[guild_id] = MusicPlayer(bot, guild)
    return music_players[guild_id]


# Initialize the commands handler
commands_handler = BotCommands(bot, get_music_player)

# Add the commands to the bot
commands_handler.setup()


# Graceful shutdown function
async def shutdown(signal_received=None):
    """Handle graceful shutdown of the bot"""
    if signal_received:
        print(f'\nReceived exit signal {signal_received.name}...')
    else:
        print('\nShutting down bot...')

    # Close all voice clients (disconnect from voice channels)
    for guild_id, music_player in music_players.items():
        try:
            if hasattr(music_player, 'cleanup'):
                await music_player.cleanup()
            elif hasattr(music_player, 'voice_client') and music_player.voice_client:
                await music_player.voice_client.disconnect()
        except Exception as e:
            print(f"Error cleaning up music player for guild {guild_id}: {e}")

    # Close the bot
    if not bot.is_closed():
        await bot.close()

    print("Bot has been successfully shut down.")

    # Exit the program
    sys.exit(0)


# Add a command to exit the bot
@bot.command(name="exit", help="Shuts down the bot (owner only)")
@commands.is_owner()
async def exit_command(ctx):
    await ctx.send("Shutting down the bot...")
    await shutdown()


# Register signal handlers for graceful exit
def register_signal_handlers():
    if sys.platform != "win32":  # Unix-like systems
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: asyncio.create_task(shutdown(s)))
    else:  # Windows
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(shutdown(s)))


# Run the bot
if __name__ == "__main__":
    register_signal_handlers()
    print("Bot started. Press Ctrl+C to exit.")
    try:
        bot.run(bot_token)
    except KeyboardInterrupt:
        # This block might not be reached due to how discord.py handles Ctrl+C,
        # but it's here as a fallback
        print("Keyboard interrupt received. Shutting down...")
        # The actual shutdown is handled by the signal handler