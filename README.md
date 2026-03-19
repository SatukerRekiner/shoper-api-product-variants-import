# Shoper Variant Import Automation

*[🇵🇱 Przejdź do polskiej wersji (Go to Polish version)](#wersja-polska)*

---

Automation of the process of preparing and inserting product variants into the Shoper store based on CSV exports and integration with the Shoper REST API.

> The project was created to solve a real business problem: mass addition of product variants to an existing store catalog without manual clicking in the administration panel.

---

## Project Scope

The project includes:

- importing product data from CSV files,
- mapping products using the Shoper REST API,
- generating an intermediary file with product IDs,
- automatically creating variants based on input data,
- validating input data and handling missing mappings,
- a repeatable import workflow for the e-commerce process.
  
---

## Tech Stack

- **Python 3**
- **requests** - communication with the Shoper REST API
- **pandas** - reading and processing CSV data in `upload.py`
- **csv / pathlib / argparse** - handling input files and CLI in `prod_id_get.py`
- **JSON** - building filters and payloads for the API
- **Shoper WebAPI / REST API** - data source for products, options, option values, and stock levels

---

## Solution Architecture

### 1. Base Data Import

First, the full product file `towar.csv` is uploaded to Shoper.

After the import, the products already exist in the store, but they have identifiers (`product_id`) assigned on the Shoper side.

### 2. Mapping `product_code -> product_id`

The `prod_id_get.py` script:

- reads `war.csv` and optionally `towar.csv`,
- collects unique `product_code` values,
- queries the Shoper API by filtering product codes,
- appends `product_id` to the records,
- saves the result to the `war_z_id.csv` file.

This is a crucial stage because subsequent operations on variants require the identifier of an existing product in Shoper.

### 3. Creating / Updating Variants

The `upload.py` script:

- fetches the API access token,
- fetches options and option values from Shoper,
- maps text from the CSV to the corresponding `option_id` and `value_id`,
- checks if the variant already exists,
- performs an **insert** or **update** of the entry in `product-stocks`,
- updates the stock / delivery settings for the base product.

---

## Project Structure

```text
.
├── prod_id_get.py      # product_code -> product_id mapping and war_z_id.csv generation
├── upload.py           # creating / updating variants via Shoper API
├── towar.csv           # base file of products imported into Shoper
├── war.csv             # variants file linked to base products
└── README.md
```

---

## Input Data Format

### `towar.csv`

Base file with products imported into Shoper. For example, it contains fields such as:

- `product_code`
- `name`
- `price`
- `category`
- `producer`
- `stock`
- `description`

### `war.csv`

Variants file containing, among others:

- `product_code`
- `Product name`
- `Variant code`
- `Price`
- `Stock level`
- `Options (name | type | value)`

The most important link between the files is made through the `product_code`.

---

## How the Entire Process Works

### Step 1 - importing base products into Shoper

First, you need to import the full `towar.csv` file through the CSV import mechanism in the Shoper panel.

After this step, the products already exist in the store, but the local files still do not know the `product_id` identifiers assigned by the Shoper API / system.

### Step 2 - generating `war_z_id.csv`

Next, the script mapping the identifiers is run:

```bash
python prod_id_get.py \
  --shop "$SHOP_URL" \
  --client-id "$SHOPER_CLIENT_ID" \
  --client-secret "$SHOPER_CLIENT_SECRET" \
  --variants "war.csv" \
  --base "towar.csv" \
  --codes-source base
```

The result of the operation is the file:

```text
war_z_id.csv
```

which is an extended version of `war.csv`, enriched with the `product_id` column.

### Step 3 - inserting variants into Shoper

After preparing the data with identifiers, you need to run `upload.py`.

Before running, you must set in the script:

- `SHOP_URL`
- `CLIENT_ID`
- `CLIENT_SECRET`
- `CSV_FILE = "war_z_id.csv"`

Example run:

```bash
python upload.py
```

The script:

- maps options and values,
- checks if the variant exists,
- updates an existing variant or creates a new one,
- sets stock, variant status (activity), and delivery.

---

## Local Setup Instructions

### Requirements

- Python 3.10+
- Shoper API access
- `client_id` and `client_secret`
- product data in CSV

### Installing Dependencies

```bash
pip install requests pandas
```

### Execution

1. Import `towar.csv` into Shoper.
2. Generate `war_z_id.csv` using `prod_id_get.py`.
3. Set the correct configuration data in `upload.py`.
4. Run `upload.py`.
5. Verify the result in the Shoper panel.

---

## Final result in the Shoper panel

![Variants after insertion](images/warianty.png)



## Wersja Polska

# Shoper Variant Import Automation

Automatyzacja procesu przygotowania i wstawiania wariantów produktów do sklepu Shoper na podstawie eksportów CSV oraz integracji z REST API Shopera.

> Projekt powstał do rozwiązania realnego problemu biznesowego: masowego dodawania wariantów produktów do istniejącego katalogu sklepu bez ręcznego klikania w panelu administracyjnym.

---

## Zakres projektu

Projekt obejmuje:

- import danych produktowych z plików CSV,
- mapowanie produktów z wykorzystaniem REST API Shopera,
- generowanie pliku pośredniego z identyfikatorami produktów,
- automatyczne tworzenie wariantów na podstawie danych wejściowych,
- walidację danych wejściowych i obsługę brakujących mapowań,
- powtarzalny workflow importowy dla procesu e-commerce.
  
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


## efekt końcowy w panelu Shopera

![Warianty po wstawieniu](images/warianty.png)



