# Noitu Bot - Nối Từ & Shiritori trên Discord ᓚᘏᗢ

<!-- Vietnamese -->
<details>
<summary>🇻🇳 Tiếng Việt</summary>

## Giới thiệu

**Noitu Bot** là một bot Discord được thiết kế để mang trò chơi Nối Từ (Tiếng Việt) và Shiritori (しりとり - Tiếng Nhật) cổ điển vào server Discord của bạn. Bot hỗ trợ cả hai ngôn ngữ, cho phép người dùng chơi trong các kênh được cấu hình riêng biệt. Với tính năng xác thực từ, tính giờ, bảng xếp hạng và các lệnh tương tác, Noitu Bot hứa hẹn sẽ mang lại những giờ phút giải trí vui vẻ cho cộng đồng của bạn.

Bot sử dụng API Wiktionary và từ điển cục bộ để xác thực từ, đảm bảo tính công bằng và thử thách của trò chơi.

**LƯU Ý QUAN TRỌNG:**

*   🔑 **BẢO MẬT API KEY & DATABASE URL:** File `.env` chứa thông tin nhạy cảm (Bot Token, Database URL). **TUYỆT ĐỐI KHÔNG** chia sẻ file này hoặc các thông tin trong đó cho bất kỳ ai.
*   🐘 **DATABASE:** Bot yêu cầu một cơ sở dữ liệu PostgreSQL để hoạt động.
*   🇯🇵 **TIẾNG NHẬT:** Để có trải nghiệm tốt nhất với Shiritori, thư viện `PyKakasi` cần được cài đặt và hoạt động đúng cách trên môi trường chạy bot. Nếu không, các tính năng liên quan đến tiếng Nhật có thể bị hạn chế.

## Tính năng

*   **Nối Từ (Tiếng Việt):**
    *   Người chơi nối từ bằng cách sử dụng từ cuối cùng của người chơi trước làm từ đầu tiên của mình.
    *   Chỉ chấp nhận cụm từ gồm 2 chữ Tiếng Việt có nghĩa.
*   **Shiritori (しりとり - Tiếng Nhật):**
    *   Người chơi nối từ bằng cách sử dụng âm tiết (mora) cuối cùng của từ trước làm âm tiết đầu tiên của từ mới (dựa trên cách đọc Hiragana).
    *   Hỗ trợ nhập liệu bằng Romaji, Hiragana, Katakana (bot sẽ cố gắng chuyển đổi sang Hiragana).
    *   Áp dụng luật "ん" (n): người chơi nào dùng từ kết thúc bằng "ん" sẽ thua cuộc.
*   **Xác thực từ:**
    *   Sử dụng API Wiktionary (Tiếng Việt & Tiếng Nhật) để kiểm tra tính hợp lệ của từ.
    *   Sử dụng từ điển cục bộ (`tudien-vn.txt`, `tudien-jp.txt`) để tăng tốc độ và bổ sung từ.
*   **Tính giờ tự động:** Nếu không ai nối từ sau một khoảng thời gian nhất định (có thể cấu hình), người chơi cuối cùng sẽ thắng.
*   **Cấu hình linh hoạt (cho Admin):**
    *   Đặt kênh riêng cho Nối Từ Tiếng Việt và Shiritori Tiếng Nhật.
    *   Thay đổi prefix lệnh của bot cho server.
    *   Điều chỉnh thời gian timeout để thắng.
    *   Thiết lập số người chơi tối thiểu để kích hoạt timeout.
*   **Bảng xếp hạng:** Theo dõi điểm số và thứ hạng của người chơi cho từng ngôn ngữ (VN/JP) trên mỗi server.
*   **Lệnh tương tác:**
    *   Hỗ trợ cả lệnh slash (ví dụ: `/start`) và lệnh prefix (ví dụ: `!start`).
    *   Các nút tương tác sau khi kết thúc game ("Chơi Lại", "Xem BXH") và trong tin nhắn trợ giúp ("Bắt Đầu Nhanh").
*   **Phản hồi người dùng:** Bot sử dụng reactions (✅, ❌, ⚠️) để thông báo kết quả lượt đi.

## Điều kiện tiên quyết (Để tự host bot)

