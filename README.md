# RNA A-minor

Projekt predykcji interakcji A-minor w RNA z wielosekwencyjnych dopasowań Rfam
(MSA), opcjonalnie ze strukturą drugorzędową. Struktury PDB i raporty DSSR
posłużą do późniejszego przygotowania obserwacji.

Obecny etap: odtwarzalne pobieranie, parsery i leniwy odczyt powiązanych plików.
Mapowanie reszt na MSA, przygotowanie cech, splity i modele pozostają kolejnymi etapami.

Zespół: Max Bohdan Stróżyk, Antonina Olejnik, Aleksander Janowiak.

- [Źródła danych, pobieranie i odczyt plików](assets/docs/acquisition.md)
- [Reader: odczyt danych, klucze, pamięć i trening](assets/docs/reader.md)
- [Architektura biblioteki](assets/docs/library-plan.md)
- [Notebooki: wybór uczestnika, tabele, sekwencje, 3D i workery](assets/analysis/base_functionality/26_10_06/README.md)
- [Artykuły i opis zadania](assets/references/README.md)

Skrypty: `assets/scripts/download/`; konfiguracja: `data/config/`;
dane: `data/<data_type>/raw/`; biblioteka: `src/aminor_msa/`.
Środowiskiem zarządza `uv`; `.python-version` wybiera Python 3.12, a `uv.lock`
ustala wersje zależności. Pobranie materiałów, przygotowanie manifestów,
pobranie danych z baz uruchamia jedna komenda:

```bash
uv run python -m assets.scripts.download
```

PyTorch instalujemy tylko przez wybrany extra:

```bash
uv sync                     # downloads and library, without PyTorch
uv sync --extra cpu          # PyTorch CPU
uv sync --extra cu118        # PyTorch CUDA 11.8
uv sync --extra notebook     # optional tables, widgets, notebook kernel and 3D viewer
```

Extras `cpu` i `cu118` są rozłączne. Oba używają PyTorch 2.7.1, dostępnego
w [oficjalnych wariantach CPU i CUDA 11.8](https://pytorch.org/get-started/previous-versions/#v271).
Uruchamiając później kod modelu przez `uv run`, podaj ten sam `--extra`,
np. `uv run --extra cu118 python ...`.

Odczyt z notebooka lub skryptu:

```python
from aminor_msa import DataStore

store = DataStore("data")  # use an absolute path outside the repository root
family = store.family("RF02683")
alignment = family.alignment  # one MSA, including its column annotations
coordinates = family.structures[0].coordinates  # one linked mmCIF
```
