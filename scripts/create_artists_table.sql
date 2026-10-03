CREATE TABLE IF NOT EXISTS public.artists (
    deezer_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    picture TEXT,
    fans BIGINT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