1.  **Python:** Phiên bản 3.10 trở lên (theo `runtime.txt`). Đảm bảo `python` và `pip` đã được thêm vào biến môi trường PATH.
2.  **PostgreSQL:** Một cơ sở dữ liệu PostgreSQL đang hoạt động.
3.  **Discord Bot Token:** Bạn cần tạo một ứng dụng bot trên Discord Developer Portal và lấy token.
4.  **Git (Tùy chọn):** Để tải mã nguồn từ repository.

## Cài đặt (Để tự host bot)

1.  **Tải mã nguồn:**
    ```bash
    git clone https://github.com/Rin1809/VN-JP_Word_Chain_Bot_Discord
    ```

2.  **Cấu hình môi trường:**
    *   Tạo một file tên là `.env` trong thư mục gốc của dự án (cùng cấp với file `README.md`, bên trong thư mục `Noitu` nếu cấu trúc của bạn là `Noitu/Noitu/...`).
    *   Thêm nội dung sau vào file `.env`, thay thế các giá trị placeholder bằng thông tin của bạn:
        ```env
        BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"
        DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
        ```
        Ví dụ `DATABASE_URL`: `postgresql://postgres:mypassword@localhost:5432/noitu_db`

3.  **Cài đặt thư viện:**
    *   (Khuyến nghị) Tạo và kích hoạt một môi trường ảo Python:
        ```bash
        python -m venv moitruongao
        source moitruongao/bin/activate  # Trên Linux/macOS
        # moitruongao\Scripts\activate    # Trên Windows
        ```
    *   Cài đặt các thư viện cần thiết từ `requirements.txt` (file này nằm trong thư mục `Noitu/` của dự án):
        ```bash
        pip install -r requirements.txt
        ```
        *Lưu ý: Đảm bảo bạn đang ở trong thư mục chứa file `requirements.txt` hoặc cung cấp đường dẫn đúng đến nó.*

4.  **Khởi tạo Cơ sở dữ liệu:**
    *   Bot sẽ tự động cố gắng tạo các bảng cần thiết khi khởi động lần đầu (thông qua `database.init_db`). Đảm bảo chuỗi kết nối `DATABASE_URL` trong `.env` là chính xác và người dùng DB có quyền tạo bảng.

5.  **Chuẩn bị từ điển (Tùy chọn):**
    *   Các file `tudien-vn.txt` và `tudien-jp.txt` nên được đặt trong thư mục `Noitu/Noitu/` (cùng cấp với `noitu.py`).
    *   Bạn có thể tùy chỉnh các file từ điển này. `tudien-jp.txt` là file CSV với định dạng: `KanjiHoặcKana,Hiragana,Romaji`.
    *   Script `dump_page_wikitionary_jp.py` có thể được sử dụng (với một file dump XML của Wiktionary tiếng Nhật) để tạo/cập nhật từ điển tiếng Nhật. Đây là một tác vụ nâng cao.

## Chạy bot

Sau khi cài đặt thành công:

1.  Điều hướng đến thưmuc gốc của project (`Noitu/` - thư mục chứa file `noitu.py`).
2.  Chạy bot bằng lệnh:
    ```bash
    python noitu.py
    ```
    Hoặc nếu bạn đặt project trong một thư mục cha và muốn chạy như một module:
    ```bash
    python -m Noitu.noitu 
    ```
    (Điều này phụ thuộc vào cách bạn cấu trúc `PYTHONPATH` và vị trí bạn chạy lệnh).

Bot sẽ kết nối với Discord và sẵn sàng nhận lệnh. Theo dõi output trên terminal để biết trạng thái và lỗi (nếu có).

## Hướng dẫn sử dụng

Khi bot đã được mời vào server của bạn và đang chạy:

*   **Lấy trợ giúp:**
    *   `/help` hoặc `!<prefix>help` (ví dụ: `!help` nếu prefix mặc định là `!`)
    *   Lệnh này sẽ hiển thị hướng dẫn chi tiết dựa trên ngôn ngữ được cấu hình cho kênh hiện tại.

