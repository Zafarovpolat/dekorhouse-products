#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {
  ROOT, loadEnv, required, parseArgs, readManifest, ensureReportsDir,
  timestamp, sha256, contentType, localImage, cuid, jsonFetch,
} from './lib/common.mjs';

const HELP = `
Supabase Storage + product_images uploader (dry-run by default)

Usage:
  node scripts/upload-supabase.mjs --manifest scripts/manifests/zelen-final-17.json
  node scripts/upload-supabase.mjs --manifest scripts/manifests/zelen-final-17.json --apply
`;

loadEnv();
const args = parseArgs();
if (args.help) { console.log(HELP); process.exit(0); }

const URL = required('SUPABASE_URL').replace(/\/$/, '');
const KEY = required('SUPABASE_SERVICE_ROLE');
const BUCKET = required('SUPABASE_BUCKET');
const CATEGORY_ID = required('SUPABASE_CATEGORY_ID');
const { manifest } = readManifest(args.manifest);
const headers = { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' };

function objectPath(storagePath) {
  return storagePath.split('/').map(encodeURIComponent).join('/');
}

async function restGet(table, query) {
  return jsonFetch(`${URL}/rest/v1/${table}?${query}`, { headers });
}

async function findProduct(item) {
  const select = encodeURIComponent('id,code,bitoSku,categoryId');
  let rows = await restGet('products', `select=${select}&categoryId=eq.${encodeURIComponent(CATEGORY_ID)}&bitoSku=eq.${encodeURIComponent(item.sku)}`);
  if (!rows.length && item.productCode) {
    rows = await restGet('products', `select=${select}&categoryId=eq.${encodeURIComponent(CATEGORY_ID)}&code=eq.${encodeURIComponent(item.productCode)}`);
  }
  if (rows.length !== 1) throw new Error(`${item.code} / SKU ${item.sku}: expected exactly 1 Supabase product, got ${rows.length}. Add productCode to the manifest when SKU differs.`);
  return rows[0];
}

async function mainImages(productId) {
  return restGet('product_images', `select=id,productId,url,alt,sortOrder,isMain&productId=eq.${encodeURIComponent(productId)}&isMain=eq.true&order=sortOrder.asc`);
}

async function uploadStorage(storagePath, buffer, filename) {
  const response = await fetch(`${URL}/storage/v1/object/${encodeURIComponent(BUCKET)}/${objectPath(storagePath)}`, {
    method: 'POST',
    headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': contentType(filename), 'x-upsert': 'true' },
    body: buffer,
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Storage HTTP ${response.status}: ${text.slice(0, 400)}`);
}

async function setMainImage(product, existing, publicUrl, item) {
  const mode = item.supabaseMode;
  if (mode !== 'update-main') throw new Error(`Unsupported Supabase mode '${mode}'. Use update-main explicitly.`);
  if (existing.length) {
    return jsonFetch(`${URL}/rest/v1/product_images?id=eq.${encodeURIComponent(existing[0].id)}`, {
      method: 'PATCH', headers: { ...headers, Prefer: 'return=representation' },
      body: JSON.stringify({ url: publicUrl, alt: item.code }),
    });
  }
  return jsonFetch(`${URL}/rest/v1/product_images`, {
    method: 'POST', headers: { ...headers, Prefer: 'return=representation' },
    body: JSON.stringify({
      id: cuid(), productId: product.id, url: publicUrl, alt: item.code,
      sortOrder: 0, isMain: true, createdAt: new Date().toISOString(),
    }),
  });
}

console.log(`Mode: ${args.apply ? 'APPLY' : 'DRY-RUN (no writes)'}`);
console.log(`Supabase category: ${CATEGORY_ID}; bucket: ${BUCKET}`);
const plan = [];
for (const item of manifest.items) {
  if (!item.sku || !item.code || !item.file) throw new Error(`Every item requires sku, code, and file: ${JSON.stringify(item)}`);
  const product = await findProduct(item);
  const existing = await mainImages(product.id);
  const filePath = localImage(item);
  const buffer = fs.readFileSync(filePath);
  const storagePath = item.storagePath || `edited/${path.basename(filePath)}`;
  const publicUrl = `${URL}/storage/v1/object/public/${encodeURIComponent(BUCKET)}/${objectPath(storagePath)}`;
  plan.push({ item, product, existing, filePath, buffer, storagePath, publicUrl, hash: sha256(buffer) });
  console.log(`✓ ${item.code.padEnd(18)} SKU ${String(item.sku).padEnd(6)} → ${product.code} (${product.id}) | ${storagePath} | mode=${item.supabaseMode || 'MISSING'}`);
}

if (!args.apply) {
  console.log(`\nValidated ${plan.length} item(s). Nothing was uploaded. Re-run with --apply after review.`);
  process.exit(0);
}

const report = { startedAt: new Date().toISOString(), categoryId: CATEGORY_ID, bucket: BUCKET, backup: [], results: [] };
for (const row of plan) {
  const { item, product, existing, filePath, buffer, storagePath, publicUrl, hash } = row;
  report.backup.push({ sku: String(item.sku), code: item.code, productId: product.id, previousMainImages: existing });
  try {
    await uploadStorage(storagePath, buffer, filePath);
    await setMainImage(product, existing, publicUrl, item);
    const downloaded = Buffer.from(await (await fetch(publicUrl)).arrayBuffer());
    if (sha256(downloaded) !== hash) throw new Error('Stored bytes do not match the local file');
    const verified = await mainImages(product.id);
    if (!verified.some(x => x.url === publicUrl)) throw new Error('product_images verification failed');
    report.results.push({ sku: String(item.sku), code: item.code, status: 'ok', storagePath, publicUrl, sha256: hash });
    console.log(`OK ${item.code} → ${storagePath}`);
  } catch (error) {
    report.results.push({ sku: String(item.sku), code: item.code, status: 'failed', error: error.message });
    console.error(`FAIL ${item.code}: ${error.message}`);
  }
}

report.finishedAt = new Date().toISOString();
const reportPath = path.join(ensureReportsDir(), `supabase-upload-${timestamp()}.json`);
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
const failed = report.results.filter(x => x.status !== 'ok');
console.log(`\nResult: ${report.results.length - failed.length} OK, ${failed.length} failed`);
console.log(`Backup/report: ${path.relative(ROOT, reportPath)}`);
if (failed.length) process.exitCode = 1;
