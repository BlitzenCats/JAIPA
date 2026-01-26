# JanitorAI Scraper

A tool for backing up your character chats and cards from JanitorAI.
BIG NOTE: You need Chrome in order to use the current release (v1.0.4)

## What It Does

- Downloads character cards (PNG + JSON) and chat histories (JSONL)
- Organizes files for direct import into SillyTavern
- Exports your user personas and generation settings
- Uses network interception to capture data efficiently
- Includes a dark-themed GUI for configuration
- Handles rate limits and can recover chats from deleted/private characters

## Installation

### Option 1: Download the Executable
Run `JanitorAI_Scraper.exe` - no installation needed.

### Option 2: Run from Source
1. Install Python 3.10 or newer
2. Install dependencies:
   ```bash
   pip install selenium Pillow requests beautifulsoup4 jsonlines
   ```
3. Run the GUI:
   ```bash
   python scraper_gui.py
   ```

## Building the Executable

If you want to build the `.exe` yourself:

1. Install dependencies (including `pyinstaller`)
2. Run:
   ```bash
   python build_exe.py
   ```
3. Find the executable in the `dist` folder

## Project Structure

### Core Files
- **`scraper_gui.py`** - Main GUI and thread management
- **`holy_grail_scraper.py`** - Orchestrates the scraping process
- **`scraper_config.py`** - Configuration settings

### Data Handlers
- **`character_list_extractor.py`** - Loads the full character list
- **`chat_network_extractor.py`** - Captures chat data from network traffic
- **`card_creator.py`** - Generates V3 character card files
- **`file_manager.py`** - File I/O and directory management
- **`file_organizer.py`** - Organizes output for SillyTavern
- **`browser_manager.py`** - Selenium WebDriver setup

### Utilities
- **`js_scripts.py`** - JavaScript for browser data extraction
- **`scraper_utils.py`** - Text sanitization and logging
- **`opt_out_checker.py`** - Checks creator opt-out list

## Settings

The GUI lets you configure:
- **Message Limit** - Minimum messages to save a chat
- **Delays** - Adjust scraping speed
- **Output Folder** - Where files are saved

For more options, edit defaults in `scraper_config.py`.

## Contributing

Fork the repo, make your changes, and submit a pull request.

Potential improvements:
- Better edge case handling for unusual chat formats
- Support for other frontend formats beyond SillyTavern
- UI improvements

## Disclaimer

This tool is for personal backups. Respect creator rights and opt-out requests.