*   **Bắt đầu game:**
    *   `/start [cụm từ bắt đầu]` (ví dụ: `/start học sinh` cho Tiếng Việt, `/start さくら` cho Tiếng Nhật)
    *   `!<prefix>start [cụm từ bắt đầu]`
    *   Nếu bỏ trống cụm từ, bot sẽ tự chọn một từ để bắt đầu.
    *   Game sẽ diễn ra trong kênh mà lệnh được gọi, miễn là kênh đó đã được admin cấu hình.

*   **Dừng game:**
    *   `/stop`
    *   `!<prefix>stop`

*   **Xem Bảng Xếp Hạng:**
    *   `/bxh`
    *   `!<prefix>bxh`
    *   Hiển thị BXH cho ngôn ngữ game của kênh hiện tại.

*   **Chơi game:**
    *   Sau khi game bắt đầu, chỉ cần gõ từ/cụm từ của bạn vào kênh đã được cấuHình.
    *   Bot sẽ tự động xử lý và phản hồi bằng reaction.

*   **Lệnh Admin (Yêu cầu quyền "Quản lý Server"):**
    *   `/config view`: Xem cấu hình hiện tại của bot cho server.
    *   `/config set_prefix <prefix_mới>`: Đặt prefix lệnh mới (1-5 ký tự).
    *   `/config set_timeout <giây>`: Đặt thời gian timeout (10-300 giây).
    *   `/config set_minplayers <số_lượng>`: Đặt số người chơi tối thiểu để kích hoạt timeout (1-10).
    *   `/config set_vn_channel <#kênh_text>`: Đặt kênh cho Nối Từ Tiếng Việt.
    *   `/config set_jp_channel <#kênh_text>`: Đặt kênh cho Shiritori Tiếng Nhật.
    *   Một số lệnh config cũng có sẵn dưới dạng prefix: `!<prefix>config prefix`, `!<prefix>config timeout`, `!<prefix>config minplayers`.

## Cấu trúc thư mục (Đơn giản hóa)

```
Noitu/                     # Thư mục gốc của dự án
├── .git/                  # (Bị Git bỏ qua trong liệt kê này)
├── __pycache__/           # (Bị Git bỏ qua)
├── moitruongao/           # Môi trường ảo Python (nếu bạn tạo)
├── Noitu/                 # Module chính của bot
│   ├── __pycache__/       # (Bị Git bỏ qua)
│   ├── cogs/              # Chứa các module lệnh (cogs)
│   │   ├── __init__.py
│   │   ├── admin_cog.py
│   │   ├── game_cog.py
│   │   └── general_cog.py
│   ├── game/              # Logic và view liên quan đến game
│   │   ├── __init__.py
│   │   ├── logic.py
│   │   └── views.py
│   ├── config.py          # Cấu hình mặc định của bot
│   ├── database.py        # Tương tác với cơ sở dữ liệu
│   ├── noitu.py           # File chính chạy bot
│   ├── tudien-jp.txt      # Từ điển Tiếng Nhật cục bộ
│   ├── tudien-vn.txt      # Từ điển Tiếng Việt cục bộ
│   ├── utils.py           # Các hàm tiện ích
│   └── wiktionary_api.py  # Tương tác với API Wiktionary
├── .env                   # Chứa BOT_TOKEN và DATABASE_URL (QUAN TRỌNG: KHÔNG COMMIT FILE NÀY)
├── .gitignore             # Các file/thư mục bị Git bỏ qua
├── dump_page_wikitionary_jp.py # Script tiện ích để xử lý dump Wiktionary JP
├── Procfile               # (Cho triển khai trên Heroku)
├── requirements.txt       # Danh sách các thư viện Python cần thiết
├── romaji_to_hiragana.py  # Script tiện ích cho chuyển đổi Romaji (có thể đã tích hợp vào utils.py)
└── runtime.txt            # (Cho triển khai trên Heroku, chỉ định phiên bản Python)
```

## Công nghệ sử dụng

*   **Python 3.10+**
*   **discord.py:** Thư viện chính để tương tác với API Discord.
*   **asyncpg:** Driver PostgreSQL bất đồng bộ cho Python.
*   **aiohttp:** Cho các yêu cầu HTTP bất đồng bộ (đến Wiktionary).
*   **PyKakasi:** Chuyển đổi giữa các dạng chữ viết Tiếng Nhật (Romaji, Hiragana, Katakana, Kanji).
*   **python-dotenv:** Tải biến môi trường từ file `.env`.
*   **PostgreSQL:** Hệ quản trị cơ sở dữ liệu.

