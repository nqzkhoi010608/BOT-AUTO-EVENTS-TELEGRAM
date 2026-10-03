import requests
import logging
from datetime import datetime
import pytz
from config import API_URL
from supabase_client import supabase_client

logger = logging.getLogger(__name__)

class EventProcessor:
    def __init__(self):
        self.api_url = API_URL
    
    def fetch_events(self) -> list:
        """Fetch events from API"""
        try:
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract splashBanners from nested response: data.splashRes.splashBanners
            splash_banners = data.get("data", {}).get("splashRes", {}).get("splashBanners", [])
            logger.info(f"Fetched {len(splash_banners)} events from API")
            return splash_banners
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
            return []
    
    @staticmethod
    def parse_timestamp(timestamp_str: str | int) -> int:
        """Parse timestamp from string or int to int (seconds)"""
        try:
            if isinstance(timestamp_str, str):
                return int(timestamp_str)
            return int(timestamp_str)
        except (ValueError, TypeError):
            return 0
    
    def format_timestamp(self, timestamp: str | int) -> str:
        """Convert Unix timestamp to readable format DD/MM/YYYY HH:MM:SS (Vietnam timezone UTC+7)"""
        try:
            ts = self.parse_timestamp(timestamp)
            if ts:
                # API returns seconds, not milliseconds
                # Use Vietnam timezone (Asia/Ho_Chi_Minh)
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                dt = datetime.fromtimestamp(ts, tz=vietnam_tz)
                return dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception as e:
            logger.error(f"Error formatting timestamp: {e}")
        return "N/A"
    
    def is_valid_link(self, link: str) -> bool:
        """Check if link is a valid URL (not just a number)"""
        if not link or not link.strip():
            return False
        link = link.strip()
        # Check if it's just a number
        if link.isdigit():
            return False
        # Check if it looks like a URL
        return link.startswith(("http://", "https://", "www."))
    
    def format_message(self, event: dict) -> str:
        """Format event message for Telegram"""
        lines = []
        
        # Title
        name = event.get("name", "N/A")
        lines.append(f"<b>Tiêu Đề:</b> {name}")
        
        # Region
        region = event.get("region", "N/A")
        lines.append(f"<b>Khu Vực:</b> {region}")
        
        # Start time
        start_time = event.get("startTime", 0)
        lines.append(f"<b>Bắt Đầu:</b> {self.format_timestamp(start_time)}")
        
        # End time
        end_time = event.get("endTime", 0)
        lines.append(f"<b>Kết Thúc:</b> {self.format_timestamp(end_time)}")
        
        # Link (only if valid URL)
        sub_go_pos = event.get("subGoPos", "")
        if self.is_valid_link(sub_go_pos):
            lines.append(f"<b>Liên Kết:</b> <a href='{sub_go_pos}'>Truy Cập Ngay</a>")
        
        return "\n".join(lines)
    
    def get_events_to_send(self) -> list:
        """
        Single function to determine all events that need to be sent.
        Logic:
        1. Events that were sent without image but now have image → send with image
        2. New events with image → send with image
        3. New events without image → send text only (first time only)
        4. Existing events without image that were already sent text-only → DON'T send again
        """
        events = self.fetch_events()
        ready_to_send = []
        seen_event_ids = set()  # Prevent duplicates in same run
        
        for event in events:
            event_id = f"{event.get('name', '')}_{event.get('startTime', '')}"
            
            # Skip if already processed in this run
            if event_id in seen_event_ids:
                continue
            
            # Check if already fully sent (with image)
            if supabase_client.is_event_processed(event_id):
                continue
            
            # Get cached event
            cached_event = supabase_client.get_event(event_id)
            has_image = bool(event.get("imageUrl", "").strip())
            
            if cached_event:
                # Existing event - read fresh statuses from cached_event (already fetched)
                sent_to_telegram = cached_event.get("sent_to_telegram", False)
                sent_without_image = cached_event.get("sent_without_image", False)
                
                # Check if image appeared (update has_image if needed)
                api_has_image = bool(event.get("imageUrl", "").strip())
                if api_has_image and not cached_event.get("has_image"):
                    # Image just appeared - update DB
                    supabase_client.update_event_image(event_id, event.get("imageUrl", ""))
                    has_image = True
                else:
                    has_image = cached_event.get("has_image", False)
                
                if sent_to_telegram:
                    # Already fully sent with image
                    continue
                
                if has_image and not sent_to_telegram:
                    # Now has image and not sent with image yet → send with image
                    ready_to_send.append(event)
                    seen_event_ids.add(event_id)
                elif not has_image and not sent_without_image:
                    # No image yet and never sent without image → send text only (first time)
                    ready_to_send.append(event)
                    seen_event_ids.add(event_id)
                # If no image and already sent_without_image=true → don't send again (wait for image)
            else:
                # New event - insert into cache
                supabase_client.upsert_event(event)
                if has_image:
                    # New event with image → send with image
                    ready_to_send.append(event)
                    seen_event_ids.add(event_id)
                else:
                    # New event without image → send text only (first time)
                    ready_to_send.append(event)
                    seen_event_ids.add(event_id)
                    logger.info(f"New event without image, sending text only: {event.get('name')}")
        
        return ready_to_send

event_processor = EventProcessor()