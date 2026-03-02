import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests


def normalize_shop_url(shop_url: str) -> str:
    shop_url = shop_url.strip().rstrip("/")
    return f"{shop_url}/webapi/rest"


def get_shoper_token(api_base: str, client_id: str, client_secret: str,
                     username: Optional[str] = None, password: Optional[str] = None,
                     timeout: int = 30) -> Optional[str]:
    url = f"{api_base}/auth"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret
    }
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=timeout)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token", None)
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania tokenu: {e}", file=sys.stderr)
        return None


def make_session(access_token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    return s


def sniff_dialect(path: Path) -> csv.Dialect:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
    except csv.Error:
        return csv.get_dialect("excel")


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str], csv.Dialect]:
    dialect = sniff_dialect(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError(f"Brak nagłówków w pliku: {path}")
        rows = list(reader)
        fieldnames = list(reader.fieldnames)
    return rows, fieldnames, dialect


def write_csv_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str], dialect: csv.Dialect) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, dialect=dialect)
        writer.writeheader()
        writer.writerows(rows)


def extract_list_payload(data):
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        items = data.get("list") or data.get("data") or data.get("items") or []
        pages = data.get("pages")
        return items, pages
    return [], None


def product_id_from_obj(p: Dict) -> Optional[int]:
    for key in ("product_id", "id"):
        v = p.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return None


def product_code_from_obj(p: Dict) -> Optional[str]:
    for key in ("code", "product_code", "sku"):
        v = p.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def fetch_products_by_filters(session, api_base, codes, limit: int = 1, timeout: int = 30, verbose: bool = True):
    """
    Pobiera product_id tylko dla podanych kodów, robiąc zapytania po 1 kodzie.
    Próbuje filtrować po stock.code (SKU) i po code.
    Używa prostego formatu filters: {"field":"value"} (bez operatorów in/eq).
    """
    url = f"{api_base}/products"
    limit = min(max(1, limit), 50)

    code_to_id = {}

    # Najczęściej kody wariantów/SKU siedzą w stock.code. :contentReference[oaicite:1]{index=1}
    candidate_fields = ["stock.code", "code"]

    for code in codes:
        found = False

        for field in candidate_fields:
            filters_obj = {field: code}
            params = {
                "limit": limit,
                "page": 1,
                "filters": json.dumps(filters_obj, ensure_ascii=False),
            }

            r = session.get(url, params=params, timeout=timeout)

            # Shoper czasem oddaje 404 przy nieobsługiwanym filtrze / brakach – traktujemy jako "nie znaleziono"
            if r.status_code == 404:
                continue

            r.raise_for_status()
            items, _ = extract_list_payload(r.json())

            if isinstance(items, list) and items:
                for p in items:
                    if not isinstance(p, dict):
                        continue
                    pid = product_id_from_obj(p)
                    pcode = product_code_from_obj(p) or code
                    if pid is not None:
                        code_to_id[pcode] = pid
                        found = True
                        break

            if found:
                break

        if verbose and not found:
            sys.stderr.write(f"[WARN] Nie znaleziono produktu dla kodu: {code}\n")

    return code_to_id


def add_product_ids(rows: List[Dict[str, str]], code_col: str, out_col: str, code_to_id: Dict[str, int]) -> Tuple[int, int]:
    ok = 0
    missing = 0
    for row in rows:
        code = (row.get(code_col) or "").strip()
        pid = code_to_id.get(code) if code else None
        if pid is None:
            row[out_col] = ""
            missing += 1
        else:
            row[out_col] = str(pid)
            ok += 1
    return ok, missing


def main():
    ap = argparse.ArgumentParser(description="Dopisuje product_id z Shopera do CSV po product_code.")
    ap.add_argument("--shop", required=True, help="Adres sklepu, np. https://fazikids.pl")
    ap.add_argument("--token", default=None, help="(Opcjonalnie) gotowy access_token")
    ap.add_argument("--client-id", default=None)
    ap.add_argument("--client-secret", default=None)
    ap.add_argument("--username", default=None)
    ap.add_argument("--password", default=None)

    ap.add_argument("--variants", required=True)
    ap.add_argument("--base", default=None)
    ap.add_argument("--code-col", default="product_code")
    ap.add_argument("--out-col", default="product_id")

    # NOWE: skąd brać listę kodów do mapowania
    ap.add_argument("--codes-source", choices=["variants", "base", "both"], default="both",
                    help="Z jakiego pliku brać kody do mapowania (domyślnie: both)")

    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    api_base = normalize_shop_url(args.shop)
    verbose = not args.quiet

    token = args.token
    if not token:
        if not args.client_id or not args.client_secret:
            print("Brak --token oraz brak kompletu --client-id/--client-secret.", file=sys.stderr)
            sys.exit(2)
        token = get_shoper_token(api_base, args.client_id, args.client_secret, args.username, args.password)
        if not token:
            print("Nie udało się pobrać access_token.", file=sys.stderr)
            sys.exit(3)

    session = make_session(token)

    variants_path = Path(args.variants)
    v_rows, v_fields, v_dialect = read_csv_rows(variants_path)

    base_rows = base_fields = base_dialect = None
    base_path = None
    if args.base:
        base_path = Path(args.base)
        base_rows, base_fields, base_dialect = read_csv_rows(base_path)

    # zbuduj potrzebne kody wg --codes-source
    needed_codes: Set[str] = set()

    if args.codes_source in ("variants", "both"):
        for r in v_rows:
            c = (r.get(args.code_col) or "").strip()
            if c:
                needed_codes.add(c)

    if args.codes_source in ("base", "both"):
        if base_rows is None:
            print("Ustawiono --codes-source base/both, ale nie podano --base.", file=sys.stderr)
            sys.exit(4)
        for r in base_rows:
            c = (r.get(args.code_col) or "").strip()
            if c:
                needed_codes.add(c)

    if verbose:
        sys.stderr.write(f"[INFO] Unikalne kody do zmapowania: {len(needed_codes)}\n")

    # NAJWAŻNIEJSZE: pobierz tylko to co trzeba przez filters (bez skanowania setek stron)
    code_list = sorted(needed_codes)
    code_to_id = fetch_products_by_filters(session, api_base, code_list, verbose=verbose)

    # dopisz product_id do wariantów
    if args.out_col not in v_fields:
        v_fields.append(args.out_col)
    add_product_ids(v_rows, args.code_col, args.out_col, code_to_id)

    out_variants = variants_path.with_name(variants_path.stem + "_z_id.csv")
    write_csv_rows(out_variants, v_rows, v_fields, v_dialect)

    if verbose:
        sys.stderr.write(f"[INFO] Zapisano: {out_variants}\n")

    # opcjonalnie dopisz też do base
    if base_rows is not None:
        if args.out_col not in base_fields:
            base_fields.append(args.out_col)
        add_product_ids(base_rows, args.code_col, args.out_col, code_to_id)
        out_base = base_path.with_name(base_path.stem + "_z_id.csv")
        write_csv_rows(out_base, base_rows, base_fields, base_dialect)
        if verbose:
            sys.stderr.write(f"[INFO] Zapisano: {out_base}\n")


if __name__ == "__main__":
    main()
