"""Character info fetching for JanitorAI Scraper"""

import logging
import time
from typing import Optional, Dict, Any

from bs4 import BeautifulSoup

from browser_manager import BrowserManager
from character_parser import CharacterDataParser, CharacterDataValidator
from scraper_utils import janitor_to_janny_url, normalize_url

logger = logging.getLogger(__name__)


class CharacterFetcher:
    """Fetches and extracts character information"""
    
    def __init__(self, browser_manager: BrowserManager):
        """Initialize character fetcher
        
        Args:
            browser_manager: BrowserManager instance
        """
        self.browser = browser_manager
        self.parser = CharacterDataParser()
        self.validator = CharacterDataValidator()
    
    def get_character_info(self, character_url: str) -> Optional[Dict[str, Any]]:
        """Get character information from jannyai
        
        Args:
            character_url: URL of character
        
        Returns:
            Character data dictionary or None
        """
        # Normalize URL
        character_url = normalize_url(character_url)
        jannyai_url = janitor_to_janny_url(character_url)
        
        logger.info(f"Fetching character from: {jannyai_url}")
        
        # Load page
        if not self._load_page(jannyai_url):
            return None
        
        page_source = self.browser.get_page_source()
        
        # Check for error page
        if self.parser.is_error_page(page_source):
            logger.warning("Page returned 404 or not found")
            return None
        
        # Create default data
        character_data = self.validator.create_default_character()
        character_data["url"] = jannyai_url
        character_data["extracted_at"] = time.time()
        
        # Parse HTML
        soup = BeautifulSoup(page_source, "html.parser")
        
        # Try astro-island props first
        extracted_from_props = self._extract_from_astro_props(soup, character_data)
        
        # Fallback to HTML extraction
        if not extracted_from_props:
            logger.debug("Falling back to HTML extraction...")
            html_data = self.parser.parse_html_fallback(soup)
            character_data.update(html_data)
        else:
            # Even if we got data from props, still extract tags from HTML
            # since tags aren't available in the astro props regex patterns
            html_data = self.parser.parse_html_fallback(soup)
            if "tags" in html_data:
                character_data["tags"] = html_data["tags"]
                logger.debug(f"Extracted {len(html_data['tags'])} tags from HTML")
        
        # Validate
        if not self.parser.validate_character_data(character_data):
            return None
        
        logger.info(f"✓ Successfully extracted character data")
        return character_data
    
    def _load_page(self, url: str, scroll_for_content: bool = True) -> bool:
        """Load page and wait for content
        
        Args:
            url: URL to load
            scroll_for_content: Whether to scroll for lazy-loaded content
        
        Returns:
            True if successful
        """
        try:
            if not self.browser.navigate_to(url, wait_time=5):
                return False
            
            if scroll_for_content:
                logger.debug("Scrolling page to load all content...")
                
                # Scroll to top
                self.browser.scroll_to_top(0.5)
                
                # Scroll down incrementally
                for i in range(5):
                    self.browser.scroll_by(0, 500, 0.5)
                
                # Scroll to bottom
                self.browser.scroll_to_bottom(2)
                
                # Back to top
                self.browser.scroll_to_top(1)
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading page: {e}")
            return False
    
    def _extract_from_astro_props(
        self,
        soup: BeautifulSoup,
        character_data: Dict[str, Any]
    ) -> bool:
        """Try to extract data from astro-island props
        
        Args:
            soup: BeautifulSoup object
            character_data: Dictionary to update with extracted data
        
        Returns:
            True if successful extraction from props
        """
        astro_islands = soup.find_all("astro-island")
        
        for island in astro_islands:
            props_attr = island.get("props")
            
            if not props_attr or "character" not in props_attr.lower():
                continue
            
            logger.debug("Found astro-island with character props")
            
            # Parse props
            props_data = self.parser.parse_astro_props(props_attr)
            
            if not props_data:
                continue
            
            # Map parsed field names to our data structure
            field_mapping = {
                "name": "name",
                "creator": "creator",
                "image_url": "image_url",
                "description": "description",
                "personality": "personality",
                "scenario": "scenario",
                "first_message": "first_message",
                "example_dialogs": "example_dialogs",
            }
            
            for src_field, dest_field in field_mapping.items():
                if src_field in props_data:
                    character_data[dest_field] = self.validator.sanitize_text(
                        props_data[src_field]
                    )
                    if props_data[src_field]:
                        logger.debug(
                            f"Found {src_field}: {props_data[src_field][:50]}..."
                        )
            
            return True
        
        return False
