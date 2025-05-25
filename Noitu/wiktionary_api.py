# Noitu/wiktionary_api.py
import aiohttp
import traceback
from . import config as bot_cfg
from . import utils 

def japanese_input_to_hiragana(text: str, kakasi_converter_instance) -> str | None:
    if not text: return None
    text_stripped = text.strip()
    if not text_stripped: return None

    converted_for_pykakasi = text_stripped 

    if utils.is_pure_katakana(text_stripped): 
        h_from_k = utils.convert_katakana_to_hiragana_custom(text_stripped)
        if h_from_k and h_from_k != text_stripped: 
            converted_for_pykakasi = h_from_k
    elif utils.is_romaji(text_stripped): 
        h_from_r = utils.convert_romaji_to_hiragana_custom(text_stripped)
        if h_from_r and h_from_r != text_stripped: 
            converted_for_pykakasi = h_from_r

    if not kakasi_converter_instance:
        if converted_for_pykakasi != text_stripped and utils.is_pure_hiragana(converted_for_pykakasi):
            return converted_for_pykakasi
        # print("DEBUG: japanese_input_to_hiragana returning None - no kakasi and pre-conversion ineffective.") # Bỏ comment nếu cần
        return None 

    try:
        result = kakasi_converter_instance.convert(converted_for_pykakasi)
        if not result:
            # print(f"DEBUG: japanese_input_to_hiragana - kakasi returned no result for '{converted_for_pykakasi}'") # Bỏ comment nếu cần
            return None

        hira_parts = [item['hira'] for item in result if 'hira' in item and item['hira']]
        reconstructed_hira = "".join(hira_parts)
        
        if not reconstructed_hira:
            # print(f"DEBUG: japanese_input_to_hiragana - no hira_parts from kakasi for '{converted_for_pykakasi}'") # Bỏ comment nếu cần
            return None

        if not utils.is_pure_hiragana(reconstructed_hira):
            if converted_for_pykakasi == reconstructed_hira and utils.is_pure_hiragana(converted_for_pykakasi):
                pass 
            else: 
                # print(f"DEBUG: PyKakasi ko trả về Hira thuần. Input: '{text_stripped}', PreConv: '{converted_for_pykakasi}', PyKakasiOut: '{reconstructed_hira}'") # Bỏ comment nếu cần
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

    if text_lower in local_dictionary_vn: return True
    if text_lower in cache: return cache[text_lower]

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

