# DEKOR MARKET — Каталог ZELEN

Печатный каталог категории **«Декоративные зелёные ветки»** для DekorMarket.
Формат: A4 landscape.

Живой просмотр: <https://dekorhouse-products.vercel.app/catalog/>
Готовые PDF в релизах: см. вкладку **Releases** в GitHub-репо.

---

## 📁 Файлы

| Файл | Что это |
|---|---|
| `index.html` | Сам каталог. Открывается в браузере, автоматом строит все страницы. |
| `products.json` | Список товаров: код, цена, имя файла картинки. Меняешь тут — обновляется каталог. |
| `logo.png` | Логотип DekorMarket (прозрачный PNG). |
| `build-pdf.py` | Скрипт: HTML → PDF (headless Chromium). |
| `README.md` | Эта инструкция. |

Всё остальное (фото товаров) лежит в Supabase Storage и подгружается через `imagesBase` URL из `index.html`.

---

## 🖥 Как посмотреть каталог

**Способ 1 — через локальный сервер (рекомендуется):**
```bash
cd catalog
python3 -m http.server 8000
```
Открой в браузере <http://localhost:8000>

**Способ 2 — двойным кликом на `index.html`:**
Работает, но некоторые браузеры блокируют `fetch()` локальных файлов. Если увидишь ошибку — используй способ 1.

---

## 🖨 Как сохранить PDF

**Вариант A — из браузера (проще):**
1. Открой каталог по способу 1 выше
2. `Ctrl+P` (или `Cmd+P` на Mac)
3. В диалоге печати:
   - Принтер → «Сохранить как PDF»
   - Макет → **Альбомная**
   - Размер → **A4**
   - Поля → **Нет** / None
   - Печать фона → **Включено** (важно!)
4. «Сохранить»

**Вариант B — скриптом (для автоматизации):**
```bash
cd catalog
pip install playwright pypdf
python3 -m playwright install chromium
python3 -m playwright install-deps chromium   # только на Linux

python3 build-pdf.py                          # → catalog.pdf
python3 build-pdf.py my-name.pdf              # → my-name.pdf
```

**Сжатие PDF** (если получился огромный, 100+ MB):
```bash
# нужен ghostscript
gs -sDEVICE=pdfwrite -dPDFSETTINGS=/printer -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=catalog-small.pdf catalog.pdf
# уровни качества: /screen (мелкий), /ebook, /printer, /prepress (макс)
```

---

## ✏️ Как менять содержимое

### Добавить/убрать товар
Открой `products.json`, добавь/удали запись:
```json
{
  "code": "Z-99",
  "price": 45000,
  "file": "12345_Z-99_edited.png"
}
```
`file` — имя файла в бакете Supabase `products/edited/`. Обновил файл → сохранил → перезагрузил браузер.

### Поменять цену / название
Правишь в том же `products.json`.

### Поменять цвета фирменной палитры
В `index.html` найди блок `:root` (в самом верху `<style>`):
```css
:root{
  --forest:    #1B4332;   /* меняй тут */
  --terracotta:#C67C4E;   /* цены — этот цвет */
  ...
}
```

### Поменять размер логотипа
Там же в `:root`:
```css
--logo-cover: 150px;   /* на титуле */
--logo-head:  55px;    /* в шапке страниц */
```

### Поменять заголовок / даты / контакты
В `index.html` найди блок `window.CONFIG = { ... }`:
```javascript
window.CONFIG = {
  coverTitleLine1: "Декоративные",
  coverTitleLine2Italic: "зелёные",
  coverTitleLine2Suffix: " ветки",
  coverDates:  "ИЮНЬ — ИЮЛЬ 2026",
  telegram:    "@DekorHouseAdmin",
  phone:       "+998 (99) 368-11-00",
  ...
};
```

### Поменять шрифты
В `<head>` замени `<link href="https://fonts.googleapis.com/css2?family=...">`.
Дальше в CSS: `font-family:"Твой шрифт", fallback;`

### Раскладка (сколько товаров на странице)
Логика в JavaScript-функции `planPages()`: минимум **3**, максимум **6**. Раскладки:
- 3 → одна строка × 3
- 4 → 2×2
- 5 → 3+2 (5-я ячейка в центре)
- 6 → 3×2

Товары одной серии (например `Z-16-1..4`) остаются на одной странице.

---

## 🔄 Как обновить `products.json` из Supabase

Свежий список активных товаров ZELEN (нужен ключ):
```bash
curl -s "https://yjfyvedavmrdifmepvkh.supabase.co/rest/v1/products?categoryId=eq.c6adaef3b9b984cbab0aa5ac1&isActive=eq.true&select=code,price,product_images(url,isMain,sortOrder)&order=code" \
  -H "apikey: <ANON_KEY>" -H "Authorization: Bearer <ANON_KEY>" \
  | python3 -c "
import json, sys
raw = json.load(sys.stdin)
out = []
for p in raw:
    imgs = sorted(p.get('product_images') or [], key=lambda x:(not x['isMain'], x['sortOrder']))
    if not imgs: continue
    file = imgs[0]['url'].split('/edited/')[-1]
    out.append({'code':p['code'],'price':p['price'] or 0,'file':file})
out.sort(key=lambda x:x['code'].lower())
print(json.dumps(out, ensure_ascii=False, indent=2))
" > products.json
```

**Категория ZELEN:** `id=c6adaef3b9b984cbab0aa5ac1`, `slug=zelen-c0aad8`
**Supabase URL:** `https://yjfyvedavmrdifmepvkh.supabase.co`
**Публичный бакет:** `products/edited/`

---

## 🤖 Для ИИ-ассистента

Если тебя попросили сгенерить PDF или что-то поменять:

1. **Всё содержимое в 3 файлах:** `index.html` (вёрстка), `products.json` (данные), `logo.png` (лого).
2. **Не нужно ничего парсить и генерить HTML с нуля** — просто правь эти файлы.
3. **PDF получаешь одной командой:** `python3 build-pdf.py`.
4. **Ставить браузер обязательно:** `pip install playwright pypdf && python3 -m playwright install chromium && python3 -m playwright install-deps chromium`.
5. **Формат PDF:** A4 landscape, без полей, `print_background=True`, `prefer_css_page_size=True`. Скрипт `build-pdf.py` уже так настроен.
6. **Картинки товаров** — публичный Supabase (не требуют auth), доступны в браузере по прямому URL.
7. **Раскладка страниц** генерируется автоматически в JS (`planPages()` в `index.html`) — трогать её обычно не надо.

---

## 🎨 Фирменная палитра (для справки)

| Цвет | Hex | Назначение |
|---|---|---|
| Forest | `#1B4332` | Заголовки, рамки, основной тёмный |
| Emerald | `#2D6A4F` | Акцент |
| Sage | `#40916C` | Второстепенные акценты |
| Mint | `#52B788` | Иллюстративные элементы |
| Olive | `#7C8B6F` | Дополнительный |
| Terracotta | `#C67C4E` | **Цены**, акцентные слова |
| Cream | `#FFFCF5` | Фон (был), сейчас белый |
| Sand | `#F0EBE3` | Фон бэкграунда |
| Charcoal | `#2C2C2C` | Основной текст |

## 🖋 Шрифты

- **Playfair Display** — заголовки, серифная эстетика
- **Lato** — подписи, uppercase-метки
- **Nunito** — цены, имена товаров, контакты
