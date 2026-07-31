#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Лечит PDF от Chromium и делает ebook-версию. Замена ghostscript, которого нет в среде.

ПРОБЛЕМА (описана в PROJECT_CONTEXT.md, ловилась на телефонах):
Chromium вшивает каждую картинку с цветовым пространством /ICCBased. В собранном
каталоге таких 306 из 306, а /DeviceRGB не встречается ни разу. Часть мобильных
PDF-viewer'ов (Adobe Reader Android, некоторые iOS) такие ICC не переваривает и
просто не показывает картинки — при том что на десктопе всё видно.

ЧТО ДЕЛАЕМ:
1. /ColorSpace [ /ICCBased N ] -> /DeviceRGB у всех image XObject.
   Картинки готовились как обычный sRGB JPEG без встроенного профиля, поэтому
   ICC-обёртка не несёт информации и её снятие ничего не меняет визуально.
2. Убираем /ColorTransform, если он остался от Chromium: для трёхканального
   DCTDecode это подсказка декодеру, и в связке с DeviceRGB она лишняя.
3. Для ebook-версии дополнительно пережимаем сами JPEG-потоки: меньше сторона,
   ниже качество. Форма, цвет и кадрирование товара не меняются.

Проверка после: страницы рендерятся и сравниваются с оригиналом по пикселям.
"""
import io, os, sys, collections
import pikepdf
from PIL import Image

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog-vetka.pdf")


def fix_colorspace(pdf):
    """ICCBased -> DeviceRGB у всех картинок. Возвращает счётчики."""
    stat = collections.Counter()
    for obj in pdf.objects:
        try:
            if not isinstance(obj, pikepdf.Stream):
                continue
            if obj.get('/Subtype') != pikepdf.Name('/Image'):
                continue
        except Exception:
            continue

        cs = obj.get('/ColorSpace')
        changed = False
        if cs is not None:
            # [ /ICCBased <stream> ]
            if isinstance(cs, pikepdf.Array) and len(cs) >= 1 and cs[0] == pikepdf.Name('/ICCBased'):
                prof = cs[1] if len(cs) > 1 else None
                n = None
                try:
                    n = int(prof.get('/N'))
                except Exception:
                    pass
                obj['/ColorSpace'] = pikepdf.Name('/DeviceGray' if n == 1 else '/DeviceRGB')
                stat[f'ICCBased -> Device ({n or 3} канала)'] += 1
                changed = True
            elif cs == pikepdf.Name('/DeviceRGB'):
                stat['уже DeviceRGB'] += 1

        # /ColorTransform от Chromium вместе с DeviceRGB только мешает
        if '/ColorTransform' in obj and changed:
            del obj['/ColorTransform']
            stat['снят /ColorTransform'] += 1
    return stat


def recompress(pdf, maxside, quality):
    """Пережимаем JPEG-потоки для ebook-версии."""
    before = after = 0
    n = 0
    for obj in pdf.objects:
        try:
            if not isinstance(obj, pikepdf.Stream):
                continue
            if obj.get('/Subtype') != pikepdf.Name('/Image'):
                continue
            if obj.get('/Filter') != pikepdf.Name('/DCTDecode'):
                continue          # трогаем только JPEG, флейты (лого с маской) не ломаем
        except Exception:
            continue
        try:
            raw = obj.read_raw_bytes()
            im = Image.open(io.BytesIO(raw))
            if im.mode != 'RGB':
                continue
            w0 = im.size
            if max(im.size) > maxside:
                im.thumbnail((maxside, maxside), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=False,
                    subsampling=2)
            new = buf.getvalue()
            if len(new) >= len(raw) and im.size == w0:
                continue
            obj.write(new, filter=pikepdf.Name('/DCTDecode'))
            obj['/Width'], obj['/Height'] = im.size
            obj['/ColorSpace'] = pikepdf.Name('/DeviceRGB')
            obj['/BitsPerComponent'] = 8
            if '/ColorTransform' in obj:
                del obj['/ColorTransform']
            before += len(raw); after += len(new); n += 1
        except Exception as e:
            print(f"    пропуск картинки: {type(e).__name__}")
    print(f"  пережато картинок: {n}, {before/1024/1024:.1f} МБ -> {after/1024/1024:.1f} МБ")


def build(out, maxside=None, quality=None, label=""):
    pdf = pikepdf.open(SRC)
    print(f"\n=== {label} -> {out.split('/')[-1]} ===")
    stat = fix_colorspace(pdf)
    for k, v in stat.most_common():
        print(f"  {v:>4}  {k}")
    if maxside:
        recompress(pdf, maxside, quality)
        # после пережатия заново нормализуем (новые объекты уже DeviceRGB, но на всякий)
        fix_colorspace(pdf)
    pdf.save(out, linearize=True, compress_streams=True,
             object_stream_mode=pikepdf.ObjectStreamMode.generate)
    import os
    print(f"  готово: {os.path.getsize(out)//1024} KB")
    pdf.close()


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__)) + "/"
    build(base + "catalog-vetka-printer.pdf", label="ПЕЧАТНАЯ (полное качество)")
    build(base + "catalog-vetka-ebook.pdf", maxside=1000, quality=72,
          label="EBOOK (для телефона и мессенджеров)")
