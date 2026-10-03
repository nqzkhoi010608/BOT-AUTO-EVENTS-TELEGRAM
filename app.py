import asyncio
import logging
import signal
import sys
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, SUPABASE_URL, SUPABASE_KEY
from supabase_client import supabase_client
from scheduler import event_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)

# Fix console encoding for Vietnamese
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer)

logger = logging.getLogger(__name__)

class EventBot:
    def __init__(self):
        self.running = False
    
    async def initialize(self):
        """Initialize bot components"""
        # Validate config
        if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, SUPABASE_URL, SUPABASE_KEY]):
            logger.error("Missing required environment variables!")
            logger.error("Please check your .env file")
            return False
        
        # Initialize Supabase table
        supabase_client.init_table()
        
        # Sync existing events (fix missing sent_without_image for already-sent events)
        synced = supabase_client.sync_existing_events()
        if synced > 0:
            logger.info(f"Synced {synced} existing events")
        
        logger.info("Bot initialized successfully")
        return True
    
    async def start(self):
        """Start the bot"""
        if not await self.initialize():
            return
        
        self.running = True
        event_scheduler.start()
        
        # Run initial check immediately
        logger.info("Running initial event check...")
        await event_scheduler.check_and_send_events()
        
        logger.info("Bot started. Press Ctrl+C to stop.")
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot"""
        self.running = False
        event_scheduler.stop()
        logger.info("Bot stopped")

async def main():
    bot = EventBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)