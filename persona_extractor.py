"""Persona and Generation Settings extraction for JanitorAI Scraper"""

import json
import logging
import re
import unicodedata
import codecs
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class PersonaExtractor:
    """Extracts personas and generation settings from window._storeState_"""
    
    AVATAR_BASE_URL = "https://ella.janitorai.com/avatars/"
    DEFAULT_AVATAR_URL = "https://ella.janitorai.com/hotlink-ok/logo.png"
    
    @staticmethod
    def extract_store_state_from_html(page_source: str) -> Optional[Dict[str, Any]]:
        """Extract window._storeState_ from HTML page source
        
        Args:
            page_source: HTML page source
        
        Returns:
            Parsed store state dictionary or None
        """
        try:
            # Find the script tag containing window._storeState_
            # Pattern: window._storeState_ = JSON.parse("{...escaped json...}");
            pattern = r'window\._storeState_\s*=\s*JSON\.parse\("({[^"]*(?:\\.[^"]*)*)"\);'
            match = re.search(pattern, page_source)
            
            if not match:
                logger.debug("Could not find window._storeState_ in page source")
                return None
            
            # Extract the escaped JSON string
            escaped_json = match.group(1)
            
            # Properly unescape the JSON string using codecs
            # This handles unicode_escape sequences correctly without double-encoding
            try:
                unescaped_json = codecs.decode(escaped_json, 'unicode_escape')
            except:
                # Fallback: manual unescaping for problematic cases
                unescaped_json = escaped_json.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r').replace('\\"', '"')
            
            # Parse the JSON
            store_state = json.loads(unescaped_json)
            
            # Normalize Unicode in all string values to fix malformed characters
            store_state = PersonaExtractor._normalize_unicode_recursive(store_state)
            
            logger.info("✓ Successfully extracted _storeState_ from HTML")
            return store_state
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing _storeState_ JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting _storeState_ from HTML: {e}")
            return None
    
    @staticmethod
    def _normalize_unicode_recursive(obj: Any) -> Any:
        """Recursively normalize Unicode in all strings to fix encoding issues
        
        Converts strings like 'â¢' (mis-encoded UTF-8) to proper Unicode equivalents.
        Uses NFD (canonical decomposition) followed by NFC (canonical composition).
        
        Args:
            obj: Any JSON-serializable object
        
        Returns:
            Object with normalized Unicode strings
        """
        if isinstance(obj, str):
            # Try to fix mis-encoded UTF-8 (e.g., 'â¢' -> '•')
            try:
                # If the string looks like it has mis-encoded UTF-8, fix it
                if 'â' in obj or 'â€' in obj:
                    # Try to recover by encoding to latin-1 then decoding as UTF-8
                    try:
                        obj = obj.encode('latin-1').decode('utf-8')
                    except:
                        pass
            except:
                pass
            
            # Normalize to NFC (composed) form
            return unicodedata.normalize('NFC', obj)
        
        elif isinstance(obj, dict):
            return {k: PersonaExtractor._normalize_unicode_recursive(v) for k, v in obj.items()}
        
        elif isinstance(obj, list):
            return [PersonaExtractor._normalize_unicode_recursive(item) for item in obj]
        
        return obj
    
    @staticmethod
    def _insert_before_extension(filename: str, insert_text: str) -> str:
        """Insert text before file extension
        
        Args:
            filename: Original filename (e.g., 'logo.png')
            insert_text: Text to insert (e.g., '_1')
        
        Returns:
            Modified filename (e.g., 'logo_1.png')
        """
        if '.' in filename:
            parts = filename.rsplit('.', 1)
            return f"{parts[0]}{insert_text}.{parts[1]}"
        return f"{filename}{insert_text}"
    
    @staticmethod
    def extract_personas(store_state: Dict[str, Any], avatar_mapping: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Extract personas from store state
        
        Args:
            store_state: Parsed _storeState_ dictionary
            avatar_mapping: Dictionary mapping persona indices to avatar filenames (from download_and_map_avatars)
        
        Returns:
            Dictionary with personas data in SillyTavern format or None
        """
        try:
            # Navigate to Sb.personas in the store state
            personas_list = store_state.get("Sb", {}).get("personas", [])
            
            if not personas_list:
                logger.warning("No personas found in _storeState_")
                return None
            
            logger.info(f"Found {len(personas_list)} personas in _storeState_")
            
            # Build personas dictionary for JSON export (SillyTavern format)
            # Structure: image_filename -> persona_name
            personas_dict = {}
            persona_descriptions = {}
            
            for idx, persona in enumerate(personas_list):
                name = persona.get("name", "Unknown")
                avatar = persona.get("avatar", "")
                appearance = persona.get("appearance", "")
                
                # Use avatar mapping if provided (preferred for SillyTavern compatibility)
                if avatar_mapping and str(idx) in avatar_mapping:
                    avatar_filename = avatar_mapping[str(idx)]
                else:
                    # Fallback to original avatar or empty string
                    avatar_filename = avatar if avatar else ""
                
                # If avatar exists, use it as the key, name as the value
                if avatar_filename:
                    personas_dict[avatar_filename] = name
                    
                    # Build persona description entry (keyed by name for now)
                    persona_descriptions[name] = {
                        "description": appearance,
                        "position": 0,  # Default position
                        "depth": 2,     # Default depth
                        "role": 0,      # Default role
                        "lorebook": "", # No lorebook
                        "title": ""     # No title
                    }
                    
                    logger.debug(f"Extracted persona {idx + 1}: {name} (avatar: {avatar_filename})")
                else:
                    logger.warning(f"Persona {idx + 1} ({name}) has no avatar, skipping")
            
            logger.info(f"Successfully extracted all {len(personas_list)} personas with unique mappings")
            
            return {
                "personas": personas_dict,
                "persona_descriptions": persona_descriptions,
                "default_persona": None  # User must set manually
            }
        
        except Exception as e:
            logger.error(f"Error extracting personas: {e}")
            return None
    
    @staticmethod
    def create_personas_txt(
        store_state: Dict[str, Any],
        output_path: Optional[Path] = None
    ) -> Optional[str]:
        """Create Personas.txt file with readable persona information
        
        Args:
            store_state: Parsed _storeState_ dictionary
            output_path: Path to save file (optional)
        
        Returns:
            Text content or None
        """
        try:
            personas_list = store_state.get("Sb", {}).get("personas", [])
            
            if not personas_list:
                logger.warning("No personas to export to txt")
                return None
            
            lines = []
            lines.append("=" * 70)
            lines.append("JANITORAI PERSONAS EXPORT")
            lines.append("=" * 70)
            lines.append("")
            lines.append("NOTE: Your Default Persona must be manually set after importing.")
            lines.append("      In SillyTavern, go to User Settings > Personas to set default.")
            lines.append("")
            lines.append("=" * 70)
            lines.append("")
            
            for idx, persona in enumerate(personas_list, 1):
                name = persona.get("name", "Unknown")
                avatar = persona.get("avatar", "")
                appearance = persona.get("appearance", "")
                
                lines.append(f"PERSONA #{idx}")
                lines.append("-" * 70)
                lines.append(f"Name: {name}")
                
                if avatar:
                    lines.append(f"Avatar: {avatar}")
                    lines.append(f"Avatar URL: {PersonaExtractor.AVATAR_BASE_URL}{avatar}")
                else:
                    lines.append(f"Avatar: (none - uses default)")
                    lines.append(f"Avatar URL: {PersonaExtractor.DEFAULT_AVATAR_URL}")
                
                lines.append(f"Description:")
                lines.append(appearance if appearance else "(No description)")
                lines.append("")
                lines.append("=" * 70)
                lines.append("")
            
            content = "\n".join(lines)
            
            # Save to file if path provided
            if output_path:
                with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(content)
                logger.info(f"✓ Saved personas to {output_path}")
            
            return content
        
        except Exception as e:
            logger.error(f"Error creating personas txt: {e}")
            return None
    
    @staticmethod
    def extract_generation_settings(store_state: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract generation settings (proxy configurations) from store state
        
        Args:
            store_state: Parsed _storeState_ dictionary
        
        Returns:
            List of proxy configuration dictionaries or None
        """
        try:
            # Navigate to user.config.proxyConfigurations
            config = store_state.get("user", {}).get("config", {})
            proxy_configs = config.get("proxyConfigurations", [])
            
            if not proxy_configs:
                logger.warning("No proxy configurations found in _storeState_")
                return None
            
            logger.info(f"Found {len(proxy_configs)} proxy configurations")
            
            # Extract relevant fields
            extracted_configs = []
            for cfg in proxy_configs:
                extracted = {
                    "name": cfg.get("name", "Unknown"),
                    "model": cfg.get("model", ""),
                    "api_url": cfg.get("apiUrl", ""),
                    "api_key": cfg.get("apiKey", ""),
                    "jailbreak_prompt": cfg.get("jailbreakPrompt", "")
                }
                extracted_configs.append(extracted)
                logger.debug(f"Extracted config: {extracted['name']}")
            
            return extracted_configs
        
        except Exception as e:
            logger.error(f"Error extracting generation settings: {e}")
            return None
    
    @staticmethod
    def create_generation_settings_txt(
        store_state: Dict[str, Any],
        output_path: Optional[Path] = None
    ) -> Optional[str]:
        """Create Generation_Settings.txt file with proxy configurations
        
        Args:
            store_state: Parsed _storeState_ dictionary
            output_path: Path to save file (optional)
        
        Returns:
            Text content or None
        """
        try:
            configs = PersonaExtractor.extract_generation_settings(store_state)
            
            if not configs:
                logger.warning("No generation settings to export to txt")
                return None
            
            lines = []
            lines.append("=" * 70)
            lines.append("JANITORAI GENERATION SETTINGS (PROXY CONFIGURATIONS)")
            lines.append("=" * 70)
            lines.append("")
            lines.append("WARNING: API Keys are stored in PLAIN TEXT.")
            lines.append("Please keep this file secure and do not share it publicly.")
            lines.append("")
            lines.append("=" * 70)
            lines.append("")
            
            for idx, cfg in enumerate(configs, 1):
                lines.append(f"CONFIGURATION #{idx}")
                lines.append("-" * 70)
                lines.append(f"Configuration Name: {cfg['name']}")
                lines.append(f"Model: {cfg['model']}")
                lines.append(f"API Link: {cfg['api_url']}")
                lines.append(f"API Key: {cfg['api_key']}")
                lines.append(f"Custom Prompt: {cfg['jailbreak_prompt']}")
                lines.append("")
                lines.append("=" * 70)
                lines.append("")
            
            content = "\n".join(lines)
            
            # Save to file if path provided
            if output_path:
                with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(content)
                logger.info(f"✓ Saved generation settings to {output_path}")
            
            return content
        
        except Exception as e:
            logger.error(f"Error creating generation settings txt: {e}")
            return None
    
    @staticmethod
    def export_personas_json(
        store_state: Dict[str, Any],
        output_path: Optional[Path] = None,
        avatar_mapping: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Export personas in SillyTavern-compatible JSON format
        
        Args:
            store_state: Parsed _storeState_ dictionary
            output_path: Path to save JSON file (optional)
            avatar_mapping: Dictionary mapping persona indices to avatar filenames
        
        Returns:
            Personas dictionary or None
        """
        try:
            personas_data = PersonaExtractor.extract_personas(store_state, avatar_mapping)
            
            if not personas_data:
                return None
            
            # Save to file if path provided
            if output_path:
                with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
                    json.dump(personas_data, f, indent=2, ensure_ascii=False)
                logger.info(f"✓ Saved personas JSON to {output_path}")
            
            return personas_data
        
        except Exception as e:
            logger.error(f"Error exporting personas JSON: {e}")
            return None
    
    @staticmethod
    def download_persona_avatars(
        store_state: Dict[str, Any],
        output_dir: Path
    ) -> Dict[str, str]:
        """Download persona avatar images and map them to personas
        
        For personas without avatars, downloads the default logo.png
        and assigns it as "logo - #.png" (numbered sequentially)
        
        Args:
            store_state: Parsed _storeState_ dictionary
            output_dir: Directory to save avatars
        
        Returns:
            Dictionary mapping persona index (str) to avatar filename
        """
        import requests
        
        avatar_mapping = {}  # Index -> filename mapping
        default_logo_counter = 1  # Counter for default logos
        
        try:
            personas_list = store_state.get("Sb", {}).get("personas", [])
            
            for idx, persona in enumerate(personas_list):
                name = persona.get("name", "Unknown")
                avatar = persona.get("avatar", "")
                
                if avatar:
                    # Persona has a custom avatar
                    avatar_url = f"{PersonaExtractor.AVATAR_BASE_URL}{avatar}"
                    output_path = output_dir / avatar
                    
                    try:
                        logger.debug(f"Downloading avatar for '{name}': {avatar_url}")
                        response = requests.get(avatar_url, timeout=15)
                        
                        if response.status_code == 200:
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            
                            avatar_mapping[str(idx)] = avatar
                            logger.info(f"✓ Downloaded avatar: {avatar}")
                        else:
                            logger.warning(f"Failed to download avatar {avatar} (status {response.status_code}), using default")
                            # Fall through to download default
                            avatar = None
                    
                    except Exception as e:
                        logger.error(f"Error downloading avatar {avatar}: {e}, using default")
                        # Fall through to download default
                        avatar = None
                
                if not avatar:
                    # Persona has no avatar or download failed - use default logo
                    default_filename = f"logo - {default_logo_counter}.png"
                    avatar_url = PersonaExtractor.DEFAULT_AVATAR_URL
                    output_path = output_dir / default_filename
                    
                    try:
                        logger.debug(f"Downloading default logo for '{name}': {avatar_url}")
                        response = requests.get(avatar_url, timeout=15)
                        
                        if response.status_code == 200:
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            
                            avatar_mapping[str(idx)] = default_filename
                            logger.info(f"✓ Downloaded default avatar as: {default_filename}")
                            default_logo_counter += 1
                        else:
                            logger.warning(f"Failed to download default logo (status {response.status_code})")
                    
                    except Exception as e:
                        logger.error(f"Error downloading default logo: {e}")
            
            if avatar_mapping:
                logger.info(f"✓ Mapped {len(avatar_mapping)} persona avatars")
            
            return avatar_mapping
        
        except Exception as e:
            logger.error(f"Error downloading persona avatars: {e}")
            return {}


class PersonaManager:
    """High-level manager for persona extraction workflow"""
    
    def __init__(self, browser_manager, file_manager):
        """Initialize persona manager
        
        Args:
            browser_manager: BrowserManager instance
            file_manager: FileManager instance
        """
        self.browser = browser_manager
        self.file_manager = file_manager
        self.extractor = PersonaExtractor()
    
    def extract_and_save_personas(
        self,
        output_dir: Optional[Path] = None,
        download_avatars: bool = True
    ) -> bool:
        """Extract personas from /my_personas page and save to files
        
        Workflow:
        1. Navigate to https://janitorai.com/my_personas
        2. Extract _storeState_ from HTML
        3. Download avatar images (including default logos for personas without avatars)
        4. Parse personas and generation settings
        5. Save personas.json (SillyTavern format) with avatar mappings
        6. Save Personas.txt (human-readable)
        7. Save Generation_Settings.txt
        
        Args:
            output_dir: Directory to save files (uses FileManager default if None)
            download_avatars: Whether to download persona avatar images
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if output_dir is None:
                output_dir = Path(self.file_manager.output_dir)
            
            logger.info("\n" + "="*60)
            logger.info("EXTRACTING PERSONAS AND GENERATION SETTINGS")
            logger.info("="*60)
            
            # Step 1: Navigate to personas page
            logger.info("Navigating to https://janitorai.com/my_personas")
            if not self.browser.navigate_to("https://janitorai.com/my_personas", wait_time=3):
                logger.error("Failed to navigate to /my_personas")
                return False
            
            # Wait for page to load fully
            import time
            time.sleep(2)
            
            # Step 1.5: Scroll to bottom to load all personas before extracting
            logger.info("Scrolling to load all personas...")
            driver = self.browser.get_driver()
            
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count = 0
            max_scrolls = 100
            
            while scroll_count < max_scrolls:
                # Scroll down
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(0.5)
                scroll_count += 1
                
                # Calculate new height
                new_height = driver.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height:
                    logger.info(f"Reached bottom of personas page after {scroll_count} scrolls")
                    break
                
                last_height = new_height
            
            # Scroll back to top for extraction
            logger.info("Scrolling back to top...")
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Step 2: Get page source and extract store state
            logger.info("Extracting _storeState_ from page...")
            page_source = self.browser.get_page_source()
            store_state = PersonaExtractor.extract_store_state_from_html(page_source)
            
            if not store_state:
                logger.error("Failed to extract _storeState_ from page")
                return False
            
            # Step 3: Download avatar images and get mapping
            avatar_mapping = {}
            if download_avatars:
                logger.info("Downloading persona avatar images...")
                avatars_dir = output_dir / "User Avatars"
                avatars_dir.mkdir(exist_ok=True)
                
                avatar_mapping = PersonaExtractor.download_persona_avatars(
                    store_state,
                    avatars_dir
                )
                
                if avatar_mapping:
                    logger.info(f"✓ Downloaded and mapped {len(avatar_mapping)} persona avatars")
            
            # Step 4: Export personas JSON (SillyTavern format) with avatar mapping
            logger.info("Exporting personas to JSON...")
            personas_json_path = output_dir / "personas.json"
            personas_data = PersonaExtractor.export_personas_json(
                store_state,
                personas_json_path,
                avatar_mapping
            )
            
            if personas_data:
                logger.info(f"✓ Exported {len(personas_data.get('personas', {}))} personas to JSON")
            
            # Step 5: Create Personas.txt (human-readable)
            logger.info("Creating Personas.txt...")
            personas_txt_path = output_dir / "Personas.txt"
            PersonaExtractor.create_personas_txt(store_state, personas_txt_path)
            
            # Step 6: Create Generation_Settings.txt
            logger.info("Creating Generation_Settings.txt...")
            settings_txt_path = output_dir / "Generation_Settings.txt"
            PersonaExtractor.create_generation_settings_txt(store_state, settings_txt_path)
            
            logger.info("\n" + "="*60)
            logger.info("PERSONA EXTRACTION COMPLETE")
            logger.info("="*60)
            logger.info(f"Files saved to: {output_dir}")
            logger.info("\nIMPORTANT: Default Persona must be manually set in SillyTavern")
            logger.info("           Go to User Settings > Personas after importing")
            logger.info("="*60 + "\n")
            
            return True
        
        except Exception as e:
            logger.error(f"Error extracting personas: {e}", exc_info=True)
            return False
