"""Message parsing and character card creation for JanitorAI Scraper"""

import base64
import io
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

try:
    from PIL import Image, PngImagePlugin
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from file_manager import FileManager
from scraper_utils import sanitize_filename

logger = logging.getLogger(__name__)


class MessageParser:
    """Parses raw message text into structured message objects"""
    
    @staticmethod
    def parse_messages(
        raw_text_items: List[str],
        character_name: str
    ) -> List[Dict[str, Any]]:
        """Parse raw text items from Virtuoso into structured messages
        
        Args:
            raw_text_items: List of raw text items from page
            character_name: Name of character
        
        Returns:
            List of structured message dictionaries
        """
        messages = []
        
        for item_text in raw_text_items:
            message = MessageParser.parse_single_message(item_text, character_name)
            if message:
                messages.append(message)
        
        return messages
    
    @staticmethod
    def parse_single_message(
        item_text: str,
        character_name: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single raw message text into structured message
        
        Args:
            item_text: Raw message text
            character_name: Character name
        
        Returns:
            Structured message dictionary or None
        """
        lines = item_text.split("\n")
        
        if not lines or len(lines) == 0:
            return None
        
        first_line = lines[0].strip()
        
        # Determine message type and sender
        is_user = False
        sender_name = character_name
        content_start = 0
        
        # Check for disclaimer (character message)
        if "All replies" in first_line and "work of fiction" in first_line:
            is_user = False
            sender_name = character_name
            content_start = 1
            
            # Skip character name if it's next line
            if len(lines) > 1 and lines[1].strip() == character_name:
                content_start = 2
        
        # Check if first line is character name
        elif first_line == character_name:
            is_user = False
            sender_name = character_name
            content_start = 1
        
        else:
            # User message - first line is persona name
            is_user = True
            sender_name = first_line
            content_start = 1
        
        # Extract message content
        message_content = "\n".join(lines[content_start:]).strip()
        
        # Only add if we have actual content
        if not message_content or len(message_content.strip()) < 2:
            return None
        
        return {
            "message": message_content,
            "is_bot": not is_user,
            "name": sender_name,
            "character_name": character_name,
            "created_at": datetime.now().isoformat() + "Z",
        }


class CharacterCardCreator:
    """Creates character card PNG files with V3 format"""
    
    def __init__(self, file_manager: FileManager):
        """Initialize card creator
        
        Args:
            file_manager: FileManager instance for saving files
        """
        self.file_manager = file_manager
        
        if not HAS_PIL:
            logger.warning("PIL not installed - character cards will not have images")
    
    def create_card(
        self,
        character_data: Dict[str, Any],
        output_dir: Optional[str] = None,
        image_path: Optional[str] = None,
        keep_json: bool = False
    ) -> Optional[str]:
        """Create character card PNG in V3 format
        
        Args:
            character_data: Character information
            output_dir: Directory to save card
            image_path: Path to character image
            keep_json: If True, keep the edited JSON file after embedding
        
        Returns:
            Path to created card or None
        """
        if not HAS_PIL:
            logger.warning("PIL not available - skipping character card creation")
            return None
        
        try:
            if output_dir is None:
                output_dir = self.file_manager.output_dir
            
            # Download or load image
            if not image_path:
                if not character_data.get("image_url"):
                    logger.warning(f"No image available for character card")
                    return None
                
                image_data = self._download_image(character_data["image_url"])
                if not image_data:
                    return None
                
                img = Image.open(io.BytesIO(image_data))
            else:
                img = Image.open(image_path)
            
            # Convert to RGBA
            if img.mode in ("P", "RGB"):
                img = img.convert("RGBA")
            
            # Create V3 format data
            v3_data = self._create_v3_data(character_data)
            
            # Add metadata
            metadata = self._create_png_metadata(v3_data)
            
            # Save card to character folder
            card_filename = f"{sanitize_filename(character_data['name'])}.png"
            card_path = Path(output_dir) / card_filename
            
            img.save(str(card_path), "PNG", pnginfo=metadata)
            
            logger.info(f"[OK] Created character card: {card_filename}")
            
            # Clean up JSON file if not keeping it
            if not keep_json:
                json_filename = f"{sanitize_filename(character_data['name'])}.json"
                json_path = Path(output_dir) / json_filename
                if json_path.exists():
                    json_path.unlink()
                    logger.debug(f"Removed JSON file: {json_filename}")
            else:
                logger.debug(f"Keeping JSON file as requested")
            
            return str(card_path)
        
        except Exception as e:
            logger.error(f"Error creating character card: {e}")
            return None
    
    def save_character_json(
        self,
        character_data: Dict[str, Any],
        output_dir: Optional[str] = None
    ) -> Optional[str]:
        """Save character data as JSON file in Character Card V3 format
        
        Args:
            character_data: Character information
            output_dir: Directory to save JSON
        
        Returns:
            Path to saved JSON file or None
        """
        try:
            if output_dir is None:
                output_dir = self.file_manager.output_dir
            
            json_filename = f"{sanitize_filename(character_data['name'])}.json"
            json_path = Path(output_dir) / json_filename
            
            # Get alternate greetings
            alternate_greetings = character_data.get("alternate_greetings", [])
            if isinstance(alternate_greetings, list) and alternate_greetings:
                alt_greetings = [g.get("message", g) if isinstance(g, dict) else g 
                               for g in alternate_greetings if g]
            else:
                alt_greetings = []
            
            # Get tags
            tags = character_data.get("tags", [])
            
            # Create proper V3 format matching Example Character V3.json
            output_data = {
                # Top-level V2-compatible fields
                "name": character_data.get("name", "Unknown"),
                "description": "",
                "personality": character_data.get("personality", ""),
                "scenario": character_data.get("scenario", ""),
                "first_mes": character_data.get("first_message", ""),
                "mes_example": character_data.get("example_dialogs", ""),
                "creatorcomment": (
                    f"Creator: {character_data.get('creator', 'Unknown')}\n"
                    f"Source: {character_data.get('url', '')}\n\n"
                    f"Description:\n{character_data.get('description', '')}"
                ),
                "avatar": "none",
                "talkativeness": "0.5",
                "fav": False,
                "tags": tags,
                
                # V3 spec info
                "spec": "chara_card_v3",
                "spec_version": "3.0",
                
                # V3 data block
                "data": {
                    "name": character_data.get("name", "Unknown"),
                    "description": "",
                    "personality": character_data.get("personality", ""),
                    "scenario": character_data.get("scenario", ""),
                    "first_mes": character_data.get("first_message", ""),
                    "mes_example": character_data.get("example_dialogs", ""),
                    "creator_notes": (
                        f"Creator: {character_data.get('creator', 'Unknown')}\n"
                        f"Source: {character_data.get('url', '')}\n\n"
                        f"Description:\n{character_data.get('description', '')}"
                    ),
                    "system_prompt": "",
                    "post_history_instructions": "",
                    "tags": tags,
                    "creator": character_data.get("creator", "Unknown"),
                    "character_version": "1.0",
                    "alternate_greetings": alt_greetings,
                    "extensions": {
                        "talkativeness": "0.5",
                        "fav": False,
                        "world": "",
                        "depth_prompt": {
                            "prompt": "",
                            "depth": 4,
                            "role": "system"
                        }
                    },
                    "group_only_greetings": []
                },
                
                # Create date in ISO format
                "create_date": datetime.now().isoformat() + "Z"
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            
            logger.debug(f"Saved character JSON (V3 format): {json_filename}")
            return str(json_path)
        
        except Exception as e:
            logger.error(f"Error saving character JSON: {e}")
            return None
    
    def update_character_json_with_alternates(
        self,
        character_data: Dict[str, Any],
        alternates: List[str],
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update character data with alternate greetings from chat
        
        Args:
            character_data: Character information
            alternates: List of alternate greeting messages
            output_dir: Directory to update JSON in
        
        Returns:
            Updated character data
        """
        try:
            # Update with alternates
            if alternates:
                character_data["alternate_greetings"] = alternates
                logger.info(f"Added {len(alternates)} alternate greetings to character card")
            
            # Save updated JSON
            if output_dir:
                self.save_character_json(character_data, output_dir)
            
            return character_data
        
        except Exception as e:
            logger.error(f"Error updating character JSON with alternates: {e}")
            return character_data
    
    @staticmethod
    def _create_v3_data(character_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create V3 format character data
        
        Args:
            character_data: Character information
        
        Returns:
            V3 format data structure
        """
        # Extract alternate greetings if available
        alternate_greetings = character_data.get("alternate_greetings", [])
        if isinstance(alternate_greetings, list) and alternate_greetings:
            # Filter out None/empty entries
            alt_greetings = [g.get("message", g) if isinstance(g, dict) else g 
                           for g in alternate_greetings if g]
        else:
            alt_greetings = []
        
        return {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {
                "name": character_data.get("name", "Unknown"),
                "description": "",
                "personality": character_data.get("personality", ""),
                "scenario": character_data.get("scenario", ""),
                "first_mes": character_data.get("first_message", ""),
                "mes_example": character_data.get("example_dialogs", ""),
                "creator": character_data.get("creator", "Unknown"),
                "character_version": "1.0",
                "tags": character_data.get("tags", []),
                "creator_notes": (
                    f"Creator: {character_data.get('creator', 'Unknown')}\n"
                    f"Source: {character_data.get('url', '')}\n\n"
                    f"Description:\n{character_data.get('description', '')}"
                ),
                "system_prompt": "",
                "post_history_instructions": "",
                "extensions": {},
                "alternate_greetings": alt_greetings,
                "group_only_greetings": [],
                "creation_date": int(time.time()),
                "modification_date": int(time.time()),
                "assets": [
                    {
                        "type": "icon",
                        "uri": "ccdefault:",
                        "name": "main",
                        "ext": "png",
                    }
                ],
            },
        }
    
    @staticmethod
    def _create_png_metadata(v3_data: Dict[str, Any]) -> "PngImagePlugin.PngInfo":
        """Create PNG metadata with embedded character data
        
        Args:
            v3_data: V3 format data
        
        Returns:
            PngImagePlugin.PngInfo object
        """
        metadata = PngImagePlugin.PngInfo()
        
        # V3 format
        v3_json_str = json.dumps(v3_data, ensure_ascii=False, indent=0)
        v3_encoded = base64.b64encode(v3_json_str.encode("utf-8")).decode("utf-8")
        metadata.add_text("ccv3", v3_encoded)
        
        # V2 format for compatibility
        v2_data = {
            "name": v3_data["data"]["name"],
            "description": "",
            "personality": v3_data["data"]["personality"],
            "scenario": v3_data["data"]["scenario"],
            "first_mes": v3_data["data"]["first_mes"],
            "mes_example": v3_data["data"]["mes_example"],
            "creator": v3_data["data"]["creator"],
            "character_version": "1.0",
            "tags": v3_data["data"]["tags"],
            "creator_notes": v3_data["data"]["creator_notes"],
            "system_prompt": "",
            "post_history_instructions": "",
            "alternate_greetings": [],
        }
        
        v2_json_str = json.dumps(v2_data, ensure_ascii=False, indent=0)
        v2_encoded = base64.b64encode(v2_json_str.encode("utf-8")).decode("utf-8")
        metadata.add_text("chara", v2_encoded)
        
        return metadata
    
    @staticmethod
    def _download_image(image_url: str, timeout: int = 15) -> Optional[bytes]:
        """Download image from URL
        
        Args:
            image_url: URL of image to download
            timeout: Request timeout in seconds
        
        Returns:
            Image data as bytes or None
        """
        try:
            logger.debug(f"Downloading image from: {image_url}")
            response = requests.get(image_url, timeout=timeout)
            
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"Failed to download image (status {response.status_code})")
                return None
        
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
