import dotenv
import discord
import yt_dlp
import random
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import os
import asyncio
import concurrent.futures
from functools import partial

dotenv.load_dotenv()

client = os.getenv("SPOTIFY_CLIENT")
secret = os.getenv("SPOTIFY_SECRET")
ffmpeg = os.getenv("FFMPEG_PATH")


class MusicPlayer:
    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild
        self.queue = []
        self.titles = []
        self.video_urls = []  # Store video URLs for reference
        self.current_song = None
        self.current_video_url = None  # Track current video URL
        self.last_interaction = None

        # Create a thread pool for handling downloads
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # Initialize Spotify API
        self.sp = Spotify(auth_manager=SpotifyClientCredentials(
            client_id=client,
            client_secret=secret))

        # FFmpeg options for better stream handling
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        # Path to FFmpeg executable
        self.ffmpeg_path = ffmpeg

    async def search_song(self, query, limit=5):
        """Search for songs and return a list of options"""

        def _search():
            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': 'True',
                'quiet': True,
                'extract_flat': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                results = []
                for entry in info['entries']:
                    results.append({
                        'url': f"https://www.youtube.com/watch?v={entry['id']}",
                        'title': entry['title']
                    })
                return results

        # Run in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(self.thread_pool, _search)

    async def get_youtube_url(self, query):
        """Helper function to get YouTube URL from Spotify link or search query"""

        def _get_url():
            ydl_opts = {
                'format': 'bestaudio/best',
                'noplaylist': 'True',
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                return info['entries'][0]['url'], info['entries'][0]['title'], info['entries'][0]['webpage_url']

        # Run in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(self.thread_pool, _get_url)

    async def get_youtube_playlist(self, url):
        """Extract songs from a YouTube playlist"""

        def _get_playlist():
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'extract_flat': True,
                'force_generic_extractor': False
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                tracks = []

                # Check if it's a playlist or just a single video
                if 'entries' in info:
                    for entry in info['entries']:
                        if entry:
                            video_url = f"https://www.youtube.com/watch?v={entry['id']}"

                            # Extract the stream URL for each video
                            try:
                                with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                                    video_info = ydl2.extract_info(video_url, download=False)
                                    stream_url = video_info['url']
                                    title = entry.get('title', video_info.get('title', 'Unknown title'))
                                    tracks.append({
                                        'stream_url': stream_url,
                                        'video_url': video_url,
                                        'title': title
                                    })
                            except Exception as e:
                                print(f"Error processing playlist item: {str(e)}")
                                continue

                return tracks

        # Run in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(self.thread_pool, _get_playlist)

    async def process_playlist(self, interaction, url):
        """Process a playlist URL and add all songs to the queue"""
        try:
            tracks = []
            if "youtube.com/playlist" in url or "youtube.com/watch" in url and "list=" in url:
                # YouTube playlist
                await interaction.followup.send("Processing YouTube playlist... This may take a moment.")

                # Process tracks in batches to avoid long blocking operations
                tracks = await self.get_youtube_playlist(url)

                # Add each track to the queue
                added_count = 0
                for track in tracks:
                    try:
                        self.queue.append(track['stream_url'])
                        self.titles.append(track['title'])
                        if not hasattr(self, 'video_urls'):
                            self.video_urls = []
                        self.video_urls.append(track['video_url'])
                        added_count += 1
                    except Exception as e:
                        print(f"Error adding YouTube playlist track: {str(e)}")

                await interaction.followup.send(f"Added {added_count} songs from YouTube playlist to the queue.")

            elif "spotify.com/playlist/" in url or "spotify.com/album/" in url:
                # Spotify playlist or album
                await interaction.followup.send("Processing Spotify playlist... This may take a moment.")
                spotify_tracks = await self.get_spotify_playlist(url)

                # Process tracks in smaller batches
                batch_size = 5
                batches = [spotify_tracks[i:i + batch_size] for i in range(0, len(spotify_tracks), batch_size)]

                total_added = 0
                for i, batch in enumerate(batches):
                    if i > 0 and i % 2 == 0:  # Update progress every few batches
                        await interaction.followup.send(
                            f"Progress: {total_added}/{len(spotify_tracks)} songs processed...")

                    # Process each batch concurrently
                    tasks = []
                    for track in batch:
                        task = asyncio.create_task(self.process_url(track['query']))
                        tasks.append(task)

                    # Wait for all tasks in batch to complete
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Add successful results to queue
                    for result in results:
                        if isinstance(result, Exception):
                            continue

                        try:
                            stream_url, title, video_url = result
                            self.queue.append(stream_url)
                            self.titles.append(title)
                            if not hasattr(self, 'video_urls'):
                                self.video_urls = []
                            self.video_urls.append(video_url)
                            total_added += 1
                        except Exception as e:
                            print(f"Error adding Spotify track to queue: {str(e)}")

                await interaction.followup.send(f"Added {total_added} songs from Spotify playlist/album to the queue.")

            # Start playing if not already playing
            voice_client = interaction.guild.voice_client
            if voice_client and not (voice_client.is_playing() or voice_client.is_paused()) and self.queue:
                await self.play_next()

            return True

        except Exception as e:
            await interaction.followup.send(f"Error processing playlist: {str(e)}")
            return False

    async def get_spotify_playlist(self, url):
        """Extract songs from a Spotify playlist"""

        def _get_spotify_playlist():
            # Extract playlist ID from URL
            tracks = []

            if "playlist" in url:
                playlist_id = url.split("playlist/")[1].split("?")[0]
                results = self.sp.playlist_items(playlist_id)

                # Process each track in the playlist
                for item in results['items']:
                    track = item['track']
                    if track:
                        query = f"{track['name']} {track['artists'][0]['name']}"
                        tracks.append({'query': query})

            # Extract album if it's an album URL
            elif "album" in url:
                album_id = url.split("album/")[1].split("?")[0]
                results = self.sp.album_tracks(album_id)

                # Process each track in the album
                for track in results['items']:
                    if track:
                        query = f"{track['name']} {track['artists'][0]['name']}"
                        tracks.append({'query': query})

            return tracks

        # Run in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(self.thread_pool, _get_spotify_playlist)

    async def process_url(self, url):
        """Process the URL to get a playable YouTube URL and title"""

        def _process_url():
            # Handle Spotify track links
            if "spotify.com/track/" in url:
                track_id = url.split("track/")[1].split("?")[0]
                track_info = self.sp.track(track_id)
                query = f"{track_info['name']} {track_info['artists'][0]['name']}"
                # Convert to a YouTube search
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': 'True',
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    video_info = info['entries'][0]
                    # Get the actual stream URL
                    stream_url = video_info['url']
                    title = video_info['title']
                    return stream_url, title, video_info['webpage_url']  # Return stream URL, title, and video page URL

            # Handle direct YouTube URLs
            elif "youtube.com/" in url or "youtu.be/" in url:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': 'False',  # Allow playlists
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if '_type' in info and info['_type'] == 'playlist':
                        # This is a playlist, but we're just getting the first item for now
                        entry = info['entries'][0]
                        stream_url = entry['url']  # This is the actual playable stream URL
                        title = entry['title']
                        video_url = entry['webpage_url']  # Original video URL
                    else:
                        stream_url = info['url']  # This is the actual playable stream URL
                        title = info['title']
                        video_url = info['webpage_url'] if 'webpage_url' in info else url  # Original video URL
                return stream_url, title, video_url

            # Handle normal search queries
            else:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'noplaylist': 'True',
                    'quiet': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch:{url}", download=False)
                    video_info = info['entries'][0]
                    # Get the actual stream URL
                    stream_url = video_info['url']
                    title = video_info['title']
                    return stream_url, title, video_info['webpage_url']  # Return stream URL, title, and video page URL

        # Run in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(self.thread_pool, _process_url)

    async def play(self, interaction, query):
        """Play a song or add it to the queue if something is already playing"""
        self.last_interaction = interaction
        voice_client = interaction.guild.voice_client

        if not voice_client:
            await interaction.followup.send("I need to join a voice channel first! Use /join")
            return

        # Check if it's a playlist
        if ("youtube.com/playlist" in query or "youtube.com/watch" in query and "list=" in query or
                "spotify.com/playlist/" in query or "spotify.com/album/" in query):
            return await self.process_playlist(interaction, query)

        try:
            # Process the URL to get the playable stream URL and title
            await interaction.followup.send("Processing your request... This may take a moment.")
            stream_url, title, video_url = await self.process_url(query)
        except Exception as e:
            await interaction.followup.send(f"Error processing URL: {str(e)}")
            return

        if voice_client.is_playing() or voice_client.is_paused():
            # Add to queue if already playing
            self.queue.append(stream_url)
            self.titles.append(title)
            self.video_urls.append(video_url)  # Store the original video URL for reference
            await interaction.followup.send(f"Added to queue: {title}")
        else:
            # Play immediately if nothing is playing
            self.current_song = title
            self.current_video_url = video_url  # Store the current video URL

            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                # Use the bot's event loop to call the next song
                asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

            try:
                voice_client.play(
                    discord.FFmpegPCMAudio(executable=self.ffmpeg_path, source=stream_url, **self.ffmpeg_options),
                    after=after_playing
                )

                await interaction.followup.send(f"Mao is boppin' to: {title}")
            except Exception as e:
                await interaction.followup.send(f"Error playing the song: {str(e)}")

    async def play_next(self):
        """Play the next song in the queue"""
        voice_client = self.guild.voice_client
        if not voice_client:
            return

        if self.queue:
            # Get the next song from the queue
            next_url = self.queue.pop(0)
            self.current_song = self.titles.pop(0)
            if self.video_urls:
                self.current_video_url = self.video_urls.pop(0)

            # Play it
            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

            try:
                voice_client.play(
                    discord.FFmpegPCMAudio(executable=self.ffmpeg_path, source=next_url, **self.ffmpeg_options),
                    after=after_playing
                )

                # Send a message to the channel
                if self.last_interaction:
                    await self.last_interaction.channel.send(f"Now playing: {self.current_song}")
            except Exception as e:
                if self.last_interaction:
                    await self.last_interaction.channel.send(f"Error playing next song: {str(e)}")

    async def add_to_queue(self, url):
        """Add a song to the queue"""
        try:
            # Process the URL to get the playable stream URL and title
            stream_url, title, video_url = await self.process_url(url)

            self.queue.append(stream_url)
            self.titles.append(title)
            self.video_urls.append(video_url)  # Store the original video URL for reference
            return title
        except Exception as e:
            print(f"Error adding to queue: {str(e)}")
            return "Unknown title (error occurred)"

    def shuffle_queue(self):
        """Shuffle the queue"""
        if len(self.queue) > 1:
            # Create a list of pairs (url, title, video_url) to keep them together
            queue_triplets = list(zip(self.queue, self.titles, self.video_urls))
            # Shuffle the triplets
            random.shuffle(queue_triplets)
            # Unzip the triplets back into separate lists
            self.queue, self.titles, self.video_urls = map(list, zip(*queue_triplets))
            return True
        return False

    def stop(self):
        """Stop playing and clear the queue"""
        if self.guild.voice_client:
            self.guild.voice_client.stop()
        self.clear_queue()

    def pause(self):
        """Pause the current song"""
        if self.guild.voice_client and self.guild.voice_client.is_playing():
            self.guild.voice_client.pause()
            return True
        return False

    def resume(self):
        """Resume the current song"""
        if self.guild.voice_client and self.guild.voice_client.is_paused():
            self.guild.voice_client.resume()
            return True
        return False

    async def skip(self, interaction):
        """Skip to the next song in the queue"""
        self.last_interaction = interaction

        if self.guild.voice_client:
            self.guild.voice_client.stop()  # This will trigger the after callback
            return len(self.queue) > 0
        return False

    def clear_queue(self):
        """Clear the song queue"""
        self.queue = []
        self.titles = []
        self.video_urls = []
        self.current_song = None
        self.current_video_url = None

    def get_queue_info(self):
        """Return information about the current queue"""
        if self.current_song:
            return [f"Currently playing: {self.current_song}"] + self.titles
        return self.titles

    def __del__(self):
        """Clean up thread pool when the player is deleted"""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown()