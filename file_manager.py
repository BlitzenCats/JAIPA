"""File management for JanitorAI Scraper"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import jsonlines

from scraper_utils import sanitize_filename, safe_create_directory

logger = logging.getLogger(__name__)


class FileManager:
    """Handles all file I/O operations"""
    
    def __init__(self, output_dir: str = "Output"):
        """Initialize file manager
        
        Args:
            output_dir: Base output directory
        """
        self.output_dir = Path(output_dir)
        self.existing_folders = set()
        self._initialize_output_dir()
    
    def _initialize_output_dir(self) -> None:
        """Create output directory if needed"""
        if safe_create_directory(self.output_dir):
            logger.info(f"Output directory: {self.output_dir.absolute()}")
        
        # Load existing folders for duplicate detection
        if self.output_dir.exists():
            self.existing_folders = {folder.name for folder in self.output_dir.iterdir() if folder.is_dir()}
    
    def create_character_folder(
        self,
        character_name: str,
        character_url: str = ""
    ) -> Optional[Path]:
        """Create folder for character with duplicate handling
        
        Args:
            character_name: Character name for folder
            character_url: Character URL for uniqueness checking
        
        Returns:
            Path to character folder or None
        """
        safe_name = sanitize_filename(character_name)
        
        # Check if folder exists and is same character
        folder_path = self.output_dir / safe_name
        if folder_path.exists() and character_url:
            json_file = folder_path / f"{safe_name}.json"
            if json_file.exists():
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                        if existing_data.get("url") == character_url:
                            logger.info(f"Character already processed: {character_name}")
                            return folder_path
                except Exception as e:
                    logger.warning(f"Could not read existing character data: {e}")
        
        # Add suffix for duplicates
        counter = 1
        original_name = safe_name
        while folder_path.exists():
            safe_name = f"{original_name}_+{counter}"
            folder_path = self.output_dir / safe_name
            counter += 1
        
        # Create folder
        if safe_create_directory(folder_path):
            self.existing_folders.add(folder_path.name)
            logger.info(f"Created character folder: {folder_path.name}")
            return folder_path
        
        return None
    
    def save_json(
        self,
        data: Dict[str, Any],
        filename: str,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Save JSON file
        
        Args:
            data: Dictionary to save
            filename: Filename (without extension)
            output_dir: Directory to save in (uses character dir if None)
        
        Returns:
            Path to saved file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            file_path = output_dir / f"{sanitize_filename(filename)}.json"
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved JSON to {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")
            return None
    
    def save_jsonl(
        self,
        data_lines: List[Dict[str, Any]],
        filename: str,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Save JSONL file (JSON lines format)
        
        Args:
            data_lines: List of dictionaries to save as lines
            filename: Filename (without extension)
            output_dir: Directory to save in
        
        Returns:
            Path to saved file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            file_path = output_dir / f"{sanitize_filename(filename)}.jsonl"
            
            with jsonlines.open(file_path, mode="w") as writer:
                for line in data_lines:
                    writer.write(line)
            
            logger.debug(f"Saved JSONL to {file_path}")
            return file_path
        
        except Exception as e:
            logger.error(f"Error saving JSONL: {e}")
            return None
    
    def save_chat_jsonl(
        self,
        messages: List[Dict[str, Any]],
        character_name: str,
        character_creator: str,
        chat_index: int = 1,
        output_dir: Optional[Path] = None,
        chat_id: Optional[Any] = None
    ) -> Optional[Path]:
        """Save chat history as JSONL file
        
        CRITICAL CHANGE: Messages are ALREADY in JSONL format from ChatNetworkParser!
        Just prepend metadata and save - DO NOT recreate them!
        
        FIX: Use actual chat_id from API in metadata
        
        Args:
            messages: List of JSONL-formatted message dicts (from ChatNetworkParser)
            character_name: Character name
            character_creator: Creator name
            chat_index: Chat index (for multiple chats)
            output_dir: Directory to save in
            chat_id: Chat ID to use in metadata (extracted from API)
        
        Returns:
            Path to saved file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            # FIX: Extract chat ID properly
            # First check if provided as parameter
            if chat_id is None and messages and len(messages) > 0:
                # Try to get from first message's extra data
                first_msg = messages[0]
                if isinstance(first_msg, dict):
                    # Could be stored in extra during parsing
                    chat_id = first_msg.get("extra", {}).get("chat_id", 0)
            
            # If still None, default to 0
            if chat_id is None:
                chat_id = 0
            
            # Convert chat_id to int if it's a string
            if isinstance(chat_id, str):
                try:
                    chat_id = int(chat_id)
                except (ValueError, TypeError):
                    # Keep as string if conversion fails
                    pass
            
            # Create metadata line with actual chat_id
            metadata = {
                "chat_metadata": {
                    "integrity": "",
                    "chat_id_hash": chat_id,  # FIX: Use actual chat ID
                    "note_prompt": "",
                    "note_interval": 1,
                    "note_position": 1,
                    "note_depth": 4,
                    "note_role": 0,
                    "tainted": False,  # Changed from True to False to match spec
                    "timedWorldInfo": {"sticky": {}, "cooldown": {}},
                    "lastInContextMessageId": 0,
                },
                "user_name": "unused",
                "character_name": character_name,
            }
            
            # CRITICAL: Messages are ALREADY formatted!
            # Just prepend metadata - don't recreate!
            data_lines = [metadata] + messages
            
            # Create filename using chat_id for uniqueness
            filename = f"{sanitize_filename(character_name)}_chat_{chat_id}"
            file_path = output_dir / f"{filename}.jsonl"
            
            # Save to JSONL
            with jsonlines.open(file_path, mode="w") as writer:
                for line in data_lines:
                    writer.write(line)
            
            logger.info(f"Saved chat history: {filename}.jsonl ({len(messages)} messages)")
            return file_path
        
        except Exception as e:
            logger.error(f"Error saving chat JSONL: {e}")
            return None
    
    def save_text(
        self,
        content: str,
        filename: str,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Save plain text file
        
        Args:
            content: Text content
            filename: Filename
            output_dir: Directory to save in
        
        Returns:
            Path to saved file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            file_path = output_dir / sanitize_filename(filename)
            
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
            
            return file_path
        
        except Exception as e:
            logger.error(f"Error saving text: {e}")
            return None
    
    def save_binary(
        self,
        content: bytes,
        filename: str,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Save binary file
        
        Args:
            content: Binary content
            filename: Filename
            output_dir: Directory to save in
        
        Returns:
            Path to saved file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            file_path = output_dir / sanitize_filename(filename)
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            return file_path
        
        except Exception as e:
            logger.error(f"Error saving binary: {e}")
            return None
    
    def file_exists(self, filename: str, output_dir: Optional[Path] = None) -> bool:
        """Check if file exists
        
        Args:
            filename: Filename to check
            output_dir: Directory to check in
        
        Returns:
            True if file exists
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        return (Path(output_dir) / sanitize_filename(filename)).exists()
    
    def delete_file(self, filename: str, output_dir: Optional[Path] = None) -> bool:
        """Delete file if it exists
        
        Args:
            filename: Filename to delete
            output_dir: Directory to delete from
        
        Returns:
            True if deleted successfully
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            file_path = Path(output_dir) / sanitize_filename(filename)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def delete_character_folder(self, folder_path: Path) -> bool:
        """Delete entire character folder and its contents
        
        Args:
            folder_path: Path to character folder
        
        Returns:
            True if deleted successfully
        """
        try:
            if folder_path.exists() and folder_path.is_dir():
                import shutil
                shutil.rmtree(folder_path)
                logger.info(f"Deleted character folder: {folder_path.name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting character folder {folder_path}: {e}")
            return False
    
    def track_below_message_limit(
        self,
        character_name: str,
        character_id: str,
        message_count: int,
        message_limit: int,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Track characters that were skipped due to low message count
        
        Creates a Below_Message_Count.txt file listing skipped characters with links
        
        Args:
            character_name: Character name
            character_id: Character ID (for constructing URL)
            message_count: Actual message count (0 if no chats met limit)
            message_limit: Required message limit
            output_dir: Directory to save tracking file
        
        Returns:
            Path to tracking file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            # Create tracking file
            tracking_file = output_dir / "Below_Message_Count.txt"
            
            # Format: Character Name (X messages - needed Y) | https://janitorai.com/characters/[ID]
            character_url = f"https://janitorai.com/characters/{character_id}"
            entry = f"{character_name} ({message_count} messages - needed {message_limit}) | {character_url}"
            
            # Append to file (create if doesn't exist)
            with open(tracking_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            
            logger.debug(f"Tracked below-limit character: {entry}")
            return tracking_file
        
        except Exception as e:
            logger.error(f"Error tracking below-limit character: {e}")
            return None
    
    def track_failed_chat(
        self,
        character_name: str,
        chat_url: str,
        reason: str = "unknown",
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """Track chats that failed to extract
        
        Creates/appends to Failed_Chat_Extractions.txt with format:
        Character Name
        - https://janitorai.com/chats/12345 (reason)
        
        Args:
            character_name: Character name
            chat_url: Full URL of the failed chat
            reason: Reason for failure (e.g., "timeout", "no response", "parse error")
            output_dir: Directory to save tracking file
        
        Returns:
            Path to tracking file or None
        """
        if output_dir is None:
            output_dir = self.output_dir
        
        try:
            output_dir = Path(output_dir)
            safe_create_directory(output_dir)
            
            tracking_file = output_dir / "Failed_Chat_Extractions.txt"
            
            # Read existing content to check if character already has entries
            existing_content = ""
            if tracking_file.exists():
                with open(tracking_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            
            # Check if character name already exists in file
            char_header = f"{character_name}\n"
            entry = f"- {chat_url} ({reason})\n"
            
            if char_header in existing_content:
                # Character exists - insert entry after the header
                # Find position after the character name line
                lines = existing_content.split('\n')
                new_lines = []
                inserted = False
                for i, line in enumerate(lines):
                    new_lines.append(line)
                    if line == character_name and not inserted:
                        # Insert our new entry right after the character name
                        # But first check if the entry already exists
                        if entry.strip() not in existing_content:
                            new_lines.append(entry.rstrip())
                        inserted = True
                
                with open(tracking_file, "w", encoding="utf-8") as f:
                    f.write('\n'.join(new_lines))
            else:
                # New character - append header and entry
                with open(tracking_file, "a", encoding="utf-8") as f:
                    # Add newline before if file not empty
                    if existing_content and not existing_content.endswith('\n\n'):
                        f.write("\n")
                    f.write(char_header)
                    f.write(entry)
            
            logger.debug(f"Tracked failed chat: {character_name} - {chat_url} ({reason})")
            return tracking_file
        
        except Exception as e:
            logger.error(f"Error tracking failed chat: {e}")
            return None

