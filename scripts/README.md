# Upload scripts

See [`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) first.

## Safety model

- Dry-run is the default.
- Writes require `--apply`.
- Targets are explicit in a JSON manifest.
- Bito is validated by exact SKU + category ID.
- Supabase is validated by category + `bitoSku`, with `productCode` fallback.
- Backups and results are written to ignored `reports/` files.
- Secrets are read from ignored `.env.local`; they are never hardcoded.

## Setup

```bash
cp .env.example .env.local
# Fill .env.local with fresh credentials.
node --version   # Node 18+ required (native fetch)
```

No npm installation is required.

## Bito

```bash
# No writes
node scripts/upload-bito.mjs --manifest scripts/manifests/zelen-final-17.json

# Explicit write
node scripts/upload-bito.mjs --manifest scripts/manifests/zelen-final-17.json --apply
```

`bitoMode` must be explicit per manifest item:

- `replace` — make the uploaded file the only image.
- `prepend` — make it primary and retain old images after it.

## Supabase

```bash
# No writes
node scripts/upload-supabase.mjs --manifest scripts/manifests/zelen-final-17.json

# Explicit write
node scripts/upload-supabase.mjs --manifest scripts/manifests/zelen-final-17.json --apply
```

The script uploads to `products/edited/...`, then updates or creates the main `product_images` row, then downloads and hashes the result.

## Creating a manifest

```json
{
  "name": "batch name",
  "items": [
    {
      "sku": "7605",
      "code": "DH-140",
      "productCode": "DH-140",
      "file": "7605_DH-140_edited.png",
      "bitoMode": "replace",
      "supabaseMode": "update-main"
    }
  ]
}
```

- `sku` is the actual Bito SKU. Do not infer it from the filename.
- `code` is a human-readable audit label.
- `productCode` is a Supabase lookup fallback.
- `file` is normally relative to `assets/edited/`.
- `storagePath` is optional; default is `edited/<file basename>`.
