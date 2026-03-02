# Shoper Variant Import Automation

Automatyzacja procesu przygotowania i wstawiania wariantów produktów do sklepu Shoper na podstawie eksportów CSV oraz integracji z REST API Shopera.

> Projekt powstał do rozwiązania realnego problemu biznesowego: masowego dodawania wariantów produktów do istniejącego katalogu sklepu bez ręcznego klikania w panelu administracyjnym.

---

## Cel projektu

Celem projektu było zautomatyzowanie procesu, który w praktyce składa się z 3 kroków:

1. Import produktów bazowych do Shopera z pliku `towar.csv`.
2. Pobranie identyfikatorów `product_id` nadanych przez Shopera i zmapowanie ich do lokalnych kodów produktów przy użyciu `prod_id_get.py`.
3. Dodanie / aktualizacja wariantów produktów z pliku `war.csv` przy użyciu `upload.py`.

Dzięki temu można szybko przejść od danych CSV do gotowych wariantów w sklepie, bez ręcznego przepisywania identyfikatorów i bez ręcznej konfiguracji każdego wariantu osobno.

---

## Co pokazuje ten projekt

Ten projekt dobrze pokazuje umiejętności praktyczne związane z:

- automatyzacją procesów e-commerce,
- integracją z REST API,
- przetwarzaniem i walidacją danych CSV,
- mapowaniem danych pomiędzy systemami,
- obsługą błędów i scenariuszy częściowo niekompletnych,
- tworzeniem skryptów używanych w realnym procesie biznesowym,
- projektowaniem prostego, powtarzalnego workflow importowego.

---

## Stack technologiczny

- **Python 3**
- **requests** - komunikacja z REST API Shopera
- **pandas** - wczytywanie i przetwarzanie danych CSV w `upload.py`
- **csv / pathlib / argparse** - obsługa plików wejściowych i CLI w `prod_id_get.py`
- **JSON** - budowanie filtrów i payloadów dla API
- **Shoper WebAPI / REST API** - źródło danych o produktach, opcjach, wartościach opcji i stanach magazynowych

---

## Architektura rozwiązania

### 1. Import danych bazowych

Najpierw do Shopera trafia pełny plik produktowy `towar.csv`.

Po imporcie produkty istnieją już w sklepie, ale mają identyfikatory (`product_id`) nadane po stronie Shopera.

### 2. Mapowanie `product_code -> product_id`

Skrypt `prod_id_get.py`:

- wczytuje `war.csv` oraz opcjonalnie `towar.csv`,
- zbiera unikalne `product_code`,
- odpytuje API Shopera filtrowaniem po kodach produktów,
- dopisuje `product_id` do rekordów,
- zapisuje wynik do pliku `war_z_id.csv`.

To jest kluczowy etap, bo kolejne operacje na wariantach wymagają już identyfikatora produktu istniejącego w Shoperze.

### 3. Tworzenie / aktualizacja wariantów

Skrypt `upload.py`:

- pobiera token dostępu do API,
- pobiera opcje i wartości opcji z Shopera,
- mapuje tekst z CSV do odpowiednich `option_id` i `value_id`,
- sprawdza, czy wariant już istnieje,
- wykonuje **insert** albo **update** wpisu w `product-stocks`,
- aktualizuje ustawienia stock / delivery dla produktu bazowego.

---

## Struktura projektu

```text
.
├── prod_id_get.py      # mapowanie product_code -> product_id i generowanie war_z_id.csv
├── upload.py           # tworzenie / aktualizacja wariantów przez API Shopera
├── towar.csv           # plik bazowy produktów importowanych do Shopera
├── war.csv             # plik wariantów powiązanych z produktami bazowymi
└── README.md
```

---

## Format danych wejściowych

### `towar.csv`

Plik bazowy z produktami importowanymi do Shopera. Przykładowo zawiera pola takie jak:

- `product_code`
- `name`
- `price`
- `category`
- `producer`
- `stock`
- `description`

### `war.csv`

Plik wariantów zawierający m.in.:

