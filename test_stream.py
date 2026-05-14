# Interaktywny test streamu. Uruchom najpierw serwer:
#   $env:DB_BACKEND = "null"
#   .venv/Scripts/uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000
#
# Potem w drugim terminalu:
#   .venv/Scripts/python.exe test_stream.py
#
# Ctrl+C zatrzymuje i usuwa subskrypcje.
import json
import signal
import sys
import urllib.request
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"
STREAM_URL = "https://dash4.antik.sk/live/test_tvp_info/playlist.m3u8"  # TVP Info HLS
HEADERS = {"X-Org-Code": "__local_dev__", "Content-Type": "application/json"}

sub_id = None


def subscribe():
    body = json.dumps(
        {
            "name": "TVP Info test",
            "stream_url": STREAM_URL,
            "stream_type": "tv",
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/v2/streams/subscriptions", data=body, headers=HEADERS, method="POST"
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print(f"✓ Subskrybowano: {data['id']} (status={data['status']})")
    return data["id"]


def unsubscribe(sid):
    req = urllib.request.Request(
        f"{BASE}/v2/streams/subscriptions/{sid}",
        headers={"X-Org-Code": "__local_dev__"},
        method="DELETE",
    )
    try:
        urllib.request.urlopen(req)
        print(f"\n✓ Zatrzymano subskrypcję {sid}")
    except Exception as e:
        print(f"\n⚠ Błąd przy zatrzymaniu: {e}")


def _parse_at(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso) if iso else None


def print_chunk(data: dict):
    chunk_start = data["chunk_start"]
    chunk_end = data["chunk_end"]
    start_at = _parse_at(data.get("chunk_start_at"))
    end_at = _parse_at(data.get("chunk_end_at"))

    print(f"\n{'─' * 60}")
    if start_at and end_at:
        print(
            f"⏱  Chunk [{start_at.strftime('%H:%M:%S')} – {end_at.strftime('%H:%M:%S')}]  [SSE→klient]"
        )
    else:
        print(f"⏱  Chunk {chunk_start:.0f}s – {chunk_end:.0f}s  [SSE→klient]")

    if data.get("speakers"):
        print("🎙  " + "  ".join(f"[{s['label']}] {s['description']}" for s in data["speakers"]))

    if data.get("topic_transitions"):
        for tr in data["topic_transitions"]:
            off = tr["timestamp_offset_seconds"]
            ts = (
                (start_at + timedelta(seconds=off)).strftime("%H:%M:%S")
                if start_at
                else f"{chunk_start + off:.0f}s"
            )
            print(f"🔀 [{ts}] {tr['description']}")

    for t in data.get("topics", []):
        t_off_start = t.get("start_offset_seconds", 0)
        t_off_end = t.get("end_offset_seconds")
        if start_at:
            t_start_str = (start_at + timedelta(seconds=t_off_start)).strftime("%H:%M:%S")
            t_end_str = (
                (start_at + timedelta(seconds=t_off_end)).strftime("%H:%M:%S")
                if t_off_end is not None
                else end_at.strftime("%H:%M:%S")
                if end_at
                else "?"
            )
            time_range = f"{t_start_str}–{t_end_str}"
        else:
            t_start = chunk_start + t_off_start
            t_end = chunk_start + t_off_end if t_off_end is not None else chunk_end
            time_range = f"{t_start:.0f}s–{t_end:.0f}s"
        conf = f" ({t['confidence']:.0%})" if t.get("confidence") else ""
        print(f"\n📌 {t['title']}{conf}  [{time_range}]")
        for f in t.get("facts", []):
            who = f" [{f['speaker_label']}]" if f.get("speaker_label") else ""
            f_off = f.get("timestamp_offset_seconds", 0)
            if start_at:
                f_ts = (start_at + timedelta(seconds=f_off)).strftime("%H:%M:%S")
            else:
                f_ts = f"{chunk_start + f_off:.0f}s"
            print(f"   💡 {f['text']}{who} @{f_ts}")
        for q in t.get("quotes", []):
            who = f" — {q['speaker_label']}" if q.get("speaker_label") else ""
            print(f'   💬 "{q["text"]}"{who}')

    if not data.get("topics") and not data.get("raw_transcript"):
        print("   (pusty chunk — muzyka/dżingiel)")


def print_digest(data: dict):
    stories = data.get("stories", [])
    w_start = data.get("window_start", 0)
    w_end = data.get("window_end", 0)
    digest_num = data.get("digest_number", "?")
    report = data.get("report_path", "")
    print(f"\n{'=' * 60}")
    print(
        f"DIGEST #{digest_num}  {w_start:.0f}s – {w_end:.0f}s  "
        f"({len(stories)} {'temat' if len(stories) == 1 else 'tematy/tematow'})"
    )
    if report:
        print(f"Raport: {report}")
    print(f"{'=' * 60}")
    for i, story in enumerate(stories, 1):
        print(f"\n[{i}] {story.get('title', '(bez tytulu)')}")
        if story.get("summary"):
            print(f"    {story['summary']}")
        if story.get("speakers"):
            names = ", ".join(s["name_or_role"] for s in story["speakers"])
            print(f"    Rozmowcy: {names}")
        if story.get("facts"):
            print("    Fakty:")
            for f in story["facts"][:3]:
                who = f" [{f['speaker']}]" if f.get("speaker") else ""
                print(f"      • {f['text']}{who}")
        if story.get("quotes"):
            print("    Cytaty:")
            for q in story["quotes"][:2]:
                who = f" — {q['speaker']}" if q.get("speaker") else ""
                print(f'      "{q["text"]}"{who}')
    if not stories:
        print("  (brak tematow — reklamy/muzyka)")


def listen(sid):
    req = urllib.request.Request(
        f"{BASE}/v2/streams/subscriptions/{sid}/results/stream",
        headers={"X-Org-Code": "__local_dev__"},
    )
    print(
        "\nNasłuchuję... (pierwsze chunki za ~3 min, pierwszy digest za ~15 min, Ctrl+C zatrzymuje)\n"
    )
    event_type = None
    with urllib.request.urlopen(req) as r:
        for raw in r:
            line = raw.decode().strip()
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and event_type == "chunk":
                payload = json.loads(line.split(":", 1)[1].strip())
                print_chunk(payload)
                event_type = None
            elif line.startswith("data:") and event_type == "digest":
                payload = json.loads(line.split(":", 1)[1].strip())
                print_digest(payload)
                event_type = None
            elif line.startswith("data:") and event_type == "keepalive":
                print(".", end="", flush=True)
                event_type = None


def main():
    global sub_id
    sub_id = subscribe()

    def _stop(sig, frame):
        if sub_id:
            unsubscribe(sub_id)
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        listen(sub_id)
    except KeyboardInterrupt:
        pass
    finally:
        if sub_id:
            unsubscribe(sub_id)


if __name__ == "__main__":
    main()
