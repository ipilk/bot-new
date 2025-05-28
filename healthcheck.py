import os
import subprocess
import sys

def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            print("✓ FFmpeg is installed and working")
            return True
        else:
            print("✗ FFmpeg test failed")
            return False
    except Exception as e:
        print(f"✗ FFmpeg error: {e}")
        return False

def check_environment():
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
    print("\n=== Bot Health Check ===")
    checks = [
        ("Environment Variables", check_environment),
        ("FFmpeg Installation", check_ffmpeg),
        ("Python Packages", check_python_packages)
    ]
    
    all_passed = True
    for name, check in checks:
        print(f"\nChecking {name}...")
        if not check():
            all_passed = False
    
    if all_passed:
        print("\n✓ All checks passed!")
        return 0
    else:
        print("\n✗ Some checks failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
 