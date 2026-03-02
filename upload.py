# -*- coding: utf-8 -*-
import json
import math
import re
import sys
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

# =========================
# USTAWIENIA
# =========================
SHOP_URL = "adres sklepu"
CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"

CSV_FILE = "war_z_id.csv" # nazwa pliku z wariantami
CSV_SEP = ";"
CSV_ENCODING = "utf-8-sig"

# Kolumny z Twojego CSV:
COL_PRODUCT_ID = "product_id"
COL_STOCK = "Stan magazynowy"
COL_OPTIONS_TEXT = "Opcje (nazwa | typ | wartość)"
# Kod wariantu nie będzie pobierany

# Wymagania:
DEFAULT_WARNLEVEL = 1
DEFAULT_DELIVERY_HOURS = 24
DEFAULT_VARIANT_ACTIVE = 1

AUTO_CREATE_OPTION_VALUES = True
DRY_RUN = False

FORCED_OPTION_ID_BY_NAME = {
    "rozmiar": 7,
}

DEBUG_MAPPING = True

# =========================
# TOKEN
# =========================
def get_shoper_token(client_id, client_secret):
    url = f"{SHOP_URL.rstrip('/')}/webapi/rest/auth"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"grant_type": "password", "client_id": client_id, "client_secret": client_secret}

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token", None)
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania tokenu: {e}", file=sys.stderr)
        if getattr(e, "response", None) is not None:
            print(getattr(e.response, "text", "")[:800], file=sys.stderr)
        return None

# =========================
# POMOCNICZE
# =========================
def safe_int(value, default: Optional[int] = 0) -> Optional[int]:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        s = str(value).strip()
        if s == "":
            return default
        return int(float(s.replace(",", ".")))
    except Exception:
        return default

def extract_list_payload(data) -> Tuple[List[dict], Optional[int]]:
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        items = data.get("list") or data.get("data") or data.get("items") or []
        pages = data.get("pages")
        return items if isinstance(items, list) else [], pages
    return [], None

def norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = " ".join(s.split())
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s

def parse_options_cell(cell: str) -> Optional[Tuple[str, str, str]]:
    cell = (cell or "").strip()
    if not cell:
        return None
    toks = [t.strip() for t in cell.split("|")]
    if len(toks) < 3:
        return None
    opt_name = toks[0]
    opt_type = toks[1]
    opt_val = "|".join(toks[2:]).strip()
    return opt_name, opt_type, opt_val

