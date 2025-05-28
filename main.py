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
from healthcheck import main as health_check

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('discord_bot')

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
    logger.error("DISCORD_TOKEN not found in environment variables")
    logger.error("Available environment variables: %s", 
                 [k for k in os.environ.keys() if not k.startswith('PATH')])
    raise RuntimeError("DISCORD_TOKEN is required")
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
intents.voice_states = True  # Enable voice state updates
bot = commands.Bot(command_prefix='!', intents=intents)

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
    'no_check_certificate': True
}

if FFMPEG_PATH:
    YTDL_OPTIONS['ffmpeg_location'] = os.path.dirname(FFMPEG_PATH) if os.path.dirname(FFMPEG_PATH) else '.'

# FFmpeg options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

logger.info("Bot configuration completed")

# Create YouTube DL client
print("\n=== Initializing YouTube-DL ===")
ssl._create_default_https_context = ssl._create_unverified_context
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
logger.info("YouTube-DL initialized")

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        try:
            logger.info(f"Extracting info from URL: {url}")
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            
            if 'entries' in data:
                data = data['entries'][0]
                
            filename = data['url']
            logger.info(f"Creating audio source for: {data.get('title', 'Unknown title')}")
            return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_PATH, **FFMPEG_OPTIONS), data=data)
        except Exception as e:
            logger.error(f"Error in from_url: {e}", exc_info=True)
            raise e

@bot.event
async def on_ready():
    logger.info("\n=== Bot is Ready! ===")
    logger.info(f"Logged in as: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Discord.py version: {discord.__version__}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)

@bot.tree.command(name="play", description="تشغيل مقطع صوتي من يوتيوب")
@app_commands.describe(url="رابط مقطع اليوتيوب")
async def play(interaction: discord.Interaction, url: str):
    """Plays audio from YouTube URL"""
    logger.info(f"Received play command from {interaction.user} with URL: {url}")
    
    try:
        if not interaction.user.voice:
            await interaction.response.send_message("أنت لست متصل بقناة صوتية!", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        if not channel:
            await interaction.response.send_message("لم أتمكن من العثور على قناة صوتية!", ephemeral=True)
            return

        # Check if FFmpeg exists
        if not os.path.exists(FFMPEG_PATH):
            error_msg = f"لم يتم العثور على FFmpeg في المسار: {FFMPEG_PATH}"
            logger.error(error_msg)
            await interaction.response.send_message(error_msg, ephemeral=True)
            return

        # Defer the response since audio loading might take time
        await interaction.response.defer(ephemeral=False, thinking=True)
        logger.info("Response deferred, processing audio...")

        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_connected():
            await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()
            logger.info(f"Connected to voice channel: {channel.name}")

        player = await YTDLSource.from_url(url, loop=bot.loop)
        if voice_client.is_playing():
            voice_client.stop()
            logger.info("Stopped current playback")
            
        def after_playing(error):
            if error:
                logger.error(f"Error after playing: {error}")
            else:
                logger.info("Finished playing audio")

        voice_client.play(player, after=after_playing)
        logger.info(f"Started playing: {player.title}")
        await interaction.followup.send(f'🎵 جاري تشغيل: **{player.title}**')
        
    except Exception as e:
        logger.error(f"Error in play command: {e}", exc_info=True)
        error_message = f"حدث خطأ أثناء تشغيل المقطع: {str(e)}"
        if not interaction.response.is_done():
            await interaction.response.send_message(error_message, ephemeral=True)
        else:
            await interaction.followup.send(error_message, ephemeral=True)

@bot.tree.command(name="stop", description="إيقاف تشغيل المقطع الصوتي والخروج من القناة")
async def stop(interaction: discord.Interaction):
    """Stops and disconnects the bot from voice"""
    logger.info(f"Received stop command from {interaction.user}")
    try:
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            logger.info("Disconnected from voice channel")
            await interaction.response.send_message("تم إيقاف التشغيل وقطع الاتصال ✅")
        else:
            await interaction.response.send_message("البوت غير متصل بأي قناة صوتية!", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in stop command: {e}", exc_info=True)
        await interaction.response.send_message(f"حدث خطأ أثناء محاولة إيقاف التشغيل: {str(e)}", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates"""
    if member == bot.user and after.channel is None:  # Bot was disconnected
        logger.info("Bot was disconnected from voice channel")
        for guild in bot.guilds:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                logger.info("Stopped playback due to disconnection")

logger.info("Starting bot...")
try:
    bot.run(TOKEN)
except Exception as e:
    logger.critical(f"Error starting bot: {e}", exc_info=True) 