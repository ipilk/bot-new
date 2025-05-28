import os
import sys
import subprocess
import shutil

def check_ffmpeg():
    print("Checking FFmpeg installation...")
    
    # Check environment variable first
    ffmpeg_path = os.getenv('FFMPEG_PATH')
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        print(f"Found FFmpeg at environment path: {ffmpeg_path}")
        return True
        
    # Check in PATH
    ffmpeg_in_path = shutil.which('ffmpeg')
    if ffmpeg_in_path:
        print(f"Found FFmpeg in PATH: {ffmpeg_in_path}")
        return True
        
    # Try common locations
    common_locations = [
        '/usr/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/opt/ffmpeg/ffmpeg'
    ]
    
    for location in common_locations:
        if os.path.exists(location):
            print(f"Found FFmpeg at: {location}")
            os.environ['FFMPEG_PATH'] = location
            return True
    
    print("ERROR: FFmpeg not found!")
    print("Searched locations:")
    print(f"- FFMPEG_PATH: {os.getenv('FFMPEG_PATH', 'Not set')}")
    print(f"- PATH: {os.getenv('PATH', 'Not set')}")
    print("- Common locations:", common_locations)
    return False

def run_ffmpeg_test():
    try:
        # Try to run FFmpeg version command
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            print("FFmpeg test successful!")
            print("Version info:", result.stdout.split('\n')[0])
            return True
        else:
            print("FFmpeg test failed!")
            print("Error:", result.stderr)
            return False
    except Exception as e:
        print("FFmpeg test failed with exception:", str(e))
        return False

def check_environment(skip_token_check=False):
    if skip_token_check:
        print("ℹ Skipping DISCORD_TOKEN check (build mode)")
        return True

    required_vars = ['DISCORD_TOKEN']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"✗ Missing environment variables: {', '.join(missing)}")
        return False
    print("✓ All required environment variables are set")
    return True

def check_python_packages():
    required = [
        'discord.py',
        'yt-dlp',
        'python-dotenv',
        'PyNaCl',
        'certifi',
        'aiohttp'
    ]
    try:
        import pkg_resources
        missing = []
        for package in required:
            try:
                pkg_resources.require(package)
            except pkg_resources.DistributionNotFound:
                missing.append(package)
        if missing:
            print(f"✗ Missing Python packages: {', '.join(missing)}")
            return False
        print("✓ All required Python packages are installed")
        return True
    except Exception as e:
        print(f"✗ Error checking packages: {e}")
        return False

def main():
    print("=== Starting Health Check ===")
    
    checks = [
        ("FFmpeg Installation", check_ffmpeg),
        ("FFmpeg Functionality", run_ffmpeg_test),
        ("Environment Variables", lambda: check_environment(os.environ.get('DOCKER_BUILD') == 'true')),
        ("Python Packages", check_python_packages)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        print(f"\nRunning {check_name} check...")
        try:
            if not check_func():
                all_passed = False
                print(f"❌ {check_name} check failed!")
            else:
                print(f"✅ {check_name} check passed!")
        except Exception as e:
            all_passed = False
            print(f"❌ {check_name} check failed with error: {str(e)}")
    
    print("\n=== Health Check Complete ===")
    if not all_passed:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
 