async def query_wiktionary_jp(session: aiohttp.ClientSession, term_to_query: str) -> tuple[bool, dict | None]:
    """Hàm phụ để query Wiktionary JP, trả về (success, page_info)."""
    if not term_to_query:
        return False, None
    
    params = {"action": "query", "titles": term_to_query, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.JAPANESE_WIKTIONARY_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                print(f"DEBUG WIKI_JP_API (query_wiktionary_jp): Query: '{term_to_query}', Raw API Data: {data}")
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    return True, None # Query thành công, nhưng ko có trang
                
                page_info = pages[0]
                # Trang hợp lệ nếu ko 'missing' và ko 'invalid'
                is_valid_page = "missing" not in page_info and "invalid" not in page_info
                return True, page_info if is_valid_page else None
            else:
                print(f"Lỗi API Wiktionary JP khi query '{term_to_query}': Status {response.status}")
                return False, None
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary JP cho '{term_to_query}': {e}")
        traceback.print_exc()
        return False, None


async def is_japanese_word_valid_api(
    original_input: str, 
    session: aiohttp.ClientSession,
    cache: dict, 
    local_dictionary_jp: list, 
    kakasi_converter
) -> tuple[bool, str | None]: 
    if not original_input: return False, None
    
    input_stripped = original_input.strip()
    if not input_stripped: return False, None

    processed_hiragana = japanese_input_to_hiragana(input_stripped, kakasi_converter)
    print(f"DEBUG WIKI_JP_API (is_japanese_word_valid_api): Input '{input_stripped}' -> processed_hiragana: '{processed_hiragana}'")
    
    # 1. Ktra từ điển local
    for entry in local_dictionary_jp:
        entry_hira = entry.get('hira', '').strip()
        entry_kanji = entry.get('kanji', '').strip()
        entry_roma = entry.get('roma', '').strip().lower()

        if input_stripped == entry_kanji and entry_kanji: 
            return True, entry_hira if entry_hira else processed_hiragana 
        if input_stripped == entry_hira and entry_hira: 
            return True, entry_hira
        if entry_roma and input_stripped.lower() == entry_roma: 
            return True, entry_hira if entry_hira else processed_hiragana
        if processed_hiragana and processed_hiragana == entry_hira and entry_hira:
            return True, entry_hira 

    # 2. Ktra cache (dùng input_stripped làm key chính vì nó đại diện cho từ nd nhập)
    if input_stripped in cache:
        cached_is_valid, cached_hira_form = cache[input_stripped]
        print(f"DEBUG WIKI_JP_API: Cache hit for key '{input_stripped}'. Valid: {cached_is_valid}, Hira: '{cached_hira_form}'")
        # Trả về hira đã xử lý nếu cache ko có hira, nhưng lần này có
        return cached_is_valid, cached_hira_form if cached_hira_form else processed_hiragana

    # 3. Query Wiktionary
    # Chiến lược:
    # a. Nếu input_stripped là Katakana thuần hoặc chứa Kanji, ưu tiên query bằng input_stripped.
    # b. Nếu thất bại (hoặc input ko phải a), và có processed_hiragana khác input_stripped, query bằng processed_hiragana.
    
    is_valid_on_wiktionary = False
    page_info_from_api = None
    query_success = False

    # Thử query bằng input gốc nếu nó là Katakana hoặc có vẻ là Kanji/hỗn hợp (ko phải Romaji thuần)
    if utils.is_pure_katakana(input_stripped) or (not utils.is_romaji(input_stripped) and input_stripped != processed_hiragana):
        print(f"DEBUG WIKI_JP_API: Attempting query with original input '{input_stripped}'")
        query_success, page_info_from_api = await query_wiktionary_jp(session, input_stripped)
        if query_success and page_info_from_api:
            is_valid_on_wiktionary = True
            # Nếu thành công bằng input gốc, processed_hiragana vẫn là dạng chuẩn hóa để dùng trong game
            # (nếu chưa có từ quá trình cv ban đầu, thử cv từ input_stripped)
            if not processed_hiragana and kakasi_converter:
                 processed_hiragana = japanese_input_to_hiragana(input_stripped, kakasi_converter)
            print(f"DEBUG WIKI_JP_API: Valid by original input '{input_stripped}'. Final hira: '{processed_hiragana}'")


    # Nếu query bằng input gốc ko thành công HOẶC ko đc thực hiện, và có processed_hiragana khác biệt, thử query bằng nó
    if not is_valid_on_wiktionary and processed_hiragana and processed_hiragana != input_stripped:
        print(f"DEBUG WIKI_JP_API: Attempting query with processed_hiragana '{processed_hiragana}'")
        query_success_hira, page_info_hira = await query_wiktionary_jp(session, processed_hiragana)
        if query_success_hira and page_info_hira:
            is_valid_on_wiktionary = True
            # page_info_from_api = page_info_hira # Không cần gán lại vì đã có is_valid_on_wiktionary
            print(f"DEBUG WIKI_JP_API: Valid by processed_hiragana '{processed_hiragana}'")
    
    # Nếu cả hai cách query đều ko tìm thấy trang hợp lệ, nhưng query API thành công (ko lỗi mạng)
    # thì coi như từ ko hợp lệ. processed_hiragana vẫn được trả về nếu có.
    if not is_valid_on_wiktionary and (query_success or (processed_hiragana and processed_hiragana != input_stripped)): # (query_success ở đây ám chỉ lần query cuối cùng thành công nhưng ko có trang)
        print(f"DEBUG WIKI_JP_API: Word not found on Wiktionary by any method. Input: '{input_stripped}', Hira: '{processed_hiragana}'")
        cache[input_stripped] = (False, processed_hiragana)
        return False, processed_hiragana

    # Nếu có lỗi API nghiêm trọng ở cả 2 lần (nếu có)
    if not is_valid_on_wiktionary and not query_success:
        print(f"DEBUG WIKI_JP_API: Wiktionary API query failed for all attempts. Input: '{input_stripped}'")
        cache[input_stripped] = (False, processed_hiragana) # Cache lỗi, trả về hira nếu có
        return False, processed_hiragana

    # Nếu từ hợp lệ trên Wiktionary
    if is_valid_on_wiktionary:
        # Đảm bảo processed_hiragana có giá trị
        if not processed_hiragana and kakasi_converter:
             current_term_for_hira_conversion = input_stripped # Lấy từ input gốc nếu hira chưa có
             processed_hiragana = japanese_input_to_hiragana(current_term_for_hira_conversion, kakasi_converter)

        print(f"DEBUG WIKI_JP_API: Word IS valid. Final hira: '{processed_hiragana}' for input '{input_stripped}'")
        cache[input_stripped] = (True, processed_hiragana)
        return True, processed_hiragana
    
    # Fallback cuối cùng: nếu không có gì ở trên khớp, từ không hợp lệ
    cache[input_stripped] = (False, processed_hiragana)
    return False, processed_hiragana