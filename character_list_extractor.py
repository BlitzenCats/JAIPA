"""Extract character list and chats using network logging - Holy Grail approach"""

import json
import logging
import time
from typing import Optional, Dict, Any, List, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from browser_manager import BrowserManager
from network_logger import NetworkLogger
from scraper_config import ScraperConfig

logger = logging.getLogger(__name__)


class CharacterListExtractor:
    """Extract character list and chat data via network logging"""
    
    def __init__(self, browser_manager: BrowserManager, config: ScraperConfig):
        """Initialize character list extractor
        
        Args:
            browser_manager: BrowserManager instance
            config: ScraperConfig instance
        """
        self.browser = browser_manager
        self.config = config
        self.network_logger: Optional[NetworkLogger] = None
        self.character_list_responses: List[Dict[str, Any]] = []
        self.characters_by_id: Dict[str, Dict[str, Any]] = {}
        self.deleted_characters: List[str] = []
        self.private_characters: List[str] = []
        self.character_chats: Dict[str, List[Dict[str, Any]]] = {}
        self.total_characters_expected: int = 0  # From API response
        self.total_chats_expected: int = 0  # From API response
    
    def setup_network_logging(self) -> bool:
        """Initialize network logging via CDP and enable focus emulation
        
        Returns:
            True if successful, False otherwise
        """
        try:
            driver = self.browser.get_driver()
            if not driver:
                logger.error("No driver available for network logging")
                return False
            
            self.network_logger = NetworkLogger(driver)
            if not self.network_logger.enable_network_logging():
                logger.warning("Network logging not fully available")
            
            # Enable focus emulation so window doesn't need to stay focused
            try:
                driver.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
                logger.info("✓ Focus emulation enabled - browser will work in background")
            except Exception as e:
                logger.warning(f"Could not enable focus emulation: {e}")
            
            logger.info("Network logging initialized")
            return True
        
        except Exception as e:
            logger.error(f"Error setting up network logging: {e}")
            return False
    
    def extract_character_list(self) -> bool:
        """Extract all characters by scrolling and capturing network responses
        
        The page is already at janitorai.com/my_chats (loaded by caller).
        We just scroll to trigger all character-chats API pagination calls.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting character list extraction via network logging")
            
            if not self.network_logger:
                logger.error("Network logger not initialized")
                return False
            
            driver = self.browser.get_driver()
            
            # Wait for page to fully load
            logger.info("Waiting for character list to load...")
            time.sleep(3)
            
            # Prefer window scrolling for better network response capture
            logger.info("Using window scrolling (most reliable for API capture)")
            scroller = None  # Use None to indicate window scroll
            
            # Scroll through the entire list to load all characters
            logger.info("Scrolling to load all characters...")
            last_char_count = 0
            no_progress_count = 0
            max_no_progress = 8  # Increased from 5
            scroll_count = 0
            max_scrolls = 500  # Increased from 200
            
            while scroll_count < max_scrolls and no_progress_count < max_no_progress:
                # Scroll down using window scroll
                try:
                    scroll_increment = 3000 if self.config.turbo_mode else 1000
                    driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                    logger.debug(f"Scrolled window (scroll #{scroll_count + 1})")
                except Exception as e:
                    logger.warning(f"Scroll attempt {scroll_count + 1} failed: {e}")
                
                wait_time = self.config.scroll_wait_time if self.config.turbo_mode else 0.4
                time.sleep(wait_time) 
                scroll_count += 1
                
                # Process network responses
                self._process_network_responses()
                
                current_count = len(self.characters_by_id)
                
                if current_count > last_char_count:
                    logger.info(f"Loaded {current_count} characters (scroll #{scroll_count})...")
                    last_char_count = current_count
                    no_progress_count = 0
                else:
                    no_progress_count += 1
                    if no_progress_count % 2 == 1:
                        logger.debug(f"No new characters after scroll #{scroll_count} ({no_progress_count}/{max_no_progress})")
                
                # Log progress every 30 scrolls
                if scroll_count % 30 == 0:
                    logger.info(f"Progress: {scroll_count} scrolls, {current_count} characters loaded")
            
            if scroll_count >= max_scrolls:
                logger.warning(f"Reached maximum scroll count ({max_scrolls})")
            elif no_progress_count >= max_no_progress:
                logger.info(f"No new characters after {max_no_progress} consecutive scrolls - list is complete")
            
            # Scroll back to top to begin expanding characters
            logger.info("Scrolling back to top to begin expanding characters...")
            try:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                logger.info("✓ Scrolled to top")
            except Exception as e:
                logger.warning(f"Error scrolling to top: {e}")
            
            # Validate character count
            total_found = len(self.characters_by_id)
            total_deleted = len(self.deleted_characters)
            total_private = len(self.private_characters)
            
            # Calculate true unique count (accounting for characters that are both deleted+private)
            deleted_and_private = sum(1 for char_id, char_data in self.characters_by_id.items() 
                                     if char_data.get("is_deleted") and not char_data.get("is_public"))
            
            total_unique = len(self.characters_by_id)
            total_extracted = len(self.characters_by_id)  # Unique count
            
            # Log GUI-parseable progress info
            logger.info(f"[PROGRESS] Characters extracted: {total_unique}/{self.total_characters_expected}")
            if deleted_and_private > 0:
                logger.info(f"[PROGRESS] Breakdown: public={total_unique - total_deleted - total_private + deleted_and_private}, "
                           f"deleted={total_deleted}, private={total_private}, deleted+private={deleted_and_private}")
            else:
                logger.info(f"[PROGRESS] Breakdown: public={total_unique - total_deleted - total_private}, deleted={total_deleted}, private={total_private}")
            logger.info(f"[PROGRESS] Total chats expected: {self.total_chats_expected}")
            
            # Validate extraction
            if self.total_characters_expected > 0:
                if total_extracted == self.total_characters_expected:
                    logger.info(f"✓ Character count validation PASSED: {total_extracted}/{self.total_characters_expected}")
                else:
                    logger.warning(
                        f"⚠ Character count mismatch: extracted {total_extracted} "
                        f"but expected {self.total_characters_expected} "
                        f"(Note: {deleted_and_private} characters are both deleted+private)"
                    )
            
            logger.info(f"[OK] Character list extraction complete: {total_unique} total characters")
            
            # Log tracking info for GUI
            if self.deleted_characters:
                logger.info(f"[INFO] Deleted/Inaccessible characters: {total_deleted}")
            if self.private_characters:
                logger.info(f"[INFO] Private characters: {total_private}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error extracting character list: {e}", exc_info=True)
            return False
    
    def _process_network_responses(self) -> None:
        """Process character list from network responses"""
        try:
            if not self.network_logger:
                logger.debug("Network logger not available")
                return
            
            # Get all new responses
            responses = self.network_logger.get_responses()
            
            if not responses:
                logger.debug("No new network responses")
                return
            
            logger.debug(f"Processing {len(responses)} network responses")
            
            character_responses_found = 0
            
            for response in responses:
                url = response.get("url", "")
                
                # Look for character-chats API responses
                if "hampter/chats/character-chats" in url:
                    character_responses_found += 1
                    try:
                        body = response.get("body")
                        if isinstance(body, str):
                            data = json.loads(body)
                        else:
                            data = body
                        
                        # Log response details for debugging
                        char_count_in_response = len(data.get("characters", []))
                        has_more = data.get("hasMore", False)
                        page = data.get("page", 0)
                        total = data.get("totalCharacters", 0)
                        total_chats = data.get("totalChats", 0)
                        
                        # Track expected totals from first response
                        if self.total_characters_expected == 0 and total > 0:
                            self.total_characters_expected = total
                            self.total_chats_expected = total_chats
                            logger.info(f"[PROGRESS] API reports: {total} total characters, {total_chats} total chats")
                        
                        logger.debug(
                            f"Character-chats response: page={page}, "
                            f"chars_in_page={char_count_in_response}, "
                            f"hasMore={has_more}, total={total}"
                        )
                        
                        # Process this page of characters
                        self._process_character_list_response(data)
                    
                    except Exception as e:
                        logger.warning(f"Error processing character-chats response: {e}")
            
            if character_responses_found > 0:
                logger.debug(f"Found {character_responses_found} character-chats responses")
            else:
                logger.debug("No character-chats API responses found in this batch")
        
        except Exception as e:
            logger.warning(f"Error in _process_network_responses: {e}")
    
    def _process_character_list_response(self, data: Dict[str, Any]) -> None:
        """Process character list from API response
        
        Expected structure (from CharacterListNetworkResponse.txt):
        {
            "characters": [
                {
                    "character_id": "...",
                    "name": "...",
                    "is_deleted": false,
                    "is_public": true,
                    "chat_count": 2,
                    ...
                }
            ],
            "hasMore": true,
            "page": 1,
            "totalCharacters": 1360
        }
        
        Args:
            data: Response data from API
        """
        try:
            if not isinstance(data, dict):
                logger.warning(f"Expected dict response, got {type(data)}")
                return
            
            characters = data.get("characters", [])
            
            if not isinstance(characters, list):
                logger.warning(f"Expected characters list, got {type(characters)}")
                return
            
            if not characters:
                logger.debug("Response contains no characters")
                return
            
            new_chars_count = 0
            skipped_count = 0
            
            for char in characters:
                char_id = char.get("character_id")
                char_name = char.get("name", "Unknown")
                is_deleted = char.get("is_deleted", False)
                is_public = char.get("is_public", True)
                chat_count = char.get("chat_count", 0)
                
                if not char_id:
                    logger.debug(f"Skipping character without ID: {char_name}")
                    skipped_count += 1
                    continue
                
                # Skip if already processed
                if char_id in self.characters_by_id:
                    logger.debug(f"Character already in list: {char_name}")
                    skipped_count += 1
                    continue
                
                # Store character
                self.characters_by_id[char_id] = {
                    "id": char_id,
                    "name": char_name,
                    "is_deleted": is_deleted,
                    "is_public": is_public,
                    "chat_count": chat_count,
                    "data": char
                }
                new_chars_count += 1
                
                # Track deleted/private - handle all combinations
                categories = []
                if is_deleted:
                    self.deleted_characters.append(f"{char_name} (ID: {char_id}) | https://janitorai.com/characters/{char_id}")
                    categories.append("deleted")
                
                if not is_public:
                    self.private_characters.append(f"{char_name} (ID: {char_id}) | https://janitorai.com/characters/{char_id}")
                    categories.append("private")
                
                if not categories:
                    categories.append("public")
                
                # Log with all categories
                category_str = "+".join(categories)
                if len(categories) > 1:
                    logger.debug(f"Added {category_str} character: {char_name}")
                else:
                    logger.debug(f"Added character: {char_name} ({chat_count} chats) [{categories[0]}]")
            
            if new_chars_count > 0 or skipped_count > 0:
                logger.debug(f"Processed response: {new_chars_count} new, {skipped_count} skipped")
        
        except Exception as e:
            logger.error(f"Error processing character list response: {e}", exc_info=True)
    
    def is_on_my_chats_page(self) -> bool:
        """Check if we're on the /my_chats page
        
        Returns:
            True if on /my_chats page, False otherwise
        """
        try:
            driver = self.browser.get_driver()
            current_url = driver.current_url
            return "/my_chats" in current_url
        except Exception as e:
            logger.error(f"Error checking current page: {e}")
            return False
    
    def navigate_to_my_chats(self) -> bool:
        """Navigate back to /my_chats page
        
        Returns:
            True if successful, False otherwise
        """
        try:
            driver = self.browser.get_driver()
            
            # Check if we're already there
            if self.is_on_my_chats_page():
                logger.debug("Already on /my_chats page")
                return True
            
            logger.info("Navigating back to /my_chats page...")
            driver.get("https://janitorai.com/my_chats")
            time.sleep(2)  # Wait for page to load
            
            # Verify we're on the right page
            if self.is_on_my_chats_page():
                logger.info("✓ Successfully navigated back to /my_chats")
                # Re-enable network logging after navigation
                self.setup_network_logging()
                return True
            else:
                logger.warning("Failed to navigate to /my_chats")
                return False
        
        except Exception as e:
            logger.error(f"Error navigating to /my_chats: {e}", exc_info=True)
            return False
    
    def scroll_to_find_character(self, character_id: str, max_scrolls: int = 10) -> bool:
        """Scroll down the character list to find a specific character's accordion button
        
        Args:
            character_id: ID of character to find
            max_scrolls: Maximum number of scrolls to attempt
        
        Returns:
            True if found, False otherwise
        """
        try:
            driver = self.browser.get_driver()
            logger.debug(f"Scrolling to find character {character_id}")
            
            for scroll_attempt in range(max_scrolls):
                # Check if element is now visible
                try:
                    element = driver.find_element(By.ID, character_id)
                    logger.debug(f"Found character {character_id} after {scroll_attempt} scrolls")
                    return True
                except NoSuchElementException:
                    pass
                
                # Scroll down
                scroll_increment = 500 if self.config.turbo_mode else 300
                driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
                
                wait_time = self.config.scroll_wait_time if self.config.turbo_mode else 0.5
                time.sleep(wait_time)
            
            logger.warning(f"Could not find character {character_id} after {max_scrolls} scrolls")
            return False
        
        except Exception as e:
            logger.error(f"Error scrolling to find character: {e}", exc_info=True)
            return False
    
    def expand_character_to_get_chats(self, character_id: str) -> Optional[List[Dict[str, Any]]]:
        """Expand character to get chats via network response
        
        Strategy: Click the accordion button to expand, wait for the actual network response
        to arrive (via CDP), then immediately capture and collapse without unnecessary delays.
        Includes safety checks to avoid accidentally clicking chat links.
        
        Args:
            character_id: ID of character to expand
        
        Returns:
            List of chats or None
        """
        try:
            if not self.network_logger:
                logger.error("Network logger not initialized")
                return None
            
            driver = self.browser.get_driver()
            char_name = self.characters_by_id.get(character_id, {}).get("name", character_id)
            
            logger.debug(f"Expanding character {char_name} (ID: {character_id})")
            
            # Safety check: ensure we're on the my_chats page before expanding
            if not self.is_on_my_chats_page():
                logger.warning(f"Not on /my_chats page when trying to expand {char_name}. Navigating back...")
                if not self.navigate_to_my_chats():
                    logger.error(f"Failed to navigate back to /my_chats")
                    return None
            
            # Find the accordion button by ID
            try:
                logger.debug(f"Searching for accordion button with ID: {character_id}")
                accordion_div = driver.find_element(By.ID, character_id)
                logger.debug(f"Found accordion div with ID {character_id}")
                
                # Find the button INSIDE the div
                accordion_btn = accordion_div.find_element(By.TAG_NAME, "button")
                logger.debug(f"Found button inside accordion div")
                
                # Verify it's actually a button element
                tag_name = accordion_btn.tag_name.lower()
                logger.debug(f"Button tag name: {tag_name}")
                if tag_name != "button":
                    logger.warning(f"Element inside accordion is a {tag_name}, not a button. Skipping.")
                    return None
                
                # Scroll into view with instant jump (auto) instead of smooth scroll
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", accordion_btn)
                time.sleep(self.config.scroll_wait_time)  # Wait for layout to stabilize
                
                # Click to expand using execute_script to be more precise
                driver.execute_script("arguments[0].click();", accordion_btn)
                logger.debug(f"Clicked accordion for {char_name}")
                
                # Wait for the chats response to arrive and capture it
                target_url_pattern = f"hampter/chats/character/{character_id}/chats"
                chats = self._wait_for_and_capture_response(target_url_pattern, timeout=5.0)
                
                if chats is None:
                    logger.warning(f"Timeout waiting for chats response for {char_name}")
                    
                    # Check if we accidentally navigated away
                    if not self.is_on_my_chats_page():
                        logger.warning(f"Accidentally navigated away while expanding {char_name}")
                        self.navigate_to_my_chats()
                else:
                    # Store chats for later retrieval
                    self.character_chats[character_id] = chats
                
                # Collapse immediately after capturing
                try:
                    driver.execute_script("arguments[0].click();", accordion_btn)
                except:
                    pass  # Don't fail if collapse doesn't work
                
                return chats
            
            except NoSuchElementException:
                logger.warning(f"Could not find accordion button with ID={character_id}")
                
                # Try scrolling to find the character
                logger.debug("Attempting to scroll to find character...")
                if self.scroll_to_find_character(character_id, max_scrolls=10):
                    logger.info(f"Found character after scrolling, retrying expansion...")
                    # Retry the expansion
                    try:
                        accordion_div = driver.find_element(By.ID, character_id)
                        accordion_btn = accordion_div.find_element(By.TAG_NAME, "button")
                        
                        # Scroll into view
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", accordion_btn)
                        time.sleep(self.config.scroll_wait_time)
                        
                        # Click to expand
                        driver.execute_script("arguments[0].click();", accordion_btn)
                        logger.debug(f"Clicked accordion for {char_name} (after scroll retry)")
                        
                        # Wait for response
                        target_url_pattern = f"hampter/chats/character/{character_id}/chats"
                        chats = self._wait_for_and_capture_response(target_url_pattern, timeout=5.0)
                        
                        if chats is not None:
                            # Store chats for later retrieval
                            self.character_chats[character_id] = chats
                        
                        # Collapse
                        try:
                            driver.execute_script("arguments[0].click();", accordion_btn)
                        except:
                            pass
                        
                        return chats
                    
                    except Exception as retry_e:
                        logger.warning(f"Retry after scroll also failed: {retry_e}")
                        return None
                else:
                    logger.warning(f"Could not find character {char_name} even after scrolling")
                    
                    # Debug: List all accordion items
                    try:
                        all_accordions = driver.find_elements(By.CSS_SELECTOR, "[id^='accordionItem_']")
                        logger.debug(f"Available accordion items on page: {len(all_accordions)}")
                        
                        # Show first 5 accordion IDs for debugging
                        for i, accordion in enumerate(all_accordions[:5]):
                            acc_id = accordion.get_attribute("id")
                            logger.debug(f"  Accordion {i+1}: ID={acc_id}")
                    except Exception as e:
                        logger.debug(f"Could not list accordion items: {e}")
                
                # Check if we navigated away
                if not self.is_on_my_chats_page():
                    logger.warning(f"Lost accordion button - navigated away. Recovering...")
                    self.navigate_to_my_chats()

                return None
        
        except Exception as e:
            logger.error(f"Error expanding character: {e}", exc_info=True)
            # Try to recover by going back to /my_chats
            if not self.is_on_my_chats_page():
                logger.info("Attempting recovery by navigating back to /my_chats...")
                self.navigate_to_my_chats()
            return None
    
    def _wait_for_and_capture_response(self, url_pattern: str, timeout: float = 5.0) -> Optional[List[Dict[str, Any]]]:
        """Wait for a specific network response and capture chats data
        
        Uses CDP to monitor responses in real-time. When the response arrives,
        immediately captures and parses the chats data.
        
        Args:
            url_pattern: Pattern to match in response URL
            timeout: Maximum time to wait in seconds
        
        Returns:
            List of chats or None if timeout
        """
        import time as time_module
        start_time = time_module.time()
        
        while time_module.time() - start_time < timeout:
            if not self.network_logger:
                return None
            
            responses = self.network_logger.get_responses()
            
            for response in responses:
                if url_pattern in response.get("url", ""):
                    logger.debug(f"Response found: {url_pattern}")
                    
                    # Capture and parse immediately
                    try:
                        body = response.get("body")
                        if not body:
                            logger.warning(f"Response found but body is empty")
                            return None
                        
                        if isinstance(body, str):
                            data = json.loads(body)
                        else:
                            data = body
                        
                        chats = data.get("chats", [])
                        
                        if chats:
                            logger.info(f"[OK] Captured {len(chats)} chats from response")
                        
                        return chats
                    
                    except Exception as e:
                        logger.error(f"Error parsing response: {e}")
                        return None
            
            # Sleep briefly to avoid busy-waiting
            time_module.sleep(0.05)
        
        return None
    
    def get_character_info(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get stored character info
        
        Args:
            character_id: ID of character
        
        Returns:
            Character info dict or None
        """
        return self.characters_by_id.get(character_id)
    
    def get_character_chats(self, character_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get stored chats for character
        
        Args:
            character_id: ID of character
        
        Returns:
            List of chats or None
        """
        return self.character_chats.get(character_id)
    
    def get_all_valid_characters(self) -> Dict[str, Dict[str, Any]]:
        """Get all valid (non-deleted, public) characters
        
        Returns:
            Dict of character_id -> character info
        """
        valid = {}
        for char_id, char_data in self.characters_by_id.items():
            if not char_data.get("is_deleted", False) and char_data.get("is_public", True):
                valid[char_id] = char_data
        return valid
    
    def get_deleted_characters(self) -> Dict[str, Dict[str, Any]]:
        """Get all deleted characters
        
        Returns:
            Dict of character_id -> character info
        """
        deleted = {}
        for char_id, char_data in self.characters_by_id.items():
            if char_data.get("is_deleted", False):
                deleted[char_id] = char_data
        return deleted
    
    def get_private_characters(self) -> Dict[str, Dict[str, Any]]:
        """Get all private characters
        
        Returns:
            Dict of character_id -> character info
        """
        private = {}
        for char_id, char_data in self.characters_by_id.items():
            if not char_data.get("is_public", True):
                private[char_id] = char_data
        return private
    
    def cleanup(self) -> None:
        """Clean up network logger"""
        if self.network_logger:
            self.network_logger.disable_network_logging()
            logger.info("Network logger stopped")
