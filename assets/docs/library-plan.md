# Biblioteka: odpowiedzialności i przepływ danych

[Reader: odczyt, formaty, klucze i trening](reader.md) opisuje użycie API.
[Notebooki podstaw](../analysis/base_functionality/26_10_06/README.md) pokazują przeglądanie danych.

## Pakiety

```text
src/aminor_msa/
├── io/
│   ├── store.py           # public DataStore facade
│   ├── parsers/           # Stockholm, Rfam, Infernal, mmCIF and DSSR
│   ├── catalog/           # lazy family, PDB and ZIP-name indexes
│   ├── sources/           # lazy family, structure and report handles
│   ├── storage/           # parsed-object LRU and selected ZIP reads
│   └── parallel/          # keys, worker contexts and bounded execution
├── visualization/
│   ├── catalogue/        # participant/family/source tables and browser
│   ├── alignment/        # sequence/annotation tables, HTML view and browser
│   ├── structure/        # residue/atom tables, coordinate view and motif markers
│   ├── dssr/             # annotation tables and residue-link diagnostics
│   ├── _tables.py        # optional pandas construction shared by domain tables
│   └── config.py         # shared palette, dimensions and rendering limits
├── utils/                 # logging, paths, TOML, hashes and atomic records
├── mapping/               # future residue, sequence, CM and MSA correspondences
├── features/              # future representations and availability masks
├── models/{baseline,mlp}/
├── training/
│   ├── datasets/          # future examples, labels, Dataset and collate
│   ├── splitting/         # future group assignments and leakage checks
│   ├── objectives.py
│   └── trainer.py
├── evaluation/
└── inference/
```

Implementację mają `io`, `visualization` i `utils`. Pozostałe pakiety wyznaczają odpowiedzialności przyszłego pipeline'u. Pobieranie jest osobno w `assets/scripts/download/`, z jednym zewnętrznym wejściem `python -m assets.scripts.download` i podziałem na źródła, manifesty, transfer/walidację, integralność oraz wewnętrzne CLI.

## Od źródła do podglądu

`DataStore` tworzy uchwyty `FamilySource`, `StructureSource` i `ReportSource`. Uchwyty delegują parsowanie wybranego pliku do `io.parsers`, odczyt członka ZIP-a i cache do `io.storage`, a powiązania do leniwych katalogów `io.catalog`. Odczyt pojedynczego pliku nie wykonuje automatycznego odczytu plików z nim powiązanych.

`io.parallel` oddziela plan kluczy od wykonania. Workery mają własne sklepy i zasoby; ograniczona kolejka dostarcza wyniki w kolejności planu. Uchwyt archiwum jest ponownie używany w workerze i zamykany z końcem iteratora. Serializacja sklepu pomija obiekty cache, indeksy i czytnik procesu.

`visualization` przyjmuje uchwyty lub już sparsowane obiekty. Tabele katalogowe czytają małe indeksy; tabele struktur i adnotacji operują na danych dostarczonych przez reader. Kontrolka rodziny aktualizuje wybór i tabele katalogowe. Kontrolka MSA zmienia sekwencje i okno już wczytanego wyrównania. Widok 3D tworzy osobną reprezentację wskazanego modelu/łańcucha, zachowując oryginalną strukturę Gemmi.

Każda dziedzina wizualizacji ma osobne pliki `tables.py`, `browser.py` lub `view.py`, stosownie do odpowiedzialności. `structure/motifs.py` odpowiada za znaczniki tripletów, `dssr/validation.py` za tabelaryczną diagnostykę dokładnych kluczy reszt. Publiczna fasada pozostaje w `aminor_msa.visualization`; importy notebooków nie wymagają znajomości podziału wewnętrznego. Parsery są dostępne przez `aminor_msa.io`, klasy formatów przez `io.parsers.<format>`, a odczyt równoległy przez `io.parallel`.

Pandas, ipywidgets i py3Dmol są opcjonalnym extra `notebook`; podstawowy reader ich nie importuje. Podglądy mają wspólny `ViewStyle`. Widok 3D wymaga w przeglądarce JavaScript/WebGL i dostępu do CDN 3Dmol.js; współrzędne pochodzą z lokalnego źródła. Notebooki nie zapisują CSV, provenance ani trwałego cache.

## Granica przygotowania treningu

Obecny reader odczytuje źródła oraz pozwala zweryfikować jawne klucze. Przygotowanie mapowań, cech i splitów jest kolejnym etapem. `training.datasets` będzie konsumować gotowe przykłady, a `training.splitting` utrwalać grupy i sprawdzać leakage. Reader pozostanie warstwą wejściową przygotowania, dzięki czemu parsowanie tekstowych źródeł będzie można wykonać przed epokami treningowymi. [Przewodnik readera](reader.md#pamięć-równoległość-i-trening) opisuje ograniczenia pamięci i sposób użycia workerów.

Testy biblioteki i opcjonalnych podglądów:

```bash
uv run --extra notebook python -m unittest discover -s tests -t .
```

Bez extra `notebook` testy wymagające pandas/ipywidgets są pomijane. Projekt używa unittest, Ruff i hatchling; statyczny type checker nie jest skonfigurowany.
