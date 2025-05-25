# Noitu/wiktionary_api.py
import aiohttp
import traceback
from . import config as bot_cfg
from . import utils # Import utils để dùng map & func cv mới

# Nâng cấp to_hiragana: Thử map Romaji/Kata tùy chỉnh trc, rồi mới PyKakasi
def japanese_input_to_hiragana(text: str, kakasi_converter_instance) -> str | None:
    """
    Cv input JP (Romaji, Katakana, Kanji-mixed) -> Hiragana.
    Ưu tiên cv Romaji/Katakana tùy chỉnh cho input dễ nhận diện.
    Dùng PyKakasi cho các loại khác hoặc nếu cv tùy chỉnh ko hoàn chỉnh.
    """
    if not text: return None
    text_stripped = text.strip()
    if not text_stripped: return None

    converted_for_pykakasi = text_stripped # Mặc định là text gốc đã strip

    # Giai đoạn 1: Tiền xử lý cho các loại script dễ nhận diện
    if utils.is_pure_katakana(text_stripped): # Nếu là Katakana thuần
        h_from_k = utils.convert_katakana_to_hiragana_custom(text_stripped)
        if h_from_k and h_from_k != text_stripped: # Đảm bảo có cv
            converted_for_pykakasi = h_from_k
            # Lúc này ta có Hiragana thuần, có thể đưa PyKakasi để xác nhận/chuẩn hóa thêm
    elif utils.is_romaji(text_stripped): # is_romaji nên cho input chủ yếu là romaji
        h_from_r = utils.convert_romaji_to_hiragana_custom(text_stripped)
        if h_from_r and h_from_r != text_stripped: # Đảm bảo có cv
            converted_for_pykakasi = h_from_r

    # Giai đoạn 2: Dùng PyKakasi để cv chung và tinh chỉnh
    if not kakasi_converter_instance:
        # Ko có PyKakasi, tiền xử lý là tất cả những gì ta có.
        # Chỉ trả về nếu nó khác gốc VÀ là Hiragana thuần.
        if converted_for_pykakasi != text_stripped and utils.is_pure_hiragana(converted_for_pykakasi):
            return converted_for_pykakasi
        return None # Ko thể cv đáng tin cậy nếu ko có PyKakasi & tiền xử lý ko ra Hiragana

    try:
        result = kakasi_converter_instance.convert(converted_for_pykakasi)
        if not result: return None

        hira_parts = [item['hira'] for item in result if 'hira' in item and item['hira']]
        reconstructed_hira = "".join(hira_parts)
        
        if not reconstructed_hira: return None

        # Ktra cuối: KQ có phải Hiragana thuần ko?
        if not utils.is_pure_hiragana(reconstructed_hira):
            # Nếu input tiền-cv đã là hira thuần, và pykakasi trả về nó, thì OK.
            if converted_for_pykakasi == reconstructed_hira and utils.is_pure_hiragana(converted_for_pykakasi):
                pass # Đã là hiragana, pykakasi xác nhận.
            else: # PyKakasi trả về thứ gì đó ko thuần hiragana
                print(f"PyKakasi ko trả về Hira thuần. Input: '{text_stripped}', PreConv: '{converted_for_pykakasi}', PyKakasiOut: '{reconstructed_hira}'")
                return None
        
        return reconstructed_hira
    except Exception as e:
        print(f"Lỗi pykakasi khi cv Hira cho '{text}' (pre-cv: '{converted_for_pykakasi}'): {e}")
        traceback.print_exc()
        return None


async def is_vietnamese_phrase_or_word_valid_api(
    text: str,
    session: aiohttp.ClientSession,
    cache: dict, 
    local_dictionary_vn: set
) -> bool:
    if not text: return False
    text_lower = text.lower().strip()
    if not text_lower: return False

    # 1. Ktra local dict VN
    if text_lower in local_dictionary_vn: return True
    # 2. Ktra API cache (Wiktionary VN)
    if text_lower in cache: return cache[text_lower]

    # 3. Gọi API Wiktionary VN
    params = {"action": "query", "titles": text_lower, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.VIETNAMESE_WIKTIONARY_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    cache[text_lower] = False; return False
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
    original_input: str, 
    session: aiohttp.ClientSession,
    cache: dict, 
    local_dictionary_jp: list, 
    kakasi_converter
) -> tuple[bool, str | None]: # Trả về (is_valid, hiragana_form_if_valid)
    if not original_input: return False, None
    
    input_stripped = original_input.strip()
    if not input_stripped: return False, None

    # 1. Cố cv input -> Hiragana chuẩn
    processed_hiragana = japanese_input_to_hiragana(input_stripped, kakasi_converter)
    
    # 2. Ktra local dict JP
    for entry in local_dictionary_jp:
        entry_hira = entry.get('hira', '').strip()
        entry_kanji = entry.get('kanji', '').strip()
        entry_roma = entry.get('roma', '').strip().lower()

        if input_stripped == entry_kanji and entry_kanji: # Khớp Kanji
            return True, entry_hira if entry_hira else processed_hiragana # Ưu tiên hira từ dict
        if input_stripped == entry_hira and entry_hira: # Khớp Hira trực tiếp
            return True, entry_hira
        if entry_roma and input_stripped.lower() == entry_roma: # Khớp Romaji
            return True, entry_hira if entry_hira else processed_hiragana
        
        if processed_hiragana and processed_hiragana == entry_hira and entry_hira:
            return True, entry_hira # Trả Hira từ dict

    # 3. Ktra API cache (key là processed_hira nếu có, ko thì input_stripped)
    cache_key = processed_hiragana if processed_hiragana else input_stripped
    if cache_key in cache:
        cached_is_valid, cached_hira_form = cache[cache_key]
        return cached_is_valid, cached_hira_form 

    # 4. Gọi API Wiktionary JP
    wiktionary_query_term = processed_hiragana if processed_hiragana else input_stripped
    params = {"action": "query", "titles": wiktionary_query_term, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.JAPANESE_WIKTIONARY_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages: # Ko tìm thấy trang
                    cache[cache_key] = (False, None)
                    return False, None
                
                page_info = pages[0]
                is_valid_on_wiktionary = "missing" not in page_info and "invalid" not in page_info
                final_hiragana_to_return = None

                if is_valid_on_wiktionary:
                    final_hiragana_to_return = processed_hiragana # Dùng hira đã xử lý
                    # Nếu processed_hiragana rỗng, thử lại lần nữa với kakasi nếu input có thể là Kanji/Kata
                    if not final_hiragana_to_return and kakasi_converter: 
                        final_hiragana_to_return = japanese_input_to_hiragana(input_stripped, kakasi_converter)

                cache[cache_key] = (is_valid_on_wiktionary, final_hiragana_to_return)
                return is_valid_on_wiktionary, final_hiragana_to_return
            else:
                print(f"Lỗi API Wiktionary JP: Status {response.status} cho '{wiktionary_query_term}'")
                cache[cache_key] = (False, None)
                return False, None
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary JP cho '{wiktionary_query_term}': {e}")
        traceback.print_exc()
        cache[cache_key] = (False, None)
        return False, None