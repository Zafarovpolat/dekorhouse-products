#!/usr/bin/env python3
"""
VETKA live Bito audit (DIAGNOSTIC ONLY).
Does NOT modify catalog-vetka/products.json.
Uses only Python stdlib.
"""

import json
import re
import time
import ssl
import urllib.request
import urllib.error
import os

# The Bito API cert chain is not resolvable in this environment; use an
# unverified SSL context so the diagnostic fetch can proceed.
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

PROJECT_ROOT = "/Users/sarvaribrokhimov/Documents/dkhs/dekorhouse-products"
API_KEY = "dekor-house:572cb1a59f9b6ca88975d1edb83e355d"
PRODUCT_ENDPOINT = "https://api.bito.uz/integration-api/integration/api/v2/product/get-paging"
PRICE_ENDPOINT = "https://api.bito.uz/integration-api/integration/api/v2/price/items/get-paging"
VETKA_CATEGORY_ID = "695a13d5b8932277286d87b1"
ORG_ID = "6701170d334dc069f51e4c82"
PRICE_ID = "6706187e485b322ea8c90155"
PRODUCTS_JSON = os.path.join(PROJECT_ROOT, "catalog-vetka", "products.json")
OUT_BITO = os.path.join(PROJECT_ROOT, "vetka-live-bito-0808.json")
OUT_AUDIT = os.path.join(PROJECT_ROOT, "vetka-live-audit-0808.json")

HEADERS = {
    "api-key": API_KEY,
    "Content-Type": "application/json",
}


def post_json(url, body, retries=3):
    """POST JSON with basic 3x retry on network errors."""
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last_err = e
            print(f"    [retry {attempt}/{retries}] network error: {e}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Failed after {retries} retries: {last_err}")


def normalize(s):
    """
    lowercase; strip parentheses but keep their content;
    replace any run of [-\\s]+ with single '-'; strip leading/trailing '-'.
    """
    if s is None:
        return ""
    s = str(s).lower()
    # strip parentheses but keep content
    s = s.replace("(", " ").replace(")", " ")
    # replace runs of dash/whitespace with single dash
    s = re.sub(r"[-\s]+", "-", s)
    s = s.strip("-")
    return s


# ===================== STEP A: fetch VETKA products =====================
def fetch_products():
    print("=== STEP A: fetching VETKA products ===")
    products = []
    page = 1
    total = None
    while True:
        body = {
            "page": page,
            "limit": 100,
            "is_product": True,
            "category_id": VETKA_CATEGORY_ID,
        }
        resp = post_json(PRODUCT_ENDPOINT, body)
        data = resp.get("data", {}) or {}
        if total is None:
            total = data.get("total", 0)
            print(f"  total products reported: {total}")
        batch = data.get("data", []) or []
        products.extend(batch)
        print(f"  page {page}: fetched {len(batch)} (collected {len(products)}/{total})")
        if not batch:
            break
        if len(products) >= (total or 0):
            break
        page += 1
    return products, total


# ===================== STEP B: fetch prices =====================
def fetch_prices():
    print("=== STEP B: fetching prices ===")
    price_map = {}
    zero_price_count = 0
    kept_items = 0
    page = 1
    total = None
    while True:
        body = {
            "page": page,
            "limit": 100,
            "price_id": PRICE_ID,
        }
        resp = post_json(PRICE_ENDPOINT, body)
        data = resp.get("data", {}) or {}
        if total is None:
            total = data.get("total", 0)
            print(f"  total price items reported: {total}")
        batch = data.get("data", []) or []
        for item in batch:
            if item.get("organization_id") != ORG_ID:
                continue
            product = item.get("product") or {}
            pid = product.get("_id")
            if not pid:
                continue
            try:
                price = int(round(float(item.get("amount", 0))))
            except (TypeError, ValueError):
                price = 0
            if price == 0:
                zero_price_count += 1
            price_map[pid] = price
            kept_items += 1
        print(f"  page {page}: fetched {len(batch)} (processed toward {total}); kept-for-org {kept_items}")
        if not batch:
            break
        # price total counts ALL items (not just org), paginate through all pages
        collected = page * 100
        if collected >= (total or 0):
            break
        page += 1
    print(f"  price items with price==0 (org): {zero_price_count}")
    return price_map, total, zero_price_count


def product_availability(product):
    orgs = product.get("organizations", []) or []
    for entry in orgs:
        if entry.get("organization_id") == ORG_ID:
            is_available = bool(entry.get("is_available", False))
            is_available_for_sale = bool(entry.get("is_available_for_sale", False))
            try:
                amount = int(entry.get("amount", 0) or 0)
            except (TypeError, ValueError):
                amount = 0
            return is_available, is_available_for_sale, amount
    return False, False, 0


