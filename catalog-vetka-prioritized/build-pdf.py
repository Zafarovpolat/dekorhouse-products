#!/usr/bin/env python3
import asyncio, os, sys, http.server, socketserver, threading, functools
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
PORT = 8126
OUT = os.path.join(HERE, "catalog-vetka-prioritized-ebook.pdf")

def start_server():
    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=REPO_ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd

async def main():
    httpd = start_server()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--disable-dev-shm-usage", "--no-sandbox"])
            page = await (await browser.new_context(viewport={"width": 1600, "height": 1131})).new_page()
            await page.goto(f"http://127.0.0.1:{PORT}/catalog-vetka-prioritized/index.html", wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_function("document.querySelectorAll('.page').length > 1", timeout=60000)
            try:
                await page.wait_for_function("() => Array.from(document.images).filter(i => i.complete && i.naturalWidth > 0).length >= 10", timeout=90000)
            except: pass
            await page.emulate_media(media="print")
            await page.wait_for_timeout(1500)
            await page.pdf(path=OUT, format="A4", landscape=True, print_background=True, margin={"top":"0","right":"0","bottom":"0","left":"0"})
            await browser.close()
        print(f"✅ PDF ready: {OUT} ({os.path.getsize(OUT)//1024//1024} MB)")
    finally:
        httpd.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
