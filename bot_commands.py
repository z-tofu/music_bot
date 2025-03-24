import discord
from discord import app_commands
from discord.ext import commands
import asyncio


class BotCommands:
    def __init__(self, bot, get_music_player_func):
        self.bot = bot
        self.get_music_player = get_music_player_func

    def setup(self):
        """Register all commands with the bot"""
        self._setup_music_commands()

    def _setup_music_commands(self):
        """Set up music related commands as slash commands"""

        @self.bot.tree.command(name="join", description="Join your voice channel")
        async def join(interaction: discord.Interaction):
            """Join a voice channel"""
            # Defer the response as connecting might take time
            await interaction.response.defer(ephemeral=False)

            # Get the member's voice channel
            member = interaction.user
            if not member.voice:
                await interaction.followup.send("You are not in a voice channel.")
                return

            voice_channel = member.voice.channel

            # Check if bot is already in a voice channel in this guild
            voice_client = interaction.guild.voice_client
            if voice_client:
                if voice_client.channel.id == voice_channel.id:
                    await interaction.followup.send("I'm already in your voice channel!")
                    return
                else:
                    await voice_client.disconnect()

            # Connect to the voice channel
            try:
                await voice_channel.connect()
                await interaction.followup.send("Mao has joined your great empire!")
            except Exception as e:
                await interaction.followup.send(f"Error joining voice channel: {str(e)}")

        @self.bot.tree.command(name="leave", description="Leave the voice channel")
        async def leave(interaction: discord.Interaction):
            """Leave the voice channel"""
            voice_client = interaction.guild.voice_client
            if voice_client:
                player = self.get_music_player(interaction.guild)
                player.clear_queue()
                await voice_client.disconnect()
                await interaction.response.send_message("Mao was disappointed in your channel")
            else:
                await interaction.response.send_message("I'm not connected to a voice channel.")

        @self.bot.tree.command(name="play", description="Play a song from YouTube, Spotify or search term")
        @app_commands.describe(query="The song URL, playlist URL or search term")
        async def play(interaction: discord.Interaction, query: str):
            """Play a song, playlist or search result"""
            # Defer the response as processing might take time
            await interaction.response.defer(ephemeral=False)

            # Check if user is in a voice channel
            member = interaction.user
            if not member.voice:
                await interaction.followup.send("You need to be in a voice channel to play music.")
                return

            voice_channel = member.voice.channel

            # Connect to voice channel if not already connected
            voice_client = interaction.guild.voice_client
            if not voice_client:
                try:
                    voice_client = await voice_channel.connect()
                except Exception as e:
                    await interaction.followup.send(f"Error connecting to voice channel: {str(e)}")
                    return

            # Get music player and play the song
            player = self.get_music_player(interaction.guild)
            await player.play(interaction, query)

        @self.bot.tree.command(name="search", description="Search for a song on YouTube")
        @app_commands.describe(query="The search term for the song")
        async def search(interaction: discord.Interaction, query: str):
            """Search for a song and let the user choose from results"""
            # Defer the response as searching might take time
            await interaction.response.defer(ephemeral=False)

            player = self.get_music_player(interaction.guild)
            results = await player.search_song(query)

            if not results:
                await interaction.followup.send("No results found.")
                return

            # Create a list of results with numbers
            result_message = "**Search Results:**\n"
            for i, result in enumerate(results, 1):
                result_message += f"{i}. {result['title']}\n"
            result_message += "\nType the number of the song you want to play."

            # Send the results
            await interaction.followup.send(result_message)

            # Wait for user's response
            try:
                # Create a check function to verify the response is from the original user and in the same channel
                def check(msg):
                    return (
                            msg.author.id == interaction.user.id
                            and msg.channel.id == interaction.channel.id
                            and msg.content.isdigit()
                            and 1 <= int(msg.content) <= len(results)
                    )

                # Wait for response
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                choice = int(msg.content)
                selected = results[choice - 1]

                # Send a new message to indicate processing
                process_msg = await interaction.channel.send(f"Processing your selection: {selected['title']}...")

                # Check if user is in a voice channel
                if not interaction.user.voice:
                    await interaction.channel.send("You need to be in a voice channel to play music.")
                    return

                voice_channel = interaction.user.voice.channel

                # Connect to voice channel if not already connected
                voice_client = interaction.guild.voice_client
                if not voice_client:
                    try:
                        voice_client = await voice_channel.connect()
                    except Exception as e:
                        await interaction.channel.send(f"Error connecting to voice channel: {str(e)}")
                        return

                # Play the selected song using the player.play method which now properly processes URLs
                player.last_interaction = interaction  # Store the original interaction

                # Create a DummyInteraction that has a channel send method
                class DummyFollowup:
                    def __init__(self, channel):
                        self.channel = channel

                    async def send(self, content):
                        return await self.channel.send(content)

                class DummyInteraction:
                    def __init__(self, interaction, channel):
                        self.guild = interaction.guild
                        self.user = interaction.user
                        self.channel = channel
                        self.followup = DummyFollowup(channel)

                dummy = DummyInteraction(interaction, interaction.channel)

                # Use the video URL from the search results
                await player.play(dummy, selected['url'])

            except asyncio.TimeoutError:
                await interaction.channel.send("Selection timed out.")
            except Exception as e:
                await interaction.channel.send(f"Error processing selection: {str(e)}")

        @self.bot.tree.command(name="stop", description="Stop playing and clear the queue")
        async def stop(interaction: discord.Interaction):
            """Stop the current song and clear the queue"""
            voice_client = interaction.guild.voice_client
            if voice_client:
                player = self.get_music_player(interaction.guild)
                player.stop()
                await interaction.response.send_message("Stopped playing music.")
            else:
                await interaction.response.send_message("I'm not connected to a voice channel.")

        @self.bot.tree.command(name="pause", description="Pause the current song")
        async def pause(interaction: discord.Interaction):
            """Pause the current song"""
            voice_client = interaction.guild.voice_client
            if voice_client:
                player = self.get_music_player(interaction.guild)
                if player.pause():
                    await interaction.response.send_message("Music paused.")
                else:
                    await interaction.response.send_message("No music is currently playing.")
            else:
                await interaction.response.send_message("I'm not connected to a voice channel.")

        @self.bot.tree.command(name="resume", description="Resume the paused song")
        async def resume(interaction: discord.Interaction):
            """Resume the paused song"""
            voice_client = interaction.guild.voice_client
            if voice_client:
                player = self.get_music_player(interaction.guild)
                if player.resume():
                    await interaction.response.send_message("Music resumed.")
                else:
                    await interaction.response.send_message("No music is currently paused.")
            else:
                await interaction.response.send_message("I'm not connected to a voice channel.")

        @self.bot.tree.command(name="queue", description="Add a song to the queue")
        @app_commands.describe(query="The song URL or search term")
        async def queue_song(interaction: discord.Interaction, query: str):
            """Add a song to the queue"""
            # Defer the response as processing might take time
            await interaction.response.defer(ephemeral=False)

            if not interaction.guild.voice_client:
                await interaction.followup.send("I need to join a voice channel first! Use /join")
                return

            # Check if it's a playlist
            if ("youtube.com/playlist" in query or "youtube.com/watch" in query and "list=" in query or
                    "spotify.com/playlist/" in query or "spotify.com/album/" in query):
                player = self.get_music_player(interaction.guild)
                await player.process_playlist(interaction, query)
                return

            player = self.get_music_player(interaction.guild)
            title = await player.add_to_queue(query)
            await interaction.followup.send(f"Added to queue: {title}")

        @self.bot.tree.command(name="show_queue", description="Show the current song queue")
        async def show_queue(interaction: discord.Interaction):
            """Show the current song queue"""
            player = self.get_music_player(interaction.guild)
            queue_list = player.get_queue_info()
            if queue_list:
                queue_text = "\n".join([f"{i + 1}. {title}" for i, title in enumerate(queue_list)])
                await interaction.response.send_message(f"**Current Queue:**\n{queue_text}")
            else:
                await interaction.response.send_message("Queue is empty.")

        @self.bot.tree.command(name="skip", description="Skip to the next song in the queue")
        async def skip(interaction: discord.Interaction):
            """Skip to the next song in the queue"""
            voice_client = interaction.guild.voice_client
            if not voice_client:
                await interaction.response.send_message("I'm not connected to a voice channel.")
                return

            player = self.get_music_player(interaction.guild)
            if await player.skip(interaction):
                await interaction.response.send_message("Skipped to next song.")
            else:
                await interaction.response.send_message("No more songs in queue.")

        @self.bot.tree.command(name="shuffle", description="Shuffle the current queue")
        async def shuffle(interaction: discord.Interaction):
            """Shuffle the current queue"""
            player = self.get_music_player(interaction.guild)
            if player.shuffle_queue():
                await interaction.response.send_message("Queue has been shuffled.")
            else:
                await interaction.response.send_message("Queue is empty or contains only one song.")

        @self.bot.tree.command(name="playlist", description="Load a YouTube or Spotify playlist")
        @app_commands.describe(url="The URL of the YouTube or Spotify playlist")
        async def playlist(interaction: discord.Interaction, url: str):
            """Load and play a playlist from YouTube or Spotify"""
            # Defer the response as processing might take time
            await interaction.response.defer(ephemeral=False)

            # Check if user is in a voice channel
            member = interaction.user
            if not member.voice:
                await interaction.followup.send("You need to be in a voice channel to play music.")
                return

            voice_channel = member.voice.channel

            # Connect to voice channel if not already connected
            voice_client = interaction.guild.voice_client
            if not voice_client:
                try:
                    voice_client = await voice_channel.connect()
                except Exception as e:
                    await interaction.followup.send(f"Error connecting to voice channel: {str(e)}")
                    return

            # Verify it's a playlist URL
            if not any(x in url for x in
                       ["youtube.com/playlist", "youtube.com/watch?v=", "spotify.com/playlist/", "spotify.com/album/"]):
                await interaction.followup.send(
                    "That doesn't look like a valid playlist URL. Please provide a YouTube or Spotify playlist link.")
                return

            # Process the playlist
            player = self.get_music_player(interaction.guild)
            await player.process_playlist(interaction, url)