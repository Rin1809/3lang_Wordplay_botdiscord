import pykakasi

# --- Bảng ánh xạ Romaji sang Hiragana ---
ROMAJI_TO_HIRAGANA_MAP = {
    'kya': 'きゃ', 'kyu': 'きゅ', 'kyo': 'きょ',
    'sha': 'しゃ', 'shu': 'しゅ', 'sho': 'しょ',
    'cha': 'ちゃ', 'chu': 'ちゅ', 'cho': 'ちょ',
    'nya': 'にゃ', 'nyu': 'にゅ', 'nyo': 'にょ',
    'hya': 'ひゃ', 'hyu': 'ひゅ', 'hyo': 'ひょ',
    'mya': 'みゃ', 'myu': 'みゅ', 'myo': 'みょ',
    'rya': 'りゃ', 'ryu': 'りゅ', 'ryo': 'りょ',
    'gya': 'ぎゃ', 'gyu': 'ぎゅ', 'gyo': 'ぎょ',
    'ja': 'じゃ', 'ju': 'じゅ', 'jo': 'じょ', # 'dja', 'dju', 'djo'
    'dha': 'ぢゃ', 'dhu': 'ぢゅ', 'dho': 'ぢょ', # Ít phổ biến, nhưng có
    'bya': 'びゃ', 'byu': 'びゅ', 'byo': 'びょ',
    'pya': 'ぴゃ', 'pyu': 'ぴゅ', 'pyo': 'ぴょ',

    'tsu': 'つ', 'chi': 'ち', 'shi': 'し',
    'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
    'sa': 'さ', 'su': 'す', 'se': 'せ', 'so': 'そ',
    'ta': 'た', 'te': 'て', 'to': 'と',
    'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
    'ha': 'は', 'hi': 'ひ', 'fu': 'ふ', 'he': 'へ', 'ho': 'ほ', # 'fu' thay cho 'hu'
    'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
    'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
    'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
    'wa': 'わ', 'wi': 'ゐ', 'we': 'ゑ', 'wo': 'を', # wi, we ít dùng
    'ga': 'が', 'gi': 'ぎ', 'gu': 'ぐ', 'ge': 'げ', 'go': 'ご',
    'za': 'ざ', 'ji': 'じ', 'zu': 'ず', 'ze': 'ぜ', 'zo': 'ぞ', # 'ji' thay cho 'zi'
    'da': 'だ', 'di': 'ぢ', 'du': 'づ', 'de': 'で', 'do': 'ど', # 'di', 'du' ít dùng
    'ba': 'ば', 'bi': 'び', 'bu': 'ぶ', 'be': 'べ', 'bo': 'ぼ',
    'pa': 'ぱ', 'pi': 'ぴ', 'pu': 'ぷ', 'pe': 'ぺ', 'po': 'ぽ',
    'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
    'vu': 'ゔ', # cho âm 'v'
    # 'n' sẽ được xử lý riêng
}

# Sắp xếp keys theo độ dài giảm dần
ROMAJI_KEYS_SORTED = sorted(ROMAJI_TO_HIRAGANA_MAP.keys(), key=len, reverse=True)

def romaji_to_hiragana(romaji_text):
    romaji_text = romaji_text.lower()
    hiragana_text = ""
    i = 0
    n = len(romaji_text)

    while i < n:

        if i + 1 < n and romaji_text[i] == romaji_text[i+1] and \
           romaji_text[i] not in "aiueon'":
            hiragana_text += "っ"
            i += 1 # Bỏ qua phụ âm đầu tiên, phụ âm thứ hai sẽ được xử lý bình thường
            continue


        if romaji_text[i] == 'n':
            if i + 1 == n or \
               (romaji_text[i+1] not in "aiueoy" and romaji_text[i+1].isalpha()):
                hiragana_text += "ん"
                i += 1
                continue


        # 3. Tìm khớp dài nhất trong ROMAJI_TO_HIRAGANA_MAP
        matched = False
        for key_len in range(3, 0, -1): # Thử khớp 3, 2, rồi 1 ký tự
            if i + key_len <= n:
                segment = romaji_text[i : i + key_len]
                if segment in ROMAJI_TO_HIRAGANA_MAP:
                    hiragana_text += ROMAJI_TO_HIRAGANA_MAP[segment]
                    i += key_len
                    matched = True
                    break
        if matched:
            continue

        # 4. Nếu không khớp, giữ nguyên ký tự (vd: dấu câu, số)
        hiragana_text += romaji_text[i]
        i += 1

    return hiragana_text

def hiragana_to_katakana(hiragana_text):
    katakana_text = ""
    for char_h in hiragana_text:
        code_h = ord(char_h)
        if 0x3041 <= code_h <= 0x3096: # Bao gồm cả ゐゑゔ
            katakana_text += chr(code_h + 96)
        elif char_h == 'っ': # Sokuon
            katakana_text += 'ッ'
        elif char_h == 'ー': # Chōonpu (dấu trường âm), thường dùng trong Katakana
            katakana_text += 'ー'
        else:

            katakana_text += char_h
    return katakana_text

