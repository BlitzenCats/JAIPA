"""Character data extraction and parsing for JanitorAI Scraper"""

import logging
import re
from html import unescape
from typing import Optional, Dict, Any

from bs4 import BeautifulSoup

from scraper_config import REGEX_PATTERNS, ERROR_INDICATORS, REQUIRED_CONTENT_INDICATORS

logger = logging.getLogger(__name__)


class CharacterDataParser:
    """Parses character data from HTML and JSON"""
    
    @staticmethod
    def parse_astro_props(props_attr: str) -> Dict[str, str]:
        """Extract character data from astro-island props
        
        Args:
            props_attr: Props attribute containing character data
        
        Returns:
            Dictionary of extracted character data
        """
        data = {}
        
        for key, pattern in REGEX_PATTERNS.items():
            if key == "chats_count" or key == "creator_pattern":
                continue  # Skip non-character patterns
            
            match = re.search(pattern, props_attr, re.DOTALL)
            if match:
                value = match.group(1)
                
                # Unescape HTML entities and clean up
                value = unescape(value)
                value = value.replace("\\n", "\n")
                value = value.replace("\\\"", "\"")
                value = re.sub(r"<[^>]+>", "", value)  # Remove HTML tags
                
                data[key] = value
        
        return data
    
    @staticmethod
    def parse_html_fallback(soup: BeautifulSoup) -> Dict[str, str]:
        """Extract character data from HTML as fallback
        
        Args:
            soup: BeautifulSoup object of page
        
        Returns:
            Dictionary of extracted character data
        """
        data = {}
        
        # Extract name from h1
        h1_tag = soup.find("h1")
        if h1_tag:
            data["name"] = h1_tag.get_text(strip=True)
            logger.debug(f"Found name from h1: {data['name']}")
        
        # Extract description from markdown div
        markdown_div = soup.find("div", class_="markdown")
        if markdown_div:
            description_text = markdown_div.get_text(separator="\n", strip=True)
            if description_text:
                data["description"] = description_text[:500]
                logger.debug(f"Found description from markdown: {description_text[:50]}...")
        
        # Find image URL
        img_tags = soup.find_all("img")
        for img in img_tags:
            src = img.get("src", "")
            alt = img.get("alt", "")
            
            if "bot-avatar" in src or "character" in alt.lower():
                if src.startswith("http"):
                    data["image_url"] = src
                elif src.startswith("/"):
                    data["image_url"] = f"https://jannyai.com{src}"
                
                if data.get("image_url"):
                    logger.debug(f"Found image URL: {data['image_url'][:60]}...")
                    break
        
        # Fallback image from og:image
        if "image_url" not in data:
            og_image = soup.find("meta", property="og:image")
            if og_image:
                data["image_url"] = og_image.get("content")

        # Extract tags
        # Expecting structure: ul > li > (a or span) > text
        # - Regular tags have <a> elements
        # - NSFW/SFW badges have <span> elements
        tags_ul = soup.find("ul", class_=lambda x: x and all(c in x for c in ["flex", "max-w-full", "flex-wrap"]))
        if tags_ul:
            tags = []
            for li in tags_ul.find_all("li"):
                # First try to find tag link (regular tags)
                tag_link = li.find("a")
                if tag_link:
                    tag_text = tag_link.get_text(strip=True)
                else:
                    # Fall back to span (NSFW/SFW badges)
                    tag_span = li.find("span")
                    if tag_span:
                        tag_text = tag_span.get_text(strip=True)
                    else:
                        tag_text = None
                
                if tag_text:
                    tags.append(tag_text)
            
            if tags:
                data["tags"] = tags
                logger.debug(f"Found {len(tags)} tags: {tags[:3]}...")
        
        # Extract from text sections (use separator to preserve structure)
        all_text = soup.get_text(separator="\n")
        
        if "Personality:" in all_text:
            start = all_text.find("Personality:")
            end = all_text.find("Scenario:", start)
            if end == -1:
                end = len(all_text)
            data["personality"] = all_text[start + 12:end].strip()[:500]
        
        if "Scenario:" in all_text:
            start = all_text.find("Scenario:")
            end = all_text.find("First Message:", start)
            if end == -1:
                end = all_text.find("Example", start)
            if end == -1:
                end = len(all_text)
            data["scenario"] = all_text[start + 9:end].strip()[:500]
        
        if "First Message:" in all_text:
            start = all_text.find("First Message:")
            end = all_text.find("Example", start)
            if end == -1:
                end = len(all_text)
            data["first_message"] = all_text[start + 14:end].strip()[:500]
        
        return data
    
    @staticmethod
    def validate_character_data(data: Dict[str, Any]) -> bool:
        """Validate extracted character data
        
        Args:
            data: Character data dictionary
        
        Returns:
            True if data appears valid, False otherwise
        """
        # Check for error pages
        name = data.get("name", "").lower()
        if "oops" in name and "not found" in name:
            logger.warning(f"Detected error page: {name}")
            return False
        
        # Check for required fields
        if not data.get("name"):
            logger.warning("Character data missing name")
            return False
        
        return True
    
    @staticmethod
    def is_error_page(page_source: str) -> bool:
        """Check if page is an error page
        
        Args:
            page_source: HTML page source
        
        Returns:
            True if error page detected
        """
        # Check for explicit error indicators
        for indicator in ERROR_INDICATORS:
            if indicator in page_source:
                # Check that page doesn't have required content
                has_content = any(
                    content in page_source
                    for content in REQUIRED_CONTENT_INDICATORS
                )
                if not has_content:
                    return True
        
        return False


class CharacterDataValidator:
    """Validates and normalizes character data"""
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = None) -> str:
        """Sanitize text field
        
        Args:
            text: Text to sanitize
            max_length: Maximum length to keep
        
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Unescape HTML
        text = unescape(text)
        
        # Normalize whitespace but PRESERVE newlines
        # 1. Replace multiple spaces/tabs with single space
        text = re.sub(r'[ \t]+', ' ', text)
        # 2. Replace multiple newlines with double newline (paragraph break)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        if max_length and len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    @staticmethod
    def create_default_character() -> Dict[str, Any]:
        """Create default character data structure
        
        Returns:
            Default character data
        """
        return {
            "name": "Unknown Character",
            "description": "",
            "personality": "",
            "scenario": "",
            "first_message": "",
            "example_dialogs": "",
            "url": "",
            "image_url": None,
            "creator": "Unknown Creator",
            "tags": [],
            "extracted_at": None,
        }
