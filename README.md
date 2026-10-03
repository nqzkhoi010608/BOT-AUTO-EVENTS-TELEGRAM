# Auto Events Telegram Bot

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v21-26A5E4?style=flat-square&logo=telegram&logoColor=white)
![Supabase](https://img.shields.io/badge/Database-Supabase-3FCF8E?style=flat-square&logo=supabase&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)

A production-ready Python bot that automatically polls a splash-banner events API and announces new events to a Telegram channel — complete with banner images, formatted event details, and validated deep links. Delivery state is persisted in Supabase (PostgreSQL), so every event is published exactly once, even after restarts.

**[English](#english)** | **[Tiếng Việt](#tiếng-việt)**

---

## English

### Overview

The bot follows a simple, reliable pipeline:

1. **Poll** — every 5 minutes (`CHECK_INTERVAL_MINUTES`), the bot fetches the current event list from the upstream API.
2. **Detect** — each event gets a stable identity (`name + startTime`) and is diffed against the `event_cache` table in Supabase.
3. **Deliver**:
   - New event **with banner** → a photo with caption is sent immediately and marked `sent_to_telegram`.
   - New event **without banner** → a text-only message is sent and marked `sent_without_image`.
   - Banner **appears later** → the photo is posted as a reply to the original message, then the event is marked as fully delivered.
4. **Validate links** — an event link is only rendered as an "Access Now" button if it is a real URL (not a numeric ID) and responds with a 2xx status.
5. **Cleanup** — a daily job deletes cache rows older than 5 days (`EVENT_TTL_DAYS`).

### Features

- Automatic event polling every 5 minutes (configurable)
- Exactly-once delivery — deduplication backed by Supabase
- Smart banner handling: text announcement first, image posted as a reply once available
- Deep links validated for both format and HTTP health before being shown
- Timestamps rendered in Vietnam time (UTC+7)
- Graceful API error handling — the channel never receives error spam
- Rich HTML message formatting
- Automatic retention cleanup of stale cache rows
- Dual logging to console and `bot.log`

### Message Format

Each announcement looks like this (with the banner image attached when available):

```text
Title: FIREWORK FESTIVAL
Region: GLOBAL
Start: 01/10/2026 00:00:00
End: 08/10/2026 23:59:59
Link: Access Now        ← only shown when a valid, healthy URL exists
```

### Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.10+ |
| Telegram | python-telegram-bot v21 |
| Database | Supabase (PostgreSQL) via supabase-py v2 |
| Scheduling | APScheduler v3 (async) |
| HTTP | requests |
| Timezone | pytz (Asia/Ho_Chi_Minh) |
| Configuration | python-dotenv |

### Project Structure

```text
BOT-AUTO-EVENTS-TELEGRAM/
├── app.py                 # Entry point: initializes components and keeps the process alive
├── config.py              # Loads .env and defines global tunables
├── event_processor.py     # Fetches events and decides which ones need sending
├── supabase_client.py     # Persistence layer: cache, deduplication, status flags
├── telegram_bot.py        # Message formatting and Telegram delivery
├── scheduler.py           # APScheduler jobs: poll every 5 min, cleanup daily
├── supabase_schema.sql    # SQL schema for the event_cache table
├── requirements.txt       # Pinned dependencies
├── .env.example           # Environment variable template
├── start.sh               # Quick-start helper script
├── LICENSE
├── .gitignore
└── README.md
```

### Getting Started

#### Prerequisites

- Python **3.10+**
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Telegram channel with the bot added as an **administrator**
- A [Supabase](https://supabase.com) project (the free tier is enough)

#### 1. Clone the repository

```bash
git clone https://github.com/nqzkhoi010608/BOT-AUTO-EVENTS-TELEGRAM.git
cd BOT-AUTO-EVENTS-TELEGRAM
```

#### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Create the database table

Open your Supabase dashboard → **SQL Editor** and run the contents of [`supabase_schema.sql`](supabase_schema.sql), reproduced below:

```sql
CREATE TABLE event_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    region TEXT,
    start_time BIGINT,
    end_time BIGINT,
    image_url TEXT,
    sub_go_pos TEXT,
    has_image BOOLEAN DEFAULT FALSE,
    sent_to_telegram BOOLEAN DEFAULT FALSE,
    sent_without_image BOOLEAN DEFAULT FALSE,
    telegram_message_id BIGINT,
    posted_to_facebook BOOLEAN DEFAULT FALSE,
    facebook_post_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_event_cache_event_id ON event_cache(event_id);
CREATE INDEX idx_event_cache_created_at ON event_cache(created_at);
CREATE INDEX idx_event_cache_has_image ON event_cache(has_image);
CREATE INDEX idx_event_cache_sent_to_telegram ON event_cache(sent_to_telegram);
CREATE INDEX idx_event_cache_sent_without_image ON event_cache(sent_without_image);
CREATE INDEX idx_event_cache_posted_to_facebook ON event_cache(posted_to_facebook);

-- Allow the anon key to read/write this table
ALTER TABLE event_cache DISABLE ROW LEVEL SECURITY;
```

> Disabling Row Level Security lets the anon key work out of the box. For a public event cache this is acceptable; if you need stricter access, replace it with permissive RLS policies instead.

#### 4. Configure environment variables

```bash
cp .env.example .env
```

Then fill in the values:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token issued by @BotFather |
| `TELEGRAM_CHANNEL_ID` | Yes | Target channel username (e.g. `@mychannel`) or numeric chat ID |
| `SUPABASE_URL` | Yes | Supabase project URL, e.g. `https://xxxxxxxx.supabase.co` |
| `SUPABASE_KEY` | Yes | Supabase anon (public) key |

#### 5. Run the bot

```bash
python app.py    # or: python3 app.py on Linux
```

On startup the bot validates the configuration, verifies the database table, runs an initial check immediately, then settles into the 5-minute polling loop. Press `Ctrl+C` for a clean shutdown.

### Configuration Reference

Besides the environment variables above, three tunables live in `config.py`:

| Constant | Default | Description |
|---|---|---|
| `API_URL` | `https://api-aurust.onrender.com/api/splash` | Upstream event source |
| `CHECK_INTERVAL_MINUTES` | `5` | How often events are polled |
| `EVENT_TTL_DAYS` | `5` | How long cache rows survive before cleanup |

### Deployment

#### start.sh (Linux)

```bash
chmod +x start.sh
./start.sh
```

#### PM2 (recommended for VPS)

```bash
npm install -g pm2
pm2 start app.py --name telegram-event-bot --interpreter python3
pm2 save
pm2 startup
```

#### Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t telegram-event-bot .
docker run -d --env-file .env --restart unless-stopped --name telegram-event-bot telegram-event-bot
```

### Logging

Logs are written to both the console (stdout) and the `bot.log` file:

```text
2026-10-03 09:15:00,000 - scheduler - INFO - Starting event check...
```

### Security Notes

- Never commit `.env` — it is already listed in `.gitignore`.
- If the bot token or Supabase keys leak, rotate them immediately.
- The bot only needs the anon key; never expose the service-role key in the application.

### Contributing

Issues and pull requests are welcome at the [issue tracker](https://github.com/nqzkhoi010608/BOT-AUTO-EVENTS-TELEGRAM/issues).

1. Fork the repository
2. Create your branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes
4. Open a pull request

### License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

## Tiếng Việt

### Giới thiệu

Bot hoạt động theo một pipeline đơn giản và đáng tin cậy:

1. **Kiểm tra** — cứ mỗi 5 phút (`CHECK_INTERVAL_MINUTES`), bot lấy danh sách sự kiện mới nhất từ API nguồn.
2. **Phát hiện** — mỗi sự kiện có một định danh ổn định (`name + startTime`) và được so sánh với bảng `event_cache` trên Supabase.
3. **Gửi tin**:
   - Sự kiện mới **có banner** → gửi ảnh kèm chú thích ngay lập tức, đánh dấu `sent_to_telegram`.
   - Sự kiện mới **chưa có banner** → gửi tin nhắn văn bản, đánh dấu `sent_without_image`.
   - Banner **xuất hiện sau đó** → ảnh được gửi dưới dạng reply vào tin nhắn gốc, sự kiện được đánh dấu là đã gửi đầy đủ.
4. **Kiểm tra liên kết** — link chỉ hiển thị dưới dạng "Access Now" khi là URL hợp lệ (không phải ID dạng số) và phản hồi HTTP 2xx.
5. **Dọn dẹp** — job hàng ngày xóa các dòng dữ liệu cũ hơn 5 ngày (`EVENT_TTL_DAYS`).

### Tính năng

- Tự động kiểm tra sự kiện mỗi 5 phút (có thể cấu hình)
- Mỗi sự kiện chỉ được gửi đúng một lần — chống trùng lặp bằng Supabase
- Xử lý banner thông minh: gửi văn bản trước, ảnh sẽ reply vào tin nhắn đó khi có sẵn
- Liên kết được kiểm tra cả định dạng lẫn trạng thái HTTP trước khi hiển thị
- Thời gian hiển thị theo múi giờ Việt Nam (UTC+7)
- Xử lý lỗi API mềm dẻo — kênh không bao giờ nhận các thông báo lỗi
- Định dạng tin nhắn HTML đẹp mắt
- Tự động dọn dẹp dữ liệu cache cũ
- Ghi log ra cả console và file `bot.log`

### Định dạng tin nhắn

Mỗi thông báo có dạng như sau (kèm ảnh banner khi có sẵn):

```text
Title: FIREWORK FESTIVAL
Region: GLOBAL
Start: 01/10/2026 00:00:00
End: 08/10/2026 23:59:59
Link: Access Now        ← chỉ hiện khi URL hợp lệ và truy cập được
```

### Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Runtime | Python 3.10+ |
| Telegram | python-telegram-bot v21 |
| Cơ sở dữ liệu | Supabase (PostgreSQL) qua supabase-py v2 |
| Lập lịch | APScheduler v3 (async) |
| HTTP | requests |
| Múi giờ | pytz (Asia/Ho_Chi_Minh) |
| Cấu hình | python-dotenv |

### Cấu trúc dự án

```text
BOT-AUTO-EVENTS-TELEGRAM/
├── app.py                 # Điểm khởi đầu: khởi tạo các thành phần và giữ tiến trình chạy
├── config.py              # Nạp biến môi trường từ .env và các hằng số cấu hình
├── event_processor.py     # Lấy sự kiện từ API và quyết định sự kiện nào cần gửi
├── supabase_client.py     # Lớp lưu trữ: cache, chống trùng lặp, cờ trạng thái
├── telegram_bot.py        # Định dạng tin nhắn và gửi lên Telegram
├── scheduler.py           # Job APScheduler: kiểm tra mỗi 5 phút, dọn dẹp hàng ngày
├── supabase_schema.sql    # Schema SQL cho bảng event_cache
├── requirements.txt       # Các dependency đã ghim phiên bản
├── .env.example           # Mẫu biến môi trường
├── start.sh               # Script khởi động nhanh
├── LICENSE
├── .gitignore
└── README.md
```

### Bắt đầu nhanh

#### Yêu cầu trước

- Python **3.10+**
- Token bot Telegram từ [@BotFather](https://t.me/BotFather)
- Kênh Telegram với bot được thêm vào làm **quản trị viên**
- Một project [Supabase](https://supabase.com) (gói miễn phí là đủ)

#### 1. Clone repository

```bash
git clone https://github.com/nqzkhoi010608/BOT-AUTO-EVENTS-TELEGRAM.git
cd BOT-AUTO-EVENTS-TELEGRAM
```

#### 2. Cài đặt dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Tạo bảng dữ liệu

Mở Supabase Dashboard → **SQL Editor** và chạy nội dung file [`supabase_schema.sql`](supabase_schema.sql) (script SQL đầy đủ nằm ở [phần tiếng Anh](#3-create-the-database-table) phía trên).

> Tắt Row Level Security giúp anon key hoạt động ngay lập tức. Với cache sự kiện công khai thì cách này chấp nhận được; nếu cần bảo mật chặt hơn, hãy thay bằng các RLS policy cho phép.

#### 4. Cấu hình biến môi trường

```bash
cp .env.example .env
```

Sau đó điền các giá trị:

| Biến | Bắt buộc | Mô tả |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Có | Token bot do @BotFather cấp |
| `TELEGRAM_CHANNEL_ID` | Có | Username kênh (vd: `@mychannel`) hoặc chat ID dạng số |
| `SUPABASE_URL` | Có | URL project Supabase, vd: `https://xxxxxxxx.supabase.co` |
| `SUPABASE_KEY` | Có | Anon key (public) của Supabase |

#### 5. Chạy bot

```bash
python app.py    # hoặc: python3 app.py trên Linux
```

Khi khởi động, bot sẽ kiểm tra cấu hình, xác nhận bảng dữ liệu, chạy kiểm tra lần đầu ngay lập tức, sau đó chuyển sang vòng lặp kiểm tra mỗi 5 phút. Nhấn `Ctrl+C` để dừng sạch sẽ.

### Tham khảo cấu hình

Ngoài các biến môi trường trên, ba hằng số cấu hình nằm trong `config.py`:

| Hằng số | Giá trị mặc định | Mô tả |
|---|---|---|
| `API_URL` | `https://api-aurust.onrender.com/api/splash` | Nguồn sự kiện |
| `CHECK_INTERVAL_MINUTES` | `5` | Chu kỳ kiểm tra sự kiện |
| `EVENT_TTL_DAYS` | `5` | Thời gian giữ dòng dữ liệu trước khi dọn dẹp |

### Triển khai

#### start.sh (Linux)

```bash
chmod +x start.sh
./start.sh
```

#### PM2 (khuyên dùng cho VPS)

```bash
npm install -g pm2
pm2 start app.py --name telegram-event-bot --interpreter python3
pm2 save
pm2 startup
```

#### Docker

Tạo file `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

Build và chạy:

```bash
docker build -t telegram-event-bot .
docker run -d --env-file .env --restart unless-stopped --name telegram-event-bot telegram-event-bot
```

### Nhật ký hệ thống

Log được ghi ra cả console (stdout) và file `bot.log`:

```text
2026-10-03 09:15:00,000 - scheduler - INFO - Starting event check...
```

### Lưu ý bảo mật

- Không bao giờ commit file `.env` — file này đã được đưa vào `.gitignore`.
- Nếu token bot hoặc khóa Supabase bị lộ, hãy thu hồi và tạo mới ngay lập tức.
- Bot chỉ cần anon key; không bao giờ dùng service-role key trong ứng dụng.

### Đóng góp

Mọi báo cáo lỗi và đóng góp đều được chào đón tại [issue tracker](https://github.com/nqzkhoi010608/BOT-AUTO-EVENTS-TELEGRAM/issues).

1. Fork repository
2. Tạo nhánh mới (`git checkout -b feature/ten-tinh-nang`)
3. Commit các thay đổi
4. Mở pull request

### Giấy phép

Được phân phối dưới giấy phép MIT. Xem [`LICENSE`](LICENSE) để biết chi tiết.
