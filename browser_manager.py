"""Browser management for JanitorAI Scraper"""

import logging
import time
import traceback
import re
import subprocess
from typing import Optional

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False

logger = logging.getLogger(__name__)


def get_chrome_version() -> Optional[int]:
    """Detect installed Chrome version on Windows.
    
    Returns:
        Major version number (e.g., 144) or None if detection fails
    """
    try:
        # Try Windows registry first (most reliable)
        try:
            import winreg
            reg_path = r"Software\Google\Chrome\BLBeacon"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                version_str, _ = winreg.QueryValueEx(key, "version")
                major_version = int(version_str.split(".")[0])
                logger.info(f"Detected Chrome version {version_str} (major: {major_version})")
                return major_version
        except Exception:
            pass
        
        # Fallback: Query Chrome directly
        result = subprocess.run(
            [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_match = re.search(r"Chrome (\d+)", result.stdout)
            if version_match:
                major_version = int(version_match.group(1))
                logger.info(f"Detected Chrome version via CLI (major: {major_version})")
                return major_version
    except Exception as e:
        logger.warning(f"Failed to detect Chrome version: {e}")
    
    return None


class BrowserManager:
    """Manages Selenium WebDriver lifecycle and browser operations"""
    
    def __init__(self, headless: bool = True):
        """Initialize browser manager
        
        Args:
            headless: Run browser in headless mode
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
    
    def setup_driver(self) -> bool:
        """Initialize Selenium WebDriver with bot detection bypass
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Initializing Chrome options...")
        
        try:
            if HAS_UNDETECTED:
                logger.info("Using undetected-chromedriver to bypass bot detection...")
                options = uc.ChromeOptions()
            else:
                logger.warning("undetected-chromedriver not available, using standard Selenium")
                logger.warning("Bot detection may be triggered")
                options = webdriver.ChromeOptions()
            
            # Common options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-extensions")
            
            if self.headless:
                options.add_argument("--headless")
            
            # Images are loaded by default. Use runtime methods to disable them after login if desired.
            
            # Enable network logging for API response capture
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            logger.info("Starting Chrome browser...")
            
            try:
                if HAS_UNDETECTED:
                    logger.debug("Initializing undetected-chromedriver...")
                    
                    # Detect Chrome version to ensure chromedriver matches
                    chrome_version = get_chrome_version()
                    
                    try:
                        # First attempt: use detected Chrome version if available
                        if chrome_version:
                            logger.info(f"Using detected Chrome version: {chrome_version}")
                            self.driver = uc.Chrome(
                                options=options,
                                version_main=chrome_version,
                                suppress_welcome=True,
                                use_subprocess=False
                            )
                        else:
                            # Fallback: auto-detect
                            logger.info("Chrome version detection failed, using auto-detection")
                            self.driver = uc.Chrome(
                                options=options,
                                version_main=None,
                                suppress_welcome=True,
                                use_subprocess=False
                            )
                    except Exception as e:
                        # If main attempt fails, retry with use_subprocess=True
                        logger.warning(f"Driver initialization failed: {e}. Retrying with use_subprocess=True...")
                        try:
                            self.driver = uc.Chrome(
                                options=options,
                                version_main=chrome_version if chrome_version else None,
                                suppress_welcome=True,
                                use_subprocess=True
                            )
                        except Exception as e2:
                            # Final fallback: use standard Selenium
                            logger.warning(f"undetected-chromedriver failed ({e2}), falling back to standard Selenium")
                            logger.warning("Note: Bot detection may be triggered without undetected-chromedriver")
                            self.driver = webdriver.Chrome(options=options)
                else:
                    logger.debug("Initializing standard Selenium WebDriver...")
                    self.driver = webdriver.Chrome(options=options)
                
                logger.info("[OK] Chrome WebDriver created successfully")
                self.driver.implicitly_wait(10)
                logger.info("[OK] Implicit wait set to 10 seconds")
                
                # Navigate to login page
                logger.info("Navigating to JanitorAI login page...")
                self.driver.get("https://janitorai.com/login")
                time.sleep(3)  # Wait for page to load
                logger.info("[OK] Opened login page - ready for user login")
                
                return True
            
            except Exception as e:
                logger.error(f"[ERROR] Error creating WebDriver: {e}")
                traceback.print_exc()
                return False
        
        except Exception as e:
            logger.error(f"[ERROR] Error in setup_driver: {e}")
            traceback.print_exc()
            return False
    
    def get_driver(self) -> Optional[webdriver.Chrome]:
        """Get the WebDriver instance
        
        Returns:
            WebDriver or None if not initialized
        """
        return self.driver
    
    def navigate_to(self, url: str, wait_time: int = 5) -> bool:
        """Navigate to URL and wait for page to load
        
        Args:
            url: URL to navigate to
            wait_time: Seconds to wait for page load
        
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            
            # Wait for body element
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "body"))
                )
            except TimeoutException:
                logger.warning("Timeout waiting for page to load")
                return False
            
            time.sleep(wait_time)
            return True
        
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            return False
    
    def execute_script(self, script: str, *args):
        """Execute JavaScript in browser
        
        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to script
        
        Returns:
            Result of script execution or None
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return None
        
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            return None
    
    def find_elements(self, by: By, value: str):
        """Find elements using CSS selector or xpath
        
        Args:
            by: Selenium By strategy
            value: Selector value
        
        Returns:
            List of WebElements
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return []
        
        try:
            return self.driver.find_elements(by, value)
        except Exception as e:
            logger.error(f"Error finding elements: {e}")
            return []
    
    def maximize_window(self) -> bool:
        """Maximize browser window
        
        Returns:
            True if successful
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False
        
        try:
            self.driver.maximize_window()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Error maximizing window: {e}")
            return False
    
    def scroll_to_top(self, wait_time: float = 1.0) -> None:
        """Scroll to top of page"""
        if not self.driver:
            return
        
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(wait_time)
    
    def scroll_to_bottom(self, wait_time: float = 1.0) -> None:
        """Scroll to bottom of page"""
        if not self.driver:
            return
        
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
    
    def scroll_by(self, x: int = 0, y: int = 0, wait_time: float = 0.3) -> None:
        """Scroll by specified amounts
        
        Args:
            x: Horizontal scroll amount
            y: Vertical scroll amount
            wait_time: Wait time after scrolling
        """
        if not self.driver:
            return
        
        self.driver.execute_script(f"window.scrollBy({x}, {y});")
        time.sleep(wait_time)
    
    def get_page_source(self) -> str:
        """Get current page HTML source
        
        Returns:
            Page source or empty string
        """
        if not self.driver:
            return ""
        
        try:
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Error getting page source: {e}")
            return ""

    def disable_images(self) -> bool:
        """Disable image loading at runtime using Chrome DevTools Protocol.

        Call this after user login when you want to stop further image requests.
        Returns True on success, False otherwise.
        """
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        try:
            # Enable Network domain and block common image extensions
            self.driver.execute_cdp_cmd("Network.enable", {})
            self.driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg", "*.ico"]})
            logger.info("Image loading disabled via CDP")
            return True
        except Exception as e:
            logger.error(f"Error disabling images: {e}")
            return False

    def enable_images(self) -> bool:
        """Re-enable image loading by clearing blocked URLs set via CDP."""
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        try:
            self.driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})
            logger.info("Image loading enabled via CDP")
            return True
        except Exception as e:
            logger.error(f"Error enabling images: {e}")
            return False
    
    def close(self) -> None:
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        """Context manager entry"""
        if self.setup_driver():
            return self
        raise RuntimeError("Failed to initialize browser")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