</details>

<!-- English -->
<details>
<summary>🇬🇧 English</summary>

## Introduction

**Noitu Bot** is a Discord bot designed to bring the classic Word Chain (Vietnamese "Nối Từ") and Shiritori (しりとり - Japanese) games to your Discord server. The bot supports both languages, allowing users to play in separately configured channels. With features like word validation, timeouts, leaderboards, and interactive commands, Noitu Bot promises to provide hours of fun for your community.

The bot utilizes Wiktionary APIs and local dictionaries for word validation, ensuring fair and challenging gameplay.

**IMPORTANT NOTES:**

*   🔑 **API KEY & DATABASE URL SECURITY:** The `.env` file contains sensitive information (Bot Token, Database URL). **NEVER** share this file or its contents with anyone.
*   🐘 **DATABASE:** The bot requires a PostgreSQL database to function.
*   🇯🇵 **JAPANESE LANGUAGE:** For the best Shiritori experience, the `PyKakasi` library needs to be correctly installed and functional in the bot's runtime environment. Otherwise, Japanese-related features might be limited.

## Features

*   **Vietnamese Word Chain ("Nối Từ"):**
    *   Players chain words by using the last word of the previous player as their first word.
    *   Accepts only meaningful 2-word Vietnamese phrases.
*   **Japanese Word Chain ("Shiritori - しりとり"):**
    *   Players chain words by using the last mora (syllable) of the previous word as the first mora of their new word (based on Hiragana reading).
    *   Supports input in Romaji, Hiragana, Katakana (the bot will attempt conversion to Hiragana).
    *   Implements the "ん" (n) rule: a player who uses a word ending in "ん" loses.
*   **Word Validation:**
    *   Uses Wiktionary APIs (Vietnamese & Japanese) to check word validity.
    *   Utilizes local dictionaries (`tudien-vn.txt`, `tudien-jp.txt`) for speed and supplementary words.
*   **Automatic Timeout:** If no one makes a move after a configurable amount of time, the last player to make a valid move wins.
*   **Flexible Configuration (for Admins):**
    *   Set separate channels for Vietnamese Nối Từ and Japanese Shiritori.
    *   Change the bot's command prefix for the server.
    *   Adjust the timeout duration for winning.
    *   Set the minimum number of players required to activate the timeout.
*   **Leaderboards:** Tracks scores and rankings for players in each language (VN/JP) per server.
*   **Interactive Commands:**
    *   Supports both slash commands (e.g., `/start`) and prefix commands (e.g., `!start`).
    *   Interactive buttons after game ends ("Play Again", "View Leaderboard") and in help messages ("Quick Start").
*   **User Feedback:** The bot uses reactions (✅, ❌, ⚠️) to indicate the outcome of a move.

## Prerequisites (For self-hosting)

1.  **Python:** Version 3.10 or higher (as per `runtime.txt`). Ensure `python` and `pip` are added to your system's PATH.
2.  **PostgreSQL:** A running PostgreSQL database instance.
3.  **Discord Bot Token:** You'll need to create a bot application on the Discord Developer Portal and obtain its token.
4.  **Git (Optional):** To clone the source code from the repository.

## Installation (For self-hosting)

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Rin1809/VN-JP_Word_Chain_Bot_Discord
    ```

2.  **Configure Environment:**
    *   Create a file named `.env` in the project's root directory (same level as `README.md`, inside the `Noitu` directory if your structure is `Noitu/Noitu/...`).
    *   Add the following content to the `.env` file, replacing placeholder values with your actual credentials:
        ```env
        BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"
        DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
        ```
        Example `DATABASE_URL`: `postgresql://postgres:mypassword@localhost:5432/noitu_db`

3.  **Install Dependencies:**
    *   (Recommended) Create and activate a Python virtual environment:
        ```bash
        python -m venv venv
        source venv/bin/activate  # On Linux/macOS
        # venv\Scripts\activate    # On Windows
        ```
    *   Install the required libraries from `requirements.txt` (this file is located in the `Noitu/` directory of the project):
        ```bash
        pip install -r requirements.txt
        ```
        *Note: Ensure you are in the directory containing `requirements.txt` or provide the correct path to it.*