- `product_code`
- `Nazwa produktu`
- `Kod wariantu`
- `Cena`
- `Stan magazynowy`
- `Opcje (nazwa | typ | wartość)`

Najważniejsze powiązanie między plikami odbywa się przez `product_code`.

---

## Jak działa cały proces

### Krok 1 - import produktów bazowych do Shopera

Najpierw należy zaimportować pełny plik `towar.csv` przez mechanizm importu CSV w panelu Shopera.

Po tym kroku produkty istnieją już w sklepie, ale lokalne pliki nadal nie znają identyfikatorów `product_id` nadanych przez API / system Shopera.

### Krok 2 - wygenerowanie `war_z_id.csv`

Następnie uruchamiany jest skrypt mapujący identyfikatory:

```bash
python prod_id_get.py \
  --shop "$SHOP_URL" \
  --client-id "$SHOPER_CLIENT_ID" \
  --client-secret "$SHOPER_CLIENT_SECRET" \
  --variants "war.csv" \
  --base "towar.csv" \
  --codes-source base
```

Efektem działania jest plik:

```text
war_z_id.csv
```

czyli rozszerzona wersja `war.csv`, wzbogacona o kolumnę `product_id`.

### Krok 3 - wstawienie wariantów do Shopera

Po przygotowaniu danych z identyfikatorami należy uruchomić `upload.py`.

Przed uruchomieniem trzeba ustawić w skrypcie:

- `SHOP_URL`
- `CLIENT_ID`
- `CLIENT_SECRET`
- `CSV_FILE = "war_z_id.csv"`

Przykładowe uruchomienie:

```bash
python upload.py
```

Skrypt:

- mapuje opcje i wartości,
- sprawdza, czy wariant istnieje,
- aktualizuje istniejący wariant lub tworzy nowy,
- ustawia stock, aktywność wariantu i delivery.

---

## Instrukcja uruchomienia lokalnie

### Wymagania

- Python 3.10+
- dostęp do API Shopera
- `client_id` i `client_secret`
- dane produktowe w CSV

### Instalacja zależności

```bash
pip install requests pandas
```

### Uruchomienie

1. Zaimportuj `towar.csv` do Shopera.
2. Wygeneruj `war_z_id.csv` przy pomocy `prod_id_get.py`.
3. Ustaw poprawne dane konfiguracyjne w `upload.py`.
4. Uruchom `upload.py`.
5. Zweryfikuj wynik w panelu Shopera.

---

## Bezpieczeństwo publikacji repozytorium

Do publicznego repozytorium warto wrzucać:

- kod źródłowy,
- zanonimizowane / przykładowe CSV,
- instrukcję działania,
- zrzuty ekranu pokazujące efekt działania.

Nie warto wrzucać:

- prawdziwych `client_id` / `client_secret`,
- access tokenów,
- pełnych produkcyjnych plików CSV z realnym asortymentem,
- danych biznesowych, których nie chcesz upubliczniać.

### Rekomendowane praktyki przed publikacją

- przygotować `sample_towar.csv` i `sample_war.csv` zamiast realnych eksportów,
- zostawić w kodzie tylko placeholdery konfiguracyjne,
- ustawić tryb testowy / `DRY_RUN` jako domyślny tam, gdzie to możliwe,
- dodać plik `.gitignore` dla wyników typu `*_z_id.csv`,
- upewnić się, że w historii Git nie ma starych commitów z sekretami.

### Uwaga o uruchamianiu z CLI

`prod_id_get.py` przyjmuje sekrety jako argumenty CLI. To działa poprawnie, ale surowe wpisywanie sekretów w terminalu może zostawić ślad w historii shella lub być widoczne w liście procesów systemowych.

Dlatego bezpieczniej uruchamiać skrypt z użyciem zmiennych środowiskowych, np.:

```bash
export SHOP_URL="https://twoj-sklep.pl"
export SHOPER_CLIENT_ID="twoj_client_id"
export SHOPER_CLIENT_SECRET="twoj_client_secret"

python prod_id_get.py \
  --shop "$SHOP_URL" \
  --client-id "$SHOPER_CLIENT_ID" \
  --client-secret "$SHOPER_CLIENT_SECRET" \
  --variants "war.csv" \
  --base "towar.csv" \
  --codes-source base
```

