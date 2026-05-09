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
    print(f"\n{'─' * 60}")
    print(f"⏱  Chunk {data['chunk_start']:.0f}s – {data['chunk_end']:.0f}s")

    if data.get("raw_transcript"):
        print(f"\n📝 Transkrypcja:\n   {data['raw_transcript'][:300]}")

    if data.get("speakers"):
        print("\n🎙  Mówcy:")
        for s in data["speakers"]:
            print(f"   [{s['label']}] {s['description']}")

    if data.get("topics"):
        print("\n📌 Tematy:")
        for t in data["topics"]:
            conf = f" ({t['confidence']:.0%})" if t.get("confidence") else ""
            print(f"   • {t['title']}{conf}")

    if data.get("facts"):
        print("\n💡 Fakty:")
        for f in data["facts"]:
            who = f" [{f['speaker_label']}]" if f.get("speaker_label") else ""
            print(f"   • {f['text']}{who}")

    if data.get("quotes"):
        print("\n💬 Cytaty:")
        for q in data["quotes"]:
            who = f" — {q['speaker_label']}" if q.get("speaker_label") else ""
            print(f'   "{q["text"]}"{who}')

    if not any(
        [data.get("raw_transcript"), data.get("topics"), data.get("facts"), data.get("quotes")]
    ):
        print("   (pusty chunk — muzyka/dżingiel lub brak klucza API)")


def print_digest(data: dict):
    stories = data.get("stories", [])
    w_start = data.get("window_start", 0)
    w_end = data.get("window_end", 0)
    print(f"\n{'=' * 60}")
    print(
        f"DIGEST {w_start:.0f}s – {w_end:.0f}s  ({len(stories)} {'temat' if len(stories) == 1 else 'tematy/tematow'})"
    )
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
    print("\nNasłuchuję... (pierwsze wyniki za ~2 minuty, Ctrl+C zatrzymuje)\n")
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
