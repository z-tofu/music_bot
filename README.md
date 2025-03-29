# Discord Music Bot

A feature-rich Discord music bot that allows users to play music from YouTube and Spotify in Discord voice channels.

## Features

- **Multi-Platform Support**: Play music from YouTube, Spotify playlists/albums, or direct search queries
- **Queue Management**: Add songs to queue, skip, pause, resume, and shuffle
- **Playlist Support**: Load entire YouTube or Spotify playlists
- **Asynchronous Processing**: Downloads and processes audio in separate threads to prevent Discord connection issues
- **Rich Audio Controls**: Easy-to-use commands for controlling playback

## Requirements

- Python 3.8 or higher
- FFmpeg installed on your system
- Discord Bot Token
- Spotify API credentials (for Spotify functionality)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/z-tofu/music_bot.git
   cd music_bot
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with the following:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   SPOTIFY_CLIENT=your_spotify_client_id
   SPOTIFY_SECRET=your_spotify_client_secret
   FFMPEG_PATH=path/to/ffmpeg.exe
   ```
4. Run main.py:
   ```
   python main.py
   ```

## Usage

### Commands

- `/join` - Join the voice channel you're in
- `/play <song>` - Play a song or add it to the queue
  - Accepts YouTube links, Spotify links, or search terms
  - Example: `/play https://www.youtube.com/watch?v=dQw4w9WgXcQ`
  - Example: `/play https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT`
  - Example: `/play never gonna give you up`
- `/playlist <url>` - Add an entire YouTube or Spotify playlist to the queue
- `/skip` - Skip the current song
- `/pause` - Pause the current song
- `/resume` - Resume playback if paused
- `/stop` - Stop playback and clear the queue
- `/queue` - Show the current queue
- `/shuffle` - Shuffle the songs in the queue
- `/leave` - Leave the voice channel

## Project Structure

- `music_player.py` - Main music player class with audio playback and queue functionality
- `bot_commands.py` - Discord bot commands and event handlers
- `main.py` - Main

## Troubleshooting

### Common Issues

1. **FFmpeg errors**:
   - Ensure FFmpeg is properly installed and the path is correctly set in the code
   - Check if your FFmpeg installation supports the audio formats you're trying to play

2. **Discord connection issues**:
   - If you see "discord.gateway: Shard ID None voice heartbeat blocked", it means some operations are blocking the main thread
   - This should be addressed by the asynchronous processing implemented in the music player

3. **Spotify API issues**:
   - Verify your Spotify credentials are correct
   - Ensure you've set up the proper redirect URIs in your Spotify Developer Dashboard

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [discord.py](https://github.com/Rapptz/discord.py) - The Discord API wrapper
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [spotipy](https://github.com/spotipy-dev/spotipy) - Spotify API wrapper
