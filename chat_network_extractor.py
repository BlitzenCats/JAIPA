"""Chat extraction using network logging - New approach for API response capture"""

import json
import logging
import time
from typing import Optional, Dict, Any, List

from selenium.webdriver.common.by import By

from browser_manager import BrowserManager
from card_creator import MessageParser
from chat_network_parser import ChatNetworkParser
from network_logger import NetworkLogger
from scraper_config import ScraperConfig

logger = logging.getLogger(__name__)


class ChatNetworkExtractor:
    """Extracts chat history by capturing network API responses"""
    
    def __init__(
        self,
        browser_manager: BrowserManager,
        rate_limiter,
        config: ScraperConfig
    ):
        """Initialize chat network extractor
        
        Args:
            browser_manager: BrowserManager instance
            rate_limiter: RateLimiter instance
            config: ScraperConfig instance
        """
        self.browser = browser_manager
        self.rate_limiter = rate_limiter
        self.config = config
        self.message_parser = MessageParser()
        self.network_logger: Optional[NetworkLogger] = None
        self.alternate_greetings: List[Dict[str, Any]] = []  # Store alternate greetings
    
    def setup_network_logging(self) -> bool:
        """Initialize network logging
        
        Returns:
            True if successful, False otherwise
        """
        try:
            driver = self.browser.get_driver()
            if not driver:
                logger.error("No driver available for network logging")
                return False
            
            self.network_logger = NetworkLogger(driver)
            success = self.network_logger.enable_network_logging()
            
            if success:
                logger.info("[OK] Network logging initialized for chat extraction")
            else:
                logger.warning("Network logging not fully available")
                self.network_logger = None
            
            return success
        except Exception as e:
            logger.error(f"Error setting up network logging: {e}")
            self.network_logger = None
            return False
    
    def cleanup_network_logging(self) -> None:
        """Clean up network logging resources"""
        if self.network_logger:
            try:
                self.network_logger.disable_network_logging()
                logger.debug("Network logging disabled")
            except Exception as e:
                logger.debug(f"Error disabling network logging: {e}")
    
    def extract_persona_from_html(self) -> Optional[str]:
        """Extract user persona name from the HTML page source
        
        FIX: Parse page source directly to extract window._storeState_
        This is more reliable than JavaScript execution
        
        The persona name is in: window._storeState_.user.profile.name
        
        Returns:
            Persona name or None
        """
        try:
            driver = self.browser.get_driver()
            if not driver:
                logger.warning("No driver available for persona extraction")
                return None
            
            # Get page source directly
            page_source = driver.page_source
            
            # Find the script tag containing window._storeState_
            # Pattern: window._storeState_ = JSON.parse("{...escaped json...}");
            import re
            pattern = r'window\._storeState_\s*=\s*JSON\.parse\("({[^"]*(?:\\.[^"]*)*)"\);'
            match = re.search(pattern, page_source)
            
            if not match:
                logger.debug("Could not find window._storeState_ in page source")
                return None
            
            # Extract the escaped JSON string
            escaped_json = match.group(1)
            
            # Unescape the JSON string
            # It's been escaped for JavaScript, so we need to decode it
            unescaped_json = escaped_json.encode('utf-8').decode('unicode_escape')
            
            # Parse the JSON
            store_state = json.loads(unescaped_json)
            
            # Extract persona name from user.profile.name
            persona_name = store_state.get("user", {}).get("profile", {}).get("name")
            
            if persona_name and isinstance(persona_name, str) and persona_name.strip():
                logger.info(f"✓ Extracted persona name from page source: {persona_name}")
                return persona_name.strip()
            
            logger.debug("Persona name not found in _storeState_")
            return None
            
        except json.JSONDecodeError as e:
            logger.debug(f"Error parsing _storeState_ JSON: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error extracting persona from page source: {e}")
            return None
    
    def get_chat_history_from_network(self, chat_url: str) -> Optional[Dict[str, Any]]:
        """Get chat history by capturing the network API response
        
        Follows proper Selenium navigation: setup CDP -> clear logs -> navigate -> capture
        
        Args:
            chat_url: URL of chat (e.g., janitorai.com/chats/[CHATID])
        
        Returns:
            Chat data dictionary from API response or None
        """
        if not self.network_logger:
            logger.warning("Network logger not initialized")
            return None
        
        logger.info(f"Extracting chat via network API: {chat_url}")
        
        # Apply rate limiting
        self.rate_limiter.apply_limit(self.config.delay_between_chats)
        
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                # Step 1: Prepare network logger (enable CDP, clear data, clear logs)
                # This MUST happen before navigation
                if not self.network_logger.prepare_for_navigation():
                    logger.error("Failed to prepare network logger")
                    return None
                
                # Step 2: Navigate to chat (triggers network requests)
                # Now that CDP is listening and logs are cleared, navigate
                logger.debug(f"Navigating to chat URL (attempt {attempt}/{max_retries})")
                wait_time = 1 if self.config.turbo_mode else 4
                if not self.browser.navigate_to(chat_url, wait_time=wait_time):
                    logger.error("Failed to navigate to chat URL")
                    return None
                
                # Step 3: Wait and capture network response
                # CDP should have captured the requests during navigation
                timeout = 15
                chat_data = self.network_logger.extract_chat_data(chat_url, timeout=timeout)
                
                if chat_data:
                    logger.info(f"[OK] Retrieved chat data from network API on attempt {attempt}")
                    return chat_data
                else:
                    if attempt < max_retries:
                        logger.warning(f"No chat data captured (attempt {attempt}/{max_retries}), reloading page and retrying...")
                        # Use proper Selenium navigation to refresh
                        self.browser.get_driver().navigate().refresh()
                        time.sleep(2)  # Wait for page to reload
                    else:
                        logger.warning("No chat data captured from network after all retries")
                        return None
            
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Error extracting chat (attempt {attempt}/{max_retries}): {e}, retrying...")
                    # Use proper Selenium navigation to refresh
                    self.browser.get_driver().navigate().refresh()
                    time.sleep(2)
                else:
                    logger.error(f"Error extracting chat from network: {e}")
                    return None
        
        return None
    
    def parse_chat_api_response(self, api_response: Dict[str, Any], user_persona_name: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Parse API response to extract messages using ChatNetworkParser
        
        Goals implemented:
        1. Parse network response and order by time (oldest first)
        2. Handle alternate greetings (first_message vs first_messages)
        3. Manage swipe behavior based on is_main boolean
        4. Retrieve created_at times
        
        Args:
            api_response: Raw API response dictionary
            user_persona_name: User's persona name from HTML extraction
        
        Returns:
            List of parsed messages in JSONL format or None
        """
        try:
            # Parse using ChatNetworkParser which handles all 4 goals
            parsed_chat = ChatNetworkParser.parse_api_response(api_response, user_persona_name)
            
            if not parsed_chat:
                logger.warning("Failed to parse API response")
                return None
            
            # Get messages - already in proper JSONL format from parser
            messages = parsed_chat.get("messages", [])
            
            if not messages:
                logger.warning("No messages extracted from parsed response")
                return None
            
            logger.info(f"Parsed {len(messages)} messages from API response")
            
            # Extract alternate greetings separately (Goal 2)
            # Clear previous alternates before extracting new ones
            self.alternate_greetings = []
            alternate_greetings = ChatNetworkParser.extract_alternate_greetings(api_response)
            if alternate_greetings:
                logger.info(f"Found {len(alternate_greetings)} alternate greetings")
                # Store for potential later use in character card
                self.alternate_greetings = alternate_greetings
            
            return messages if messages else None
        
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            return None
    
    def get_chat_history(self, chat_url: str) -> Optional[List[Dict[str, Any]]]:
        """Get chat history by monitoring network responses
        
        Handles the two [CHAT ID] responses - one is React framework data,
        the other contains the actual chat messages
        
        Args:
            chat_url: URL of chat (e.g., janitorai.com/chats/[CHAT_ID])
        
        Returns:
            List of message dictionaries or None
        """
        chat_id = chat_url.rstrip('/').split('/')[-1]
        logger.info(f"Extracting chat history for ID: {chat_id}")
        
        # Apply rate limiting
        self.rate_limiter.apply_limit(self.config.delay_between_chats)
        
        # Navigate to chat page (triggers the two API calls)
        if not self.network_logger:
            logger.error("Network logger not initialized")
            return None
        
        # Prepare for navigation
        if not self.network_logger.prepare_for_navigation():
            logger.error("Failed to prepare network logger")
            return None
        
        # Navigate to the chat (triggers API calls)
        wait_time = 1 if self.config.turbo_mode else 4
        if not self.browser.navigate_to(chat_url, wait_time=wait_time):
            logger.error("Failed to navigate to chat URL")
            return None
        
        # Capture all responses containing this chat ID (loop for up to 5s for robustness)
        all_responses = []
        capture_start = time.time()
        capture_timeout = 5.0
        
        while time.time() - capture_start < capture_timeout:
            captured = self.network_logger.parse_network_responses()
            
            for request_id, metadata in captured.items():
                if chat_id in metadata['url']:
                    logger.debug(f"Found matching URL: {metadata['url']}")
                    body = self.network_logger.get_response_body(request_id)
                    
                    if body:
                        try:
                            data = json.loads(body)
                            all_responses.append({
                                'url': metadata['url'],
                                'data': data
                            })
                            logger.debug(f"Captured response from {metadata['url']}")
                        except json.JSONDecodeError as e:
                            logger.debug(f"Failed to parse JSON from {metadata['url']}: {e}")
            
            # Check if we've found the actual chat data response (not just framework data)
            # breaking early if we have the "meat" of the response
            if any('chatMessages' in r['data'] or 'character' in r['data'] for r in all_responses if isinstance(r.get('data'), dict)):
                break
                
            time.sleep(0.5)
        
        logger.info(f"Found {len(all_responses)} total responses for chat {chat_id} after polling")
        
        # Identify the correct response (not the React framework)
        for idx, resp in enumerate(all_responses, 1):
            data = resp['data']
            logger.debug(f"Response {idx} type: {type(data).__name__}")
            
            # Check if this looks like chat data (has messages/history)
            if isinstance(data, dict):
                keys = list(data.keys())
                logger.debug(f"Response {idx} keys: {keys}")
                
                # Look for actual chat API response structure
                # Real chat response has: character, chat, chatMessages
                if 'chatMessages' in data or 'character' in data:
                    logger.info(f"[OK] Found chat data response (keys: {', '.join(keys[:5])})")
                    logger.debug(f"Response has {len(data.get('chatMessages', []))} messages in chatMessages")
                    
                    # Extract persona name from HTML BEFORE parsing
                    user_persona_name = self.extract_persona_from_html()
                    
                    # Parse the API response into messages with persona name
                    messages = self.parse_chat_api_response(data, user_persona_name)
                    if messages:
                        logger.info(f"[OK] Parsed {len(messages)} messages from chat API response")
                        return messages
                    else:
                        logger.warning("Failed to parse chat data response")
                        continue
                # Fallback: Look for message-like structure
                elif 'messages' in data:
                    logger.info(f"Found chat data with 'messages' key ({len(data.get('messages', []))} messages)")
                    return data
                elif 'history' in data:
                    logger.info(f"Found chat data with 'history' key ({len(data.get('history', []))} messages)")
                    return data
                elif isinstance(data.get('data'), list):
                    logger.info(f"Found chat data with 'data' array ({len(data.get('data', []))} items)")
                    return data
            elif isinstance(data, list):
                # Might be a direct array of messages
                if len(data) > 0:
                    first_item = data[0]
                    if isinstance(first_item, dict) and 'message' in first_item:
                        logger.info(f"Found direct message array ({len(data)} messages)")
                        return data
        
        logger.warning(f"Could not identify correct response for chat {chat_id}")
        
        # Debug: Log the structure of responses that we couldn't identify
        for idx, resp in enumerate(all_responses, 1):
            data = resp['data']
            if isinstance(data, dict):
                logger.debug(f"Response {idx} structure: {list(data.keys())}")
                # Show first few items if it's a dict
                if len(data) <= 5:
                    logger.debug(f"Response {idx} full content: {json.dumps(data, default=str)[:500]}")
            elif isinstance(data, list) and len(data) > 0:
                logger.debug(f"Response {idx} is list with {len(data)} items")
                if isinstance(data[0], dict):
                    logger.debug(f"Response {idx} first item keys: {list(data[0].keys())}")
        
        logger.debug(f"As a fallback, trying to return single response...")
        
        # As a fallback, if there's only 1 response, return it even if we can't identify
        # (Sometimes the API structure changes or we get partial data)
        if len(all_responses) == 1:
            logger.warning(f"Returning single response for chat {chat_id} (structure unknown)")
            return all_responses[0]['data']
        
        return None
    
    def get_all_captured_responses(self) -> Dict[str, Dict[str, Any]]:
        """Get all captured network responses for debugging
        
        Returns:
            Dictionary of captured responses
        """
        if not self.network_logger:
            return {}
        
        return self.network_logger.get_all_captured_data()
    
    def save_api_response_debug(self, filename: str = "api_response_debug.json") -> bool:
        """Save captured API responses to file for debugging
        
        Args:
            filename: Output filename
        
        Returns:
            True if successful, False otherwise
        """
        try:
            captured = self.get_all_captured_responses()
            
            if not captured:
                logger.warning("No captured responses to save")
                return False
            
            with open(filename, 'w', encoding='utf-8') as f:
                # Convert for JSON serialization
                debug_data = {
                    url: {
                        'metadata': data.get('metadata', {}),
                        'data': data.get('data', {})
                    }
                    for url, data in captured.items()
                }
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[OK] Saved {len(captured)} captured responses to {filename}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving API response debug: {e}")
            return False