4.  **Initialize Database:**
    *   The bot will attempt to create the necessary tables automatically on its first startup (via `database.init_db`). Ensure the `DATABASE_URL` in `.env` is correct and the DB user has privileges to create tables.

5.  **Prepare Dictionaries (Optional):**
    *   The `tudien-vn.txt` and `tudien-jp.txt` files should be placed in the `Noitu/Noitu/` directory (alongside `noitu.py`).
    *   You can customize these dictionary files. `tudien-jp.txt` is a CSV file with the format: `KanjiOrKana,Hiragana,Romaji`.
    *   The `dump_page_wikitionary_jp.py` script can be used (with a Japanese Wiktionary XML dump file) to generate/update the Japanese dictionary. This is an advanced task.

## Running the Bot

After successful installation:

1.  Navigate to the project's root directory (`Noitu/` - the one containing `noitu.py`).
2.  Run the bot using:
    ```bash
    python noitu.py
    ```
    Or, if you've structured your project within a parent directory and want to run it as a module:
    ```bash
    python -m Noitu.noitu
    ```
    (This depends on your `PYTHONPATH` setup and where you execute the command from).

The bot will connect to Discord and be ready for commands. Monitor the terminal output for status and any errors.

## Usage Guide

Once the bot is invited to your server and running:

*   **Getting Help:**
    *   `/help` or `!<prefix>help` (e.g., `!help` if the default prefix is `!`)
    *   This command displays detailed instructions based on the language configured for the current channel.

*   **Starting a Game:**
    *   `/start [starting phrase]` (e.g., `/start học sinh` for Vietnamese, `/start さくら` for Japanese)
    *   `!<prefix>start [starting phrase]`
    *   If the starting phrase is omitted, the bot will pick a word to start.
    *   The game takes place in the channel where the command is invoked, provided that channel has been configured by an admin.

*   **Stopping a Game:**
    *   `/stop`
    *   `!<prefix>stop`

*   **Viewing Leaderboard:**
    *   `/bxh`
    *   `!<prefix>bxh`
    *   Displays the leaderboard for the game language of the current channel.

*   **Playing the Game:**
    *   After a game starts, simply type your word/phrase in the configured channel.
    *   The bot will automatically process it and respond with a reaction.

*   **Admin Commands (Requires "Manage Server" permission):**
    *   `/config view`: View the bot's current configuration for the server.
    *   `/config set_prefix <new_prefix>`: Set a new command prefix (1-5 characters).
    *   `/config set_timeout <seconds>`: Set the timeout duration (10-300 seconds).
    *   `/config set_minplayers <count>`: Set the minimum players to activate timeout (1-10).
    *   `/config set_vn_channel <#text_channel>`: Set the channel for Vietnamese Nối Từ.
    *   `/config set_jp_channel <#text_channel>`: Set the channel for Japanese Shiritori.
    *   Some config commands are also available via prefix: `!<prefix>config prefix`, `!<prefix>config timeout`, `!<prefix>config minplayers`.

## Folder Structure (Simplified)

```
Noitu/                     # Project Root
├── .git/                  # (Ignored by Git in listing)
├── __pycache__/           # (Ignored by Git)
├── venv/                  # Python virtual environment (if you create one)
├── Noitu/                 # Main bot module
│   ├── __pycache__/       # (Ignored by Git)
│   ├── cogs/              # Contains command modules (cogs)
│   │   ├── __init__.py
│   │   ├── admin_cog.py
│   │   ├── game_cog.py
│   │   └── general_cog.py
│   ├── game/              # Game-related logic and views
│   │   ├── __init__.py
│   │   ├── logic.py
│   │   └── views.py
│   ├── config.py          # Bot's default configurations
│   ├── database.py        # Database interaction
│   ├── noitu.py           # Main bot execution file
│   ├── tudien-jp.txt      # Local Japanese dictionary
│   ├── tudien-vn.txt      # Local Vietnamese dictionary
│   ├── utils.py           # Utility functions
│   └── wiktionary_api.py  # Wiktionary API interaction
├── .env                   # Stores BOT_TOKEN and DATABASE_URL (IMPORTANT: DO NOT COMMIT THIS FILE)
├── .gitignore             # Files/folders ignored by Git
├── dump_page_wikitionary_jp.py # Utility script for processing Wiktionary JP dump
├── Procfile               # (For Heroku deployment)
├── requirements.txt       # List of Python dependencies
├── romaji_to_hiragana.py  # Utility script for Romaji conversion (may be integrated into utils.py)
└── runtime.txt            # (For Heroku deployment, specifies Python version)
```

