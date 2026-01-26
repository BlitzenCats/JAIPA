"""Browser management for JanitorAI Scraper

Supports multiple Chromium-based browsers:
- Chrome
- Opera GX / Opera
- Microsoft Edge
- Brave
- Vivaldi
- Chromium

All Chromium-based browsers support the Chrome DevTools Protocol (CDP)
which is required for network interception.
"""

import logging
import os
import platform
import time
import traceback
from enum import Enum
from typing import Optional, List, Tuple

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


class BrowserType(Enum):
    """Supported browser types"""
    CHROME = "chrome"
    OPERA_GX = "opera_gx"
    OPERA = "opera"
    EDGE = "edge"
    BRAVE = "brave"
    VIVALDI = "vivaldi"
    CHROMIUM = "chromium"
    AUTO = "auto"  # Auto-detect installed browser


def get_browser_paths() -> dict:
    """Get common browser binary paths for each OS

    Returns:
        Dictionary mapping BrowserType to list of possible paths
    """
    system = platform.system()

    if system == "Windows":
        # Windows paths
        local_app = os.environ.get('LOCALAPPDATA', '')
        program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')

        return {
            BrowserType.CHROME: [
                f"{program_files}\\Google\\Chrome\\Application\\chrome.exe",
                f"{program_files_x86}\\Google\\Chrome\\Application\\chrome.exe",
                f"{local_app}\\Google\\Chrome\\Application\\chrome.exe",
            ],
            BrowserType.OPERA_GX: [
                f"{local_app}\\Programs\\Opera GX\\opera.exe",
                f"{program_files}\\Opera GX\\opera.exe",
                f"{program_files_x86}\\Opera GX\\opera.exe",
            ],
            BrowserType.OPERA: [
                f"{local_app}\\Programs\\Opera\\opera.exe",
                f"{program_files}\\Opera\\opera.exe",
                f"{program_files_x86}\\Opera\\opera.exe",
            ],
            BrowserType.EDGE: [
                f"{program_files}\\Microsoft\\Edge\\Application\\msedge.exe",
                f"{program_files_x86}\\Microsoft\\Edge\\Application\\msedge.exe",
            ],
            BrowserType.BRAVE: [
                f"{program_files}\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                f"{program_files_x86}\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                f"{local_app}\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            ],
            BrowserType.VIVALDI: [
                f"{local_app}\\Vivaldi\\Application\\vivaldi.exe",
                f"{program_files}\\Vivaldi\\Application\\vivaldi.exe",
            ],
            BrowserType.CHROMIUM: [
                f"{local_app}\\Chromium\\Application\\chrome.exe",
                f"{program_files}\\Chromium\\Application\\chrome.exe",
            ],
        }

    elif system == "Darwin":  # macOS
        return {
            BrowserType.CHROME: [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ],
            BrowserType.OPERA_GX: [
                "/Applications/Opera GX.app/Contents/MacOS/Opera",
            ],
            BrowserType.OPERA: [
                "/Applications/Opera.app/Contents/MacOS/Opera",
            ],
            BrowserType.EDGE: [
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ],
            BrowserType.BRAVE: [
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            ],
            BrowserType.VIVALDI: [
                "/Applications/Vivaldi.app/Contents/MacOS/Vivaldi",
            ],
            BrowserType.CHROMIUM: [
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ],
        }

    else:  # Linux
        return {
            BrowserType.CHROME: [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/snap/bin/chromium",
            ],
            BrowserType.OPERA_GX: [
                "/usr/bin/opera-gx",
                "/snap/bin/opera-gx",
            ],
            BrowserType.OPERA: [
                "/usr/bin/opera",
                "/snap/bin/opera",
            ],
            BrowserType.EDGE: [
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
            ],
            BrowserType.BRAVE: [
                "/usr/bin/brave-browser",
                "/usr/bin/brave",
                "/snap/bin/brave",
            ],
            BrowserType.VIVALDI: [
                "/usr/bin/vivaldi",
                "/usr/bin/vivaldi-stable",
            ],
            BrowserType.CHROMIUM: [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ],
        }


def find_browser_binary(browser_type: BrowserType) -> Optional[str]:
    """Find the binary path for a specific browser

    Args:
        browser_type: The browser to find

    Returns:
        Path to browser binary or None if not found
    """
    paths = get_browser_paths()

    if browser_type not in paths:
        return None

    for path in paths[browser_type]:
        if os.path.exists(path):
            logger.info(f"Found {browser_type.value} at: {path}")
            return path

    return None


def detect_installed_browsers() -> List[Tuple[BrowserType, str]]:
    """Detect all installed Chromium-based browsers

    Returns:
        List of (BrowserType, path) tuples for installed browsers
    """
    installed = []
    paths = get_browser_paths()

    # Check in preferred order
    check_order = [
        BrowserType.CHROME,
        BrowserType.OPERA_GX,
        BrowserType.OPERA,
        BrowserType.EDGE,
        BrowserType.BRAVE,
        BrowserType.VIVALDI,
        BrowserType.CHROMIUM,
    ]

    for browser_type in check_order:
        if browser_type in paths:
            for path in paths[browser_type]:
                if os.path.exists(path):
                    installed.append((browser_type, path))
                    break  # Only add first found path for each browser

    return installed


def get_browser_display_name(browser_type: BrowserType) -> str:
    """Get human-readable browser name

    Args:
        browser_type: Browser type enum

    Returns:
        Display name string
    """
    names = {
        BrowserType.CHROME: "Google Chrome",
        BrowserType.OPERA_GX: "Opera GX",
        BrowserType.OPERA: "Opera",
        BrowserType.EDGE: "Microsoft Edge",
        BrowserType.BRAVE: "Brave",
        BrowserType.VIVALDI: "Vivaldi",
        BrowserType.CHROMIUM: "Chromium",
        BrowserType.AUTO: "Auto-detect",
    }
    return names.get(browser_type, browser_type.value)


class BrowserManager:
    """Manages Selenium WebDriver lifecycle and browser operations

    Supports multiple Chromium-based browsers including Chrome, Opera GX,
    Edge, Brave, Vivaldi, and Chromium.
    """

    def __init__(self, headless: bool = True, browser_type: BrowserType = BrowserType.AUTO,
                 custom_binary_path: Optional[str] = None):
        """Initialize browser manager

        Args:
            headless: Run browser in headless mode
            browser_type: Which browser to use (default: auto-detect)
            custom_binary_path: Optional custom path to browser binary
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.browser_type = browser_type
        self.custom_binary_path = custom_binary_path
        self.actual_browser_type: Optional[BrowserType] = None  # Set after detection

    def _get_browser_binary(self) -> Tuple[Optional[str], BrowserType]:
        """Get the browser binary path

        Returns:
            Tuple of (binary_path, browser_type)
        """
        # If custom path provided, use it
        if self.custom_binary_path and os.path.exists(self.custom_binary_path):
            logger.info(f"Using custom browser path: {self.custom_binary_path}")
            return self.custom_binary_path, self.browser_type

        # Auto-detect browser
        if self.browser_type == BrowserType.AUTO:
            installed = detect_installed_browsers()
            if installed:
                browser_type, path = installed[0]
                logger.info(f"Auto-detected browser: {get_browser_display_name(browser_type)}")
                return path, browser_type
            else:
                logger.error("No supported Chromium-based browser found!")
                return None, BrowserType.AUTO
        else:
            # Find specific browser
            path = find_browser_binary(self.browser_type)
            if path:
                return path, self.browser_type
            else:
                logger.error(f"{get_browser_display_name(self.browser_type)} not found!")
                return None, self.browser_type

    def setup_driver(self) -> bool:
        """Initialize Selenium WebDriver with bot detection bypass

        Supports Chrome, Opera GX, Edge, Brave, Vivaldi, and other
        Chromium-based browsers. All use the Chrome DevTools Protocol
        for network interception.

        Returns:
            True if successful, False otherwise
        """
        # Find browser binary
        binary_path, detected_type = self._get_browser_binary()
        self.actual_browser_type = detected_type

        if not binary_path:
            logger.error("No browser binary found. Please install a Chromium-based browser.")
            logger.info("Supported browsers: Chrome, Opera GX, Opera, Edge, Brave, Vivaldi, Chromium")
            return False

        browser_name = get_browser_display_name(detected_type)
        logger.info(f"Initializing {browser_name} options...")

        try:
            # Determine if we can use undetected-chromedriver
            # Note: undetected-chromedriver works best with Chrome
            use_undetected = HAS_UNDETECTED and detected_type == BrowserType.CHROME

            if use_undetected:
                logger.info("Using undetected-chromedriver to bypass bot detection...")
                options = uc.ChromeOptions()
            else:
                if detected_type != BrowserType.CHROME and HAS_UNDETECTED:
                    logger.info(f"undetected-chromedriver not fully compatible with {browser_name}")
                    logger.info("Using standard Selenium (may trigger bot detection)")
                elif not HAS_UNDETECTED:
                    logger.warning("undetected-chromedriver not available")
                    logger.warning("Bot detection may be triggered")
                options = webdriver.ChromeOptions()

            # Set binary location for non-Chrome browsers
            if binary_path and detected_type != BrowserType.CHROME:
                options.binary_location = binary_path
                logger.info(f"Using browser binary: {binary_path}")

            # Common options for all Chromium-based browsers
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-extensions")

            # Opera-specific: disable some Opera-specific features that might interfere
            if detected_type in (BrowserType.OPERA_GX, BrowserType.OPERA):
                options.add_argument("--disable-features=OperaGX")  # Disable GX-specific features
                logger.info("Applied Opera-specific compatibility options")

            if self.headless:
                options.add_argument("--headless")

            # Disable image loading for faster page loads
            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)

            # Enable network logging for API response capture
            # This works on ALL Chromium-based browsers via CDP
            options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

            logger.info(f"Starting {browser_name} browser...")

            try:
                if use_undetected:
                    logger.debug("Initializing undetected-chromedriver...")
                    self.driver = uc.Chrome(
                        options=options,
                        version_main=None,
                        suppress_welcome=True,
                        use_subprocess=False
                    )
                else:
                    logger.debug("Initializing standard Selenium WebDriver...")
                    # Use ChromeDriver for all Chromium-based browsers
                    # Selenium's ChromeDriver is compatible with Opera, Edge, Brave, etc.
                    self.driver = webdriver.Chrome(options=options)

                logger.info(f"[OK] {browser_name} WebDriver created successfully")
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
                logger.error(f"Make sure you have the correct WebDriver installed for {browser_name}")
                if detected_type in (BrowserType.OPERA_GX, BrowserType.OPERA):
                    logger.info("For Opera/Opera GX: ChromeDriver should work, but versions must match")
                elif detected_type == BrowserType.EDGE:
                    logger.info("For Edge: Consider installing Microsoft Edge WebDriver (msedgedriver)")
                elif detected_type == BrowserType.BRAVE:
                    logger.info("For Brave: ChromeDriver should work with matching version")
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
