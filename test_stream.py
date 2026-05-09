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

BASE = "http://127.0.0.1:8000"
STREAM_URL = "https://playerservices.streamtheworld.com/api/livestream-redirect/RADIO_TOKFM.mp3"
HEADERS = {"X-Org-Code": "__local_dev__", "Content-Type": "application/json"}

sub_id = None


def subscribe():
    body = json.dumps({"name": "TOK FM test", "stream_url": STREAM_URL}).encode()
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


def print_chunk(data: dict):
    chunk_start = data["chunk_start"]
    print(f"\n{'─' * 60}")
    print(f"⏱  Chunk {chunk_start:.0f}s – {data['chunk_end']:.0f}s")

    if data.get("raw_transcript"):
        print(f"\n📝 Transkrypcja:\n   {data['raw_transcript'][:300]}")

    if data.get("speakers"):
        print("\n🎙  Mówcy:")
        for s in data["speakers"]:
            print(f"   [{s['label']}] {s['description']}")

    if data.get("topic_transitions"):
        print("\n🔀 Zmiany tematu:")
        for tr in data["topic_transitions"]:
            abs_ts = chunk_start + tr["timestamp_offset_seconds"]
            print(f"   [{abs_ts:.0f}s] {tr['description']}")

    if data.get("topics"):
        print("\n📌 Tematy:")
        # index facts and quotes by topic for hierarchical display
        facts_by_topic: dict[str, list] = {}
        for f in data.get("facts", []):
            key = f.get("topic_title") or "__none__"
            facts_by_topic.setdefault(key, []).append(f)
        quotes_by_topic: dict[str, list] = {}
        for q in data.get("quotes", []):
            key = q.get("topic_title") or "__none__"
            quotes_by_topic.setdefault(key, []).append(q)

        for t in data["topics"]:
            t_start = chunk_start + t.get("start_offset_seconds", 0)
            t_end = chunk_start + t["end_offset_seconds"] if t.get("end_offset_seconds") is not None else data["chunk_end"]
            conf = f" ({t['confidence']:.0%})" if t.get("confidence") else ""
            print(f"\n   📌 {t['title']}{conf}  [{t_start:.0f}s–{t_end:.0f}s]")
            for f in facts_by_topic.get(t["title"], []):
                who = f" [{f['speaker_label']}]" if f.get("speaker_label") else ""
                ts = f" @{chunk_start + f['timestamp_offset_seconds']:.0f}s" if f.get("timestamp_offset_seconds") else ""
                print(f"      💡 {f['text']}{who}{ts}")
            for q in quotes_by_topic.get(t["title"], []):
                who = f" — {q['speaker_label']}" if q.get("speaker_label") else ""
                print(f'      💬 "{q["text"]}"{who}')

        # facts/quotes not assigned to any topic
        for f in facts_by_topic.get("__none__", []):
            who = f" [{f['speaker_label']}]" if f.get("speaker_label") else ""
            print(f"   💡 {f['text']}{who}")
        for q in quotes_by_topic.get("__none__", []):
            who = f" — {q['speaker_label']}" if q.get("speaker_label") else ""
            print(f'   💬 "{q["text"]}"{who}')

    elif not data.get("raw_transcript"):
        print("   (pusty chunk — muzyka/dżingiel lub brak klucza API)")


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
    print("\nNasłuchuję... (pierwsze chunki za ~2 min, pierwszy digest za ~10 min, Ctrl+C zatrzymuje)\n")
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
