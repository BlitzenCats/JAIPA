"""Build script for JanitorAI Scraper EXE"""

import subprocess
import sys
from pathlib import Path


def build_exe():
    """Build the scraper as a single executable"""
    
    # Get the project directory
    project_dir = Path(__file__).parent
    
    # Main script to package
    main_script = project_dir / "scraper_gui.py"
    
    if not main_script.exists():
        print(f"Error: {main_script} not found!")
        return False
    
    print("=" * 60)
    print("Building JanitorAI Scraper EXE")
    print("=" * 60)
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                          # Single exe
        "--windowed",                         # No console window
        "--name", "JanitorAI_Scraper",        # Exe name
        # Icon configuration
        "--icon", "icon.ico" if (project_dir / "icon.ico").exists() else "NONE",
        
        # Hidden imports for modules that PyInstaller might miss
        "--hidden-import", "selenium",
        "--hidden-import", "selenium.webdriver",
        "--hidden-import", "selenium.webdriver.chrome",
        "--hidden-import", "selenium.webdriver.chrome.service",
        "--hidden-import", "selenium.webdriver.chrome.options",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.PngImagePlugin",
        "--hidden-import", "requests",
        "--hidden-import", "bs4",
        "--hidden-import", "jsonlines",
        
        # Collect all data files
        "--collect-all", "selenium",
        
        # Main script
        str(main_script),
    ]
    
    print(f"Running: {' '.join(cmd[:10])}...")
    print()
    
    try:
        result = subprocess.run(cmd, cwd=str(project_dir), check=True)
        print()
        print("=" * 60)
        print("BUILD SUCCESSFUL!")
        print("=" * 60)
        print(f"Executable: {project_dir / 'dist' / 'JanitorAI_Scraper.exe'}")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        return False
    
    except FileNotFoundError:
        print("PyInstaller not found! Install with: pip install pyinstaller")
        return False


def install_requirements():
    """Install required packages for building"""
    packages = [
        "pyinstaller",
        "selenium",
        "Pillow",
        "requests",
        "beautifulsoup4",
        "jsonlines",
    ]
    
    print("Installing required packages...")
    for pkg in packages:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    print("Done!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build JanitorAI Scraper EXE")
    parser.add_argument("--install", action="store_true", help="Install required packages first")
    args = parser.parse_args()
    
    if args.install:
        install_requirements()
    
    success = build_exe()
    sys.exit(0 if success else 1)
