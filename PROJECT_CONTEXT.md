# DekorHouse Products — project context

Last verified: **2026-07-15** (Asia/Tashkent)

This file is the handoff for another developer or AI agent. Read it before changing Bito, Supabase, product images, or the ZELEN PDF catalog.

## Repositories and systems

- **Primary repository:** `Zafarovpolat/dekorhouse-products`
  - `assets/edited/` — approved edited product images.
  - `catalog/products.json` — source list for the PDF catalog.
  - `catalog/index.html` — printable catalog layout.
  - `catalog/catalog-printer.pdf` and `catalog/catalog-ebook.pdf` — generated catalogs.
- **Legacy/helper repository:** `zafarovpolat/bito-cat-zelen`
  - Older upload scripts and source comparisons. Do not copy its hardcoded secrets.
- **Bito category:** `ZELEN`
  - category ID: `6943e7089f1e6d061cc0aad8`
  - organization ID: `6701170d334dc069f51e4c82`
- **Supabase project:** `https://yjfyvedavmrdifmepvkh.supabase.co`
  - storage bucket: `products`
  - edited image prefix: `edited/`
  - ZELEN category ID: `c6adaef3b9b984cbab0aa5ac1`

## Security and credentials

**Never commit real credentials.** This repository may be public. Live GPT/OpenAI, GitHub, Bito, and Supabase keys were previously exposed in chat/history and must be rotated.

1. Copy `.env.example` to `.env.local`.
2. Fill the values locally.
3. `.env.local` is ignored by Git.
4. Scripts redact credentials and do not print them.

Required variables:

- `BITO_API_KEY` — Integration API read/update key.
- `BITO_JWT` — Bito back-office token used by the upload service. JWTs expire.
- `SUPABASE_SERVICE_ROLE` — required for Storage and database writes.

The real keys are intentionally **not** stored in GitHub. An agent must request fresh keys from the owner when missing or expired.

## Confirmed Bito endpoints

- Read products:
  - `POST https://api.bito.uz/integration-api/integration/api/v2/product/get-paging`
  - header: `api-key: BITO_API_KEY`
- Update product image:
  - `POST https://api.bito.uz/integration-api/integration/api/v1/product/update`
  - header: `api-key: BITO_API_KEY`
  - minimal body used successfully: `{ "_id": "...", "image": "/uploads/...", "images": ["/uploads/..."] }`
- Upload file:
  - `POST https://api.bito.uz/upload-api/public/upload`
  - header: `Authorization: BITO_JWT`
  - multipart field: `file`
- Public uploaded file:
  - `https://api.bito.uz/upload-api/public` + returned `/uploads/...` path.

Important: the old `back-api/admin/product/get-paging` route is obsolete. The old `back-api/admin/product/update` route exists but rejects expired JWTs. The Integration API v1 update route above was verified and is preferred.

## Upload workflow

Uploads are manifest-driven and dry-run by default.

```bash
cp .env.example .env.local
# fill .env.local

# Validate Bito mapping; no writes
node scripts/upload-bito.mjs --manifest scripts/manifests/zelen-final-17.json

# Apply only after reviewing the dry-run
node scripts/upload-bito.mjs --manifest scripts/manifests/zelen-final-17.json --apply

# Validate Supabase mapping; no writes
node scripts/upload-supabase.mjs --manifest scripts/manifests/zelen-final-17.json

# Apply to Storage and product_images
node scripts/upload-supabase.mjs --manifest scripts/manifests/zelen-final-17.json --apply
```

Both scripts:

- validate category and SKU/code before writes;
- create JSON backups/reports under `reports/`;
- require explicit `--apply`;
- verify the result after uploading.

## Product-image mapping caveats

- The numeric filename prefix normally equals Bito SKU, but **not always**.
- Always use the explicit manifest `sku`; never infer targets only from filenames.
- B-5 final mapping:
  - B-5-green → Bito SKU `6458` → `6458-3_B-5_green_originalcolor_edited.png`
  - B-5-red → Bito SKU `6460` → `6458-1_B-5_red_gpt2_enlarged_nocut_edited.png`
  - B-5-white → Bito SKU `6456` → `6458-2_B-5_green_edited.png`
- W-5 edited variants:
  - W-5-1/white-looking source → `6716-1_W-5_edited.png`
  - W-5 light green, Bito SKU `12686` → `6716-2_W-5_edited.png`
  - W-5 red, Bito SKU `12682` → `6716-3_W-5_edited.png`
- Do not upload `mix` composites as a single product image unless explicitly requested.

## Current verified state

At the last audit:

- Bito ZELEN products: **89** total.
- In stock and enabled for sale: **81**.
- PDF catalog: **81** products, **16** pages.
- The catalog intentionally excludes 8 out-of-stock/unavailable products.
- The 17 final changed images in `scripts/manifests/zelen-final-17.json` were uploaded to Bito and verified byte-for-byte.
- Catalog background and image canvas background are `#fafafa`.
- Latest background correction commit at handoff: `8c5bfd2`.

## PDF catalog rules

- Data source: `catalog/products.json`.
- Document background: **`#fafafa`**.
- Product images must have no visible rectangular white/black canvas against the document.
- Do not change product form, color, or approved edited image while normalizing the canvas.
- Keep at least 3 product cards per page.
- Z-81…Z-86 should remain together on one page.
- Generate both printer and ebook PDFs.
- Validate:
  - every JSON product code exists in PDF text;
  - every image is embedded;
  - no blank product image;
  - 16 pages / 81 products unless stock state changes;
  - mobile viewers display images (strip malformed ICC profiles or normalize images to sRGB before PDF rendering).

## Safe operating procedure

1. Pull latest `main`.
2. Run dry-run and save output.
3. Confirm every SKU, Bito `_id`, code, and filename.
4. Back up old Bito/Supabase image references.
5. Apply a small batch first when using a new token or endpoint.
6. Re-read APIs and verify uploaded bytes/URLs.
7. Rebuild and visually inspect PDF pages.
8. Commit only scripts, docs, manifests, edited assets, and final catalogs — never `.env.local` or generated reports.
