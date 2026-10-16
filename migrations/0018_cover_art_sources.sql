-- Run as the Supabase Postgres admin/owner. Safe to run more than once.
ALTER TABLE public.tracks
    ADD COLUMN IF NOT EXISTS cover_url text;

ALTER TABLE public.upload_jobs
    ADD COLUMN IF NOT EXISTS cover_data bytea;

ALTER TABLE public.tracks
    ALTER COLUMN cover_source DROP NOT NULL;

ALTER TABLE public.tracks
    DROP CONSTRAINT IF EXISTS ck_tracks_cover_source;

ALTER TABLE public.tracks
    ADD CONSTRAINT ck_tracks_cover_source
    CHECK (
        cover_source IS NULL OR cover_source IN (
            'upload',
            'embedded',
            'musicbrainz',
            'audiodb',
            'generated',
            'user',
            'placeholder',
            'unknown'
        )
    );

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
        GRANT SELECT (id, user_id, title, artist, album, filename, storage_path,
                      size_bytes, cover_source, cover_url, cover_path, cover_data,
                      has_cover)
            ON public.tracks TO app_runtime;
        GRANT UPDATE (cover_source, cover_url, cover_path, cover_data, has_cover)
            ON public.tracks TO app_runtime;
    END IF;
END
$$;