## Technologies Used

*   **Python 3.10+**
*   **discord.py:** Main library for Discord API interaction.
*   **asyncpg:** Asynchronous PostgreSQL driver for Python.
*   **aiohttp:** For asynchronous HTTP requests (to Wiktionary).
*   **PyKakasi:** Conversion between Japanese writing systems (Romaji, Hiragana, Katakana, Kanji).
*   **python-dotenv:** Loads environment variables from a `.env` file.
*   **PostgreSQL:** Database management system.

</details>

<!-- Japanese -->
<details>
<summary>🇯🇵 日本語</summary>

## Noituボット - Discord用 Nối Từ & しりとりゲーム ᓚᘏᗢ

## 概要

**Noituボット**は、Discordサーバーに古典的なワードチェーンゲーム「Nối Từ」（ベトナム語）と「しりとり」（日本語）を導入するために設計されたDiscordボットです。ボットは両方の言語をサポートしており、ユーザーは個別に設定されたチャンネルでプレイできます。単語検証、タイムアウト、リーダーボード、インタラクティブなコマンドなどの機能を備えたNoituボットは、あなたのコミュニティに楽しい時間を提供することをお約束します。

ボットはWiktionary APIとローカル辞書を利用して単語を検証し、ゲームの公平性と挑戦性を保証します。

**重要な注意点:**

*   🔑 **APIキーとデータベースURLのセキュリティ:** `.env`ファイルには機密情報（ボットトークン、データベースURL）が含まれています。このファイルまたはその内容を誰とも**絶対に共有しないでください**。
*   🐘 **データベース:** ボットが機能するにはPostgreSQLデータベースが必要です。
*   🇯🇵 **日本語:** しりとりを最大限に楽しむためには、ボットの実行環境に`PyKakasi`ライブラリが正しくインストールされ、機能している必要があります。そうでない場合、日本語関連の機能が制限される可能性があります。

## 機能

*   **Nối Từ (ベトナム語ワードチェーン):**
    *   プレイヤーは、前のプレイヤーの最後の単語を自分の最初の単語として使用して単語をつなぎます。
    *   意味のある2単語のベトナム語フレーズのみを受け付けます。
*   **しりとり (日本語ワードチェーン):**
    *   プレイヤーは、前の単語の最後のモーラ（音節）を新しい単語の最初のモーラとして使用して単語をつなぎます（ひらがなの読みに基づく）。
    *   ローマ字、ひらがな、カタカナでの入力をサポートします（ボットはひらがなへの変換を試みます）。
    *   「ん」ルールを適用：最後に「ん」で終わる単語を使用したプレイヤーは負けとなります。
*   **単語検証:**
    *   Wiktionary API（ベトナム語と日本語）を使用して単語の有効性を確認します。
    *   ローカル辞書（`tudien-vn.txt`、`tudien-jp.txt`）を利用して速度を向上させ、単語を補足します。
*   **自動タイムアウト:** 設定可能な時間が経過しても誰も次の手を打たない場合、最後に有効な手を打ったプレイヤーが勝利します。
*   **柔軟な設定（管理者向け）:**
    *   ベトナム語のNối Từと日本語のしりとり用に個別のチャンネルを設定します。
    *   サーバーのボットのコマンドプレフィックスを変更します。
    *   勝利のためのタイムアウト時間を調整します。
    *   タイムアウトを有効にするために必要な最小プレイヤー数を設定します。
*   **リーダーボード:** サーバーごとに各言語（VN/JP）のプレイヤーのスコアとランキングを追跡します。
*   **インタラクティブコマンド:**
    *   スラッシュコマンド（例：`/start`）とプレフィックスコマンド（例：`!start`）の両方をサポートします。
    *   ゲーム終了後のインタラクティブボタン（「もう一度プレイ」、「リーダーボード表示」）およびヘルプメッセージ内のボタン（「クイックスタート」）。
