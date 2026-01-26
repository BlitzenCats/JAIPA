"""
JanitorAI Web Scraper - Refactored Version
Extracts characters and chat histories from JanitorAI with proper architecture

Usage:
    python main.py

Requirements:
    - Selenium 4
    - BeautifulSoup4
    - undetected-chromedriver (for bot detection bypass)
    - Pillow (for character card creation)
"""

import logging
import sys
from pathlib import Path

from scraper_config import ScraperConfig
from scraper_utils import setup_logging
from holy_grail_scraper import HolyGrailScraper

# Setup logging first
setup_logging("janitor_scraper.log")
logger = logging.getLogger(__name__)


def print_header():
    """Print welcome header"""
    print("=" * 70)
    print("JanitorAI Web Scraper - Refactored")
    print("=" * 70)
    print("Extracts characters and chat histories from JanitorAI")
    print("Proper error handling | Modular architecture | Full logging")
    print("=" * 70)
    print()


def print_instructions():
    """Print login instructions"""
    print("=" * 70)
    print("IMPORTANT LOGIN INSTRUCTIONS:")
    print("=" * 70)
    print("1. A Chrome browser window will open")
    print("2. You MUST log into https://janitorai.com in that window")
    print("3. Once logged in, navigate to https://janitorai.com/my_chats")
    print("4. Then return to this terminal and press Enter")
    print("=" * 70)
    print()


def main():
    """Main entry point"""
    try:
        print_header()
        
        # Get configuration from user
        logger.info("Collecting configuration from user...")
        config = ScraperConfig.from_user_input()
        
        logger.info(f"Configuration:")
        logger.info(f"  Message limit: {config.message_limit}")
        logger.info(f"  Headless mode: {config.headless}")
        logger.info(f"  Delay between requests: {config.delay_between_requests}s")
        logger.info(f"  Delay between chats: {config.delay_between_chats}s")
        logger.info(f"  Output directory: {config.output_path}")
        
        # Create scraper (uses HolyGrailScraper for network-logging approach)
        scraper = HolyGrailScraper(config)
        
        logger.info("Starting Holy Grail Scraper...")
        logger.info("=" * 70)
        
        # Print login instructions before opening browser
        print_instructions()
        
        # Run scraper (opens browser here)
        scraper.run()
        
        logger.info("\nScraping completed!")
        logger.info(f"Output files saved to: {config.output_path.absolute()}")
    
    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
