import os
import sys
import subprocess
import logging
from aiohttp import web
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def healthcheck(request):
    """Health check endpoint"""
    try:
        # Check if FFmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         check=True, 
                         capture_output=True)
            return web.Response(text="OK", status=200)
        except Exception as e:
            return web.Response(text=f"FFmpeg check failed: {str(e)}", status=500)
    except Exception as e:
        return web.Response(text=f"Health check failed: {str(e)}", status=500)

def main():
    """Main health check function"""
    try:
        # Skip token check during build
        if os.environ.get('DOCKER_BUILD') == 'true':
            logger.info("Build phase detected, skipping token check")
            return 0

        # Check environment variables in runtime
        if not os.getenv('DISCORD_TOKEN'):
            logger.error("DISCORD_TOKEN not found")
            return 1

        # Check FFmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         check=True, 
                         capture_output=True)
            logger.info("FFmpeg check passed")
        except Exception as e:
            logger.error(f"FFmpeg check failed: {e}")
            return 1

        logger.info("All health checks passed")
        return 0
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 1

async def start_server():
    """Start the health check server"""
    app = web.Application()
    app.router.add_get('/health', healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server started on port 8080")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_server())
        loop.run_forever()
    else:
        sys.exit(main())
 