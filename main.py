import discord
from discord import app_commands
from discord.ext import commands
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
        self.reconnect_attempts = 0
        self.MAX_RECONNECT_ATTEMPTS = 5
        self.background_tasks = []
        self.initial_extensions = []
        self.start_time = time.time()
        
    async def setup_hook(self):
        """Setup hook that gets called when the bot starts"""
        self.background_tasks.append(self.loop.create_task(self.status_task()))
        self.background_tasks.append(self.loop.create_task(self.heartbeat_task()))
        logger.info("Setup hook completed")
        logger.info("Running setup hook...")
        try:
            # Sync commands
            logger.info("Syncing commands...")
            await self.tree.sync()
            logger.info("Commands synced successfully")
        except Exception as e:
            logger.error(f"Error in setup hook: {e}", exc_info=True)

    async def status_task(self):
        """Task to update bot's status and monitor connection"""
        while not self.is_closed():
            try:
                if self.is_ws_ratelimited():
                    logger.warning("Bot is being rate limited!")
                
                if not self.is_ready():
                    logger.warning("Bot is not ready!")
                    
                await self.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name="/play | 🎵"
                    ),
                    status=discord.Status.online
                )
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in status task: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def heartbeat_task(self):
        """Task to monitor bot's heartbeat"""
        global last_heartbeat
        while not self.is_closed():
            try:
                current_time = time.time()
                last_heartbeat = current_time
                latency = self.latency * 1000
                logger.info(f"Heartbeat - Latency: {latency:.2f}ms")
                
                if latency > 1000:  # High latency warning
                    logger.warning(f"High latency detected: {latency:.2f}ms")
                
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def close(self):
        """Clean up when the bot is shutting down"""
        logger.info("Bot is shutting down...")
        for task in self.background_tasks:
            task.cancel()
        await super().close()

    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Discord.py version: {discord.__version__}")
        
        # Set status
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="/play | 🎵"
                ),
                status=discord.Status.online
            )
        except Exception as e:
            logger.error(f"Failed to set presence: {e}", exc_info=True)

    async def on_error(self, event_method: str, *args, **kwargs):
        """Called when an error occurs"""
        logger.error(f"Error in {event_method}: {traceback.format_exc()}")

bot = MusicBot()

# YouTube DL options
YTDL_OPTIONS = {
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
    'prefer_insecure': True,
    'legacy_server_connect': True
}

# FFmpeg options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 0 -loglevel 0',
    'options': '-vn -acodec libopus -b:a 192k -filter:a volume=1.0'
}

# Set SSL context for requests
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

logger.info("Bot configuration completed")

# Create YouTube DL client with updated SSL context
print("\n=== Initializing YouTube-DL ===")
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
logger.info("YouTube-DL initialized")

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

async def get_audio_source(url: str) -> tuple:
    """Get audio source from URL"""
    loop = asyncio.get_event_loop()
    try:
        # Configure SSL context for this request
        original_ssl_context = ssl.get_default_verify_paths()
        ssl._create_default_https_context = ssl._create_unverified_context
        
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]

        # Reset SSL context to original state
        ssl._create_default_https_context = lambda: original_ssl_context

        return (
            discord.FFmpegPCMAudio(
                data['url'],
                executable=FFMPEG_PATH,
                **FFMPEG_OPTIONS
            ),
            data.get('title', 'Unknown title')
        )
    except Exception as e:
        logger.error(f"Error getting audio source: {e}", exc_info=True)
        raise

@bot.tree.command(name="play", description="تشغيل مقطع صوتي من يوتيوب")
@app_commands.describe(url="رابط مقطع اليوتيوب")
async def play(interaction: discord.Interaction, url: str):
    """Play a song from YouTube"""
    try:
        await interaction.response.defer(ephemeral=False, thinking=True)
        logger.info(f"Received play command from {interaction.user} for URL: {url}")

        if not interaction.user.voice:
            await interaction.followup.send("يجب أن تكون في قناة صوتية!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        if not voice_channel:
            await interaction.followup.send("لم أتمكن من العثور على قناة صوتية!", ephemeral=True)
            return

        try:
            # Get or create voice client
            voice_client = interaction.guild.voice_client
            if voice_client:
                if voice_client.channel != voice_channel:
                    await voice_client.move_to(voice_channel)
            else:
                voice_client = await voice_channel.connect(timeout=60)
            
            logger.info(f"Connected to voice channel: {voice_channel.name}")

            # Get song info with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Extracting video information (attempt {attempt + 1}/{max_retries})...")
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(1)
            
            if 'entries' in data:
                data = data['entries'][0]

            # Create FFmpeg audio source with proper error handling
            logger.info("Creating audio source...")
            try:
                audio_source = discord.FFmpegPCMAudio(
                    data['url'],
                    **FFMPEG_OPTIONS
                )
                audio_source = discord.PCMVolumeTransformer(audio_source, volume=1.0)
            except Exception as e:
                logger.error(f"Failed to create audio source: {e}", exc_info=True)
                await interaction.followup.send("فشل في إنشاء مصدر الصوت. الرجاء المحاولة مرة أخرى.", ephemeral=True)
                return

            # Play the audio with callback
            def after_playing(error):
                if error:
                    logger.error(f"Error in playback: {error}")
                    asyncio.run_coroutine_threadsafe(
                        interaction.followup.send("حدث خطأ أثناء التشغيل. جاري المحاولة مرة أخرى..."),
                        voice_client.loop
                    )
                else:
                    logger.info("Finished playing audio successfully")

            if voice_client.is_playing():
                voice_client.stop()
                logger.info("Stopped current playback")

            voice_client.play(audio_source, after=after_playing)
            logger.info(f"Started playing: {data.get('title', 'Unknown')}")
            
            await interaction.followup.send(f"🎵 جاري تشغيل: **{data.get('title', 'Unknown')}**")

        except Exception as e:
            logger.error(f"Error playing audio: {e}", exc_info=True)
            await interaction.followup.send(f"حدث خطأ أثناء محاولة التشغيل: {str(e)}", ephemeral=True)

    except Exception as e:
        logger.error(f"Unexpected error in play command: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message("حدث خطأ غير متوقع", ephemeral=True)
        else:
            await interaction.followup.send("حدث خطأ غير متوقع", ephemeral=True)

@bot.tree.command(name="stop", description="إيقاف تشغيل المقطع الصوتي والخروج من القناة")
async def stop(interaction: discord.Interaction):
    """Stop playing and disconnect"""
    try:
        await interaction.response.defer(ephemeral=False)
        logger.info(f"Received stop command from {interaction.user}")

        voice_client = interaction.guild.voice_client
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
                logger.info("Stopped playback")
            await voice_client.disconnect()
            logger.info("Disconnected from voice channel")
            await interaction.followup.send("تم إيقاف التشغيل وقطع الاتصال ✅")
        else:
            await interaction.followup.send("البوت غير متصل بأي قناة صوتية!", ephemeral=True)

    except Exception as e:
        logger.error(f"Error in stop command: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message("حدث خطأ أثناء محاولة الإيقاف", ephemeral=True)
        else:
            await interaction.followup.send("حدث خطأ أثناء محاولة الإيقاف", ephemeral=True)

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

logger.info("Starting bot...")
try:
    bot.run(TOKEN, log_handler=None)
except Exception as e:
    logger.critical(f"Failed to start bot: {e}", exc_info=True)
    sys.exit(1) 