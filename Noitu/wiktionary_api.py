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
        return None 

    try:
        result = kakasi_converter_instance.convert(converted_for_pykakasi)
        if not result:
            return None

        hira_parts = [item['hira'] for item in result if 'hira' in item and item['hira']]
        reconstructed_hira = "".join(hira_parts)
        
        if not reconstructed_hira:
            return None

        if not utils.is_pure_hiragana(reconstructed_hira):
            if converted_for_pykakasi == reconstructed_hira and utils.is_pure_hiragana(converted_for_pykakasi):
                pass 
            else: 
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

async def query_wiktionary_jp_single_term(session: aiohttp.ClientSession, term_to_query: str) -> tuple[bool, dict | None]:
    """Hàm phụ để query 1 term trên Wiktionary JP, trả về (api_call_succeeded, page_info_if_valid_page)."""
    if not term_to_query:
        return False, None # Ko có term -> coi như API call ko thành công cho mục đích này
    
    params = {"action": "query", "titles": term_to_query, "format": "json", "formatversion": 2}
    try:
        async with session.get(bot_cfg.JAPANESE_WIKTIONARY_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                print(f"DEBUG WIKI_JP_API (query_single): Query: '{term_to_query}', Raw Data: {data}")
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    return True, None # API call thành công, nhưng ko có trang
                
                page_info = pages[0]
                is_valid_page = "missing" not in page_info and "invalid" not in page_info
                return True, page_info if is_valid_page else None # API call thành công, trả page_info nếu trang hợp lệ
            else:
                print(f"Lỗi API Wiktionary JP khi query '{term_to_query}': Status {response.status}")
                return False, None # API call thất bại
    except Exception as e:
        print(f"Lỗi gọi API Wiktionary JP cho '{term_to_query}': {e}")
        traceback.print_exc()
        return False, None # API call thất bại


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

    # 1. Chuẩn bị các dạng từ
    processed_hiragana = japanese_input_to_hiragana(input_stripped, kakasi_converter)
    potential_katakana = None
    if processed_hiragana:
        potential_katakana = utils.convert_hiragana_to_katakana_custom(processed_hiragana)
        if potential_katakana == processed_hiragana : # Nếu cv Kata ko đổi gì (vd: đã là Hira thuần)
            potential_katakana = None # Ko cần ktra Kata riêng nếu nó giống Hira
    
    print(f"DEBUG WIKI_JP_API: Input='{input_stripped}', Hira='{processed_hiragana}', Kata='{potential_katakana}'")
    
    # 2. Ktra từ điển local
    # (Kiểm tra input_stripped, processed_hiragana, potential_katakana với các dạng trong local_dict_jp)
    for entry in local_dictionary_jp:
        entry_hira = entry.get('hira', '').strip()
        entry_kanji = entry.get('kanji', '').strip() # Có thể là Kanji hoặc Katakana tùy theo dict
        entry_roma = entry.get('roma', '').strip().lower()

        # Ưu tiên khớp chính xác input gốc nếu nó là Kanji/Kana từ dict
        if entry_kanji and input_stripped == entry_kanji:
             return True, entry_hira if entry_hira else processed_hiragana
        if entry_hira and input_stripped == entry_hira: # Input là Hira
            return True, entry_hira
        if entry_roma and input_stripped.lower() == entry_roma: # Input là Romaji
            return True, entry_hira if entry_hira else processed_hiragana
        
        # Ktra các dạng đã xử lý
        if processed_hiragana and entry_hira and processed_hiragana == entry_hira:
            return True, processed_hiragana
        if potential_katakana and entry_kanji and potential_katakana == entry_kanji: # entry_kanji có thể là Katakana
             return True, processed_hiragana # Luôn trả hira cho game logic

    # 3. Ktra cache (dùng input_stripped làm key chính)
    if input_stripped in cache:
        cached_is_valid, cached_hira_form = cache[input_stripped]
        # print(f"DEBUG WIKI_JP_API: Cache hit for '{input_stripped}'. Valid: {cached_is_valid}, Hira: '{cached_hira_form}'")
        return cached_is_valid, cached_hira_form if cached_hira_form else processed_hiragana


    # 4. Query Wiktionary với các dạng đã chuẩn bị
    # Thứ tự ưu tiên query: input_stripped (nếu là Kana/Kanji), potential_katakana, processed_hiragana
    
    query_terms_in_order = []
    if utils.is_pure_katakana(input_stripped) or utils.is_pure_hiragana(input_stripped) or \
       (not utils.is_romaji(input_stripped) and input_stripped != processed_hiragana and input_stripped != potential_katakana): # Có vẻ là Kanji/hỗn hợp
        query_terms_in_order.append(input_stripped)
    
    if potential_katakana and potential_katakana not in query_terms_in_order:
        query_terms_in_order.append(potential_katakana)
    
    if processed_hiragana and processed_hiragana not in query_terms_in_order:
        query_terms_in_order.append(processed_hiragana)
    
    # Loại bỏ None hoặc chuỗi rỗng nếu có
    query_terms_in_order = [term for term in query_terms_in_order if term]
    print(f"DEBUG WIKI_JP_API: Query terms for Wiktionary in order: {query_terms_in_order}")

    word_is_valid_on_wiktionary = False
    final_hiragana_for_game = processed_hiragana # Mặc định là hira đã xử lý từ input

    if not query_terms_in_order and not final_hiragana_for_game: # Ko có gì để query và ko có hira
        print(f"DEBUG WIKI_JP_API: No valid query terms and no hiragana for '{input_stripped}'.")
        cache[input_stripped] = (False, None)
        return False, None

    at_least_one_api_call_succeeded = False
    for term in query_terms_in_order:
        api_call_ok, page_info = await query_wiktionary_jp_single_term(session, term)
        if api_call_ok: # API call hoàn thành, dù có trang hay ko
            at_least_one_api_call_succeeded = True
        if page_info: # Tìm thấy trang hợp lệ
            word_is_valid_on_wiktionary = True
            # Nếu từ hợp lệ, đảm bảo final_hiragana_for_game có giá trị
            if not final_hiragana_for_game and kakasi_converter:
                # Thử cv lại từ term đã tìm thấy nếu term đó ko phải hira
                if not utils.is_pure_hiragana(term):
                    final_hiragana_for_game = japanese_input_to_hiragana(term, kakasi_converter)
                else:
                    final_hiragana_for_game = term # Term tìm thấy đã là Hira
            # Nếu vẫn ko có, thử lại từ input gốc
            if not final_hiragana_for_game and kakasi_converter:
                 final_hiragana_for_game = japanese_input_to_hiragana(input_stripped, kakasi_converter)
            print(f"DEBUG WIKI_JP_API: Word '{term}' IS VALID on Wiktionary. Final hira for game: '{final_hiragana_for_game}'")
            break # Đã tìm thấy, ko cần query thêm

    if word_is_valid_on_wiktionary:
        cache[input_stripped] = (True, final_hiragana_for_game)
        return True, final_hiragana_for_game
    else:
        # Nếu ít nhất 1 API call thành công (ko lỗi mạng) nhưng ko tìm thấy trang nào
        # HOẶC ko có gì để query nhưng có final_hiragana_for_game (từ local dict chẳng hạn)
        if at_least_one_api_call_succeeded or (not query_terms_in_order and final_hiragana_for_game):
            print(f"DEBUG WIKI_JP_API: Word NOT valid on Wiktionary (or no terms to query). Input: '{input_stripped}'. Hira for game: '{final_hiragana_for_game}'")
            cache[input_stripped] = (False, final_hiragana_for_game) # Vẫn trả hira nếu có, để game logic báo lỗi đúng
            return False, final_hiragana_for_game
        else: # Tất cả API call đều lỗi (mạng, etc.)
            print(f"DEBUG WIKI_JP_API: All API calls FAILED for '{input_stripped}'.")
            cache[input_stripped] = (False, final_hiragana_for_game) # Coi như ko hợp lệ, trả hira nếu có
            return False, final_hiragana_for_game