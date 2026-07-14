import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

export function loadEnv(file = path.join(ROOT, '.env.local')) {
  if (!fs.existsSync(file)) return;
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const at = line.indexOf('=');
    if (at < 1) continue;
    const key = line.slice(0, at).trim();
    let value = line.slice(at + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

export function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing ${name}. Copy .env.example to .env.local and fill it locally.`);
  return value;
}

export function parseArgs(argv = process.argv.slice(2)) {
  const result = { apply: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--apply') result.apply = true;
    else if (arg === '--manifest') result.manifest = argv[++i];
    else if (arg === '--help' || arg === '-h') result.help = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  return result;
}

export function readManifest(filename) {
  if (!filename) throw new Error('Pass --manifest <path.json>');
  const full = path.resolve(ROOT, filename);
  const manifest = JSON.parse(fs.readFileSync(full, 'utf8'));
  if (!Array.isArray(manifest.items) || !manifest.items.length) throw new Error('Manifest must contain a non-empty items array.');
  return { full, manifest };
}

export function ensureReportsDir() {
  const dir = path.join(ROOT, 'reports');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

export function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

export function contentType(filename) {
  const ext = path.extname(filename).toLowerCase();
  if (ext === '.png') return 'image/png';
  if (ext === '.jpg' || ext === '.jpeg') return 'image/jpeg';
  if (ext === '.webp') return 'image/webp';
  return 'application/octet-stream';
}

export function localImage(item) {
  if (!item.file) throw new Error(`Manifest item ${item.code || item.sku} has no file`);
  const full = path.resolve(ROOT, item.file.startsWith('assets/') ? item.file : path.join('assets/edited', item.file));
  if (!fs.existsSync(full)) throw new Error(`Image not found: ${full}`);
  return full;
}

export function cuid() {
  return 'c' + crypto.randomBytes(18).toString('base64url').toLowerCase().slice(0, 24);
}

export async function jsonFetch(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; }
  catch { throw new Error(`Non-JSON response ${response.status} from ${url}: ${text.slice(0, 200)}`); }
  if (!response.ok) throw new Error(`HTTP ${response.status} from ${url}: ${JSON.stringify(data).slice(0, 500)}`);
  return data;
}
