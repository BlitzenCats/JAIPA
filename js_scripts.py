"""JavaScript injection utilities for JanitorAI Scraper"""


class JSScripts:
    """Collection of JavaScript snippets used in scraping"""
    
    SCROLL_TO_TEXT = """
        const xpath = "//*[contains(text(), '{text}')]";
        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        const element = result.singleNodeValue;
        
        if (element) {{
            element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            if ({offset_y} !== 0) {{
                window.scrollBy(0, {offset_y});
            }}
            return true;
        }}
        return false;
    """
    
    GET_SCROLL_INFO = """
        return {
            scrollTop: window.scrollY || window.pageYOffset,
            scrollHeight: document.documentElement.scrollHeight,
            clientHeight: window.innerHeight,
            atBottom: (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 100)
        };
    """
    
    EXTRACT_CHARACTER_CHATS = """
        const result = {
            charUrls: [],
            charToChatMap: {}
        };
        
        const charLinks = document.querySelectorAll('a[href*="/characters/"]');
        const seenUrls = new Set();
        
        for (const charLink of charLinks) {
            const charUrl = charLink.getAttribute('href');
            const fullCharUrl = charUrl.startsWith('http') ? charUrl : ('https://janitorai.com' + charUrl);
            
            if (seenUrls.has(fullCharUrl)) continue;
            seenUrls.add(fullCharUrl);
            
            result.charUrls.push(fullCharUrl);
            
            // Find the container with "CHATS:" text
            let container = charLink.parentElement;
            let foundContainer = false;
            
            for (let i = 0; i < 30 && container; i++) {
                if (container.textContent.includes('CHATS:')) {
                    foundContainer = true;
                    break;
                }
                container = container.parentElement;
            }
            
            if (foundContainer && container) {
                // Get visible chat links
                const chatLinks = container.querySelectorAll('a[href*="/chats/"]');
                const chatUrls = [];
                
                for (const chatLink of chatLinks) {
                    const href = chatLink.getAttribute('href');
                    if (href && href.includes('/chats/')) {
                        const fullUrl = href.startsWith('http') ? href : ('https://janitorai.com' + href);
                        if (!chatUrls.includes(fullUrl)) {
                            chatUrls.push(fullUrl);
                        }
                    }
                }
                
                // Get chat count from text
                const chatsMatch = container.textContent.match(/CHATS:\\s*(\\d+)/);
                const chatCount = chatsMatch ? parseInt(chatsMatch[1]) : 0;
                
                result.charToChatMap[fullCharUrl] = {
                    chatUrls: chatUrls,
                    chatCount: chatCount,
                    needsExpansion: chatUrls.length === 0 && chatCount > 0
                };
            }
        }
        
        return result;
    """
    
    EXTRACT_CHARACTER_NAME = """
        let charName = '';
        const charButton = document.querySelector('#character-name-button');
        if (charButton) {
            charName = charButton.innerText.trim();
        }
        if (!charName) {
            const charHeader = document.querySelector('[class*="characterName"], [class*="character-name"]');
            if (charHeader) {
                charName = charHeader.innerText.trim();
            }
        }
        return charName;
    """
    
    EXTRACT_STATS = """
        // Find elements with stats text
        const allText = document.body.innerText;
        const statsMatch = allText.match(/(\\d+)[,\\.]?(\\d*)?\\s+characters?\\s+(\\d+)[,\\.]?(\\d*)?\\s+chats?/i);
        if (statsMatch) {
            const charCount = parseInt(statsMatch[1] + (statsMatch[2] || ''));
            const chatCount = parseInt(statsMatch[3] + (statsMatch[4] || ''));
            return {characters: charCount, chats: chatCount};
        }
        
        // Fallback: look for strong/span tags with badge-like content
        const badges = document.querySelectorAll('strong, [class*="badge"], [class*="count"]');
        for (const badge of badges) {
            const text = badge.innerText;
            if (text.includes('characters') || text.includes('chats')) {
                const charMatch = text.match(/(\\d+)\\s+characters?/i);
                const chatMatch = text.match(/(\\d+)\\s+chats?/i);
                if (charMatch || chatMatch) {
                    return {
                        characters: charMatch ? parseInt(charMatch[1]) : 0,
                        chats: chatMatch ? parseInt(chatMatch[1]) : 0
                    };
                }
            }
        }
        return null;
    """
    
    FIND_EXPAND_CHARACTER = """
        var allLinks = document.querySelectorAll('a[href*="/characters/{char_name}"]');
        
        // If not in DOM, scroll to find it
        if (allLinks.length === 0) {{
            window.scrollBy(0, 500);
            allLinks = document.querySelectorAll('a[href*="/characters/{char_name}"]');
        }}
        
        if (allLinks.length === 0) return null;
        
        var charLink = allLinks[0];
        var container = charLink;
        
        for (var i = 0; i < 30 && container; i++) {{
            if (container.textContent.includes('CHATS:')) {{
                var expandBtn = container.querySelector('button');
                if (expandBtn) {{
                    expandBtn.click();
                    return true;
                }}
            }}
            container = container.parentElement;
        }}
        
        return false;
    """
    
    GET_VIRTUOSO_ITEMS = """
        return Array.from(document.querySelectorAll('{selector}'))
            .map(item => item.innerText)
            .filter(text => text.trim().length > 0);
    """
    
    @staticmethod
    def scroll_to_text(text: str, offset_y: int = 0) -> str:
        """Generate scroll to text script"""
        return JSScripts.SCROLL_TO_TEXT.format(text=text, offset_y=offset_y)
    
    @staticmethod
    def get_virtuoso_items(selector: str) -> str:
        """Generate virtuoso items extraction script"""
        return JSScripts.GET_VIRTUOSO_ITEMS.format(selector=selector)
    
    @staticmethod
    def find_expand_character(char_name: str) -> str:
        """Generate find and expand character script"""
        return JSScripts.FIND_EXPAND_CHARACTER.format(char_name=char_name)
