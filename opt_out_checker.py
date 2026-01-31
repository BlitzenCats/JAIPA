"""Rate limiting and opt-out checking for JanitorAI Scraper"""

import logging
import re
import time
from typing import Optional, Set

import requests
from bs4 import BeautifulSoup

from scraper_config import RENTRY_OPT_OUT_URL, REGEX_PATTERNS

logger = logging.getLogger(__name__)


class RateLimiter:
    """Handles rate limiting for requests"""
    
    def __init__(self, delay_between_requests: float = 2.0):
        """Initialize rate limiter
        
        Args:
            delay_between_requests: Delay in seconds between requests
        """
        self.delay = delay_between_requests
        self.last_request_time = 0
    
    def apply_limit(self, custom_delay: Optional[float] = None) -> None:
        """Apply rate limiting with jitter
        
        Args:
            custom_delay: Override default delay for this call
        """
        delay = custom_delay or self.delay
        elapsed = time.time() - self.last_request_time
        
        if elapsed < delay:
            # Add small random jitter (±10%) to avoid detection
            jitter = delay * 0.1 * (2 * (time.time() % 1) - 1)
            sleep_time = delay - elapsed + jitter
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def reset(self) -> None:
        """Reset rate limiter"""
        self.last_request_time = 0


class OptOutChecker:
    """Checks if creator is on opt-out list"""
    
    def __init__(self):
        """Initialize opt-out checker"""
        self.opted_out_creators: Set[str] = set()
        self.last_load_time = 0
        self.cache_duration = 3600  # 1 hour
    
    def load_opt_out_list(self, force_refresh: bool = False) -> bool:
        """Load opt-out list from rentry.co
        
        Args:
            force_refresh: Force reload even if cached
        
        Returns:
            True if successful
        """
        # Check cache
        current_time = time.time()
        if (not force_refresh and
            self.opted_out_creators and
            (current_time - self.last_load_time) < self.cache_duration):
            logger.debug("Using cached opt-out list")
            return True
        
        try:
            logger.info(f"Loading opt-out list from {RENTRY_OPT_OUT_URL}...")
            
            response = requests.get(RENTRY_OPT_OUT_URL, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Failed to load opt-out list (status {response.status_code})")
                return False
            
            # Parse the page to find creator names
            soup = BeautifulSoup(response.content, "html.parser")
            text = soup.get_text()
            
            # Find all @creator patterns
            creator_pattern = REGEX_PATTERNS.get("creator_pattern", r"@([a-zA-Z0-9_-]+)")
            matches = re.findall(creator_pattern, text)
            
            # Add both @name and name to the set for flexibility
            self.opted_out_creators = set()
            for match in matches:
                self.opted_out_creators.add(match.lower())
                self.opted_out_creators.add(f"@{match.lower()}")
            
            self.last_load_time = current_time
            
            logger.info(f"Loaded {len(matches)} opted-out creators")
            
            if matches[:5]:
                logger.debug(f"Sample: {', '.join(matches[:5])}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading opt-out list: {e}")
            return False
    
    def is_opted_out(self, creator_name: Optional[str]) -> bool:
        """Check if creator is opted out
        
        Args:
            creator_name: Creator name to check
        
        Returns:
            True if creator is opted out
        """
        if not creator_name:
            return False
        
        normalized = creator_name.lower().strip()
        return normalized in self.opted_out_creators
    
    def clear_cache(self) -> None:
        """Clear the opt-out cache"""
        self.opted_out_creators.clear()
        self.last_load_time = 0