def romaji_to_katakana(romaji_text):
    # Đầu tiên, chuyển sang hiragana để xử lý các âm ghép và sokuon
    hiragana_intermediate = romaji_to_hiragana(romaji_text)



    katakana_text = ""
    i = 0
    n_hira = len(hiragana_intermediate)
    vowels_map = {'あ': 'ア', 'い': 'イ', 'う': 'ウ', 'え': 'エ', 'お': 'オ'}
    hiragana_vowels = "あいうえお"

    # Tạo bản đồ Hiragana -> Katakana cơ bản
    temp_katakana_map = {
        h: chr(ord(h) + 96) for h in "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわゐゑをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっ"
        if 0x3041 <= ord(h) <= 0x3096 or h in "ぁぃぅぇぉゃゅょっん"
    }
    # Chỉnh sửa lại để đảm bảo tính đúng đắn cho các ký tự đặc biệt
    hira_to_kata_specific = {
        'ゐ': 'ヰ', 'ゑ': 'ヱ', 'ゔ': 'ヴ',
        'っ': 'ッ', 'ゃ': 'ャ', 'ゅ': 'ュ', 'ょ': 'ョ',
        'ぁ': 'ァ', 'ぃ': 'ィ', 'ぅ': 'ゥ', 'ぇ': 'ェ', 'ぉ': 'ォ',
        # 'ん': 'ン' # đã có trong map chung
    }
    temp_katakana_map.update(hira_to_kata_specific)


    # Chuyển đổi cơ bản từ Hiragana trung gian sang Katakana
    base_katakana = "".join([temp_katakana_map.get(c, c) for c in hiragana_intermediate])

    # Cách tiếp cận đơn giản hơn: dựa vào `pykakasi` để chuyển Katakana
    kks = pykakasi.kakasi()
    kks.setMode("H", "K") # Hiragana to Katakana

    kks_rom_to_kata = pykakasi.kakasi()

    return hiragana_to_katakana(hiragana_intermediate)


def romaji_to_japanese_with_kanji(romaji_text):
    # Bước 1: Chuyển Romaji sang Hiragana bằng hàm của chúng ta
    hiragana_text = romaji_to_hiragana(romaji_text)

    # Bước 2: Sử dụng pykakasi để chuyển Hiragana sang dạngผสม Kanji/Kana
    kks = pykakasi.kakasi()
    kks.setMode("H", "JH")  # Hiragana to Japanese (Kanji + Hiragana)

    result = kks.convert(hiragana_text)
    return "".join([item['orig'] for item in result])


if __name__ == "__main__":
    while True:
        print("\nChọn loại chuyển đổi:")
        print("1. Romaji sang Hiragana")
        print("2. Romaji sang Katakana")
        print("3. Romaji sang Tiếng Nhật (có Kanji, nếu có)")
        print("4. Thoát")

        choice = input("Lựa chọn của bạn (1-4): ")

        if choice == '4':
            print("Tạm biệt!")
            break

        if choice not in ['1', '2', '3']:
            print("Lựa chọn không hợp lệ. Vui lòng chọn lại.")
            continue

        romaji_input = input("Nhập văn bản Romaji: ")
        if not romaji_input:
            print("Không có đầu vào. Vui lòng thử lại.")
            continue

        output_text = ""
        if choice == '1':
            output_text = romaji_to_hiragana(romaji_input)
            print(f"Hiragana: {output_text}")
        elif choice == '2':
            # Sử dụng hàm romaji_to_katakana mới
            output_text = romaji_to_katakana(romaji_input)
            print(f"Katakana: {output_text}")
        elif choice == '3':
            output_text = romaji_to_japanese_with_kanji(romaji_input)
            print(f"Tiếng Nhật (Kanji/Kana): {output_text}")

        # Hỏi xem có muốn chuyển đổi kết quả này sang dạng khác không
        if output_text and choice != '3': # Nếu đã có hiragana/katakana
            if choice == '1': # Đã có hiragana
                hira_result = output_text
                ask_further = input("Bạn có muốn chuyển kết quả Hiragana này sang Katakana hoặc Kanji không? (k/j/no): ").lower()
                if ask_further == 'k':
                    print(f"Katakana từ Hiragana: {hiragana_to_katakana(hira_result)}")
                elif ask_further == 'j':
                    kks_h_to_j = pykakasi.kakasi()
                    kks_h_to_j.setMode("H", "JH")
                    result_j = kks_h_to_j.convert(hira_result)
                    print(f"Kanji/Kana từ Hiragana: {''.join([item['orig'] for item in result_j])}")

            elif choice == '2': # Đã có katakana
                kata_result = output_text

                ask_further = input("Bạn có muốn chuyển kết quả Katakana này sang Hiragana hoặc Kanji không? (h/j/no): ").lower()
                if ask_further == 'h':

                    kks_k_to_h = pykakasi.kakasi()
                    kks_k_to_h.setMode("K", "H")
                    result_h = kks_k_to_h.convert(kata_result)
                    print(f"Hiragana từ Katakana: {''.join([item['hira'] for item in result_h])}")
                elif ask_further == 'j':
                    kks_k_to_j = pykakasi.kakasi()
                    kks_k_to_j.setMode("K", "JH") 
                    result_j = kks_k_to_j.convert(kata_result)
                    print(f"Kanji/Kana từ Katakana: {''.join([item['orig'] for item in result_j])}")