"""Parse JanitorAI network API responses and convert to JSONL chat format"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ChatNetworkParser:
    """Parses JanitorAI network API responses into JSONL format"""
    
    @staticmethod
    def parse_api_response(api_response: Dict[str, Any], user_persona_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Parse raw API response into structured chat data
        
        Goal 1: Parse network response and order by time (oldest first)
        Uses provided user_persona_name from HTML parsing
        
        Args:
            api_response: Raw API response from janitorai.com/hampter/chats/[CHATID]
            user_persona_name: User's persona name extracted from window._storeState_
        
        Returns:
            Structured chat data with messages or None
        """
        try:
            if not api_response:
                logger.warning("Empty API response")
                return None
            
            # Extract main sections
            character_data = api_response.get("character", {})
            chat_data = api_response.get("chat", {})
            messages_raw = api_response.get("chatMessages", [])
            
            if not messages_raw:
                logger.warning("No messages in API response")
                return None
            
            logger.info(f"Processing {len(messages_raw)} raw messages from API")
            logger.debug(f"User persona name: {user_persona_name or 'Not provided (will use You)'}")
            
            # Process messages with user persona name
            processed_messages = ChatNetworkParser._process_messages(
                messages_raw,
                character_data,
                chat_data,
                user_persona_name
            )
            
            if not processed_messages:
                logger.warning("No valid messages after processing")
                return None
            
            return {
                "character": character_data,
                "chat": chat_data,
                "messages": processed_messages,
                "message_count": len(processed_messages),
                "user_persona_name": user_persona_name
            }
        
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            return None
    
    @staticmethod
    def _process_messages(
        messages_raw: List[Dict[str, Any]],
        character_data: Dict[str, Any],
        chat_data: Dict[str, Any],
        user_persona_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Process raw messages and handle swipes
        
        Goal 3: Manage swipe behavior based on is_main boolean
        API returns newest first, we need oldest first
        
        Args:
            messages_raw: Raw message list from API (NEWEST FIRST!)
            character_data: Character information
            chat_data: Chat metadata
            user_persona_name: User's persona name from HTML
        
        Returns:
            Processed messages with swipes handled (OLDEST FIRST)
        """
        if not messages_raw:
            return []
        
        # CRITICAL: API returns newest first, we need oldest first
        # So reverse the entire array
        messages_oldest_first = list(reversed(messages_raw))
        
        logger.debug(f"Reversed {len(messages_raw)} messages (API gives newest first)")
        if messages_oldest_first:
            logger.debug(f"After reverse: First message timestamp = {messages_oldest_first[0].get('created_at')}")
            logger.debug(f"After reverse: Last message timestamp = {messages_oldest_first[-1].get('created_at')}")
        
        # Group messages by swipes using is_bot detection
        message_groups = ChatNetworkParser._group_swipes_by_bot(messages_oldest_first)
        
        logger.debug(f"Grouped into {len(message_groups)} message groups")
        
        # Convert to JSONL format
        processed = []
        for group in message_groups:
            jsonl_msg = ChatNetworkParser._convert_to_jsonl(
                group,
                character_data,
                chat_data,
                user_persona_name
            )
            if jsonl_msg:
                processed.append(jsonl_msg)
        
        # Sort by time (oldest first)
        processed.sort(key=lambda x: x.get("send_date", ""))
        
        logger.info(f"Processed {len(processed)} messages (after grouping swipes)")
        
        # DEBUG: Log sample of processed message
        if processed:
            logger.debug(f"Sample processed message: {json.dumps(processed[0], indent=2, default=str)[:400]}")
        
        return processed
    
    @staticmethod
    def _group_swipes_by_bot(messages_oldest_first: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group messages by swipes using is_bot for detection
        
        FIX: Since is_main is unreliable, detect swipes by looking for consecutive
        messages with the same is_bot value and close timestamps
        
        Logic:
        - Consecutive messages with same is_bot value = swipes
        - First message in group = main message (oldest)
        - Rest are alternate swipes
        
        Args:
            messages_oldest_first: Messages sorted oldest first
        
        Returns:
            List of message groups (each group = [main_message, ...alternate_swipes])
        """
        result = []
        i = 0
        
        logger.debug(f"Grouping {len(messages_oldest_first)} messages for swipes (using is_bot)")
        
        while i < len(messages_oldest_first):
            msg = messages_oldest_first[i]
            is_bot = msg.get("is_bot", False)
            created_at = msg.get("created_at", "")
            
            # Start a new group with this message
            group = [msg]
            logger.debug(f"  [{i}] Group start: {created_at[:19]} (bot={is_bot})")
            i += 1
            
            # Look ahead for consecutive messages with same is_bot (these are swipes)
            while i < len(messages_oldest_first):
                next_msg = messages_oldest_first[i]
                next_is_bot = next_msg.get("is_bot", False)
                next_created_at = next_msg.get("created_at", "")
                
                # If same is_bot value, it's a swipe
                if next_is_bot == is_bot:
                    group.append(next_msg)
                    logger.debug(f"  [{i}] Swipe: {next_created_at[:19]} (bot={next_is_bot})")
                    i += 1
                else:
                    # Different is_bot - start new group
                    break
            
            result.append(group)
            
            if len(group) > 1:
                logger.debug(f"  → Swipe group: {len(group)} messages from {'bot' if is_bot else 'user'}")
            else:
                logger.debug(f"  → Single message from {'bot' if is_bot else 'user'}")
        
        logger.debug(f"Total groups created: {len(result)}")
        return result
    
    @staticmethod
    def _extract_user_persona_name(api_response: Dict[str, Any]) -> Optional[str]:
        """Extract user's persona name from API response
        
        Looks for "name" field containing the user's persona/character name
        (different from the character being chatted with).
        
        Searches in multiple locations as persona data can appear in:
        - user.profile.name (React state store)
        - Direct "name" field
        - chat.user_name field
        
        Args:
            api_response: Raw API response
        
        Returns:
            User persona name or None
        """
        try:
            if not isinstance(api_response, dict):
                return None
            
            # Search path 1: user.profile.name (from React store state)
            user_profile = api_response.get("user", {})
            if isinstance(user_profile, dict):
                profile = user_profile.get("profile", {})
                if isinstance(profile, dict):
                    name = profile.get("name")
                    if name and isinstance(name, str) and name.strip():
                        return name.strip()
            
            # Search path 2: Direct root-level name (if present)
            if "name" in api_response and api_response.get("name"):
                name = api_response["name"]
                # Make sure it's not the character name
                char_name = api_response.get("character", {}).get("name", "")
                if name and name != char_name and isinstance(name, str):
                    return name
            
            # Search path 3: chat.user_name
            chat_data = api_response.get("chat")
            if isinstance(chat_data, dict):
                if "user_name" in chat_data:
                    user_name = chat_data["user_name"]
                    if user_name and isinstance(user_name, str) and user_name.strip():
                        return user_name.strip()
            
            logger.debug("User persona name not found in API response")
            return None
        
        except Exception as e:
            logger.debug(f"Error extracting user persona name: {e}")
            return None
    
    @staticmethod
    def _convert_to_jsonl(
        message_group: List[Dict[str, Any]],
        character_data: Dict[str, Any],
        chat_data: Dict[str, Any],
        user_persona_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Convert message group to JSONL format
        
        Goal 4: Retrieve created_at times
        
        Args:
            message_group: Group of messages (main + swipes if any)
            character_data: Character information
            chat_data: Chat metadata
            user_persona_name: User's persona name from chat (replaces "You")
        
        Returns:
            JSONL format message or None
        """
        if not message_group:
            return None
        
        try:
            # For swipes: first in list is the main displayed message
            main_msg = message_group[0]
            
            # Determine sender
            is_bot = main_msg.get("is_bot", False)
            if is_bot:
                sender_name = character_data.get("name", "Character")
            else:
                # Use actual user persona name from chat if available, else fallback to "You"
                sender_name = user_persona_name or "You"
            
            # Clean message content (handle escaped quotes)
            message_text = ChatNetworkParser._clean_message_content(main_msg.get("message", ""))
            
            logger.debug(f"Converting message: sender={sender_name}, is_bot={is_bot}, message_len={len(message_text)}, raw_msg_keys={list(main_msg.keys())}")
            
            # Build JSONL entry
            jsonl_entry = {
                "name": sender_name,
                "is_user": not is_bot,
                "is_system": False,
                "send_date": main_msg.get("created_at", ""),  # Goal 4: Use created_at
                "mes": message_text,
            }
            
            # FIX: Only add swipes if this is actually a swipe group (has multiple messages)
            has_swipes = len(message_group) > 1
            
            if has_swipes:
                # This is a swipe group - add swipes array
                swipes = [
                    ChatNetworkParser._clean_message_content(msg.get("message", ""))
                    for msg in message_group
                ]
                jsonl_entry["swipes"] = swipes
                jsonl_entry["swipe_id"] = 0
                jsonl_entry["swipe_info"] = [
                    {"send_date": msg.get("created_at", ""), "extra": {}}
                    for msg in message_group
                ]
            # NOTE: Don't add swipes array for regular messages (is_main=true)
            
            # Add extra fields
            extra = {
                "isSmallSys": False,
                "token_count": 0,
                "bias": "",
                "reasoning": "",
            }
            
            # For bot messages, add token count estimate
            if is_bot:
                extra["token_count"] = ChatNetworkParser._estimate_token_count(message_text)
            
            jsonl_entry["extra"] = extra
            jsonl_entry["force_avatar"] = ""
            
            return jsonl_entry
        
        except Exception as e:
            logger.error(f"Error converting message to JSONL: {e}")
            return None
    
    @staticmethod
    def _clean_message_content(content: str) -> str:
        """Clean message content
        
        Note: JSON parsing already handles escaped quotes correctly.
        We only strip whitespace and preserve internal structure.
        
        Args:
            content: Raw message content (already JSON-parsed)
        
        Returns:
            Cleaned message content
        """
        if not content:
            return ""
        
        try:
            # Strip leading/trailing whitespace but preserve internal structure
            # JSON parsing already handled \" -> " conversion
            content = content.strip()
            
            return content
        except Exception as e:
            logger.warning(f"Error cleaning message content: {e}")
            return content
    
    @staticmethod
    def _estimate_token_count(text: str) -> int:
        """Estimate token count for a message
        
        Args:
            text: Message content
        
        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        if not text:
            return 0
        return max(1, len(text) // 4)
    
    @staticmethod
    def extract_alternate_greetings(
        api_response: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract alternate greetings (first_messages) from API response
        
        Goal 2: Extract first_messages and separate from first_message
        
        Args:
            api_response: Raw API response
        
        Returns:
            List of alternate greeting entries
        """
        try:
            character_data = api_response.get("character", {})
            first_messages = character_data.get("first_messages", [])
            
            if not first_messages:
                logger.debug("No alternate greetings found")
                return []
            
            logger.info(f"Found {len(first_messages)} alternate greetings")
            
            # Convert to JSONL-compatible format
            alternates = []
            for idx, greeting in enumerate(first_messages):
                if greeting and greeting.strip():  # Skip empty entries
                    cleaned = ChatNetworkParser._clean_message_content(greeting)
                    if cleaned:  # Only add non-empty after cleaning
                        alternates.append({
                            "index": idx,
                            "message": cleaned,
                            "original": greeting
                        })
            
            logger.info(f"Extracted {len(alternates)} valid alternate greetings")
            return alternates
        
        except Exception as e:
            logger.error(f"Error extracting alternate greetings: {e}")
            return []
    
    @staticmethod
    def extract_chat_memory(api_response: Dict[str, Any]) -> Optional[str]:
        """Extract chat memory/summary from API response
        
        Goal 1: Extract chat summary for memory injection
        
        Args:
            api_response: Raw API response
        
        Returns:
            Chat memory/summary or None
        """
        try:
            chat_data = api_response.get("chat", {})
            summary = chat_data.get("summary", "")
            
            if summary:
                logger.info(f"Found chat memory: {len(summary)} chars")
                return summary
            
            return None
        
        except Exception as e:
            logger.error(f"Error extracting chat memory: {e}")
            return None
    
    @staticmethod
    def create_jsonl_export(
        parsed_chat: Dict[str, Any],
        include_chat_memory: bool = True
    ) -> List[str]:
        """Create JSONL export lines from parsed chat
        
        Args:
            parsed_chat: Parsed chat data from parse_api_response
            include_chat_memory: Whether to inject memory into first message
        
        Returns:
            List of JSONL lines (including metadata and messages)
        """
        try:
            lines = []
            
            # Create metadata entry
            metadata = ChatNetworkParser._create_jsonl_metadata(parsed_chat)
            lines.append(json.dumps(metadata, ensure_ascii=False))
            
            # Add messages
            messages = parsed_chat.get("messages", [])
            
            # Inject chat memory into first message if requested
            if include_chat_memory and messages:
                chat_memory = ChatNetworkParser.extract_chat_memory({
                    "chat": parsed_chat.get("chat", {})
                })
                
                if chat_memory:
                    if "extra" not in messages[0]:
                        messages[0]["extra"] = {}
                    messages[0]["extra"]["memory"] = chat_memory
                    logger.debug("Injected chat memory into first message")
            
            # Add each message
            for msg in messages:
                lines.append(json.dumps(msg, ensure_ascii=False))
            
            logger.info(f"Created JSONL export with {len(messages)} messages")
            return lines
        
        except Exception as e:
            logger.error(f"Error creating JSONL export: {e}")
            return []
    
    @staticmethod
    def _create_jsonl_metadata(parsed_chat: Dict[str, Any]) -> Dict[str, Any]:
        """Create JSONL metadata entry
        
        Args:
            parsed_chat: Parsed chat data
        
        Returns:
            Metadata dictionary
        """
        character_data = parsed_chat.get("character", {})
        chat_data = parsed_chat.get("chat", {})
        
        return {
            "chat_metadata": {
                "integrity": "",
                "chat_id_hash": chat_data.get("id", ""),
                "note_prompt": "",
                "note_interval": 1,
                "note_position": 1,
                "note_depth": 4,
                "note_role": 0,
                "tainted": False,
                "timedWorldInfo": {"sticky": {}, "cooldown": {}},
                "lastInContextMessageId": 0
            },
            "user_name": "unused",
            "character_name": character_data.get("name", "Unknown")
        }


class ChatMemoryManager:
    """Manages chat memory extraction and injection"""
    
    @staticmethod
    def extract_from_first_message(message: str) -> Optional[str]:
        """Extract chat memory from formatted first message
        
        First messages sometimes contain memory in format like:
        (memory) ...
        
        Args:
            message: Message content
        
        Returns:
            Extracted memory or None
        """
        try:
            if not message or "(memory)" not in message.lower():
                return None
            
            # Extract between (memory) and next section or end
            start = message.lower().find("(memory)")
            if start == -1:
                return None
            
            start += 8  # len("(memory)")
            content = message[start:].strip()
            
            return content if content else None
        
        except Exception as e:
            logger.debug(f"Error extracting memory from message: {e}")
            return None
    
    @staticmethod
    def inject_into_message_extra(
        message_dict: Dict[str, Any],
        memory: str
    ) -> Dict[str, Any]:
        """Inject memory into message extra field
        
        Args:
            message_dict: JSONL message dictionary
            memory: Memory text to inject
        
        Returns:
            Updated message dictionary
        """
        if not memory:
            return message_dict
        
        if "extra" not in message_dict:
            message_dict["extra"] = {}
        
        message_dict["extra"]["memory"] = memory
        
        return message_dict
