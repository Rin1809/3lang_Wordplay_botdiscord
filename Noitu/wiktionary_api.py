# Noitu/wiktionary_api.py
import aiohttp
import traceback
from . import config as bot_cfg

# Chuyển input sang Hira, None nếu kakasi ko có/lỗi
def to_hiragana(text: str, kakasi_converter_instance) -> str | None:
    if not kakasi_converter_instance or not text:
        return None
    try:
        text_stripped = text.strip()
        if not text_stripped: # Rỗng sau strip -> None
            return None
            
        result = kakasi_converter_instance.convert(text_stripped)
        if not result: # Kakasi trả list rỗng
            return None

        hira_parts = [item['hira'] for item in result if 'hira' in item and item['hira']] # Lọc 'hira' rỗng
        
        reconstructed_hira = "".join(hira_parts)
        if not reconstructed_hira: # Ghép lại vẫn rỗng
            return None

        # qtrong: nếu kq "hira" từ Kakasi == input, và input ko phải thuần Hira
        # -> ko phải cv đổi thành công sang Hira thực sự.
        if reconstructed_hira == text_stripped:
            is_actually_hiragana = True
            for char_code in map(ord, reconstructed_hira):
                # Ktra Unicode block Hira
                if not (0x3040 <= char_code <= 0x309F):
                    is_actually_hiragana = False
                    break
            if not is_actually_hiragana:
                return None
        
        return reconstructed_hira
    except Exception as e:
        print(f"Lỗi cv sang Hira cho '{text}': {e}")
        traceback.print_exc()
        return None

async def is_vietnamese_phrase_or_word_valid_api(
    text: str,
    session: aiohttp.ClientSession,
    cache: dict, # bot.wiktionary_cache_vn
    local_dictionary_vn: set # bot.local_dictionary_vn
) -> bool:
    if not text: return False
    text_lower = text.lower().strip()

    if not text_lower: return False

    # 1. Ktra local dict VN
    if text_lower in local_dictionary_vn:
        return True

    # 2. Ktra API cache (Wiktionary VN đã tra)
    if text_lower in cache:
        return cache[text_lower]

    # 3. Gọi API Wiktionary VN
    params = {"action": "query", "titles": text_lower, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.VIETNAMESE_WIKTIONARY_API_URL, params=params) as response:
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
                print(f"Lỗi API Wiktionary VN: Status {response.status} cho '{text_lower}'")
                cache[text_lower] = False # Cache lỗi để ko thử lại ngay
                return False
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary VN cho '{text_lower}': {e}")
        traceback.print_exc()
        cache[text_lower] = False
        return False

async def is_japanese_word_valid_api(
    original_input: str, # Kanji, Hira, Kata, Roma
    session: aiohttp.ClientSession,
    cache: dict, # bot.wiktionary_cache_jp
    local_dictionary_jp: list, # list of dicts
    kakasi_converter # bot.kakasi
) -> tuple[bool, str | None]: # Trả về (is_valid, hiragana_form)
    if not original_input: return False, None
    
    input_stripped = original_input.strip()
    if not input_stripped: return False, None

    # 1. Cố cv mọi input sang Hira để chuẩn hóa & tìm kiếm
    hiragana_form = to_hiragana(input_stripped, kakasi_converter)
    
    # Ưu tiên hiragana_form nếu có cho search_key
    search_key_hira = hiragana_form if hiragana_form else input_stripped 
    
    # 2. Ktra local dict JP
    # So sánh input_stripped (Kanji/Kana/Roma) và search_key_hira (Hira) với các dạng trong local_dict_jp
    for entry in local_dictionary_jp:
        if (input_stripped == entry['kanji'] or
            input_stripped == entry['hira'] or
            (entry['roma'] and input_stripped.lower() == entry['roma'].lower()) or
            (search_key_hira and search_key_hira == entry['hira'])):
            return True, entry['hira'] # Trả về Hira chuẩn từ dict

    # 3. Ktra API cache (dùng search_key_hira)
    if search_key_hira in cache:
        # cache lưu (is_valid, hiragana_form_khi_valid)
        cached_result, cached_hira_form = cache[search_key_hira]
        return cached_result, cached_hira_form if cached_result else None


    # 4. Gọi API Wiktionary JP (dùng search_key_hira, or original_input nếu hira form ko có)
    wiktionary_query_term = search_key_hira # Đã ưu tiên hira_form ở trên

    params = {"action": "query", "titles": wiktionary_query_term, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.JAPANESE_WIKTIONARY_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    cache[search_key_hira] = (False, None)
                    return False, None
                page_info = pages[0]
                is_valid = "missing" not in page_info and "invalid" not in page_info
                # Nếu valid, trả về hiragana_form đã được cố gắng tạo ra từ đầu
                # Nếu ko valid, trả về None cho hira_form
                valid_hira_to_return = hiragana_form if is_valid else None
                cache[search_key_hira] = (is_valid, valid_hira_to_return)
                return is_valid, valid_hira_to_return
            else:
                print(f"Lỗi API Wiktionary JP: Status {response.status} cho '{wiktionary_query_term}'")
                cache[search_key_hira] = (False, None)
                return False, None
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary JP cho '{wiktionary_query_term}': {e}")
        traceback.print_exc()
        cache[search_key_hira] = (False, None)
        return False, None