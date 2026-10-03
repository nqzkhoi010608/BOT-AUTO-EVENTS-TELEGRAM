from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, EVENT_TTL_DAYS
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.table_name = "event_cache"
    
    def init_table(self):
        """Initialize the table if not exists - run this once"""
        try:
            # Check if table exists by trying to select
            self.client.table(self.table_name).select("id").limit(1).execute()
            logger.info("Table already exists")
        except Exception as e:
            logger.info(f"Table may not exist, please create it manually in Supabase with this schema:")
            logger.info("""
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
            """)
    
    def is_event_processed(self, event_id: str) -> bool:
        """Check if event was already sent to Telegram"""
        try:
            result = self.client.table(self.table_name).select("sent_to_telegram").eq("event_id", event_id).execute()
            if result.data:
                return result.data[0].get("sent_to_telegram", False)
            return False
        except Exception as e:
            logger.error(f"Error checking event processed: {e}")
            return False
    
    def get_event(self, event_id: str) -> dict | None:
        """Get event from cache"""
        try:
            result = self.client.table(self.table_name).select("*").eq("event_id", event_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting event: {e}")
            return None
    
    def upsert_event(self, event_data: dict) -> bool:
        """Insert or update event in cache"""
        try:
            # Generate a unique event_id from name + start_time
            event_id = f"{event_data.get('name', '')}_{event_data.get('startTime', '')}"
            
            has_image = bool(event_data.get("imageUrl", "").strip())
            
            data = {
                "event_id": event_id,
                "name": event_data.get("name", ""),
                "region": event_data.get("region", ""),
                "start_time": event_data.get("startTime", 0),
                "end_time": event_data.get("endTime", 0),
                "image_url": event_data.get("imageUrl", ""),
                "sub_go_pos": event_data.get("subGoPos", ""),
                "has_image": has_image,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Check if exists
            existing = self.get_event(event_id)
            if existing:
                # Preserve sent statuses and message_id
                data["sent_to_telegram"] = existing.get("sent_to_telegram", False)
                data["sent_without_image"] = existing.get("sent_without_image", False)
                data["telegram_message_id"] = existing.get("telegram_message_id")
                data["created_at"] = existing.get("created_at")
                self.client.table(self.table_name).update(data).eq("event_id", event_id).execute()
            else:
                data["sent_to_telegram"] = False
                data["sent_without_image"] = False
                data["telegram_message_id"] = None
                data["created_at"] = datetime.utcnow().isoformat()
                self.client.table(self.table_name).insert(data).execute()
            
            return True
        except Exception as e:
            # If telegram_message_id column doesn't exist, log error but don't silently drop
            if "telegram_message_id" in str(e):
                logger.error(f"telegram_message_id column missing in DB! Run SQL: ALTER TABLE event_cache ADD COLUMN telegram_message_id BIGINT;")
            logger.error(f"Error upserting event: {e}")
            return False
    
    def mark_event_sent(self, event_id: str, message_id: int = None) -> bool:
        """Mark event as sent to Telegram (with image)"""
        try:
            update_data = {
                "sent_to_telegram": True,
                "sent_without_image": True,  # Also mark as sent without image since now fully sent
                "updated_at": datetime.utcnow().isoformat()
            }
            if message_id:
                update_data["telegram_message_id"] = message_id
            self.client.table(self.table_name).update(update_data).eq("event_id", event_id).execute()
            return True
        except Exception as e:
            if "telegram_message_id" in str(e) or "sent_without_image" in str(e):
                logger.warning("Column not found in DB, run migration SQL")
            logger.error(f"Error marking event sent: {e}")
            return False
    
    def mark_event_sent_without_image(self, event_id: str, message_id: int = None) -> bool:
        """Mark event as sent to Telegram without image (text only)"""
        try:
            update_data = {
                "sent_without_image": True,
                "updated_at": datetime.utcnow().isoformat()
            }
            if message_id:
                update_data["telegram_message_id"] = message_id
            self.client.table(self.table_name).update(update_data).eq("event_id", event_id).execute()
            logger.info(f"Marked event {event_id} as sent_without_image=true, message_id={message_id}")
            return True
        except Exception as e:
            if "telegram_message_id" in str(e) or "sent_without_image" in str(e):
                logger.error(f"Column missing in DB! Run SQL: ALTER TABLE event_cache ADD COLUMN sent_without_image BOOLEAN DEFAULT FALSE; ALTER TABLE event_cache ADD COLUMN telegram_message_id BIGINT;")
                return False
            logger.error(f"Error marking event sent without image: {e}")
            return False
    
    def mark_facebook_posted(self, event_id: str, facebook_post_id: str) -> bool:
        """Mark event as posted to Facebook"""
        try:
            self.client.table(self.table_name).update({
                "posted_to_facebook": True,
                "facebook_post_id": facebook_post_id,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("event_id", event_id).execute()
            logger.info(f"Marked event {event_id} as posted_to_facebook=true, post_id={facebook_post_id}")
            return True
        except Exception as e:
            if "posted_to_facebook" in str(e) or "facebook_post_id" in str(e):
                logger.error(f"Facebook columns missing in DB! Run SQL: ALTER TABLE event_cache ADD COLUMN posted_to_facebook BOOLEAN DEFAULT FALSE; ALTER TABLE event_cache ADD COLUMN facebook_post_id TEXT;")
                return False
            logger.error(f"Error marking Facebook posted: {e}")
            return False
    
    def get_pending_events_without_image(self) -> list:
        """Get events that don't have image yet and weren't sent without image"""
        try:
            result = self.client.table(self.table_name).select("*").eq("has_image", False).eq("sent_without_image", False).execute()
            return result.data or []
        except Exception as e:
            # Column might not exist yet
            if "sent_without_image" in str(e):
                logger.warning("sent_without_image column not found in DB, run migration SQL")
                # Fallback: use old logic
                result = self.client.table(self.table_name).select("*").eq("has_image", False).eq("sent_to_telegram", False).execute()
                return result.data or []
            logger.error(f"Error getting pending events: {e}")
            return []
    
    def get_events_waiting_for_image(self) -> list:
        """Get events that were sent without image but now have image"""
        try:
            result = self.client.table(self.table_name).select("*").eq("has_image", True).eq("sent_to_telegram", False).eq("sent_without_image", True).execute()
            return result.data or []
        except Exception as e:
            # Column might not exist yet
            if "sent_without_image" in str(e):
                logger.warning("sent_without_image column not found in DB, run migration SQL")
                return []
            logger.error(f"Error getting events waiting for image: {e}")
            return []
    
    def update_event_image(self, event_id: str, image_url: str) -> bool:
        """Update event with image URL"""
        try:
            self.client.table(self.table_name).update({
                "image_url": image_url,
                "has_image": bool(image_url.strip()),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("event_id", event_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating event image: {e}")
            return False
    
    def cleanup_old_events(self) -> int:
        """Delete events older than TTL days"""
        try:
            cutoff = datetime.utcnow() - timedelta(days=EVENT_TTL_DAYS)
            result = self.client.table(self.table_name).delete().lt("created_at", cutoff.isoformat()).execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Error cleaning up old events: {e}")
            return 0
    
    def sync_existing_events(self) -> int:
        """Sync events that were sent before sent_without_image column existed.
        If sent_to_telegram=true but sent_without_image=false/null, set sent_without_image=true.
        """
        try:
            # Get events that are marked as sent but missing sent_without_image
            result = self.client.table(self.table_name).select("*").eq("sent_to_telegram", True).execute()
            updated = 0
            for event in result.data or []:
                if not event.get("sent_without_image"):
                    self.client.table(self.table_name).update({
                        "sent_without_image": True,
                        "updated_at": datetime.utcnow().isoformat()
                    }).eq("event_id", event["event_id"]).execute()
                    updated += 1
                    logger.info(f"Synced event {event['event_id']}: set sent_without_image=true")
            return updated
        except Exception as e:
            if "sent_without_image" in str(e):
                logger.warning("sent_without_image column not found, skipping sync")
            else:
                logger.error(f"Error syncing existing events: {e}")
            return 0

supabase_client = SupabaseClient()