*   **ユーザーフィードバック:** ボットはリアクション（✅, ❌, ⚠️）を使用して手の結果を示します。

## 前提条件（セルフホスティング用）

1.  **Python:** バージョン3.10以上（`runtime.txt`による）。`python`と`pip`がシステムのPATHに追加されていることを確認してください。
2.  **PostgreSQL:** 実行中のPostgreSQLデータベースインスタンス。
3.  **Discordボットトークン:** Discord Developer Portalでボットアプリケーションを作成し、そのトークンを取得する必要があります。
4.  **Git（オプション）:** リポジトリからソースコードをクローンする場合。

## インストール（セルフホスティング用）

1.  **リポジトリのクローン:**
    ```bash
    git clone https://github.com/Rin1809/VN-JP_Word_Chain_Bot_Discord
    ```

2.  **環境設定:**
    *   プロジェクトのルートディレクトリ（`README.md`と同じレベル、構造が`Noitu/Noitu/...`の場合は`Noitu`ディレクトリ内）に`.env`という名前のファイルを作成します。
    *   `.env`ファイルに以下の内容を追加し、プレースホルダーの値を実際の認証情報に置き換えます。
        ```env
        BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"
        DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
        ```
        `DATABASE_URL`の例：`postgresql://postgres:mypassword@localhost:5432/noitu_db`

3.  **依存関係のインストール:**
    *   （推奨）Python仮想環境を作成してアクティブ化します。
        ```bash
        python -m venv venv
        source venv/bin/activate  # Linux/macOSの場合
        # venv\Scripts\activate    # Windowsの場合
        ```
    *   プロジェクトの`Noitu/`ディレクトリにある`requirements.txt`から必要なライブラリをインストールします。
        ```bash
        pip install -r requirements.txt
        ```
        *注意: `requirements.txt`が含まれるディレクトリにいるか、正しいパスを指定していることを確認してください。*

4.  **データベースの初期化:**
    *   ボットは最初の起動時に必要なテーブルを自動的に作成しようとします（`database.init_db`経由）。`.env`内の`DATABASE_URL`が正しく、DBユーザーがテーブル作成権限を持っていることを確認してください。

5.  **辞書の準備（オプション）:**
    *   `tudien-vn.txt`と`tudien-jp.txt`ファイルは`Noitu/Noitu/`ディレクトリ（`noitu.py`と同じ場所）に配置する必要があります。
    *   これらの辞書ファイルはカスタマイズ可能です。`tudien-jp.txt`は`漢字またはカナ,ひらがな,ローマ字`の形式のCSVファイルです。
    *   `dump_page_wikitionary_jp.py`スクリプトは、日本語WiktionaryのXMLダンプファイルを使用して日本語辞書を生成/更新するために使用できます。これは高度なタスクです。

## ボットの実行

インストールが正常に完了した後:

1.  プロジェクトのルートディレクトリ（`noitu.py`が含まれる`Noitu/`）に移動します。
2.  以下を使用してボットを実行します。
    ```bash
    python noitu.py
    ```
    または、プロジェクトを親ディレクトリ内に構成し、モジュールとして実行したい場合：
    ```bash
    python -m Noitu.noitu
    ```
    （これは`PYTHONPATH`の設定とコマンドを実行する場所によって異なります）。

ボットはDiscordに接続し、コマンドを受け付ける準備ができます。ステータスやエラー（もしあれば）については、ターミナルの出力を監視してください。

## 使用方法

ボットがサーバーに招待され、実行されたら:

*   **ヘルプの表示:**
    *   `/help` または `!<プレフィックス>help` （例：デフォルトのプレフィックスが`!`の場合は`!help`）
    *   このコマンドは、現在のチャンネル用に設定された言語に基づいて詳細な手順を表示します。

*   **ゲームの開始:**
    *   `/start [開始フレーズ]` （例：ベトナム語の場合は`/start học sinh`、日本語の場合は`/start さくら`）
    *   `!<プレフィックス>start [開始フレーズ]`
    *   開始フレーズを省略すると、ボットが開始単語を選択します。
    *   ゲームは、管理者が設定したチャンネルであれば、コマンドが呼び出されたチャンネルで行われます。

