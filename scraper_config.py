"""Configuration and constants for JanitorAI Scraper"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

# Domain constants
JANITOR_DOMAIN = "janitorai.com"
JANNY_DOMAIN = "jannyai.com"
RENTRY_OPT_OUT_URL = "https://rentry.co/thisguyscrapes"

# Error detection patterns
ERROR_INDICATORS = ['"404"', "Page not found", "Oops", "not found"]
REQUIRED_CONTENT_INDICATORS = ["astro-island", "<h1", "character"]

# Regex patterns for data extraction
REGEX_PATTERNS = {
    "name": r'"name":\[0,"([^"]+)"',
    "creator": r'"creatorName":\[0,"([^"]+)"',
    "image_url": r'"imageUrl":\[0,"([^"]+)"',
    "description": r'"description":\[0,"((?:\\.|[^"])*?)"\],',
    "personality": r'"personality":\[0,"((?:\\.|[^"])*?)"\],',
    "scenario": r'"scenario":\[0,"([^"\\]+(?:\\.[^"\\]*)*)"',
    "first_message": r'"firstMessage":\[0,"([^"\\]+(?:\\.[^"\\]*)*)"',
    "example_dialogs": r'"exampleDialogs":\[0,"((?:\\.|[^"])*?)"\],',
    "chats_count": r"CHATS:\s*(\d+)",
    "creator_pattern": r"@([a-zA-Z0-9_-]+)",
}

# CSS Selectors
CSS_SELECTORS = {
    "virtuoso_scroller": "[data-virtuoso-scroller='true']",
    "virtuoso_scroller_alt": "[data-virtuoso-scroller]",
    "virtuoso_scroller_legacy": "[data-testid='virtuoso-scroller']",
    "virtuoso_item_list": "[data-testid='virtuoso-item-list'] > div",
    "character_links": 'a[href*="/characters/"]',
    "chat_links": 'a[href*="/chats/"]',
}


@dataclass
class ScraperConfig:
    """Configuration for JanitorAI Scraper"""
    
    message_limit: int = 4  # Minimum messages for a chat to be saved (default 4: bot-user-bot-user)
    headless: bool = False  # FIXED: Always False - browser must be visible for user login
    delay_between_requests: float = 2.0
    delay_between_chats: float = 3.0
    output_dir: str = "Output"
    max_retries: int = 3
    retry_wait_min: float = 1.0
    retry_wait_max: float = 10.0
    scroll_increment: int = 200
    scroll_wait_time: float = 0.3
    scroll_no_growth_threshold: int = 10
    max_scroll_iterations: int = 1500
    expansion_no_growth_threshold: int = 5
    chat_max_iterations: int = 1000
    keep_partial_extracts: bool = False  # Keep chats/character if message count is below limit
    keep_character_json: bool = False  # Save character JSON file alongside PNG (uses Example Character V3 format)
    extract_personas: bool = True  # Extract personas and generation settings from /my_personas
    organize_for_sillytavern: bool = True  # Organize files into SillyTavern-compatible folder structure
    recover_deleted_private_chats: bool = True  # Attempt to extract chat histories from deleted/private characters
    
    @property
    def output_path(self) -> Path:
        """Get output directory as Path object"""
        return Path(self.output_dir)
    
    @classmethod
    def from_user_input(cls) -> "ScraperConfig":
        """Create config from interactive user input"""
        print("JanitorAI Scraper Configuration")
        print("=" * 60)
        
        limit_input = input("Enter message count limit (default 4): ").strip()
        message_limit = int(limit_input) if limit_input.isdigit() else 4
        
        delay_input = input("Enter delay between requests in seconds (default 2.0): ").strip()
        try:
            delay_between_requests = float(delay_input) if delay_input else 2.0
        except ValueError:
            delay_between_requests = 2.0
        
        delay_chat_input = input("Enter delay between chats in seconds (default 3.0): ").strip()
        try:
            delay_between_chats = float(delay_chat_input) if delay_chat_input else 3.0
        except ValueError:
            delay_between_chats = 3.0
        
        keep_partial_input = input("Keep character JSON files if message count is below limit? (y/n, default y): ").strip().lower()
        keep_partial = keep_partial_input == "y"
        
        keep_json_input = input("Save character JSON file alongside PNG card? (y/n, default y): ").strip().lower()
        keep_json = keep_json_input == "y"
        
        extract_personas_input = input("Extract personas and generation settings? (y/n, default y): ").strip().lower()
        extract_personas = extract_personas_input != "n"
        
        organize_input = input("Organize files into SillyTavern folder structure? (y/n, default y): ").strip().lower()
        organize_sillytavern = organize_input != "n"
        
        recovery_input = input("Attempt to recover chat histories from deleted/private characters? (y/n, default y): ").strip().lower()
        recover_deleted_private = recovery_input != "n"
        
        return cls(
            message_limit=message_limit,
            delay_between_requests=delay_between_requests,
            delay_between_chats=delay_between_chats,
            keep_partial_extracts=keep_partial,
            keep_character_json=keep_json,
            extract_personas=extract_personas,
            organize_for_sillytavern=organize_sillytavern,
            recover_deleted_private_chats=recover_deleted_private,
        )
