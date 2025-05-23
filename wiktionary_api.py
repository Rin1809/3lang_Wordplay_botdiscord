# Noitu/wiktionary_api.py
import aiohttp
import traceback

API_URL = "https://vi.wiktionary.org/w/api.php"

async def is_vietnamese_phrase_or_word_valid_api(text: str, session: aiohttp.ClientSession, cache: dict) -> bool:
    if not text: return False
    text_lower = text.lower()
    if text_lower in cache: return cache[text_lower]

    params = {"action": "query", "titles": text_lower, "format": "json", "formatversion": 2}
    try:
        async with session.get(API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    cache[text_lower] = False
                    return False
                page_info = pages[0]
                is_valid = "missing" not in page_info and "invalid" not in page_info
                cache[text_lower] = is_valid
                return is_valid
            else:
                print(f"Lỗi API Wiktionary: Status {response.status} cho '{text_lower}'")
                cache[text_lower] = False 
                return False
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary cho '{text_lower}': {e}")
        traceback.print_exc()
        cache[text_lower] = False 
        return False