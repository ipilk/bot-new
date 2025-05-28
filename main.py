import discord
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp
import os
import asyncio
import certifi
import ssl
from dotenv import load_dotenv
from shutil import which
import glob
import subprocess
import platform
import sys
import logging
import time
import traceback
from healthcheck import main as health_check
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('discord_bot')

# Global variables for voice state
voice_clients = {}
current_players = {}
last_heartbeat = 0
HEARTBEAT_INTERVAL = 60  # seconds

print("\n=== Bot Initialization Started ===")
logger.info(f"Python version: {platform.python_version()}")
logger.info(f"Operating System: {platform.system()} {platform.release()}")
logger.info(f"Running in environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'local')}")
logger.info(f"Current working directory: {os.getcwd()}")

# Run health check
print("\n=== Running Health Check ===")
if health_check() != 0:
    logger.critical("Health check failed. Exiting.")
    sys.exit(1)

# Load environment variables
print("\n=== Loading Environment Variables ===")
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logger.critical("DISCORD_TOKEN not found in environment variables")
    sys.exit(1)
logger.info("Token loaded successfully")

# Verify FFmpeg installation
print("\n=== Verifying FFmpeg Installation ===")
try:
    ffmpeg_version = subprocess.run(['ffmpeg', '-version'], 
                                  check=True, 
                                  capture_output=True, 
                                  text=True).stdout.split('\n')[0]
    FFMPEG_PATH = 'ffmpeg'
    logger.info(f"FFmpeg found: {ffmpeg_version}")
except subprocess.CalledProcessError as e:
    logger.error(f"Error running FFmpeg: {e}")
    logger.error(f"FFmpeg error output: {e.stderr}")
    FFMPEG_PATH = None
except FileNotFoundError:
    logger.error("FFmpeg not found in system PATH")
    FFMPEG_PATH = None

if not FFMPEG_PATH:
    logger.error("\n=== FFmpeg Error Details ===")
    logger.error(f"Current directory contents: {os.listdir()}")
    logger.error(f"PATH environment: {os.environ.get('PATH')}")
    raise RuntimeError("FFmpeg not found")

print("\n=== Configuring Bot ===")
# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.presences = True  # Enable presence updates

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.voice_states = {}
        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'force-ipv4': True
        }
        self.ytdl = yt_dlp.YoutubeDL(self.YTDL_OPTIONS)
        self.last_heartbeat = datetime.now()
        self.reconnect_attempts = 0
        self.MAX_RECONNECT_ATTEMPTS = 5
        self.connection_monitor.start()
        
    async def setup_hook(self):
        """Setup hook that gets called when the bot starts"""
        logger.info("Running setup hook...")
        try:
            await self.tree.sync()
            logger.info("Commands synced successfully")
            self.connection_monitor.start()
        except Exception as e:
            logger.error(f"Error in setup hook: {e}", exc_info=True)

    @tasks.loop(seconds=30)
    async def connection_monitor(self):
        """Monitor bot connection and attempt reconnection if needed"""
        try:
            if not self.is_ready():
                logger.warning("Bot is not ready!")
                if self.reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
                    self.reconnect_attempts += 1
                    logger.info(f"Attempting to reconnect... (Attempt {self.reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")
                    try:
                        await self.close()
                        await self.start(TOKEN)
                    except Exception as e:
                        logger.error(f"Reconnection attempt failed: {e}")
                else:
                    logger.critical("Max reconnection attempts reached!")
                    self.connection_monitor.stop()
                    await self.close()
                    sys.exit(1)
            else:
                self.reconnect_attempts = 0
                self.last_heartbeat = datetime.now()
                logger.debug("Connection monitor: Bot is connected")
        except Exception as e:
            logger.error(f"Error in connection monitor: {e}", exc_info=True)

    @connection_monitor.before_loop
    async def before_connection_monitor(self):
        """Wait for bot to be ready before starting the monitor"""
        await self.wait_until_ready()

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Discord.py version: {discord.__version__}")
        
        # Set status
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.LISTENING,
                    name="/play | 🎵"
                ),
                status=discord.Status.online
            )
            logger.info("Bot status set successfully")
        except Exception as e:
            logger.error(f"Failed to set presence: {e}", exc_info=True)

    async def on_disconnect(self):
        """Handle disconnection"""
        logger.warning("Bot disconnected!")
        self.reconnect_attempts += 1

    async def on_connect(self):
        """Handle successful connection"""
        logger.info("Bot connected successfully!")
        self.reconnect_attempts = 0
        self.last_heartbeat = datetime.now()

    async def on_error(self, event_method: str, *args, **kwargs):
        """Called when an error occurs"""
        logger.error(f"Error in {event_method}: {traceback.format_exc()}")
        if event_method == "on_message":
            try:
                channel_id = args[0].channel.id
                channel = self.get_channel(channel_id)
                if channel:
                    await channel.send("⚠️ حدث خطأ في معالجة الرسالة")
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    async def get_audio_player(self, url: str) -> tuple:
        """Get audio player for a YouTube URL"""
        try:
            # Extract video info
            data = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.ytdl.extract_info(url, download=False)
            )
            
            if 'entries' in data:
                data = data['entries'][0]

            # Get direct audio URL
            audio_url = data.get('url')
            if not audio_url:
                raise ValueError("Could not get audio URL from video")

            # Create FFmpeg audio source
            audio_source = discord.FFmpegPCMAudio(
                audio_url,
                **FFMPEG_OPTIONS
            )
            
            # Add volume transformer
            audio_source = discord.PCMVolumeTransformer(audio_source, volume=1.0)
            
            return audio_source, data.get('title', 'Unknown')
        except Exception as e:
            logger.error(f"Error getting audio player: {e}", exc_info=True)
            raise

