# Noitu/wiktionary_api.py
import aiohttp
import traceback
from . import config as bot_cfg

# Hàm chuyển đổi input sang Hiragana, trả về None nếu kakasi không có hoặc lỗi
def to_hiragana(text: str, kakasi_converter_instance) -> str | None: # Đổi tên tham số cho rõ ràng
    if not kakasi_converter_instance or not text:
        return None
    try:
        # Sử dụng phương thức convert() của instance kakasi
        result = kakasi_converter_instance.convert(text.strip())
        # result là một list các dict, ví dụ: [{'orig': '東京', 'hira': 'とうきょう', 'kana': 'トウキョウ', 'hepburn': 'tōkyō'}]
        # Ta cần ghép các phần 'hira' lại
        return "".join(item['hira'] for item in result if 'hira' in item)
    except Exception as e:
        print(f"Lỗi chuyển sang Hiragana cho '{text}': {e}")
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

    if not text_lower: return False # Bỏ qua nếu sau khi strip là rỗng

    # 1. Check local dictionary VN
    if text_lower in local_dictionary_vn:
        # Không cần cache cho local dict vì nó đã là set O(1) lookup
        return True

    # 2. Check API cache (từ đã tra Wiktionary VN trước đó)
    if text_lower in cache:
        return cache[text_lower]

    # 3. Gọi API Wiktionary VN nếu ko có trong cache và local
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
                cache[text_lower] = False
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

    # 1. Cố gắng chuyển mọi input sang Hiragana để chuẩn hóa và tìm kiếm
    hiragana_form = to_hiragana(input_stripped, kakasi_converter)
    
    # Nếu không chuyển được sang hiragana (ví dụ kakasi lỗi hoặc input không phải JP),
    # và input có vẻ là Kanji/Kana, dùng input_stripped làm key.
    # Nếu input có vẻ là romaji và không chuyển được, có thể nó không hợp lệ.
    # Ưu tiên hiragana_form nếu có.
    search_key_hira = hiragana_form if hiragana_form else input_stripped 
    
    # 2. Check local dictionary JP
    # So sánh input_stripped (Kanji/Kana/Roma) và search_key_hira (Hiragana) với các dạng trong local_dictionary_jp
    for entry in local_dictionary_jp:
        if (input_stripped == entry['kanji'] or
            input_stripped == entry['hira'] or
            (entry['roma'] and input_stripped.lower() == entry['roma'].lower()) or
            (search_key_hira and search_key_hira == entry['hira'])):
            return True, entry['hira'] # Trả về hiragana chuẩn từ dict

    # 3. Check API cache (dùng search_key_hira vì Wiktionary JP thường dùng Hira/Kanji)
    if search_key_hira in cache:
        return cache[search_key_hira], hiragana_form if cache[search_key_hira] else None

    # 4. Gọi API Wiktionary JP (dùng search_key_hira, hoặc original_input nếu hira form ko có)
    # Wiktionary tiếng Nhật thường tìm tốt nhất bằng Kanji hoặc Hiragana.
    # Nếu input ban đầu là Romaji và không có trong local dict, việc tra Wiktionary có thể khó.
    # Ưu tiên tra bằng search_key_hira (đã cố gắng chuyển sang Hiragana)
    wiktionary_query_term = search_key_hira if search_key_hira else input_stripped

    params = {"action": "query", "titles": wiktionary_query_term, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.JAPANESE_WIKTIONARY_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    cache[search_key_hira] = False # Cache với key đã chuẩn hóa
                    return False, None
                page_info = pages[0]
                is_valid = "missing" not in page_info and "invalid" not in page_info
                cache[search_key_hira] = is_valid
                return is_valid, hiragana_form if is_valid else None
            else:
                print(f"Lỗi API Wiktionary JP: Status {response.status} cho '{wiktionary_query_term}'")
                cache[search_key_hira] = False
                return False, None
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary JP cho '{wiktionary_query_term}': {e}")
        traceback.print_exc()
        cache[search_key_hira] = False
        return False, None