*   **ゲームの停止:**
    *   `/stop`
    *   `!<プレフィックス>stop`

*   **リーダーボードの表示:**
    *   `/bxh`
    *   `!<プレフィックス>bxh`
    *   現在のチャンネルのゲーム言語のリーダーボードを表示します。

*   **ゲームのプレイ:**
    *   ゲーム開始後、設定されたチャンネルに単語/フレーズを入力するだけです。
    *   ボットは自動的にそれを処理し、リアクションで応答します。

*   **管理者コマンド（「サーバー管理」権限が必要）:**
    *   `/config view`: サーバーのボットの現在の設定を表示します。
    *   `/config set_prefix <新しいプレフィックス>`: 新しいコマンドプレフィックスを設定します（1～5文字）。
    *   `/config set_timeout <秒数>`: タイムアウト時間を設定します（10～300秒）。
    *   `/config set_minplayers <人数>`: タイムアウトを有効にするための最小プレイヤー数を設定します（1～10人）。
    *   `/config set_vn_channel <#テキストチャンネル>`: ベトナム語Nối Từ用のチャンネルを設定します。
    *   `/config set_jp_channel <#テキストチャンネル>`: 日本語しりとり用のチャンネルを設定します。
    *   一部の設定コマンドはプレフィックス経由でも利用可能です： `!<プレフィックス>config prefix`, `!<プレフィックス>config timeout`, `!<プレフィックス>config minplayers`。

## フォルダ構造（簡易版）

```
Noitu/                     # プロジェクトルート
├── .git/                  # (Gitのリストでは無視)
├── __pycache__/           # (Gitで無視)
├── venv/                  # Python仮想環境 (作成した場合)
├── Noitu/                 # メインボットモジュール
│   ├── __pycache__/       # (Gitで無視)
│   ├── cogs/              # コマンドモジュール (cogs) を格納
│   │   ├── __init__.py
│   │   ├── admin_cog.py
│   │   ├── game_cog.py
│   │   └── general_cog.py
│   ├── game/              # ゲーム関連ロジックとビュー
│   │   ├── __init__.py
│   │   ├── logic.py
│   │   └── views.py
│   ├── config.py          # ボットのデフォルト設定
│   ├── database.py        # データベースとの対話
│   ├── noitu.py           # メインボット実行ファイル
│   ├── tudien-jp.txt      # ローカル日本語辞書
│   ├── tudien-vn.txt      # ローカルベトナム語辞書
│   ├── utils.py           # ユーティリティ関数
│   └── wiktionary_api.py  # Wiktionary APIとの対話
├── .env                   # BOT_TOKENとDATABASE_URLを格納 (重要: このファイルはコミットしないでください)
├── .gitignore             # Gitで無視されるファイル/フォルダ
├── dump_page_wikitionary_jp.py # Wiktionary JPダンプ処理用ユーティリティスクリプト
├── Procfile               # (Herokuデプロイ用)
├── requirements.txt       # Python依存関係リスト
├── romaji_to_hiragana.py  # ローマ字変換用ユーティリティスクリプト (utils.pyに統合されている可能性あり)
└── runtime.txt            # (Herokuデプロイ用, Pythonバージョン指定)
```

## 使用技術

*   **Python 3.10+**
*   **discord.py:** Discord APIとの対話用メインライブラリ。
*   **asyncpg:** Python用非同期PostgreSQLドライバ。
*   **aiohttp:** 非同期HTTPリクエスト用（Wiktionary向け）。
*   **PyKakasi:** 日本語の書記体系（ローマ字、ひらがな、カタカナ、漢字）間の変換。
*   **python-dotenv:** `.env`ファイルから環境変数をロード。
*   **PostgreSQL:** データベース管理システム。

</details>


# Image:

## Vietnam side: 
![image](https://github.com/user-attachments/assets/50c8c4de-3c8b-4288-90c2-f66201ea6174)

## Japan side:
![image](https://github.com/user-attachments/assets/7ef10ad5-3c62-4826-8454-3e9c4f2233d6)
![image](https://github.com/user-attachments/assets/0994d0e5-ed5c-4853-a541-671720e5f745)

