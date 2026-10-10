import os, mimetypes, httpx, psycopg
from urllib.parse import quote

DB = os.environ["DATABASE_URL"].strip()
SB = os.environ["SUPABASE_URL"].strip().rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_KEY"].strip()
BUCKET = os.environ["BUCKET"].strip()
print("bucket:", repr(BUCKET))

with psycopg.connect(DB) as conn, httpx.Client(timeout=120) as http:
    ids = [r[0] for r in conn.execute(
        "select id from tracks where audio_data is not null and storage_path is null")]
    print(len(ids), "to migrate")
    for tid in ids:
        user_id, fn, data = conn.execute(
            "select user_id, filename, audio_data from tracks where id = %s", (tid,)
        ).fetchone()
        ext = os.path.splitext((fn or "").strip())[1].strip().lower() or ".mp3"
        path = f"{user_id.strip()}/{tid.strip()}{ext}"
        ctype = mimetypes.guess_type(path)[0] or "audio/mpeg"
        url = f"{SB}/storage/v1/object/{quote(BUCKET)}/{quote(path)}"
        r = http.post(
            url,
            content=bytes(data),
            headers={
                "apikey": KEY,
                "Content-Type": ctype,
                "x-upsert": "true",
            },
        )
        if r.status_code >= 400:
            raise SystemExit(f"{r.status_code} {r.text} <- {url!r}")
        conn.execute("update tracks set storage_path = %s where id = %s", (path, tid))
        conn.commit()
        print("ok", tid, path)