def value_candidates(raw: str) -> List[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    cands = [raw]
    no_paren = re.sub(r"\s*\(.*?\)\s*", "", raw).strip()
    if no_paren and no_paren != raw:
        cands.append(no_paren)
    m = re.search(r"(\d+)", raw)
    if m:
        cands.append(m.group(1))

    out, seen = [], set()
    for x in cands:
        x = x.strip()
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out

def value_key_variants(label: str) -> List[str]:
    label = (label or "").strip()
    if not label:
        return []
    variants = [label]

    no_paren = re.sub(r"\s*\(.*?\)\s*", "", label).strip()
    if no_paren and no_paren != label:
        variants.append(no_paren)

    variants.append(label.replace(" ", ""))

    m = re.search(r"(\d+)", label)
    if m:
        variants.append(m.group(1))

    out, seen = [], set()
    for v in variants:
        v = v.strip()
        if v and v not in seen:
            out.append(v)
            seen.add(v)
    return out

def options_key(options: List[dict]) -> Tuple[Tuple[int, int], ...]:
    pairs = []
    for o in options:
        oid = safe_int(o.get("option_id"), None)
        vid = safe_int(o.get("value_id"), None)
        if oid and vid:
            pairs.append((oid, vid))
    return tuple(sorted(pairs))

# =========================
# API helpers
# =========================
def api_get(token: str, path: str, params: Optional[dict] = None) -> requests.Response:
    url = f"{SHOP_URL.rstrip('/')}/webapi/rest/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers, params=params, timeout=30)

def api_post(token: str, path: str, payload: dict) -> requests.Response:
    url = f"{SHOP_URL.rstrip('/')}/webapi/rest/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return requests.post(url, headers=headers, json=payload, timeout=30)

def api_put(token: str, path: str, payload: dict) -> requests.Response:
    url = f"{SHOP_URL.rstrip('/')}/webapi/rest/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return requests.put(url, headers=headers, json=payload, timeout=30)

# =========================
# OPTIONS + OPTION-VALUES
# =========================
def get_options_map(token: str) -> Dict[str, List[dict]]:
    all_items = []
    page, limit = 1, 50
    while True:
        r = api_get(token, "options", params={"limit": limit, "page": page})
        r.raise_for_status()
        items, pages = extract_list_payload(r.json())
        all_items.extend(items)
        if pages is not None and page >= int(pages):
            break
        if pages is None and (not items or len(items) < limit):
            break
        page += 1

    m: Dict[str, List[dict]] = {}
    for o in all_items:
        name = o.get("name")
        if not name and isinstance(o.get("translations"), dict):
            tr = o["translations"].get("pl_PL") or o["translations"].get("pl")
            if isinstance(tr, dict):
                name = tr.get("name")
        if isinstance(name, str) and name.strip():
            m.setdefault(norm_text(name), []).append(o)
    return m

def get_option_values_map(token: str, option_id: int) -> Dict[str, int]:
    filters = json.dumps({"option_id": int(option_id)}, ensure_ascii=False)
    all_items = []
    page, limit = 1, 50
    while True:
        r = api_get(token, "option-values", params={"limit": limit, "page": page, "filters": filters})
        if r.status_code == 404:
            break
        r.raise_for_status()
        items, pages = extract_list_payload(r.json())
        all_items.extend(items)
        if pages is not None and page >= int(pages):
            break
        if pages is None and (not items or len(items) < limit):
            break
        page += 1

    m: Dict[str, int] = {}
    for v in all_items:
        vid = v.get("ovalue_id") or v.get("value_id") or v.get("id")
        vid = safe_int(vid, None)
        if not vid:
            continue

        val_name = v.get("value") or v.get("name")
        if not val_name and isinstance(v.get("translations"), dict):
            tr = v["translations"].get("pl_PL") or v["translations"].get("pl")
            if isinstance(tr, dict):
                val_name = tr.get("value") or tr.get("name")

        if isinstance(val_name, str) and val_name.strip():
            for key in value_key_variants(val_name):
                nk = norm_text(key)
                if nk not in m:
                    m[nk] = int(vid)

    return m

def create_option_value(token: str, option_id: int, label: str) -> bool:
    payloads = [
        {"option_id": int(option_id), "translations": {"pl_PL": {"value": label}}},
        {"option_id": int(option_id), "translations": {"pl_PL": {"name": label}}},
        {"option_id": int(option_id), "value": label},
        {"option_id": int(option_id), "name": label},
    ]

    for p in payloads:
        if DRY_RUN:
            print(f"[DRY_RUN] POST /option-values\n{json.dumps(p, ensure_ascii=False)}")
            return True

        r = api_post(token, "option-values", p)
        if r.status_code in (200, 201):
            return True
        if r.status_code in (400, 422):
            continue

        print(f"❌ POST /option-values HTTP {r.status_code}: {r.text[:800]}")
        return False
    return False

# =========================
# DELIVERY + UPDATE produktu (warnlevel + delivery)
# =========================
def get_delivery_id_24h(token: str) -> Optional[int]:
    page, limit = 1, 50
    fallback = None
    while True:
        r = api_get(token, "deliveries", params={"limit": limit, "page": page})
        r.raise_for_status()
        items, pages = extract_list_payload(r.json())

        for d in items:
            did = safe_int(d.get("delivery_id") or d.get("id"), None)
            if not did:
                continue
            hours = d.get("hours")
            name = (d.get("name") or "").lower()

            try:
                if hours is not None and float(hours) == 24.0:
                    return int(did)
            except Exception:
                pass

            if "24" in name and fallback is None:
                fallback = int(did)

        if pages is not None and page >= int(pages):
            break
        if pages is None and (not items or len(items) < limit):
            break
        page += 1
    return fallback

def update_product_warnlevel_and_delivery(token: str, product_id: int, warnlevel: int, delivery_id: int) -> bool:
    # Zmieniono błędne `stock_warnlevel` na zgodne z API Shopera `stock: { warn_level: ... }`
    payload = {
        "stock": {
            "warn_level": int(warnlevel),
            "delivery_id": int(delivery_id)
        }
    }

    if DRY_RUN:
        print(f"[DRY_RUN] PUT /products/{product_id}\n{json.dumps(payload, ensure_ascii=False)}")
        return True

    r = api_put(token, f"products/{int(product_id)}", payload)
    ok = r.status_code in (200, 204)
    if not ok:
        print(f"❌ PUT /products/{product_id} HTTP {r.status_code}: {r.text[:800]}")
    return ok

# =========================
# PRODUCT-STOCKS (upsert)
# =========================
def load_product_stocks_map(token: str, product_id: int) -> Dict[Tuple[Tuple[int, int], ...], int]:
    filters = json.dumps({"product_id": int(product_id)}, ensure_ascii=False)
    page, limit = 1, 50
    mapping: Dict[Tuple[Tuple[int, int], ...], int] = {}

    while True:
        r = api_get(token, "product-stocks", params={"limit": limit, "page": page, "filters": filters})
        if r.status_code == 404:
            return mapping
        r.raise_for_status()
        items, pages = extract_list_payload(r.json())

        for s in items:
            stock_id = safe_int(s.get("stock_id") or s.get("id"), None)
            opts = s.get("options") or []
            if not stock_id or not isinstance(opts, list):
                continue
            k = options_key(opts)
            if k:
                mapping[k] = int(stock_id)

        if pages is not None and page >= int(pages):
            break
        if pages is None and (not items or len(items) < limit):
            break
        page += 1

    return mapping

def insert_product_stock(token: str, product_id: int, stock: int, options: List[dict], active: int, warn_level: int, delivery_id: int) -> bool:
    # Usunięto całkowicie "code". Dodano "warn_level" i "delivery_id" na poziomie wariantu (gdzie Shoper ich faktycznie oczekuje)
    payload = {
        "product_id": int(product_id),
        "stock": int(stock),
        "active": int(active),
        "options": options,
        "warn_level": int(warn_level),
        "delivery_id": int(delivery_id)
    }

    if DRY_RUN:
        print(f"[DRY_RUN] POST /product-stocks\n{json.dumps(payload, ensure_ascii=False)}")
        return True

    r = api_post(token, "product-stocks", payload)
    ok = r.status_code in (200, 201)
    if not ok:
        print(f"❌ POST /product-stocks HTTP {r.status_code}: {r.text[:800]}")
    return ok

def update_product_stock(token: str, stock_id: int, stock: int, active: int, warn_level: int, delivery_id: int) -> bool:
    # Usunięto całkowicie "code". Dodano "warn_level" i "delivery_id"
    payload = {
        "stock": int(stock),
        "active": int(active),
        "warn_level": int(warn_level),
        "delivery_id": int(delivery_id)
    }

    if DRY_RUN:
        print(f"[DRY_RUN] PUT /product-stocks/{stock_id}\n{json.dumps(payload, ensure_ascii=False)}")
        return True

    r = api_put(token, f"product-stocks/{int(stock_id)}", payload)
    ok = r.status_code in (200, 204)
    if not ok:
        print(f"❌ PUT /product-stocks/{stock_id} HTTP {r.status_code}: {r.text[:800]}")
    return ok

# =========================
# MAIN
# =========================
def main():
    df = pd.read_csv(CSV_FILE, sep=CSV_SEP, encoding=CSV_ENCODING)

    token = get_shoper_token(CLIENT_ID, CLIENT_SECRET)
    if not token:
        print("❌ Nie udało się pobrać tokenu.")
        return

    delivery_id_24h = get_delivery_id_24h(token)
    if not delivery_id_24h:
        print("❌ Nie znalazłem delivery_id dla 24h w /deliveries.")
        return
    print(f"✅ delivery_id dla 24h: {delivery_id_24h}")

    options_map = get_options_map(token)
    print(f"✅ Załadowane nazwy opcji z API: {len(options_map)}")

    values_cache: Dict[int, Dict[str, int]] = {}
    product_stocks_cache: Dict[int, Dict[Tuple[Tuple[int, int], ...], int]] = {}
    updated_products = set()

    processed = 0
    skipped_no_pid = 0
    skipped_no_opt = 0
    success_upserts = 0

    for idx, row in df.iterrows():
        product_id = safe_int(row.get(COL_PRODUCT_ID), None)
        if not product_id:
            skipped_no_pid += 1
            continue

        parsed = parse_options_cell(row.get(COL_OPTIONS_TEXT, ""))
        if not parsed:
            skipped_no_opt += 1
            continue

        opt_name, opt_type, opt_val = parsed
        opt_key = norm_text(opt_name)

        opt_candidates = options_map.get(opt_key)
        if not opt_candidates:
            print(f"⚠️ Brak opcji w Shoperze dla '{opt_name}'. idx={idx}")
            skipped_no_opt += 1
            continue

        forced_id = FORCED_OPTION_ID_BY_NAME.get(opt_key)
        chosen = None

        if forced_id:
            for c in opt_candidates:
                cid = safe_int(c.get("option_id") or c.get("id"), None)
                if cid == forced_id:
                    chosen = c
                    break
            if chosen is None:
                print(f"⚠️ FORCED option_id={forced_id} dla '{opt_name}', ale nie ma go w kandydatach. idx={idx}")

        if chosen is None:
            chosen = opt_candidates[0]
            for c in opt_candidates:
                if isinstance(c.get("type"), str) and norm_text(c["type"]) == norm_text(opt_type):
                    chosen = c
                    break

        option_id = safe_int(chosen.get("option_id") or chosen.get("id"), None)
        if not option_id:
            print(f"⚠️ Opcja '{opt_name}' nie ma option_id. idx={idx}")
            skipped_no_opt += 1
            continue

        if DEBUG_MAPPING and idx < 50:
            cand_ids = [safe_int(x.get("option_id") or x.get("id"), None) for x in opt_candidates]
            print(f"[MAP] '{opt_name}' -> option_id={option_id} (kandydaci={cand_ids}, forced={forced_id})")

        if option_id not in values_cache:
            values_cache[option_id] = get_option_values_map(token, option_id)

        value_id = None
        for cand in value_candidates(opt_val):
            value_id = values_cache[option_id].get(norm_text(cand))
            if value_id:
                break

        if not value_id and AUTO_CREATE_OPTION_VALUES:
            ok_create = create_option_value(token, option_id, opt_val)
            if ok_create and not DRY_RUN:
                values_cache[option_id] = get_option_values_map(token, option_id)
                for cand in value_candidates(opt_val):
                    value_id = values_cache[option_id].get(norm_text(cand))
                    if value_id:
                        break

        if not value_id:
            print(f"⚠️ Nie znalazłem value_id dla option_id={option_id} | '{opt_name}'='{opt_val}' (idx={idx})")
            skipped_no_opt += 1
            continue

        options_payload = [{"option_id": int(option_id), "value_id": int(value_id)}]

        stock = safe_int(row.get(COL_STOCK, 0), 0)
        active = DEFAULT_VARIANT_ACTIVE

        if product_id not in product_stocks_cache:
            product_stocks_cache[product_id] = load_product_stocks_map(token, product_id)

        k = options_key(options_payload)
        existing_stock_id = product_stocks_cache[product_id].get(k)

        # Zaktualizowane wywołania: bez `variant_code`, z parametrami ostrzeżenia i dostawy
        if existing_stock_id:
            ok = update_product_stock(token, existing_stock_id, stock, active, DEFAULT_WARNLEVEL, delivery_id_24h)
        else:
            ok = insert_product_stock(token, product_id, stock, options_payload, active, DEFAULT_WARNLEVEL, delivery_id_24h)

        processed += 1
        if ok:
            success_upserts += 1
            if product_id not in updated_products:
                update_product_warnlevel_and_delivery(token, product_id, DEFAULT_WARNLEVEL, delivery_id_24h)
                updated_products.add(product_id)

    print("\n====== PODSUMOWANIE ======")
    print(f"Przetworzone: {processed}")
    print(f"Udane upserty wariantów: {success_upserts}")
    print(f"Pominięte (brak product_id): {skipped_no_pid}")
    print(f"Pominięte (brak/niezmapowane opcje/wartości): {skipped_no_opt}")
    print(f"Produkty zaktualizowane (warnlevel=1 + 24h): {len(updated_products)}")

if __name__ == "__main__":
    main()