import logging
import requests
import io
from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from supabase_client import supabase_client
from event_processor import event_processor

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.channel_id = TELEGRAM_CHANNEL_ID
    
    async def send_event(self, event: dict) -> str | bool:
        """Send event to Telegram channel. Returns message_id, 'skipped', True, or False."""
        try:
            image_url = event.get("imageUrl", "").strip()
            message, valid_link = self._format_message(event)
            has_image = bool(image_url)
            event_id = f"{event.get('name', '')}_{event.get('startTime', '')}"
            
            # Check cached event for existing message_id
            cached_event = supabase_client.get_event(event_id)
            already_sent_without_image = cached_event.get("sent_without_image", False) if cached_event else False
            already_fully_sent = cached_event.get("sent_to_telegram", False) if cached_event else False
            existing_message_id = cached_event.get("telegram_message_id") if cached_event else None
            
            # Already fully sent with image -> skip
            if already_fully_sent:
                logger.info(f"Event {event.get('name')} already fully sent, skipping")
                return "skipped"
            
            # Prepare reply_to if there's an existing message
            reply_to_message_id = existing_message_id if existing_message_id else None
            
            # Case 1: Has image -> send photo (reply if existing message)
            if has_image:
                photo_file = await self._download_image(image_url)
                if photo_file:
                    send_kwargs = {
                        "chat_id": self.channel_id,
                        "photo": photo_file,
                        "caption": message,
                        "parse_mode": "HTML"
                    }
                    if reply_to_message_id:
                        send_kwargs["reply_to_message_id"] = reply_to_message_id
                        logger.info(f"Sending photo as reply to message {reply_to_message_id}: {event.get('name')}")
                    sent_msg = await self.bot.send_photo(**send_kwargs)
                    message_id = sent_msg.message_id
                    sent_with_image = True
                else:
                    # Image download failed -> send text-only
                    if already_sent_without_image:
                        logger.info(f"Image download failed but already sent text-only before, skipping: {event.get('name')}")
                        return "skipped"
                    else:
                        logger.warning(f"Failed to download image, sending text only (first time): {event.get('name')}")
                        send_kwargs = {
                            "chat_id": self.channel_id,
                            "text": message,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True
                        }
                        if reply_to_message_id:
                            send_kwargs["reply_to_message_id"] = reply_to_message_id
                        sent_msg = await self.bot.send_message(**send_kwargs)
                        message_id = sent_msg.message_id
                        sent_with_image = False
            else:
                # Case 2: No image URL -> send text only (only if not sent before)
                if already_sent_without_image:
                    logger.info(f"No image and already sent text-only before, skipping: {event.get('name')}")
                    return "skipped"
                send_kwargs = {
                    "chat_id": self.channel_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True
                }
                if reply_to_message_id:
                    send_kwargs["reply_to_message_id"] = reply_to_message_id
                sent_msg = await self.bot.send_message(**send_kwargs)
                message_id = sent_msg.message_id
                sent_with_image = False
            
            # Mark as sent in Supabase with message_id
            if sent_with_image:
                supabase_client.mark_event_sent(event_id, message_id)
            else:
                supabase_client.mark_event_sent_without_image(event_id, message_id)
            
            logger.info(f"Successfully sent event: {event.get('name')} (with_image={sent_with_image}, message_id={message_id})")
            return message_id
            
        except TelegramError as e:
            logger.error(f"Telegram error sending event: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending event: {e}")
            return False
    
    async def _download_image(self, url: str) -> io.BytesIO | None:
        """Download image from URL and return as BytesIO"""
        try:
            # Add headers to bypass hotlink protection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://ff.garena.vn/',
                'Origin': 'https://ff.garena.vn'
            }
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL is not an image: {content_type}")
                return None
            
            photo_file = io.BytesIO(response.content)
            photo_file.name = 'banner.png'
            photo_file.seek(0)
            return photo_file
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None
    
    @staticmethod
    def check_url_health(url: str) -> bool:
        """Check if URL is accessible (returns 2xx status). Returns True if OK."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            # Use HEAD request first (faster), fallback to GET if not allowed
            response = requests.head(url, timeout=10, headers=headers, allow_redirects=True)
            if response.status_code == 405:  # HEAD not allowed
                response = requests.get(url, timeout=10, headers=headers, allow_redirects=True, stream=True)
                response.close()  # Don't download body
            
            is_healthy = 200 <= response.status_code < 300
            logger.info(f"URL health check: {url} -> {response.status_code} {'OK' if is_healthy else 'FAIL'}")
            return is_healthy
        except Exception as e:
            logger.warning(f"URL health check failed for {url}: {e}")
            return False
    
    def _format_message(self, event: dict) -> tuple[str, str | None]:
        """Format event message for Telegram. Returns (message_text, valid_link_or_none)"""
        lines = []
        
        # Title
        name = event.get("name", "N/A")
        lines.append(f"<b>Title:</b> {name}")
        
        # Region
        region = event.get("region", "N/A")
        lines.append(f"<b>Region:</b> {region}")
        
        # Start time
        start_time = event.get("startTime", 0)
        lines.append(f"<b>Start:</b> {self._format_timestamp(start_time)}")
        
        # End time
        end_time = event.get("endTime", 0)
        lines.append(f"<b>End:</b> {self._format_timestamp(end_time)}")
        
        # Link - check health before including
        sub_go_pos = event.get("subGoPos", "")
        valid_link = None
        if self._is_valid_link(sub_go_pos):
            if self.check_url_health(sub_go_pos):
                valid_link = sub_go_pos
                # Use double quotes for href, escape URL for HTML safety
                import html
                safe_url = html.escape(sub_go_pos, quote=True)
                lines.append(f'<b>Link:</b> <a href="{safe_url}">Access Now</a>')
            else:
                logger.info(f"Link unhealthy, not including: {sub_go_pos}")
        else:
            logger.debug(f"Invalid link format, skipping: {sub_go_pos}")
        
        return "\n".join(lines), valid_link
    
    def _format_timestamp(self, timestamp: str | int) -> str:
        """Convert Unix timestamp to readable format (Vietnam timezone UTC+7)"""
        try:
            ts = event_processor.parse_timestamp(timestamp)
            if ts:
                import pytz
                from datetime import datetime
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                dt = datetime.fromtimestamp(ts, tz=vietnam_tz)
                return dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass
        return "N/A"
    
    def _is_valid_link(self, link: str) -> bool:
        """Check if link is a valid URL (not just a number)"""
        if not link or not link.strip():
            return False
        link = link.strip()
        if link.isdigit():
            return False
        return link.startswith(("http://", "https://", "www."))

telegram_bot = TelegramBot()