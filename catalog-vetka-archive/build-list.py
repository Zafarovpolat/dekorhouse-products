#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собирает отдельный каталог ТОЛЬКО из товаров, у которых есть фото из архива чата.

Полный каталог (catalog-vetka) содержит все 250 товаров в наличии; здесь остаются
только те, чьё фото пришло из выгрузки чата от 31.07.2026 — как есть, без обработки.
Вёрстка, титул и палитра те же, отличается только список товаров.
"""
import os, re, json, shutil

REPO     = "/agent/workspace/dekorhouse-products"
FULL     = os.path.join(REPO, "catalog-vetka")
OUT      = os.path.join(REPO, "catalog-vetka-archive")
MANIFEST = os.path.join(REPO, "vetka-archive-0731", "manifest.json")


def archive_codes():
    """Коды товаров, которым досталось фото из архива.
    Точные совпадения + подтверждённая владельцем привязка Z-8x -> B-8x."""
    man = json.load(open(MANIFEST, encoding='utf-8'))
    codes = {}
    for r in man['photos']:
        if r['status'] == 'matched':
            codes.setdefault(r['product']['code'], r['photo_number'])
        else:
            c = r['candidates'][0] if r['candidates'] else None
            if c and c['score'] <= 1 and re.match(r'^z-?8[123]', r['caption'].lower()):
                codes.setdefault(c['code'], r['photo_number'])
    return codes


def main():
    codes = archive_codes()
    full = json.load(open(os.path.join(FULL, 'products.json'), encoding='utf-8'))
    keep = [e for e in full if e['code'] in codes and e.get('img')]

    missing = sorted(set(codes) - {e['code'] for e in keep})
    print(f"товаров с фото из архива: {len(codes)}")
    print(f"попадёт в каталог: {len(keep)}")
    if missing:
        print(f"  не найдено в полном каталоге: {missing}")

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)

    # вёрстка, лого и скрипты — те же
    for f in ('index.html', 'logo.png', 'build-pdf.py', 'fix-pdf.py'):
        shutil.copy2(os.path.join(FULL, f), os.path.join(OUT, f))

    # сборщик должен смотреть в свою папку и писать свой файл
    p = os.path.join(OUT, 'build-pdf.py')
    s = open(p, encoding='utf-8').read()
    s = s.replace('/catalog-vetka/index.html', '/catalog-vetka-archive/index.html')
    s = s.replace('OUT_DEFAULT = "catalog-vetka.pdf"',
                  'OUT_DEFAULT = "catalog-vetka-archive.pdf"')
    open(p, 'w', encoding='utf-8').write(s)

    p = os.path.join(OUT, 'fix-pdf.py')
    s = open(p, encoding='utf-8').read()
    s = s.replace('"catalog-vetka.pdf"', '"catalog-vetka-archive.pdf"')
    s = s.replace('"catalog-vetka-printer.pdf"', '"catalog-vetka-archive-printer.pdf"')
    s = s.replace('"catalog-vetka-ebook.pdf"', '"catalog-vetka-archive-ebook.pdf"')
    open(p, 'w', encoding='utf-8').write(s)

    # только нужные картинки
    n = 0
    for e in keep:
        src = os.path.join(FULL, e['img'])
        dst = os.path.join(OUT, e['img'])
        shutil.copy2(src, dst)
        n += 1

    json.dump(keep, open(os.path.join(OUT, 'products.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    size = sum(os.path.getsize(os.path.join(OUT, 'img', f))
               for f in os.listdir(os.path.join(OUT, 'img')))
    print(f"скопировано картинок: {n} ({size/1024/1024:.0f} МБ)")
    print(f"папка: {OUT}")
    print("\nкоды:", ", ".join(e['code'] for e in keep))


if __name__ == '__main__':
    main()
