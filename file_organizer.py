"""Organize exported files into SillyTavern-compatible folder structure"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from scraper_utils import sanitize_filename

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Organize exported character files for easy import into SillyTavern"""
    
    def __init__(self, base_output_dir: str, organize_enabled: bool = True):
        """Initialize file organizer
        
        Args:
            base_output_dir: Base output directory containing exported files
            organize_enabled: Whether to organize files (if False, only validates)
        """
        self.base_dir = Path(base_output_dir)
        self.organize_enabled = organize_enabled
        
        # Output folders
        self.characters_dir = self.base_dir / "characters"
        self.chats_dir = self.base_dir / "chats"
        self.json_dir = self.base_dir / "json"
        
        # Create directories if organizing
        if self.organize_enabled:
            self.characters_dir.mkdir(parents=True, exist_ok=True)
            self.chats_dir.mkdir(parents=True, exist_ok=True)
            self.json_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"File organizer initialized (organize_enabled={organize_enabled})")
    
    def deduplicate_names(self, character_names: List[str]) -> Dict[str, str]:
        """Create mapping from original name to deduplicated name
        
        Duplicate names get numeric suffixes: "name1", "name2", etc.
        
        Args:
            character_names: List of character names
        
        Returns:
            Dict mapping original_name -> deduplicated_name
        """
        name_counts = defaultdict(int)
        result = {}
        
        # Count occurrences
        for name in character_names:
            name_counts[name] += 1
        
        # Reset counts for assignment
        name_assigned = defaultdict(int)
        
        for name in character_names:
            if name_counts[name] > 1:
                # Duplicate - add number
                name_assigned[name] += 1
                deduplicated = f"{name}{name_assigned[name]}"
            else:
                # Unique - keep as is
                deduplicated = name
            
            result[name] = deduplicated
        
        return result
    
    def organize_characters(self, character_data: Dict[str, Dict]) -> bool:
        """Organize character PNG files
        
        Args:
            character_data: Dict mapping character_id to character info
        
        Returns:
            True if successful
        """
        try:
            if not self.organize_enabled:
                logger.info("Organization disabled - skipping character file organization")
                return True
            
            # Instead of relying on character_data names, scan the actual directories
            # to handle cases where folder names don't exactly match character_data
            organized_count = 0
            skipped_count = 0
            
            # Scan all directories in base_dir
            for item in self.base_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip special folders
                if item.name in ["characters", "chats", "json", "User Avatars", "Deleted"]:
                    continue
                
                # Look for PNG files in this directory
                png_files = list(item.glob("*.png"))
                
                if not png_files:
                    logger.debug(f"No PNG files found in {item.name}")
                    skipped_count += 1
                    continue
                
                # Use the folder name as the character name for deduplication
                char_name = item.name
                deduplicated_name = char_name  # Could apply name mapping here if needed
                
                for png_file in png_files:
                    # Create destination with deduplicated name
                    dest_png = self.characters_dir / f"{deduplicated_name}.png"
                    
                    if self.organize_enabled:
                        shutil.copy2(png_file, dest_png)
                        logger.debug(f"Copied {png_file.name} → characters/{deduplicated_name}.png")
                        organized_count += 1
            
            logger.info(f"[OK] Organized {organized_count} character PNG files (skipped {skipped_count})")
            return True
        
        except Exception as e:
            logger.error(f"Error organizing character files: {e}", exc_info=True)
            return False
        
        except Exception as e:
            logger.error(f"Error organizing character files: {e}", exc_info=True)
            return False
    
    def organize_chats(self, character_data: Dict[str, Dict]) -> bool:
        """Organize chat JSONL files into character-named folders
        
        Structure: chats/{character_name}/{character_name}.jsonl
        
        Args:
            character_data: Dict mapping character_id to character info
        
        Returns:
            True if successful
        """
        try:
            if not self.organize_enabled:
                logger.info("Organization disabled - skipping chat file organization")
                return True
            
            # Scan actual directories instead of relying on character_data
            organized_count = 0
            skipped_count = 0
            
            # Find and move JSONL files
            for item in self.base_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip special folders
                if item.name in ["characters", "chats", "json", "User Avatars", "Deleted"]:
                    continue
                
                jsonl_files = list(item.glob("*_chat_*.jsonl"))
                
                if not jsonl_files:
                    logger.debug(f"No JSONL files found in {item.name}")
                    skipped_count += 1
                    continue
                
                char_name = item.name
                
                for jsonl_file in jsonl_files:
                    # Create character folder
                    char_chat_dir = self.chats_dir / char_name
                    char_chat_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Copy JSONL keeping original filename to preserve chat_id uniqueness
                    dest_jsonl = char_chat_dir / jsonl_file.name
                    
                    if self.organize_enabled:
                        shutil.copy2(jsonl_file, dest_jsonl)
                        logger.debug(f"Copied {jsonl_file.name} → chats/{char_name}/{jsonl_file.name}")
                        organized_count += 1
            
            logger.info(f"[OK] Organized {organized_count} chat JSONL files (skipped {skipped_count})")
            return True
        
        except Exception as e:
            logger.error(f"Error organizing chat files: {e}", exc_info=True)
            return False
        
        except Exception as e:
            logger.error(f"Error organizing chat files: {e}", exc_info=True)
            return False
    
    def organize_json_cards(self, character_data: Dict[str, Dict]) -> bool:
        """Organize character JSON card files
        
        Args:
            character_data: Dict mapping character_id to character info
        
        Returns:
            True if successful
        """
        try:
            if not self.organize_enabled:
                logger.info("Organization disabled - skipping JSON card organization")
                return True
            
            # Scan actual directories instead of relying on character_data
            organized_count = 0
            skipped_count = 0
            
            # Find and move JSON files
            for item in self.base_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip special folders
                if item.name in ["characters", "chats", "json", "User Avatars", "Deleted"]:
                    continue
                
                json_files = list(item.glob("*.json"))
                
                if not json_files:
                    logger.debug(f"No JSON files found in {item.name}")
                    skipped_count += 1
                    continue
                
                char_name = item.name
                
                for json_file in json_files:
                    # Copy with character name
                    dest_json = self.json_dir / f"{char_name}.json"
                    
                    if self.organize_enabled:
                        shutil.copy2(json_file, dest_json)
                        logger.debug(f"Copied {json_file.name} → json/{char_name}.json")
                        organized_count += 1
            
            logger.info(f"[OK] Organized {organized_count} JSON card files (skipped {skipped_count})")
            return True
        
        except Exception as e:
            logger.error(f"Error organizing JSON card files: {e}", exc_info=True)
            return False
    
    def organize_user_files(self) -> bool:
        """Organize user/metadata files into User folder
        
        Moves: mapping files, personas, generation settings, character lists, etc.
        
        Returns:
            True if successful
        """
        try:
            if not self.organize_enabled:
                logger.info("Organization disabled - skipping user file organization")
                return True
            
            # Create User folder
            user_dir = self.base_dir / "User"
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Files to move to User folder
            user_files = [
                "deleted_character_chat_mapping.txt",
                "Generation_Settings.txt",
                "personas.json",
                "Personas.txt",
                "Private_Characters.txt",
                "Deleted_Characters.txt"
            ]
            
            organized_count = 0
            
            for filename in user_files:
                src_file = self.base_dir / filename
                if src_file.exists() and src_file.is_file():
                    dest_file = user_dir / filename
                    shutil.move(str(src_file), str(dest_file))
                    logger.debug(f"Moved {filename} → User/")
                    organized_count += 1
            
            if organized_count > 0:
                logger.info(f"[OK] Organized {organized_count} user/metadata files into User folder")
            else:
                logger.debug("No user/metadata files found to organize")
            
            return True
        
        except Exception as e:
            logger.error(f"Error organizing user files: {e}", exc_info=True)
            return False
    
    def organize_all(self, character_data: Dict[str, Dict]) -> bool:
        """Organize all exported files
        
        Args:
            character_data: Dict mapping character_id to character info
        
        Returns:
            True if all operations successful
        """
        logger.info("\n" + "="*60)
        logger.info("ORGANIZING EXPORTED FILES FOR IMPORT")
        logger.info("="*60)
        
        success = True
        
        # Organize by type
        if not self.organize_characters(character_data):
            success = False
        
        if not self.organize_chats(character_data):
            success = False
        
        if not self.organize_json_cards(character_data):
            success = False
        
        # Organize user/metadata files
        if not self.organize_user_files():
            success = False
        
        # Clean up original character folders if organizing
        if success and self.organize_enabled:
            self._cleanup_original_folders(character_data)
        
        if success:
            self._print_import_instructions()
        
        return success
    
    def _cleanup_original_folders(self, character_data: Dict[str, Dict]) -> None:
        """Delete original character folders after organization
        
        Args:
            character_data: Dict mapping character_id to character info
        """
        try:
            deleted_count = 0
            
            # Scan actual directories
            for item in self.base_dir.iterdir():
                if not item.is_dir():
                    continue
                
                # Skip special folders
                if item.name in ["characters", "chats", "json", "User Avatars", "Deleted", "User"]:
                    continue
                
                try:
                    shutil.rmtree(item)
                    logger.debug(f"Deleted original folder: {item.name}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {item.name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"[OK] Cleaned up {deleted_count} original character folders")
        
        except Exception as e:
            logger.warning(f"Error during cleanup of original folders: {e}")
    
    def _print_import_instructions(self) -> None:
        """Print instructions for importing into SillyTavern"""
        instructions = """
╔══════════════════════════════════════════════════════════════╗
║   HOW TO IMPORT INTO SILLYTAVERN                             ║
╚══════════════════════════════════════════════════════════════╝

📁 Folder Structure Created:
   • characters/ - Contains all character PNG files (deduplicated names)
   • chats/ - Contains chat history organized by character
   • json/ - Contains JSON card definitions (if enabled)
   • User Avatars/ - Contains all persona avatars
   • User/ - Contains metadata files (personas, chat mappings, character lists, etc.)

📥 IMPORT STEPS:

1. Locate your SillyTavern installation folder

2. Navigate to: SillyTavern/data/{USERNAME}/

3. Backup existing files (optional but recommended):
   • Rename current 'characters' folder to 'characters_backup'
   • Rename current 'chats' folder to 'chats_backup'

4. Copy the organized files:
   • Drag 'characters' folder → SillyTavern/data/{USERNAME}/characters
   • Drag 'chats' folder → SillyTavern/data/{USERNAME}/chats
   • Drag 'User Avatars' folder → SillyTavern/data/{USERNAME}/User Avatars

5. Import Personas:
    • Open SillyTavern
    • Go to 'Personas' tab
    • Click 'Import Personas from File'
    • Select the personas.json file from the 'User' folder

6. Restart SillyTavern

🔍 REFERENCE:
   • PNG filenames match chat folder names (e.g., "character1.png" ↔ "character1/" folder)
   • Duplicates are numbered: character1, character2, character3, etc.
   • Chat files are named after their character folder
   • Metadata files in User/ include chat mappings and character information

📂 Common SillyTavern paths:
   • Windows: C:\\Users\\[YOUR_NAME]\\SillyTavern\\data\\{USERNAME}
   • Linux: /home/[YOUR_NAME]/SillyTavern/data/{USERNAME}
   • macOS: /Users/[YOUR_NAME]/SillyTavern/data/{USERNAME}

"""
        logger.info(instructions)
