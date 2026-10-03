import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_URL = "https://api-aurust.onrender.com/api/splash"
CHECK_INTERVAL_MINUTES = 5
EVENT_TTL_DAYS = 5