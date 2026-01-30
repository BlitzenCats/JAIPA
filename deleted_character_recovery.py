"""Recovery system for deleted/private character chat histories"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DeletedCharacterRecovery:
    """Track and recover chat histories for deleted/private characters"""
    
    def __init__(self, base_output_dir: str):
        """Initialize recovery system
        
        Args:
            base_output_dir: Base output directory
        """
        self.base_dir = Path(base_output_dir)
        self.recovery_dir = self.base_dir / "Deleted/Privated Character Chat history"
        self.mapping_file = self.recovery_dir / "deleted_character_chat_mapping.txt"
        
        # Track deleted/private characters with chats
        self.deleted_characters_with_chats: Dict[str, Dict] = {}
        self.private_characters_with_chats: Dict[str, Dict] = {}
    
    def track_character_chats(self, character_id: str, character_name: str, 
                            chat_count: int, is_deleted: bool, 
                            is_public: bool, chats: Optional[List] = None,
                            chat_links: Optional[List[str]] = None) -> None:
        """Track a deleted/private character that has chats
        
        Args:
            character_id: Character ID
            character_name: Character name
            chat_count: Number of chats available
            is_deleted: Whether character is deleted
            is_public: Whether character is public
            chats: List of chats (optional)
            chat_links: List of chat URLs (optional)
        """
        if is_deleted or not is_public:
            char_info = {
                "name": character_name,
                "id": character_id,
                "chat_count": chat_count,
                "is_deleted": is_deleted,
                "is_public": is_public,
                "chats": chats or [],
                "chat_links": chat_links or [],
                "url": f"https://janitorai.com/characters/{character_id}"
            }
            
            if is_deleted:
                self.deleted_characters_with_chats[character_id] = char_info
            else:
                self.private_characters_with_chats[character_id] = char_info
    
    def write_mapping_file(self) -> bool:
        """Write deleted/private character chat mapping to file
        
        Returns:
            True if successful
        """
        try:
            total = len(self.deleted_characters_with_chats) + len(self.private_characters_with_chats)
            
            if total == 0:
                logger.info("No deleted/private characters with chats to map")
                return True
            
            # Create recovery directory
            self.recovery_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.mapping_file, 'w', encoding='utf-8') as f:
                f.write("="*70 + "\n")
                f.write("DELETED/PRIVATE CHARACTER CHAT MAPPING\n")
                f.write("="*70 + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Characters: {total}\n")
                f.write(f"  Deleted: {len(self.deleted_characters_with_chats)}\n")
                f.write(f"  Private: {len(self.private_characters_with_chats)}\n\n")
                
                # Deleted characters
                if self.deleted_characters_with_chats:
                    f.write("DELETED CHARACTERS\n")
                    f.write("-"*70 + "\n\n")
                    
                    for char_id, info in self.deleted_characters_with_chats.items():
                        f.write(f"Character: {info['name']}\n")
                        f.write(f"ID: {char_id}\n")
                        f.write(f"URL: {info['url']}\n")
                        f.write(f"Chat Count: {info['chat_count']}\n")
                        f.write(f"Status: DELETED\n")
                        if info['chat_links']:
                            f.write(f"Chat Links:\n")
                            for link in info['chat_links']:
                                f.write(f"  - {link}\n")
                        f.write("\n")
                
                # Private characters
                if self.private_characters_with_chats:
                    f.write("\n" + "="*70 + "\n")
                    f.write("PRIVATE CHARACTERS\n")
                    f.write("-"*70 + "\n\n")
                    
                    for char_id, info in self.private_characters_with_chats.items():
                        f.write(f"Character: {info['name']}\n")
                        f.write(f"ID: {char_id}\n")
                        f.write(f"URL: {info['url']}\n")
                        f.write(f"Chat Count: {info['chat_count']}\n")
                        f.write(f"Status: PRIVATE\n")
                        if info['chat_links']:
                            f.write(f"Chat Links:\n")
                            for link in info['chat_links']:
                                f.write(f"  - {link}\n")
                        f.write("\n")
            
            logger.info(f"[OK] Mapping file created: {self.mapping_file}")
            logger.info(f"     Total characters mapped: {total}")
            return True
        
        except Exception as e:
            logger.error(f"Error writing mapping file: {e}", exc_info=True)
            return False
    
    def save_character_chats(self, character_name: str, chats: List[Dict], chat_id: str = "0") -> bool:
        """Save chat history for a deleted/private character
        
        Args:
            character_name: Character name
            chats: List of chats (messages)
            chat_id: Chat ID for unique filename (prevents overwrites)
        
        Returns:
            True if successful
        """
        try:
            self.recovery_dir.mkdir(parents=True, exist_ok=True)
            
            # Create character folder
            char_dir = self.recovery_dir / character_name
            char_dir.mkdir(parents=True, exist_ok=True)
            
            # Save as JSONL with chat_id to prevent overwrites
            jsonl_file = char_dir / f"{character_name}_chat_{chat_id}.jsonl"
            
            with open(jsonl_file, 'w', encoding='utf-8') as f:
                for chat in chats:
                    f.write(json.dumps(chat, ensure_ascii=False) + '\n')
            
            logger.debug(f"Saved {len(chats)} messages for {character_name} (chat_id: {chat_id})")
            return True
        
        except Exception as e:
            logger.error(f"Error saving chats for {character_name}: {e}", exc_info=True)
            return False
    
    def save_all_character_chats(self) -> bool:
        """Save all tracked deleted/private character chats
        
        Returns:
            True if all successful
        """
        try:
            success = True
            
            for char_id, info in self.deleted_characters_with_chats.items():
                if info['chats']:
                    if not self.save_character_chats(info['name'], info['chats']):
                        success = False
            
            for char_id, info in self.private_characters_with_chats.items():
                if info['chats']:
                    if not self.save_character_chats(info['name'], info['chats']):
                        success = False
            
            return success
        
        except Exception as e:
            logger.error(f"Error saving all character chats: {e}", exc_info=True)
            return False
    
    def get_summary(self) -> str:
        """Get summary of deleted/private characters found
        
        Returns:
            Summary string
        """
        deleted_with_chats = sum(1 for info in self.deleted_characters_with_chats.values() if info['chat_links'])
        private_with_chats = sum(1 for info in self.private_characters_with_chats.values() if info['chat_links'])
        
        return f"Deleted: {deleted_with_chats}, Private: {private_with_chats}"
    
    def read_chat_links_from_mapping(self) -> Dict[str, Dict[str, any]]:
        """Read chat links from mapping file for second pass extraction
        
        Returns:
            Dict mapping character_name -> {links: [...], is_deleted: bool}
        """
        try:
            if not self.mapping_file.exists():
                logger.warning(f"Mapping file not found: {self.mapping_file}")
                return {}
            
            result = {}
            current_section = None
            current_char_name = None
            current_char_data = None
            
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip()
                    
                    # Detect section
                    if "DELETED CHARACTERS" in line:
                        current_section = "deleted"
                    elif "PRIVATE CHARACTERS" in line:
                        current_section = "private"
                    
                    # Parse character name
                    if line.startswith("Character: "):
                        current_char_name = line.replace("Character: ", "").strip()
                        current_char_data = {
                            "links": [],
                            "is_deleted": current_section == "deleted"
                        }
                    
                    # Parse chat links
                    if line.strip().startswith("- ") and current_char_data:
                        chat_link = line.strip()[2:].strip()
                        current_char_data["links"].append(chat_link)
                    
                    # Save when we hit empty line (end of character)
                    if line.strip() == "" and current_char_name and current_char_data:
                        if current_char_data["links"]:  # Only save if has links
                            result[current_char_name] = current_char_data
                        current_char_name = None
                        current_char_data = None
            
            logger.info(f"[OK] Read {len(result)} deleted/private characters from mapping file")
            return result
        
        except Exception as e:
            logger.error(f"Error reading mapping file: {e}", exc_info=True)
            return {}

