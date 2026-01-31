"""Utility functions for JanitorAI Scraper"""

import io
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse, quote, urlunparse

from scraper_config import JANITOR_DOMAIN, JANNY_DOMAIN

logger = logging.getLogger(__name__)


class AnonymizingFormatter(logging.Formatter):
    """Custom formatter that anonymizes file paths in log messages"""
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        # Cache the home directory path for replacement
        self._home_dir = str(Path.home())
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, replacing home directory paths with <HOME_DIR>"""
        formatted = super().format(record)
        # Replace home directory path (case-insensitive for Windows)
        if self._home_dir:
            formatted = formatted.replace(self._home_dir, "<HOME_DIR>")
            # Also handle forward-slash version of the path
            formatted = formatted.replace(self._home_dir.replace("\\", "/"), "<HOME_DIR>")
        return formatted


def setup_logging(log_file: Optional[str] = None) -> None:
    """Configure logging for the scraper
    
    Clears existing log file at startup to ensure only current session is logged.
    Uses AnonymizingFormatter to protect user privacy by replacing home directory paths.
    """
    import sys
    import io
    
    # Clear existing log file if it exists
    if log_file:
        log_path = Path(log_file)
        if log_path.exists():
            try:
                log_path.unlink()
                print(f"Cleared previous log file: {log_file}")
            except Exception as e:
                print(f"Warning: Could not clear log file: {e}")
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Force UTF-8 output on Windows console
    # Force UTF-8 output on Windows console - ONLY if valid streams exist
    if sys.platform == 'win32':
        # Reconfigure stdout/stderr to use UTF-8
        if sys.stdout and hasattr(sys.stdout, 'buffer'):
            try:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            except Exception:
                pass
        
        if sys.stderr and hasattr(sys.stderr, 'buffer'):
            try:
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            except Exception:
                pass
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler with UTF-8 encoding - ONLY if stdout is available
    if sys.stdout:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(AnonymizingFormatter(log_format))
        # Force UTF-8 encoding
        if hasattr(console_handler, 'setEncoding'):
            try:
                console_handler.setEncoding('utf-8')
            except Exception:
                pass
        root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(AnonymizingFormatter(log_format))
        root_logger.addHandler(file_handler)
    
    # Suppress verbose selenium logging
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('selenium.webdriver').setLevel(logging.WARNING)
    logging.getLogger('selenium.webdriver.remote').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logger.info("Logging configured")


def normalize_url(url: str, base_domain: str = JANITOR_DOMAIN) -> str:
    """Normalize URL to full format with protocol and domain"""
    if not url:
        return ""
    
    if url.startswith("/"):
        return f"https://{base_domain}{url}"
    elif not url.startswith("http"):
        return f"https://{base_domain}/{url}"
    
    return url


def janitor_to_janny_url(janitor_url: str) -> str:
    """Convert janitorai.com URL to jannyai.com"""
    return janitor_url.replace(JANITOR_DOMAIN, JANNY_DOMAIN)


def encode_url_path(url: str) -> str:
    """Encode special characters in URL path while preserving structure"""
    parsed = urlparse(url)
    # Encode only the path, preserving /
    encoded_path = quote(parsed.path, safe="/")
    
    return urlunparse(
        (parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment)
    )


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Remove invalid characters from filename and truncate if too long
    
    Args:
        filename: Original filename
        max_length: Maximum length (default 100 to fit in Windows path limits)
    
    Returns:
        Sanitized and truncated filename
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Strip trailing periods, spaces, and underscores (Windows doesn't allow trailing . or space)
    sanitized = sanitized.rstrip('. _')
    
    # Ensure we have a valid name
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


def extract_url_id(url: str, id_type: str = "chat") -> str:
    """Extract chat or character ID from URL
    
    Args:
        url: Full URL
        id_type: 'chat' or 'character'
    
    Returns:
        Extracted ID or empty string
    """
    try:
        if id_type == "chat":
            return url.split("/chats/")[-1].split("?")[0]
        elif id_type == "character":
            return url.split("/characters/")[-1].split("?")[0]
    except (IndexError, AttributeError):
        pass
    
    return ""


def safe_create_directory(path: Path) -> bool:
    """Safely create directory if it doesn't exist
    
    Returns:
        True if directory exists or was created, False on error
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False


def add_duplicate_suffix(base_name: str, existing_names: set) -> str:
    """Add +1, +2, etc. suffix if name already exists
    
    Args:
        base_name: Original name
        existing_names: Set of existing names to check against
    
    Returns:
        Name with suffix if duplicate, otherwise original name
    """
    if base_name not in existing_names:
        return base_name
    
    counter = 1
    while True:
        new_name = f"{base_name}_+{counter}"
        if new_name not in existing_names:
            return new_name
        counter += 1


class RetryableError(Exception):
    """Exception that should trigger a retry"""
    pass


class FatalError(Exception):
    """Exception that should not be retried"""
    pass
