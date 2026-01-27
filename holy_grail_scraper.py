"""Holy Grail JanitorAI Scraper - Network Logging Based Approach"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

from browser_manager import BrowserManager
from card_creator import CharacterCardCreator
from character_fetcher import CharacterFetcher
from character_list_extractor import CharacterListExtractor
from chat_network_extractor import ChatNetworkExtractor
from deleted_character_recovery import DeletedCharacterRecovery
from file_manager import FileManager
from file_organizer import FileOrganizer
from opt_out_checker import OptOutChecker, RateLimiter
from persona_extractor import PersonaManager
from scraper_config import ScraperConfig
from scraper_utils import setup_logging, extract_url_id

logger = logging.getLogger(__name__)


class HolyGrailScraper:
    """Holy Grail approach: Network logging for character list and chats"""
    
    def __init__(self, config: ScraperConfig):
        """Initialize scraper
        
        Args:
            config: ScraperConfig instance
        """
        self.config = config
        
        # Initialize components
        self.browser_manager = BrowserManager(headless=config.headless)
        self.rate_limiter = RateLimiter(config.delay_between_requests)
        self.file_manager = FileManager(str(config.output_dir))
        self.file_organizer = FileOrganizer(
            str(config.output_dir),
            organize_enabled=config.organize_for_sillytavern
        )
        self.recovery_system = DeletedCharacterRecovery(str(config.output_dir))
        self.opt_out_checker = OptOutChecker()
        
        # Initialize extractors
        self.character_list_extractor = CharacterListExtractor(
            self.browser_manager,
            config
        )
        self.character_fetcher = CharacterFetcher(self.browser_manager, config)
        self.chat_extractor = ChatNetworkExtractor(
            self.browser_manager,
            self.rate_limiter,
            config
        )
        self.card_creator = CharacterCardCreator(self.file_manager)
        self.persona_manager = PersonaManager(self.browser_manager, self.file_manager)
        
        # Statistics
        self.successful = 0
        self.skipped = 0
        self.failures = 0
        self.chats_saved = 0
        
        # GUI callbacks (optional)
        self.progress_callback = None  # fn(current, total, name, chats)
        self.log_callback = None  # fn(message)
        self.stop_check = None  # fn() -> bool
    
    def launch_browser(self):
        """Phase 1: Launch browser and wait for login"""
        logger.info("\nPHASE 1: Setting up browser")
        if not self.browser_manager.setup_driver():
            logger.error("Failed to initialize browser")
            return False
            
        logger.info("Browser launched. Waiting for user login...")
        return True

    def run(self) -> None:
        """Run the holy grail scraper (Phase 2 onwards)"""
        try:
            logger.info("Starting Holy Grail Scraper Process")
            logger.info("="*60)
            
            # Check if browser is up, if not launch it
            if not self.browser_manager.driver:
                if not self.launch_browser():
                    return
            
            # Load opt-out list
            logger.info("Loading opt-out list...")
            self.opt_out_checker.load_opt_out_list()
            
            # ========================================
            # PHASE 2: NETWORK LOGGING SETUP
            # ========================================
            logger.info("\nPHASE 2: Setting up network logging")
            
            # Setup character list network logging (for character-chats API)
            if not self.character_list_extractor.setup_network_logging():
                logger.error("Failed to setup network logging")
                return
            
            # Setup chat network logging (for individual chat APIs)
            if not self.chat_extractor.setup_network_logging():
                logger.warning("Failed to setup chat network logging")
            
            # ========================================
            # PHASE 2.5: EXTRACT PERSONAS AND SETTINGS
            # ========================================
            logger.info("\nPHASE 2.5: Persona and Generation Settings Extraction")
            
            if self.config.extract_personas:
                logger.info("Starting persona extraction...")
                if self.persona_manager.extract_and_save_personas(download_avatars=True):
                    logger.info("✓ Persona extraction completed successfully")
                else:
                    logger.warning("Persona extraction failed or was skipped")
            else:
                logger.info("Skipping persona extraction (disabled in config)")
            
            # ========================================
            # PHASE 3: NAVIGATE TO MY_CHATS PAGE
            # ========================================
            logger.info("\nPHASE 3: Navigating to my_chats page")
            if not self.browser_manager.navigate_to("https://janitorai.com/my_chats", wait_time=3):
                logger.error("Failed to navigate to my_chats")
                return
            
            logger.info("Page loaded successfully")
            
            # ========================================
            # PHASE 4: EXTRACT CHARACTER LIST
            # ========================================
            logger.info("\nPHASE 4: Extracting character list (scrolling + network listening)")
            logger.info("This will scroll through the page and capture API responses...")
            
            if not self.character_list_extractor.extract_character_list():
                logger.error("Failed to extract character list")
                return
            
            # Log deleted/private characters
            if self.character_list_extractor.deleted_characters:
                logger.info(f"Found {len(self.character_list_extractor.deleted_characters)} deleted characters")
                self.file_manager.save_text(
                    "\n".join(self.character_list_extractor.deleted_characters) + "\n",
                    "Deleted_Characters.txt"
                )
            
            if self.character_list_extractor.private_characters:
                logger.info(f"Found {len(self.character_list_extractor.private_characters)} private characters")
                self.file_manager.save_text(
                    "\n".join(self.character_list_extractor.private_characters) + "\n",
                    "Private_Characters.txt"
                )
            
            # Get valid characters
            valid_characters = self.character_list_extractor.get_all_valid_characters()
            logger.info(f"Found {len(valid_characters)} valid characters")
            
            # If recovery enabled, also include deleted/private characters in expansion
            all_characters_to_expand = valid_characters.copy()
            if self.config.recover_deleted_private_chats:
                all_characters_to_expand.update(self.character_list_extractor.get_deleted_characters())
                all_characters_to_expand.update(self.character_list_extractor.get_private_characters())
                logger.info(f"Recovery enabled: Also including {len(all_characters_to_expand) - len(valid_characters)} deleted/private characters")
            
            if not all_characters_to_expand:
                logger.error("No characters found!")
                return
            
            # ========================================
            # PHASE 5: EXPAND CHARACTERS TO GET CHATS
            # ========================================
            logger.info("\nPHASE 5: Expanding characters to get chats (via network logging)")
            logger.info("This triggers hampter/chats/character/[ID]/chats API calls...")
            
            if self.log_callback:
                self.log_callback(f"📂 Expanding {len(all_characters_to_expand)} characters...")
            
            total_to_expand = len(all_characters_to_expand)
            for idx, (char_id, char_info) in enumerate(all_characters_to_expand.items(), 1):
                # Check for stop request
                if self.stop_check and self.stop_check():
                    logger.warning("Stop requested by user")
                    if self.log_callback:
                        self.log_callback("Stopped by user")
                    return
                
                char_name = char_info.get("name", "Unknown")
                is_deleted = char_info.get("is_deleted", False)
                is_private = not char_info.get("is_public", True)
                status = "DELETED" if is_deleted else ("PRIVATE" if is_private else "PUBLIC")
                
                logger.info(f"[{idx}/{total_to_expand}] Expanding {char_name} [{status}] (ID: {char_id})")
                
                # Update progress (Phase 5 = first half of progress bar)
                if self.progress_callback:
                    self.progress_callback(idx, total_to_expand, f"Expanding: {char_name}", 0)
                
                # Pass character ID to expand method
                chats = self.character_list_extractor.expand_character_to_get_chats(char_id)
                if not chats:
                    logger.debug(f"No chats found for {char_name}")
                else:
                    # If recovery enabled and this is deleted/private, also track for mapping
                    if self.config.recover_deleted_private_chats and (is_deleted or is_private):
                        # Debug: Log first chat object to see structure
                        if chats and len(chats) > 0:
                            import json
                            logger.debug(f"[Recovery] First chat structure: {json.dumps(chats[0], indent=2, default=str)}")
                            logger.debug(f"[Recovery] Chat keys: {list(chats[0].keys()) if isinstance(chats[0], dict) else 'NOT A DICT'}")
                        
                        # Extract chat links from chats
                        chat_links = []
                        for chat in chats:
                            if isinstance(chat, dict):
                                # Try multiple possible keys for chat ID
                                chat_id = chat.get("chat_id") or chat.get("id") or chat.get("chatId") or str(chat.get("_id", ""))
                                if chat_id:
                                    chat_links.append(f"https://janitorai.com/chats/{chat_id}")
                                else:
                                    logger.debug(f"[Recovery] No chat ID found in: {list(chat.keys())}")
                        
                        # Track for recovery with chat links
                        self.recovery_system.track_character_chats(
                            char_id, char_name, len(chats),
                            is_deleted=is_deleted,
                            is_public=char_info.get("is_public", True),
                            chats=chats,
                            chat_links=chat_links
                        )
                        logger.info(f"[Recovery] ✓ Found {len(chats)} chats for {char_name} ({len(chat_links)} links extracted)")
                
                self.rate_limiter.apply_limit(self.config.delay_between_chats)
            
            logger.info(f"Expansion complete. All character chats captured via network logging.")
            if self.log_callback:
                self.log_callback("✅ Character expansion complete!")
            
            # Also expand deleted/private characters to get their chat histories (if enabled)
            # NOTE: This is now handled in Phase 5 above - no separate recovery phase needed
            
            # ========================================
            # PHASE 6: PROCESS CHARACTERS
            # ========================================
            logger.info(f"\nPHASE 6: Processing {len(valid_characters)} characters")
            
            if self.log_callback:
                self.log_callback(f"⚙️ Processing {len(valid_characters)} characters...")
            
            total_chars = len(valid_characters)
            for idx, (char_id, char_info) in enumerate(valid_characters.items(), 1):
                # Check for stop request
                if self.stop_check and self.stop_check():
                    logger.warning("Stop requested by user")
                    if self.log_callback:
                        self.log_callback("Stopped by user")
                    break
                
                char_name = char_info.get("name", "Unknown")
                
                # Update progress callback (Phase 6 = second half)
                if self.progress_callback:
                    self.progress_callback(idx, total_chars, f"Processing: {char_name}", self.chats_saved)
                
                try:
                    # Get chats from network response
                    chats_data = self.character_list_extractor.get_character_chats(char_id)
                    if not chats_data:
                        self.skipped += 1
                        continue
                    
                    # Check creator opt-out
                    creator_username = char_info.get("creator_username", "Unknown")
                    if self.opt_out_checker.is_opted_out(creator_username):
                        logger.warning(f"Creator '{creator_username}' is opted out")
                        self.skipped += 1
                        continue
                    
                    # Process character
                    self._process_character(char_id, char_info, chats_data)
                    self.rate_limiter.apply_limit(self.config.delay_between_requests)
                
                except Exception as e:
                    logger.error(f"Error processing {char_name}: {e}")
                    self.failures += 1
            
            # Print summary
            self._print_summary()
        
        except Exception as e:
            logger.error(f"Fatal error in scraper: {e}", exc_info=True)
        finally:
            # Cleanup
            self.character_list_extractor.cleanup()
            self.chat_extractor.cleanup_network_logging()
            self.browser_manager.close()
    
    def _process_character(
        self,
        char_id: str,
        char_info: Dict[str, Any],
        chats_data: list
    ) -> None:
        """Process a single character
        
        Args:
            char_id: Character ID
            char_info: Character info from list
            chats_data: Chats from network response
        """
        try:
            char_name = char_info.get("name", "Unknown")
            creator_username = char_info.get("creator_username", "Unknown")
            
            # Create character folder
            char_folder = self.file_manager.create_character_folder(
                char_name,
                f"https://janitorai.com/characters/{char_id}"
            )
            
            if not char_folder:
                logger.error(f"Failed to create folder for {char_name}")
                self.failures += 1
                return
            
            # Fetch character card from janitorai.com/characters/[ID]
            logger.info(f"Fetching character card for {char_id}")
            character_data = self._fetch_character_card(char_id, char_name, creator_username)
            
            if not character_data:
                logger.error(f"Failed to fetch character card for {char_name}")
                self.failures += 1
                return
            
            # Save character JSON in V3 format
            self.card_creator.save_character_json(character_data, str(char_folder))
            
            # Process chats from network response (network logging already setup at start)
            logger.info(f"Processing {len(chats_data)} chats for {char_name}")
            self._process_chats_from_network(char_id, chats_data, character_data, char_folder)
            
            logger.info(f"[OK] Successfully processed: {char_name}")
            self.successful += 1
        
        except Exception as e:
            logger.error(f"Error processing character: {e}", exc_info=True)
            self.failures += 1
    
    def _fetch_character_card(
        self,
        char_id: str,
        char_name: str,
        creator: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch character card from janitorai.com/characters/[ID]
        
        Args:
            char_id: Character ID
            char_name: Character name
            creator: Creator username
        
        Returns:
            Character data dict or None
        """
        try:
            # Use character fetcher to get card
            card_url = f"https://janitorai.com/characters/{char_id}"
            character_data = self.character_fetcher.get_character_info(card_url)
            
            if not character_data:
                return None
            
            # Ensure creator is set
            if not character_data.get("creator"):
                character_data["creator"] = creator
            
            return character_data
        
        except Exception as e:
            logger.error(f"Error fetching character card: {e}")
            return None
    
    def _process_chats_from_network(
        self,
        char_id: str,
        chats_data: list,
        character_data: Dict[str, Any],
        char_folder
    ) -> None:
        """Process chats from network response
        
        FIX: Delete character folder if no chats meet message_limit and keep_partial_extracts=False
        
        Args:
            char_id: Character ID
            chats_data: Chats from network response
            character_data: Character data
            char_folder: Output folder for character
        """
        try:
            chat_count = 0
            alternates_from_first_chat = []
            
            for idx, chat in enumerate(chats_data, 1):
                chat_id = chat.get("id")
                
                if not chat_id:
                    logger.debug(f"Skipping chat without ID")
                    continue
                
                logger.debug(f"Processing chat {idx}/{len(chats_data)} (ID: {chat_id})")
                
                # Get chat history from network (the two [CHAT ID] responses)
                messages = self.chat_extractor.get_chat_history(
                    f"https://janitorai.com/chats/{chat_id}"
                )
                
                if not messages:
                    logger.debug(f"No messages for chat {chat_id}")
                    continue
                
                message_count = len(messages)
                
                if message_count >= self.config.message_limit:
                    # FIX: Pass chat_id to save_chat_jsonl
                    self.file_manager.save_chat_jsonl(
                        messages,
                        character_data["name"],
                        character_data.get("creator", "Unknown"),
                        chat_index=chat_count + 1,
                        output_dir=char_folder,
                        chat_id=chat_id  # FIX: Pass the actual chat_id
                    )
                    
                    chat_count += 1
                    self.chats_saved += 1
                    
                    # Get alternates from first successful chat
                    if not alternates_from_first_chat and self.chat_extractor.alternate_greetings:
                        alternates_from_first_chat = [
                            alt.get("message", alt) if isinstance(alt, dict) else alt
                            for alt in self.chat_extractor.alternate_greetings
                        ]
                        logger.info(f"Extracted {len(alternates_from_first_chat)} alternates")
                elif self.config.keep_partial_extracts:
                    # If keep_partial_extracts is enabled, save chats below message limit too
                    self.file_manager.save_chat_jsonl(
                        messages,
                        character_data["name"],
                        character_data.get("creator", "Unknown"),
                        chat_index=chat_count + 1,
                        output_dir=char_folder,
                        chat_id=chat_id
                    )
                    chat_count += 1
                    self.chats_saved += 1
                else:
                    logger.debug(f"Chat {chat_id} has {message_count} messages (below limit {self.config.message_limit}) - skipping")
                
                self.rate_limiter.apply_limit(self.config.delay_between_chats)
            
            # FIX: Check if any chats were actually saved
            if chat_count == 0:
                # No chats met the message limit
                if not self.config.keep_partial_extracts:
                    # Delete the character folder since no valid chats
                    logger.warning(f"No chats met message limit ({self.config.message_limit}) - deleting character folder")
                    self.file_manager.delete_character_folder(char_folder)
                    self.file_manager.track_below_message_limit(
                        character_data["name"],
                        char_id,  # Pass character_id for URL construction
                        0,  # No chats with sufficient messages
                        self.config.message_limit,
                        char_folder.parent
                    )
                    return
                else:
                    logger.info(f"No chats met message limit but keep_partial_extracts=True - keeping character")
            
            # Update character with alternates
            if alternates_from_first_chat:
                character_data = self.card_creator.update_character_json_with_alternates(
                    character_data,
                    alternates_from_first_chat,
                    str(char_folder)
                )
            
            # Create character card
            self.card_creator.create_card(
                character_data,
                output_dir=str(char_folder),
                keep_json=self.config.keep_character_json
            )
            
            logger.info(f"Saved {chat_count} chats for character")
        
        except Exception as e:
            logger.error(f"Error processing chats: {e}", exc_info=True)
    
    def _print_summary(self) -> None:
        """Print scraping summary"""
        logger.info("\n" + "="*60)
        logger.info("HOLY GRAIL SCRAPER SUMMARY:")
        logger.info(f"  Successful: {self.successful}")
        logger.info(f"  Skipped: {self.skipped}")
        logger.info(f"  Failed: {self.failures}")
        logger.info(f"  Total: {self.successful + self.skipped + self.failures}")
        logger.info("="*60)
        logger.info(f"\nOutput saved to: {self.config.output_path.absolute()}")
        
        # Write deleted/private character mapping file
        self.recovery_system.write_mapping_file()
        
        # Organize files if enabled
        if self.config.organize_for_sillytavern:
            logger.info("\n[ORGANIZING] Organizing files into SillyTavern structure...")
            if self.character_list_extractor.characters_by_id:
                self.file_organizer.organize_all(self.character_list_extractor.characters_by_id)
        
        # Second pass: Extract chats from deleted/private characters using mapped chat links
        if self.config.recover_deleted_private_chats:
            logger.info("\n" + "="*60)
            logger.info("PHASE 7: SECOND PASS - EXTRACTING DELETED/PRIVATE CHATS")
            logger.info("="*60)
            
            # Read chat links from mapping file
            char_chat_links = self.recovery_system.read_chat_links_from_mapping()
            
            if char_chat_links:
                logger.info(f"Found {len(char_chat_links)} deleted/private characters with chat links to extract")
                
                for char_name, data in char_chat_links.items():
                    chat_links = data.get("links", [])
                    if not chat_links:
                        continue
                    
                    status = "DELETED" if data.get("is_deleted") else "PRIVATE"
                    logger.info(f"\n[{status}] Extracting {len(chat_links)} chats for {char_name}")
                    
                    # Use chat_network_extractor to extract each chat
                    for idx, chat_link in enumerate(chat_links, 1):
                        logger.debug(f"  [{idx}/{len(chat_links)}] Extracting: {chat_link}")
                        
                        try:
                            # Extract chat messages using chat_network_extractor
                            messages = self.chat_extractor.get_chat_history(chat_link)
                            
                            if messages and len(messages) >= self.config.message_limit:
                                # Save to recovery directory
                                self.recovery_system.save_character_chats(char_name, messages)
                                logger.debug(f"  ✓ Saved {len(messages)} messages")
                            else:
                                logger.debug(f"  Skipped (insufficient messages: {len(messages) if messages else 0})")
                        
                        except Exception as e:
                            logger.warning(f"  Error extracting chat: {e}")
                        
                        self.rate_limiter.apply_limit(self.config.delay_between_chats)
                
                logger.info(f"\n[OK] Deleted/private chat extraction complete!")
            else:
                logger.info("No deleted/private character chat links found in mapping")


def main():
    """Main entry point"""
    setup_logging()
    
    try:
        config = ScraperConfig.from_user_input()
        scraper = HolyGrailScraper(config)
        scraper.run()
    
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
