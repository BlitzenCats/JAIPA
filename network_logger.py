"""Network logging for capturing API responses from JanitorAI"""

import json
import logging
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


class NetworkLogger:
    """Captures network traffic to extract API responses"""
    
    def __init__(self, driver: webdriver.Chrome):
        """Initialize network logger
        
        Args:
            driver: Selenium WebDriver instance (must be undetected_chromedriver with CDP support)
        """
        self.driver = driver
        self.captured_responses: Dict[str, Dict[str, Any]] = {}
        self.cached_response_bodies: Dict[str, str] = {}  # Early cache for response bodies
        self.target_urls = [
            'janitorai.com/hampter/chats/character-chats',  # Character list pagination
            'janitorai.com/hampter/chats/character/',        # Character expansion API
            'janitorai.com/hampter/chats/',                  # Individual chat data
        ]
        self.processed_request_ids: set = set()  # Track processed responses
    
    def enable_network_logging(self) -> bool:
        """Enable Chrome DevTools Protocol for network interception
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug("Enabling CDP network logging...")
            self.driver.execute_cdp_cmd('Network.enable', {})
            logger.info("[OK] Network logging enabled")
            return True
        except Exception as e:
            logger.warning(f"Could not enable network logging: {e}")
            logger.info("Falling back to alternative methods...")
            return False
    
    def disable_network_logging(self) -> None:
        """Disable Chrome DevTools Protocol network logging"""
        try:
            self.driver.execute_cdp_cmd('Network.disable', {})
            logger.debug("Network logging disabled")
        except Exception as e:
            logger.debug(f"Could not disable network logging: {e}")
    
    def get_performance_logs(self) -> List[Dict[str, Any]]:
        """Get performance logs from Chrome
        
        Returns:
            List of performance log entries
        """
        try:
            logs = self.driver.get_log('performance')
            return logs
        except Exception as e:
            logger.debug(f"Could not retrieve performance logs: {e}")
            return []
    
    def parse_network_responses(self, cache_bodies: bool = True) -> Dict[str, Dict[str, Any]]:
        """Parse network logs to extract API responses
        
        Args:
            cache_bodies: If True, immediately fetch and cache response bodies
                         to prevent Chrome from garbage collecting them
        
        Returns:
            Dictionary of captured responses keyed by request ID
        """
        captured = {}
        logs = self.get_performance_logs()
        
        logger.debug(f"Parsing {len(logs)} performance log entries")
        
        for log in logs:
            try:
                message = json.loads(log['message'])
                method = message['message']['method']
                
                # Look for network response events
                if method == 'Network.responseReceived':
                    response = message['message']['params']['response']
                    url = response['url']
                    request_id = message['message']['params']['requestId']
                    
                    # Check if URL matches our targets
                    if any(target in url for target in self.target_urls):
                        captured[request_id] = {
                            'url': url,
                            'status': response.get('status'),
                            'mimeType': response.get('mimeType'),
                            'requestId': request_id
                        }
                        logger.debug(f"Captured response: {url} (status {response.get('status')})")
                        
                        # EARLY CACHING: Immediately fetch and cache the body
                        # This prevents Chrome from garbage collecting it before we need it
                        if cache_bodies and request_id not in self.cached_response_bodies:
                            body = self._fetch_response_body_now(request_id)
                            if body:
                                self.cached_response_bodies[request_id] = body
                                logger.debug(f"Early-cached body for {request_id} ({len(body)} chars)")
            
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # Skip malformed logs
                pass
        
        if not captured:
            logger.debug("No matching network responses found in logs")
        
        return captured
    
    def _fetch_response_body_now(self, request_id: str) -> Optional[str]:
        """Immediately fetch response body without retry (for early caching)
        
        Args:
            request_id: Request ID from Network.responseReceived
        
        Returns:
            Response body as string, or None if unavailable
        """
        try:
            response_body = self.driver.execute_cdp_cmd(
                'Network.getResponseBody',
                {'requestId': request_id}
            )
            if response_body:
                return response_body.get('body')
        except Exception:
            # Silent fail for early cache - we'll retry later if needed
            pass
        return None
    
    def get_response_body(self, request_id: str, max_retries: int = 3) -> Optional[str]:
        """Get the actual response body for a request with retry logic
        
        First checks the early cache, then falls back to CDP retrieval with retries.
        
        Args:
            request_id: Request ID from Network.responseReceived
            max_retries: Maximum number of retry attempts (default 3)
        
        Returns:
            Response body as string, or None if unavailable
        """
        # Check early cache first
        if request_id in self.cached_response_bodies:
            body = self.cached_response_bodies[request_id]
            logger.debug(f"Retrieved body from early cache ({len(body)} chars) for {request_id}")
            return body
        
        # Fall back to CDP retrieval with retries
        for attempt in range(max_retries):
            try:
                response_body = self.driver.execute_cdp_cmd(
                    'Network.getResponseBody',
                    {'requestId': request_id}
                )
                
                if not response_body:
                    if attempt < max_retries - 1:
                        logger.debug(f"Empty response for {request_id}, retrying ({attempt + 1}/{max_retries})...")
                        time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                        continue
                    logger.debug(f"Empty response from Network.getResponseBody for {request_id} after {max_retries} attempts")
                    return None
                
                body = response_body.get('body')
                if body:
                    logger.debug(f"Successfully retrieved response body ({len(body)} chars) for {request_id}")
                    return body
                else:
                    if attempt < max_retries - 1:
                        logger.debug(f"Response body empty for {request_id}, retrying ({attempt + 1}/{max_retries})...")
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    logger.debug(f"Response body is empty/null for {request_id} after {max_retries} attempts")
                    return None
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"Error retrieving body for {request_id} (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}")
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.debug(f"Could not retrieve response body for {request_id} after {max_retries} attempts: {type(e).__name__}: {e}")
                    return None
        
        return None
    
    def get_responses(self) -> List[Dict[str, Any]]:
        """Get all captured responses as a list
        
        Returns responses that haven't been processed yet.
        Marks them as processed to avoid duplicates.
        
        Returns:
            List of response dictionaries with url, body, and metadata
        """
        responses = []
        
        # Parse current network logs
        captured = self.parse_network_responses()
        
        # Get response bodies for new captures only
        for request_id, metadata in captured.items():
            url = metadata['url']
            
            # Skip if already captured
            if url in self.captured_responses:
                continue
            
            body = self.get_response_body(request_id)
            if body:
                try:
                    data = json.loads(body)
                    
                    # Add to return list
                    responses.append({
                        'url': url,
                        'body': data,
                        'metadata': metadata
                    })
                    
                    # Mark as captured
                    self.captured_responses[url] = {
                        'metadata': metadata,
                        'data': data
                    }
                    
                    logger.debug(f"New response captured: {url}")
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON response from {url}")
        
        return responses
    
    def extract_chat_data(self, chat_url: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Extract chat data by monitoring network responses
        
        Args:
            chat_url: URL of chat to extract (e.g., janitorai.com/chats/[CHATID])
            timeout: Maximum seconds to wait for response (default 30s for large chats)
        
        Returns:
            Chat data dictionary or None if not found
        """
        # Extract chat ID from URL
        chat_id = chat_url.rstrip('/').split('/')[-1]
        logger.info(f"Monitoring network for chat ID: {chat_id} (timeout: {timeout}s)")
        
        # Clear old logs BEFORE monitoring (they're cumulative)
        self.driver.get_log('performance')
        
        start_time = time.time()
        last_count = 0
        attempts_without_progress = 0
        found_responses = []  # Collect all matching responses
        
        while time.time() - start_time < timeout:
            try:
                # Get current captured responses
                captured = self.parse_network_responses()
                current_count = len(captured)
                
                # Log if we found new responses
                if current_count > last_count:
                    logger.debug(f"Captured {current_count} responses (found {current_count - last_count} new)")
                    last_count = current_count
                    attempts_without_progress = 0
                    
                    # Log details about captured responses
                    for request_id, metadata in captured.items():
                        logger.debug(f"  → Response: {metadata['url']} (status: {metadata.get('status')})")
                else:
                    attempts_without_progress += 1
                    if attempts_without_progress == 1:
                        logger.debug(f"Waiting for network responses... ({int(time.time() - start_time)}s)")
                
                # Try to extract body from each captured response
                for request_id, metadata in captured.items():
                    # Skip if already processed
                    if request_id in self.processed_request_ids:
                        continue
                    
                    # Check if this URL contains the chat ID
                    if chat_id not in metadata['url']:
                        continue
                    
                    self.processed_request_ids.add(request_id)
                    logger.debug(f"Attempting to extract body for {metadata['url']}")
                    body = self.get_response_body(request_id)
                    
                    if body:
                        try:
                            data = json.loads(body)
                            found_responses.append({
                                'url': metadata['url'],
                                'data': data,
                                'metadata': metadata
                            })
                            self.captured_responses[metadata['url']] = {
                                'metadata': metadata,
                                'data': data
                            }
                            logger.info(f"[OK] Found response #{len(found_responses)} for chat {chat_id}")
                        except json.JSONDecodeError as je:
                            logger.debug(f"Response body not JSON: {metadata['url']} - {str(je)[:50]}")
                    else:
                        logger.debug(f"Could not retrieve response body for {metadata['url']}")
                
                # If we found both responses (there are typically 2), analyze and filter them
                if len(found_responses) >= 2:
                    logger.info(f"Found {len(found_responses)} responses for chat {chat_id}, filtering...")
                    
                    # Filter out the React framework response and return actual chat data
                    for resp in found_responses:
                        data = resp['data']
                        # Check for specific keys that indicate it's chat data, not framework
                        # The actual chat response has 'message' or 'data' with meaningful content
                        if isinstance(data, dict):
                            if 'message' in data or ('data' in data and isinstance(data['data'], list)):
                                logger.info(f"[OK] Identified correct chat data response")
                                return data
                    
                    # If we can't identify by structure, return the first one (should be chat data)
                    logger.info(f"Returning first response for chat {chat_id}")
                    return found_responses[0]['data']
                
                time.sleep(0.5)
            
            except Exception as e:
                logger.debug(f"Error during network monitoring: {e}")
                time.sleep(0.5)
        
        logger.warning(f"Timeout reached without finding chat data (found {len(found_responses)} responses)")
        
        # Return what we found even if only 1 response
        if found_responses:
            logger.info(f"Returning single response for chat {chat_id}")
            return found_responses[0]['data']
        
        return None
    
    def get_all_captured_data(self) -> Dict[str, Dict[str, Any]]:
        """Get all captured API responses
        
        Returns:
            Dictionary of all captured responses
        """
        return self.captured_responses.copy()
    
    def clear_captured_data(self) -> None:
        """Clear all captured response data"""
        self.captured_responses.clear()
        self.processed_request_ids.clear()
        self.cached_response_bodies.clear()  # Also clear the early cache
        logger.debug("Cleared captured response data, request tracking, and body cache")
    
    def prepare_for_navigation(self) -> bool:
        """Prepare network logger for page navigation
        
        Must be called BEFORE navigation to ensure CDP is listening
        
        Returns:
            True if preparation successful, False otherwise
        """
        try:
            # Step 1: Ensure network logging is enabled (CDP must be active)
            self.driver.execute_cdp_cmd('Network.enable', {})
            
            # Step 2: Clear captured data
            self.clear_captured_data()
            
            # Step 3: Clear performance logs (so we only get new events from this navigation)
            # This MUST come after Network.enable, but BEFORE navigation
            self.driver.get_log('performance')
            
            logger.debug("Network logger prepared for navigation (CDP active)")
            return True
        except Exception as e:
            logger.warning(f"Error preparing network logger: {e}")
            return False


class PerformanceLogParser:
    """Helper class to parse Chrome performance logs"""
    
    @staticmethod
    def find_network_responses(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find all network response events in logs
        
        Args:
            logs: List of performance logs
        
        Returns:
            List of Network.responseReceived events
        """
        responses = []
        
        for log in logs:
            try:
                message = json.loads(log['message'])
                if message['message']['method'] == 'Network.responseReceived':
                    responses.append(message['message']['params'])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        
        return responses
    
    @staticmethod
    def find_network_requests(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find all network request events in logs
        
        Args:
            logs: List of performance logs
        
        Returns:
            List of Network.requestWillBeSent events
        """
        requests = []
        
        for log in logs:
            try:
                message = json.loads(log['message'])
                if message['message']['method'] == 'Network.requestWillBeSent':
                    requests.append(message['message']['params'])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        
        return requests
    
    @staticmethod
    def filter_by_url_pattern(
        responses: List[Dict[str, Any]],
        pattern: str
    ) -> List[Dict[str, Any]]:
        """Filter responses by URL pattern
        
        Args:
            responses: List of response data
            pattern: URL pattern to match
        
        Returns:
            Filtered list of responses
        """
        return [
            r for r in responses
            if pattern in r.get('response', {}).get('url', '')
        ]
