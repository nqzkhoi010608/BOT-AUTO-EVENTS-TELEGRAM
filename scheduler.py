import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import CHECK_INTERVAL_MINUTES
from event_processor import event_processor
from telegram_bot import telegram_bot
from supabase_client import supabase_client

logger = logging.getLogger(__name__)

class EventScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler already running")
            return
        
        # Add job to check events every 5 minutes
        self.scheduler.add_job(
            self.check_and_send_events,
            trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINUTES),
            id="check_events",
            name="Check and send new events",
            replace_existing=True
        )
        
        # Add job to cleanup old events daily
        self.scheduler.add_job(
            self.cleanup_old_events,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_events",
            name="Cleanup old events",
            replace_existing=True
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"Scheduler started - checking events every {CHECK_INTERVAL_MINUTES} minutes")
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")
    
    async def check_and_send_events(self):
        """Main job: check for new events and send to Telegram"""
        logger.info("Starting event check...")
        
        try:
            # Single function handles all cases: new events, events waiting for image, etc.
            ready_events = event_processor.get_events_to_send()
            
            if ready_events:
                logger.info(f"Found {len(ready_events)} events to send")
            
            sent_count = 0
            skipped_count = 0
            
            for event in ready_events:
                result = await telegram_bot.send_event(event)
                if result == "skipped":
                    skipped_count += 1
                elif result:
                    sent_count += 1
                else:
                    logger.error(f"Failed to send event: {event.get('name')}")
            
            if sent_count > 0 or skipped_count > 0:
                logger.info(f"Event check completed. Sent {sent_count}, skipped {skipped_count}")
            else:
                logger.info("Event check completed. No new events to send.")
                
        except Exception as e:
            logger.error(f"Error in check_and_send_events: {e}")
    
    async def cleanup_old_events(self):
        """Cleanup events older than TTL"""
        try:
            deleted_count = supabase_client.cleanup_old_events()
            logger.info(f"Cleaned up {deleted_count} old events")
        except Exception as e:
            logger.error(f"Error cleaning up old events: {e}")

event_scheduler = EventScheduler()