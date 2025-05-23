# Noitu/wiktionary_api.py
import aiohttp
import traceback

API_URL = "https://vi.wiktionary.org/w/api.php"

async def is_vietnamese_phrase_or_word_valid_api(
    text: str,
    session: aiohttp.ClientSession,
    cache: dict,
    local_dictionary: set # Thêm dict local
) -> bool:
    if not text: return False
    text_lower = text.lower() # Chuẩn hóa input

    # 1. Check API cache (từ đã tra Wiktionary trước đó)
    if text_lower in cache:
        return cache[text_lower]

    # 2. Check local dictionary
    if text_lower in local_dictionary:
        cache[text_lower] = True # Thêm vào cache API luôn để đồng bộ, tránh check lại local_dict
        return True

    # 3. Gọi API Wiktionary nếu ko có trong cache và local
    params = {"action": "query", "titles": text_lower, "format": "json", "formatversion": 2}
    try:
        async with session.get(API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages: # Ko có page -> ko hợp lệ
                    cache[text_lower] = False
                    return False
                page_info = pages[0]
                # Trang hợp lệ nếu ko có key 'missing' hoặc 'invalid'
                is_valid = "missing" not in page_info and "invalid" not in page_info
                cache[text_lower] = is_valid # Cache kết quả từ API
                return is_valid
            else: # Lỗi API
                print(f"Lỗi API Wiktionary: Status {response.status} cho '{text_lower}'")
                cache[text_lower] = False # Mặc định là ko hợp lệ nếu API lỗi
                return False
    except Exception as e: # Lỗi kết nối, etc.
        print(f"Lỗi gọi API Wiktionary cho '{text_lower}': {e}")
        traceback.print_exc()
        cache[text_lower] = False # Mặc định là ko hợp lệ nếu có exception
        return False