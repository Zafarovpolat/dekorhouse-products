#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {
  ROOT, loadEnv, required, parseArgs, readManifest, ensureReportsDir,
  timestamp, sha256, contentType, localImage, jsonFetch,
} from './lib/common.mjs';

const HELP = `
Bito image uploader (dry-run by default)

Usage:
  node scripts/upload-bito.mjs --manifest scripts/manifests/zelen-final-17.json
  node scripts/upload-bito.mjs --manifest scripts/manifests/zelen-final-17.json --apply
`;

loadEnv();
const args = parseArgs();
if (args.help) { console.log(HELP); process.exit(0); }

const API_KEY = required('BITO_API_KEY');
const JWT = required('BITO_JWT');
const CATEGORY_ID = required('BITO_CATEGORY_ID');
const { manifest } = readManifest(args.manifest);

const READ = 'https://api.bito.uz/integration-api/integration/api/v2/product/get-paging';
const UPDATE = 'https://api.bito.uz/integration-api/integration/api/v1/product/update';
const UPLOAD = 'https://api.bito.uz/upload-api/public/upload';
const PUBLIC = 'https://api.bito.uz/upload-api/public';
const apiHeaders = { 'api-key': API_KEY, 'Content-Type': 'application/json' };

async function loadProducts() {
  const all = [];
  let page = 1, total = Infinity;
  while ((page - 1) * 100 < total) {
    const response = await jsonFetch(READ, {
      method: 'POST', headers: apiHeaders,
      body: JSON.stringify({ page, limit: 100, is_product: true }),
    });
    if (response.code !== 0) throw new Error(`Bito read failed: ${JSON.stringify(response).slice(0, 500)}`);
    total = response.data.total;
    all.push(...response.data.data);
    page++;
  }
  return all;
}

async function uploadFile(filename, buffer) {
  const boundary = `ArenaBito${Date.now()}${Math.random().toString(16).slice(2)}`;
  const body = Buffer.concat([
    Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${path.basename(filename)}"\r\nContent-Type: ${contentType(filename)}\r\n\r\n`),
    buffer,
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);
  const response = await jsonFetch(UPLOAD, {
    method: 'POST',
    headers: { Authorization: JWT, 'Content-Type': `multipart/form-data; boundary=${boundary}` },
    body,
  });
  if (response.code !== 0 || !response.data) throw new Error(`Bito upload failed: ${JSON.stringify(response).slice(0, 500)}`);
  return response.data;
}

async function updateImage(product, uploadedPath, mode) {
  let images;
  if (mode === 'replace') images = [uploadedPath];
  else if (mode === 'prepend') images = [uploadedPath, ...(product.images || []).filter(x => x !== uploadedPath)];
  else throw new Error(`Unsupported Bito mode '${mode}'. Use replace or prepend explicitly in the manifest.`);
  const response = await jsonFetch(UPDATE, {
    method: 'POST', headers: apiHeaders,
    body: JSON.stringify({ _id: product._id, image: uploadedPath, images }),
  });
  if (response.code !== 0) throw new Error(`Bito update failed: ${JSON.stringify(response).slice(0, 500)}`);
  return images;
}

console.log(`Mode: ${args.apply ? 'APPLY' : 'DRY-RUN (no writes)'}`);
console.log(`Category: ${CATEGORY_ID}`);
const products = await loadProducts();
const plan = [];

for (const item of manifest.items) {
  if (!item.sku || !item.code || !item.file) throw new Error(`Every item requires sku, code, and file: ${JSON.stringify(item)}`);
  const matches = products.filter(p => String(p.sku) === String(item.sku) && p.category?._id === CATEGORY_ID);
  if (matches.length !== 1) throw new Error(`${item.code} / SKU ${item.sku}: expected exactly 1 Bito match in ZELEN, got ${matches.length}`);
  const product = matches[0];
  const filePath = localImage(item);
  const buffer = fs.readFileSync(filePath);
  plan.push({ item, product, filePath, buffer, hash: sha256(buffer) });
  console.log(`✓ ${item.code.padEnd(18)} SKU ${String(item.sku).padEnd(6)} → ${product.name} (${product._id}) | ${path.basename(filePath)} | mode=${item.bitoMode || 'MISSING'}`);
}

if (!args.apply) {
  console.log(`\nValidated ${plan.length} item(s). Nothing was uploaded. Re-run with --apply after review.`);
  process.exit(0);
}

const report = { startedAt: new Date().toISOString(), categoryId: CATEGORY_ID, backup: [], results: [] };
for (const row of plan) {
  const { item, product, filePath, buffer, hash } = row;
  report.backup.push({ sku: String(item.sku), code: item.code, id: product._id, oldImage: product.image, oldImages: product.images || [] });
  try {
    const uploadedPath = await uploadFile(filePath, buffer);
    const images = await updateImage(product, uploadedPath, item.bitoMode);
    const downloaded = Buffer.from(await (await fetch(PUBLIC + uploadedPath)).arrayBuffer());
    if (sha256(downloaded) !== hash) throw new Error('Uploaded bytes do not match the local file');
    report.results.push({ sku: String(item.sku), code: item.code, status: 'ok', uploadedPath, images, sha256: hash });
    console.log(`OK ${item.code} → ${uploadedPath}`);
  } catch (error) {
    report.results.push({ sku: String(item.sku), code: item.code, status: 'failed', error: error.message });
    console.error(`FAIL ${item.code}: ${error.message}`);
  }
  await new Promise(resolve => setTimeout(resolve, 200));
}

report.finishedAt = new Date().toISOString();
const reportPath = path.join(ensureReportsDir(), `bito-upload-${timestamp()}.json`);
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
const failed = report.results.filter(x => x.status !== 'ok');
console.log(`\nResult: ${report.results.length - failed.length} OK, ${failed.length} failed`);
console.log(`Backup/report: ${path.relative(ROOT, reportPath)}`);
if (failed.length) process.exitCode = 1;