def main():
    products, prod_total = fetch_products()
    price_map, price_total, zero_price_count = fetch_prices()

    # ===== Build Bito records =====
    bito_records = []
    for p in products:
        pid = p.get("_id")
        name = p.get("name")
        sku = p.get("sku")
        number = p.get("number")
        category = p.get("category") or {}
        category_name = category.get("name")
        is_available, is_available_for_sale, amount = product_availability(p)
        in_stock = (is_available_for_sale is True) and (amount > 0)
        price = price_map.get(pid, None)
        rec = {
            "name": name,
            "normalized": normalize(name),
            "sku": sku,
            "number": number,
            "_id": pid,
            "in_stock": in_stock,
            "amount": amount,
            "is_available": is_available,
            "is_available_for_sale": is_available_for_sale,
            "price": price,
            "category_name": category_name,
        }
        bito_records.append(rec)

    # ===== STEP C: load products.json =====
    print("=== STEP C: reconcile against catalog-vetka/products.json ===")
    with open(PRODUCTS_JSON, "r", encoding="utf-8") as f:
        pjson = json.load(f)
    print(f"  products.json entries: {len(pjson)}")

    # index products.json by normalized code
    pjson_by_norm = {}
    for entry in pjson:
        code = entry.get("code")
        norm = normalize(code)
        pjson_by_norm[norm] = entry

    # index bito by normalized name
    bito_by_norm = {}
    for rec in bito_records:
        bito_by_norm.setdefault(rec["normalized"], []).append(rec)

    # convenience: normalized -> in-stock bito record (pick one, prefer in_stock)
    def bito_lookup(norm):
        recs = bito_by_norm.get(norm, [])
        if not recs:
            return None
        for r in recs:
            if r["in_stock"]:
                return r
        return recs[0]

    # ===== Section 1: counts =====
    total_bito = len(bito_records)
    in_stock_recs = [r for r in bito_records if r["in_stock"]]
    in_stock_count = len(in_stock_recs)
    out_count = total_bito - in_stock_count

    # ===== Section 2: in products.json but NOT in-stock / not found -> REMOVE =====
    to_remove = []
    for entry in pjson:
        code = entry.get("code")
        norm = normalize(code)
        rec = bito_lookup(norm)
        if rec is None:
            to_remove.append({"code": code, "normalized": norm, "reason": "not_found_in_bito"})
        elif not rec["in_stock"]:
            if not rec["is_available_for_sale"]:
                reason = "not_for_sale"
            elif rec["amount"] <= 0:
                reason = "out_of_stock"
            else:
                reason = "out_of_stock"
            to_remove.append({"code": code, "normalized": norm, "reason": reason})

    # ===== Section 3: in-stock on Bito but MISSING from products.json -> ADD =====
    to_add = []
    for rec in in_stock_recs:
        if rec["normalized"] not in pjson_by_norm:
            to_add.append({
                "name": rec["name"],
                "normalized": rec["normalized"],
                "sku": rec["sku"],
                "price": rec["price"],
            })

    # ===== Section 4: price mismatches (matched + in-stock) =====
    price_mismatches = []
    for entry in pjson:
        code = entry.get("code")
        norm = normalize(code)
        rec = bito_lookup(norm)
        if rec is None or not rec["in_stock"]:
            continue
        pj_price = entry.get("price")
        live_price = rec["price"]
        try:
            pj_price_cmp = int(round(float(pj_price)))
        except (TypeError, ValueError):
            pj_price_cmp = None
        if live_price is None:
            continue
        if pj_price_cmp != live_price:
            price_mismatches.append({
                "code": code,
                "normalized": norm,
                "products_json_price": pj_price,
                "live_bito_price": live_price,
            })

    # ===== Section 5: unmatched dumps =====
    matched_pjson_norms = set()
    for entry in pjson:
        norm = normalize(entry.get("code"))
        if norm in bito_by_norm:
            matched_pjson_norms.add(norm)
    unmatched_pjson = [
        {"code": e.get("code"), "normalized": normalize(e.get("code"))}
        for e in pjson if normalize(e.get("code")) not in bito_by_norm
    ]
    unmatched_bito = [
        {"name": r["name"], "normalized": r["normalized"], "sku": r["sku"], "in_stock": r["in_stock"]}
        for r in bito_records if r["normalized"] not in pjson_by_norm
    ]

    # ===== Section 6: limon/lemon check =====
    limon_re = re.compile(r"limon|lemon", re.IGNORECASE)
    limon_in_stock = [
        {"name": r["name"], "sku": r["sku"], "in_stock": r["in_stock"], "amount": r["amount"]}
        for r in in_stock_recs if r["name"] and limon_re.search(r["name"])
    ]
    limon_any = [
        {"name": r["name"], "sku": r["sku"], "in_stock": r["in_stock"], "amount": r["amount"]}
        for r in bito_records if r["name"] and limon_re.search(r["name"])
    ]

    # ===== Write bito file =====
    with open(OUT_BITO, "w", encoding="utf-8") as f:
        json.dump(bito_records, f, ensure_ascii=False, indent=2)

    # ===== Write audit file =====
    audit = {
        "generated_from": "vetka_audit.py",
        "counts": {
            "total_bito_vetka_fetched": total_bito,
            "bito_total_reported": prod_total,
            "in_stock": in_stock_count,
            "out_of_stock_or_not_for_sale": out_count,
            "products_json_count": len(pjson),
            "price_items_zero_price": zero_price_count,
            "price_total_reported": price_total,
        },
        "should_remove": to_remove,
        "candidates_to_add": to_add,
        "price_mismatches": price_mismatches,
        "unmatched_bito_names": unmatched_bito,
        "unmatched_products_json_codes": unmatched_pjson,
        "limon_lemon_check": {
            "in_stock_matches": limon_in_stock,
            "any_matches": limon_any,
        },
    }
    with open(OUT_AUDIT, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)

    # ===================== PRINT SUMMARY =====================
    print("")
    print("========================= VETKA LIVE BITO AUDIT SUMMARY =========================")
    print("")
    print("--- 1. COUNTS ---")
    print(f"  Total Bito VETKA fetched      : {total_bito} (reported total: {prod_total})")
    print(f"  In-stock                      : {in_stock_count}")
    print(f"  Out-of-stock / not-for-sale   : {out_count}")
    print(f"  products.json count           : {len(pjson)}")
    print(f"  Price items with price==0     : {zero_price_count} (of price total {price_total})")
    print("")

    print("--- 2. IN products.json but NOT in-stock / not found -> SHOULD REMOVE ---")
    if not to_remove:
        print("  (none)")
    for r in to_remove:
        print(f"  code={r['code']}  reason={r['reason']}")
    print(f"  TOTAL to remove: {len(to_remove)}")
    print("")

    print("--- 3. IN-STOCK on Bito but MISSING from products.json -> CANDIDATES TO ADD ---")
    if not to_add:
        print("  (none)")
    for r in to_add:
        print(f"  name={r['name']}  sku={r['sku']}  price={r['price']}")
    print(f"  TOTAL to add: {len(to_add)}")
    print("")

    print("--- 4. PRICE MISMATCHES (matched + in-stock) ---")
    if not price_mismatches:
        print("  (none)")
    for r in price_mismatches:
        print(f"  code={r['code']}  products.json={r['products_json_price']}  live_bito={r['live_bito_price']}")
    print(f"  TOTAL price mismatches: {len(price_mismatches)}")
    print("")

    print("--- 5a. UNMATCHED Bito names (not in products.json) ---")
    if not unmatched_bito:
        print("  (none)")
    for r in unmatched_bito:
        print(f"  name={r['name']}  norm={r['normalized']}  in_stock={r['in_stock']}  sku={r['sku']}")
    print(f"  TOTAL unmatched Bito names: {len(unmatched_bito)}")
    print("")

    print("--- 5b. UNMATCHED products.json codes (not in Bito) ---")
    if not unmatched_pjson:
        print("  (none)")
    for r in unmatched_pjson:
        print(f"  code={r['code']}  norm={r['normalized']}")
    print(f"  TOTAL unmatched products.json codes: {len(unmatched_pjson)}")
    print("")

    print("--- 6. LIMON / LEMON CHECK ---")
    print(f"  in-stock matches: {len(limon_in_stock)}")
    for r in limon_in_stock:
        print(f"    IN-STOCK: name={r['name']}  sku={r['sku']}  amount={r['amount']}")
    print(f"  any (incl. out-of-stock) matches: {len(limon_any)}")
    for r in limon_any:
        print(f"    ANY: name={r['name']}  in_stock={r['in_stock']}  amount={r['amount']}")
    if not limon_in_stock:
        print("  CONFIRMED: no limon/lemon names in the live in-stock set.")
    print("")

    print("========================= END SUMMARY =========================")
    print(f"Wrote: {OUT_BITO}")
    print(f"Wrote: {OUT_AUDIT}")


if __name__ == "__main__":
    main()