# Initialize bot with automatic reconnection
bot = MusicBot()

# FFmpeg options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -ac 2 -b:a 192k'
}

# Set SSL context for requests
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

logger.info("Bot configuration completed")

async def ensure_voice_client(interaction: discord.Interaction, channel: discord.VoiceChannel) -> discord.VoiceClient:
    """Ensure bot is connected to voice channel"""
    guild_id = interaction.guild_id
    if guild_id in voice_clients:
        voice_client = voice_clients[guild_id]
        if voice_client.is_connected():
            if voice_client.channel != channel:
                await voice_client.move_to(channel)
            return voice_client
        else:
            del voice_clients[guild_id]

    voice_client = await channel.connect(timeout=60, reconnect=True)
    voice_clients[guild_id] = voice_client
    return voice_client

@bot.tree.command(name="play", description="تشغيل مقطع صوتي من يوتيوب")
@app_commands.describe(url="رابط مقطع اليوتيوب")
async def play(interaction: discord.Interaction, url: str):
    """Play a song from YouTube"""
    try:
        # Initial response
        await interaction.response.defer(ephemeral=False)
        
        # Check if user is in a voice channel
        if not interaction.user.voice:
            await interaction.followup.send("❌ يجب أن تكون في قناة صوتية!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        
        try:
            # Connect to voice channel
            voice_client = interaction.guild.voice_client
            if voice_client:
                if voice_client.channel != voice_channel:
                    await voice_client.move_to(voice_channel)
            else:
                voice_client = await voice_channel.connect(timeout=60)
            
            # Update status message
            await interaction.followup.send("🔄 جاري تحميل المقطع...")
            
            # Get audio player
            audio_source, title = await bot.get_audio_player(url)
            
            # Play the audio
            if voice_client.is_playing():
                voice_client.stop()
            
            def after_playing(error):
                if error:
                    logger.error(f"Error in playback: {error}")
                    asyncio.run_coroutine_threadsafe(
                        interaction.followup.send("❌ حدث خطأ أثناء التشغيل"),
                        bot.loop
                    )
            
            voice_client.play(audio_source, after=after_playing)
            await interaction.edit_original_response(content=f"🎵 جاري تشغيل: **{title}**")
            
        except Exception as e:
            logger.error(f"Error in play command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ حدث خطأ: {str(e)}", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Unexpected error in play command: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ حدث خطأ غير متوقع", ephemeral=True)
        else:
            await interaction.followup.send("❌ حدث خطأ غير متوقع", ephemeral=True)

@bot.tree.command(name="stop", description="إيقاف تشغيل المقطع الصوتي والخروج من القناة")
async def stop(interaction: discord.Interaction):
    """Stop playing and disconnect"""
    try:
        await interaction.response.defer(ephemeral=False)
        
        voice_client = interaction.guild.voice_client
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            await interaction.followup.send("✅ تم إيقاف التشغيل والخروج من القناة")
        else:
            await interaction.followup.send("❌ البوت غير متصل بأي قناة صوتية!", ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in stop command: {e}", exc_info=True)
        await interaction.followup.send("❌ حدث خطأ أثناء محاولة الإيقاف", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates"""
    if member == bot.user and after.channel is None:
        logger.info("Bot was disconnected from voice channel")
        if before.channel:
            voice_client = before.channel.guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                logger.info("Stopped playback due to disconnection")

def run_bot():
    """Run the bot with proper event loop handling"""
    try:
        logger.info("Starting bot...")
        bot.run(TOKEN, log_handler=None)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_bot() 