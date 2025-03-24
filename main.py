import discord
from discord.ext import commands
from music_player import MusicPlayer
from bot_commands import BotCommands
import dotenv
import os

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

# Run the bot
if __name__ == "__main__":
    bot.run(bot_token)  # Use the token from environment variables