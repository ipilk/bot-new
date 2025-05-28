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

print("Starting bot initialization...")

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
print("Token loaded")

# Set FFmpeg path and verify installation
def verify_ffmpeg():
    try:
        # Try to run ffmpeg -version
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            print("FFmpeg is available in system PATH")
            return 'ffmpeg'
    except Exception as e:
        print(f"Error running ffmpeg: {e}")

    # Check common paths
    paths = [
        'ffmpeg',
        '/usr/bin/ffmpeg',
        os.path.join(os.getcwd(), 'ffmpeg', 'ffmpeg.exe')
    ]
    
    for path in paths:
        try:
            result = subprocess.run([path, '-version'], 
                                  capture_output=True, 
                                  text=True)
            if result.returncode == 0:
                print(f"Found working FFmpeg at: {path}")
                return path
        except Exception:
            continue
    
    print("FFmpeg not found or not working")
    return None

print("Verifying FFmpeg installation...")
FFMPEG_PATH = verify_ffmpeg()
if not FFMPEG_PATH:
    print("Error: FFmpeg not found or not working")
    print("Environment information:")
    print(f"Current directory: {os.getcwd()}")
    print(f"PATH: {os.environ.get('PATH')}")
    print(f"Files in current directory: {os.listdir()}")
else:
    print(f"Using FFmpeg from: {FFMPEG_PATH}")

# Bot configuration
print("Setting up bot configuration...")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Update YTDL options with verified FFmpeg path
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

# Create YouTube DL client with SSL context
ssl._create_default_https_context = ssl._create_unverified_context
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

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
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            
            if 'entries' in data:
                data = data['entries'][0]
                
            filename = data['url']
            return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_PATH, **FFMPEG_OPTIONS), data=data)
        except Exception as e:
            print(f"Error in from_url: {e}")
            raise e

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="play", description="تشغيل مقطع صوتي من يوتيوب")
@app_commands.describe(url="رابط مقطع اليوتيوب")
async def play(interaction: discord.Interaction, url: str):
    """Plays audio from YouTube URL"""
    print(f"Received play command with URL: {url}")
    
    if not interaction.user.voice:
        await interaction.response.send_message("أنت لست متصل بقناة صوتية!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    if not channel:
        await interaction.response.send_message("لم أتمكن من العثور على قناة صوتية!", ephemeral=True)
        return

    # Check if FFmpeg exists
    if not os.path.exists(FFMPEG_PATH):
        error_msg = f"لم يتم العثور على FFmpeg في المسار: {FFMPEG_PATH}\nالرجاء التأكد من وجود الملف في المجلد الصحيح."
        print(error_msg)
        await interaction.response.send_message(error_msg, ephemeral=True)
        return

    # Defer the response since audio loading might take time
    await interaction.response.defer(ephemeral=False)

    voice_client = interaction.guild.voice_client

    try:
        if voice_client and voice_client.is_connected():
            await voice_client.move_to(channel)
        else:
            voice_client = await channel.connect()

        player = await YTDLSource.from_url(url, loop=bot.loop)
        if voice_client.is_playing():
            voice_client.stop()
            
        voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        await interaction.followup.send(f'🎵 جاري تشغيل: **{player.title}**')
    except Exception as e:
        print(f"Error playing audio: {e}")
        await interaction.followup.send(f"حدث خطأ أثناء تشغيل المقطع: {str(e)}")

@bot.tree.command(name="stop", description="إيقاف تشغيل المقطع الصوتي والخروج من القناة")
async def stop(interaction: discord.Interaction):
    """Stops and disconnects the bot from voice"""
    print("Received stop command")
    voice_client = interaction.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message("تم إيقاف التشغيل وقطع الاتصال ✅")
    else:
        await interaction.response.send_message("البوت غير متصل بأي قناة صوتية!", ephemeral=True)

print("Starting bot...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"Error starting bot: {e}") 