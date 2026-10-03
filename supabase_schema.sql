-- Supabase Schema for Auto Events Telegram Bot
-- Run this in Supabase Dashboard > SQL Editor

-- Create table
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

-- Indexes for performance
CREATE INDEX idx_event_cache_event_id ON event_cache(event_id);
CREATE INDEX idx_event_cache_created_at ON event_cache(created_at);
CREATE INDEX idx_event_cache_has_image ON event_cache(has_image);
CREATE INDEX idx_event_cache_sent_to_telegram ON event_cache(sent_to_telegram);
CREATE INDEX idx_event_cache_sent_without_image ON event_cache(sent_without_image);
CREATE INDEX idx_event_cache_posted_to_facebook ON event_cache(posted_to_facebook);

-- Allow the anon key to read/write this table.
-- For stricter access, replace this with permissive RLS policies instead.
ALTER TABLE event_cache DISABLE ROW LEVEL SECURITY;

-- Optional: auto cleanup via pg_cron (if enabled on your project)
-- SELECT cron.schedule('cleanup-old-events', '0 3 * * *', $$DELETE FROM event_cache WHERE created_at < NOW() - INTERVAL '5 days'$$);

-- Verify the table was created
SELECT * FROM event_cache LIMIT 1;