---

## Najważniejsze decyzje projektowe

### Dlaczego osobny etap mapowania `product_id`

Po imporcie CSV do Shopera identyfikatory produktów są nadawane po stronie systemu. Żeby bezpiecznie operować na wariantach przez API, trzeba najpierw powiązać lokalny `product_code` z `product_id` istniejącym już w sklepie.

### Dlaczego warianty są obsługiwane przez API, a nie ręcznie

Ręczne dodawanie wariantów w panelu administracyjnym jest czasochłonne i podatne na błędy. API pozwala:

- zautomatyzować pracę,
- zachować spójność danych,
- szybciej przetwarzać większe partie produktów,
- łatwiej powtarzać proces.

### Dlaczego dane są rozdzielone na `towar.csv` i `war.csv`

To odzwierciedla rzeczywisty workflow:

- osobno istnieją produkty bazowe,
- osobno istnieją rekordy wariantowe,
- warianty są zależne od uprzednio zaimportowanych produktów.

---

## Potencjalne usprawnienia

W kolejnej iteracji projektu można byłoby dodać:

- obsługę konfiguracji przez `.env`,
- logger zamiast `print`,
- testy jednostkowe dla parsowania i mapowania,
- walidację schematu CSV przed startem procesu,
- raport końcowy w formacie CSV / JSON,
- pełny tryb `dry-run` dla całego pipeline'u,
- konteneryzację lub prosty CLI wrapper spinający oba kroki w jedno polecenie.

---

## Materiały do pokazania rekruterowi

### Miejsce na screenshoty

Warto dodać 2-4 zrzuty ekranu, żeby README nie było wyłącznie techniczne.

#### Screenshot 1 - efekt końcowy w panelu Shopera

**Co pokazać:** widok produktu z poprawnie dodanymi wariantami.

**Najlepszy podpis pod obrazkiem:**

> Produkt po imporcie i automatycznym utworzeniu wariantów w panelu Shopera.

```md
![Panel Shopera - gotowe warianty](./docs/images/shoper-variants-result.png)
```

#### Screenshot 2 - przykładowy plik wejściowy CSV

**Co pokazać:** krótki, zanonimizowany fragment `war.csv` albo `war_z_id.csv`.

**Podpis:**

> Fragment danych wejściowych używanych do mapowania produktów i budowania wariantów.

```md
![Przykładowe dane CSV](./docs/images/csv-preview.png)
```

#### Screenshot 3 - log działania skryptu

**Co pokazać:** terminal z podsumowaniem przetworzonych rekordów.

**Podpis:**

> Uruchomienie skryptu automatyzującego tworzenie / aktualizację wariantów przez API Shopera.

```md
![Log działania skryptu](./docs/images/script-run.png)
```

#### Screenshot 4 - architektura procesu

**Co pokazać:** prosty diagram: `towar.csv -> prod_id_get.py -> war_z_id.csv -> upload.py -> Shoper`.

**Podpis:**

> Uproszczony przepływ danych w procesie importu wariantów.

```md
![Przepływ procesu](./docs/images/workflow.png)
```

---

## Dlaczego ten projekt nadaje się do portfolio

To nie jest projekt "demo dla demo", tylko rozwiązanie praktycznego problemu biznesowego. Pokazuje umiejętność przełożenia realnego procesu operacyjnego na czytelny i powtarzalny workflow techniczny.

Z perspektywy rekrutera ten projekt pokazuje jednocześnie:

- pracę z danymi,
- integrację z zewnętrznym API,
- automatyzację powtarzalnych zadań,
- rozumienie ograniczeń systemów zewnętrznych,
- myślenie o bezpieczeństwie i jakości publikowanego kodu.

---

## Status projektu

Projekt działa w realnym scenariuszu importu wariantów do Shopera i został przygotowany jako case study do portfolio.

Wersja publiczna repozytorium powinna zawierać wyłącznie dane przykładowe / zanonimizowane.

