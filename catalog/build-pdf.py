#!/usr/bin/env python3
"""
Генерирует PDF из index.html (A4 landscape).

Использование:
    python3 build-pdf.py                # → catalog.pdf
    python3 build-pdf.py output.pdf     # → output.pdf

Требования:
    pip install playwright pypdf
    python3 -m playwright install chromium
    python3 -m playwright install-deps chromium   # linux

Как работает:
    Запускает локальный HTTP-сервер на порту 8123 (иначе fetch() не работает),
    рендерит страницы порциями по 8 (иначе браузер жрёт всю память на 30+ страниц),
    склеивает PDF через pypdf, чистит временные файлы.
"""
import asyncio, os, sys, http.server, socketserver, threading, functools, glob
from playwright.async_api import async_playwright
from pypdf import PdfWriter, PdfReader

OUT_DEFAULT = "catalog.pdf"
PORT = 8123
CHUNK = 8   # страниц за один запуск браузера (~200 МБ ОЗУ на chunk)
HERE = os.path.dirname(os.path.abspath(__file__))

def start_server():
    """Отдаём файлы из папки со скриптом."""
    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=HERE)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd

async def render_chunk(pw, first, last, out_path):
    browser = await pw.chromium.launch(args=["--disable-dev-shm-usage", "--no-sandbox"])
    ctx = await browser.new_context(viewport={"width": 1600, "height": 1131})
    page = await ctx.new_page()

    await page.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_function("document.querySelectorAll('.page').length > 1", timeout=30_000)

    await page.add_style_tag(content=f"""
        .page {{ display: none !important; }}
        .page:nth-of-type(n+{first}):nth-of-type(-n+{last}) {{ display: flex !important; }}
    """)

    # прокрутка чтобы триггернуть lazy-load
    await page.evaluate("""
        () => new Promise(r => {
            const t = document.body.scrollHeight; let y = 0;
            const step = () => { window.scrollTo(0, y); y += 300;
                if (y < t) setTimeout(step, 20);
                else { window.scrollTo(0,0); setTimeout(r, 400); }
            }; step();
        })
    """)

    try:
        await page.wait_for_function(
            "() => Array.from(document.images).filter(i => i.complete && i.naturalWidth > 0).length >= document.images.length * 0.9",
            timeout=90_000)
    except: pass

    try: await page.evaluate("document.fonts.ready")
    except: pass
    await page.wait_for_timeout(1500)

    await page.emulate_media(media="print")
    page.set_default_timeout(300_000)

    await page.pdf(
        path=out_path,
        format="A4", landscape=True,
        print_background=True,
        margin={"top":"0","right":"0","bottom":"0","left":"0"},
        prefer_css_page_size=True,
    )
    await browser.close()

async def main(out_path):
    httpd = start_server()
    try:
        # сколько всего страниц
        async with async_playwright() as pw:
            b = await pw.chromium.launch(args=["--disable-dev-shm-usage","--no-sandbox"])
            p = await b.new_page()
            await p.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="domcontentloaded", timeout=60_000)
            await p.wait_for_function("document.querySelectorAll('.page').length > 1", timeout=30_000)
            total = await p.evaluate("document.querySelectorAll('.page').length")
            await b.close()
        print(f"→ страниц всего: {total}, chunk = {CHUNK}", flush=True)

        chunks = []
        idx = 0
        for start in range(1, total+1, CHUNK):
            end = min(start+CHUNK-1, total)
            out = os.path.join(HERE, f"_chunk_{idx:02d}.pdf")
            print(f"  chunk {idx}: страницы {start}..{end}", flush=True)
            async with async_playwright() as pw:
                await render_chunk(pw, start, end, out)
            chunks.append(out); idx += 1

        writer = PdfWriter()
        for c in chunks:
            for p in PdfReader(c).pages: writer.add_page(p)
        with open(out_path, "wb") as f: writer.write(f)
        for c in chunks: os.remove(c)
        size = os.path.getsize(out_path) // 1024
        print(f"\n✅ Готово: {out_path} ({size} KB)", flush=True)
        print(f"\nЧтобы сжать до ~2 MB: gs -sDEVICE=pdfwrite -dPDFSETTINGS=/ebook -o small.pdf {out_path}", flush=True)
    finally:
        httpd.shutdown()

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else OUT_DEFAULT
    if not out.startswith('/'): out = os.path.join(HERE, out)
    asyncio.run(main(out))
