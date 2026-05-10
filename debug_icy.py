"""Quick ICY metadata debug — raw TCP, handles 'ICY 200 OK'."""
import asyncio
from urllib.parse import urlparse

URL = "http://mp3.polskieradio.pl:8900"


async def test(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or 80
    path = parsed.path or "/"

    print(f"Connecting to {host}:{port}{path} ...")
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=8.0)
    try:
        writer.write(
            f"GET {path} HTTP/1.0\r\nHost: {host}\r\nIcy-MetaData: 1\r\nConnection: close\r\n\r\n".encode()
        )
        await writer.drain()

        status = await asyncio.wait_for(reader.readline(), timeout=5.0)
        print(f"Status line: {status!r}")

        icy_metaint = None
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if line in (b"\r\n", b"\n", b""):
                break
            print(f"  Header: {line.rstrip()!r}")
            if b":" in line:
                k, v = line.split(b":", 1)
                if k.strip().lower() == b"icy-metaint":
                    icy_metaint = int(v.strip())

        print(f"\nicy-metaint: {icy_metaint}")
        if icy_metaint is None:
            print(">>> NO ICY-METAINT — stream nie wspiera ICY")
            return

        buf = bytearray()
        while len(buf) < icy_metaint + 1:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            if not chunk:
                break
            buf.extend(chunk)

        meta_len = buf[icy_metaint] * 16
        print(f"meta_len_byte={buf[icy_metaint]}, meta_len={meta_len}")
        if meta_len == 0:
            print(">>> meta_len==0 — brak tytułu w tej chwili")
            return

        meta_end = icy_metaint + 1 + meta_len
        meta_str = buf[icy_metaint + 1 : meta_end].rstrip(b"\x00").decode("utf-8", errors="replace")
        print(f">>> meta_str: {meta_str!r}")
    finally:
        writer.close()


asyncio.run(test(URL))
