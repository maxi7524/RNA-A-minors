# Podstawy biblioteki

Z katalogu głównego projektu:

```bash
uv sync --extra notebook
uv run --extra notebook python -m ipykernel install --prefix .venv --name aminor-msa
```

Otwórz notebook w VS Code/Jupyter, wybierz `.venv/bin/python` i wykonaj **Restart Kernel → Run All**. Każdy działa samodzielnie na lokalnych danych. Domyślny przykład: Antonina Olejnik (`participant_id=olejnik`), Fluoride `RF01734`, PDB `3vrs`. Zmień wybór w [settings.toml](settings.toml) albo przy wywołaniu funkcji.

| Notebook | Co możesz sprawdzić |
| --- | --- |
| [1. Katalog i uczestnik](part_0_1_catalogue_selection.ipynb) | Przydziały, filtrowanie po uczestniku i typie RNA, kontrolki wyboru, powiązane PDB i warianty raportów. |
| [2. MSA i sekwencje](part_0_2_alignment_exploration.ipynb) | Odczyt Stockholm/JSON/CM, zgodność accession, długości, luki, GF/GS/GR/GC, wybór sekwencji i okna MSA. |
| [3. Struktura i DSSR](part_0_3_structure_and_dssr.ipynb) | Modele i łańcuchy, atomy/altloc, pełne tabele mmCIF, pary/A-minor/DBN, kontrola kluczy, obracany widok 3D i znaczniki motywu. |
| [4. Pamięć i workery](part_0_4_lazy_parallel_loading.ipynb) | Leniwy odczyt, cache LRU, plan kluczy, ograniczona kolejka, odczyt w wątkach i procesach. |

Po zmianie rodziny w kontrolce wykonaj ponownie komórki odczytu pod nią. Kontrolka nie wczytuje automatycznie dużych MSA ani współrzędnych. Sekwencje i zakres MSA zmieniają się na żywo; widok ma jawne limity wierszy i kolumn. Notebook 3 wybiera PDB, wariant i model przez jawne zmienne, po wyświetleniu dostępnych opcji.

Notebooki wyliczają i wyświetlają tabele w pamięci. Nie zapisują CSV, metadanych wykonania ani katalogów wyników. Biblioteka wczytuje pojedyncze MSA/mmCIF/raporty w całości; liczba workerów i zachowane zmienne nadal wpływają na RAM. To kontrola źródeł i identyfikatorów, bez mapowania struktura → MSA.

Kontrolki wymagają aktywnego kernela i obsługi ipywidgets. Widok 3D dodatkowo wymaga JavaScript/WebGL oraz dostępu przeglądarki do CDN 3Dmol.js; tabele działają niezależnie. Po uruchomieniu komórek dostępne są również zwykłe tabele i statyczny podgląd MSA. Zapisanie uruchomionego `.ipynb` w edytorze może zachować jego outputy.

Wykonanie bez interfejsu graficznego, po rejestracji kernela:

```bash
JUPYTER_PATH="$PWD/.venv/share/jupyter" uv run --extra notebook jupyter execute \
  --kernel_name=aminor-msa assets/analysis/base_functionality/26_10_06/part_0_*.ipynb
```

[Odtworzenie danych](../../../docs/acquisition.md) · [Reader: formaty, klucze i trening](../../../docs/reader.md) · [Architektura](../../../docs/library-plan.md).
