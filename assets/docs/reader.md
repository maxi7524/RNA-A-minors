# Reader: odczyt danych, klucze i trening

`DataStore` udostępnia lokalne źródła: wybierasz rodzinę lub PDB, a konkretny plik jest odczytywany dopiero przy użyciu jego właściwości. Dane muszą być wcześniej pobrane według [instrukcji pobierania](acquisition.md). [Notebooki](../analysis/base_functionality/26_10_06/README.md) pokazują te operacje z tabelami i kontrolkami.

## Wybór i odczyt

Przykład działa z katalogu projektu lub jego podkatalogów:

```python
from aminor_msa import DataStore
from aminor_msa.utils.paths import find_project_root

store = DataStore(find_project_root() / "data")
print(store.family_ids(participant="olejnik", rna_type="riboswitch"))
records = store.family_records(participant="olejnik")

family = store.family("RF01734")       # handle only; no source payload is read
alignment = family.alignment            # one complete Stockholm MSA
metadata = family.metadata              # one Rfam JSON response
model = family.covariance_model         # Infernal header, without numerical body
print(metadata.name, len(alignment.sequences), alignment.length)
print(family.mappings)                  # catalogue chain/range records
print([source.pdb_id for source in family.structures])
```

Filtry łączą się przecięciem, bez rozróżniania wielkości liter. `participant` dopasowuje **podciąg** `participant_id`; `rna_type` cały token rozdzielony średnikiem lub całe pole; `entry_type` całe pole. Np. `riboswitch` pasuje do `Cis-reg; riboswitch`. `family_records()` zwraca kopie wierszy manifestu z nazwiskami, opisami i flagami pobierania. Identyfikator uczestnika pochodzi z przydziału, nie z pliku struktury.

| Odczyt | Plik | Co dostajesz |
| --- | --- | --- |
| `family.alignment` | `rfam/raw/RF01734/seed.sto.gz` | `sequences`: ID → wyrównany ciąg; GF/GS/GR/GC w odpowiednich słownikach adnotacji. |
| `family.metadata` | `family.json` w tym samym katalogu | Accession, nazwa, opis; pełna odpowiedź w `payload`. |
| `family.covariance_model` | `model.cm` | Nagłówek CM, `consensus_length`, ścieżka do części numerycznej używanej przez Infernal. |
| `source.coordinates` | `pdb/raw/3vrs.cif.gz` | Natywna struktura Gemmi: wszystkie modele, łańcuchy, reszty, atomy i altlocy. |
| `source.cif_document` | ten sam mmCIF | Pełne kategorie CIF, także numeracja i sekwencje polimerów; osobny odczyt. |
| `source.report("1").read()` | jeden członek `dssr/raw/dssr_out_261003.zip` | Nukleotydy, pary, A-minor, DBN, `complete`, oryginalny `raw_text` i nazwy sekcji. |

Stockholm zachowuje luki `-`/`.`, wielkość liter i powtórzone adnotacje. `SS_cons` i `RF` znajdują się w `alignment.column_annotations`, jeżeli występują w źródle. Kolumny MSA w Pythonie są indeksowane od zera. Wybór sekwencji w `AlignmentBrowser` pokazuje ich istniejące wyrównanie we wspólnym oknie kolumn; nie wylicza nowego dopasowania.

## Klucze i sprawdzanie powiązań

| Obiekt lub relacja | Klucz i źródło |
| --- | --- |
| Uczestnik → rodzina | `participant_id`, `rfam_acc` z `data/config/families.csv`. |
| Rodzina → PDB/łańcuch | `rfam_acc`, `pdb_id`, `chain`, zakresy z `rfam/raw/Rfam.pdb`. Relacja wiele-do-wielu; `family.mappings` zachowuje wszystkie wiersze, `family.structures` deduplikuje PDB. |
| PDB → raport | PDB oraz literalny sufiks `.out…` w nazwie członka ZIP-a. Przy kilku raportach wybierz wariant jawnie. |
| Sekwencja MSA | Dokładny klucz `alignment.sequences`, zachowany z wiersza Stockholm. Sama nazwa sekwencji nie ustanawia relacji do PDB. |
| Reszta we współrzędnych | `(source_model, author_chain, author_number, insertion, residue_name)`. Osobno zachowane są `label_chain` i `label_number`. |
| Zadanie odczytu | `SourceRequest(kind, accession, variant)`; rodzina RF dla MSA/JSON/CM, PDB dla współrzędnych/CIF/DSSR, wariant tylko dla DSSR. |

`Rfam.pdb` daje powiązanie katalogowe i zakresy, ale **nie mapuje reszt na kolumny MSA**. Numer reszty autora, numer label, pozycja CM i kolumna MSA to różne współrzędne. Dla wielu rodzin nie istnieje wspólna numeracja kolumn.

```python
source = store.structure("3vrs")
print([(handle.variant, handle.member) for handle in source.reports])  # ZIP names only
report = source.report("1").read()
coordinates = source.coordinates
print([model.num for model in coordinates.structure])

residue = coordinates.resolve_nucleotide(
    report.nucleotides[0].identifier,
    model_number=1,                     # explicit source mmCIF model number
)
print(residue.chain, residue.number, residue.insertion, residue.name)
print(residue.label_chain, residue.label_number)
```

Wariant `out1`, pole modelu wewnątrz ID DSSR i model 1 mmCIF nie są automatycznie tym samym identyfikatorem. Raporty Baulina powstały z plików pośrednich. Resolver szuka dokładnego klucza autora w podanym modelu; brak daje `KeyError`, niejednoznaczność lub nieobsługiwany kwalifikator ID daje `ValueError`. Pierwsze wyszukanie buduje indeks modelu/łańcucha, kolejne używają słownika. Po edycji identyfikatorów lub topologii Gemmi wywołaj `coordinates.clear_residue_index()`.

`residue_links_table(coordinates, report, model_number=1)` z `aminor_msa.visualization` pokazuje dla każdego nukleotydu status `matched`, `missing` lub `unresolved`. Dopasowany klucz potwierdza obecność reszty, nie zgodność snapshotów źródeł, wyboru atomów ani mapowanie do MSA.

Parser Stockholm sprawdza długości sekwencji i GC/GR; uchwyty rodziny porównują accession MSA/JSON/CM z wybraną rodziną. DSSR sprawdza liczniki obsługiwanych tabel. `report.complete=False` oznacza brak zweryfikowanego podsumowania nukleotydów. Brak raportu lub podsumowania nie tworzy ujemnej etykiety. Typy motywów I/II/X i gwiazdki są zachowane; donor z gwiazdką może być inny niż A.

## Pamięć, równoległość i trening

`DataStore(...)` i tworzenie uchwytu nie otwierają źródeł. Manifest rodzin, katalog Rfam–PDB i nazwy członków ZIP-a są indeksowane na żądanie. ZIP jest dekompresowany po jednym wybranym raporcie, bez ekstrakcji całego archiwum. Wybrany MSA, mmCIF lub tekst raportu po odczycie znajduje się **w całości w RAM**; filtr modelu/łańcucha i limit widoku nie ograniczają rozmiaru odczytanego pliku.

Domyślnie cache jest wyłączony: przypisz odczyt do zmiennej i korzystaj z niej ponownie. `cache_entries=2` zatrzymuje najwyżej dwa obiekty LRU, bez limitu bajtów. `store.clear_cache()` zwalnia referencje cache; Twoje zmienne nadal utrzymują obiekty. `store.load_state()` pokazuje stan indeksów i liczbę obiektów bez kolejnego I/O.

```python
from contextlib import closing
from aminor_msa.io.parallel import iter_requests, iter_loaded, summarize_request

requests = iter_requests(
    store, participant="olejnik", families=("RF01734",),
    kinds=("alignment", "coordinates", "dssr"),
)
with closing(iter_loaded(
    store, requests, workers=2, prefetch=2, backend="thread",
    transform=summarize_request,
)) as results:
    for result in results:
        print(result.request, result.data)  # small counts, not retained raw objects
```

`iter_requests` wybiera i deduplikuje klucze przed odczytem payloadów. `workers` ogranicza liczbę workerów, `prefetch` wysłane zadania; wyniki zachowują kolejność planu. Każdy worker ma własny store bez cache i ponownie używa własnego uchwytu ZIP. `closing` zamyka iterator również po wcześniejszym przerwaniu. RAM obejmuje kolejkę, parsowanie w workerach i obiekty zachowane przez odbiorcę; unikaj `list(iter_loaded(...))` dla całego zbioru.

Dla przygotowania obciążającego CPU dostępny jest `backend="process"` ze spawn. Własny `transform(worker_store, request)` umieść w importowalnym module `.py`; skrypt uruchamiający procesy wymaga `if __name__ == "__main__"`. Odczyt i przygotowanie wykonuj w workerze, zwracając mały wynik lub ścieżkę, żeby ograniczyć kopiowanie dużych obiektów między procesami.

**Docelowy trening — jeszcze niezaimplementowany:**

1. `mapping/`: zweryfikować źródła i uzgodnić reszty struktury, sekwencję oraz kolumny MSA, uwzględniając luki, reszty modyfikowane i brakujące.
2. `training/splitting/`: utrwalić grupy train/validation/test z uwzględnieniem homologii, rodzin i współdzielonych struktur. Przydział studentów nie gwarantuje braku leakage.
3. `features/`: przygotować reprezentacje, etykiety i maski dostępności. Transformacje uczone na danych dopasowywać tylko na train; nieobserwowane kontakty pozostawić jako nieznane.
4. `training/datasets/`: odczytywać gotowe przykłady, np. z shardów tensorów lub tablic memory-mapped, zamiast parsować mmCIF/DSSR w każdej epoce. To pozwoli osobno mierzyć czas przygotowania i przepustowość treningu.

Bieżące notebooki są przeglądarką źródeł: obliczają tabele w pamięci i nie zapisują katalogów wyników. Podział odpowiedzialności modułów opisuje [architektura biblioteki](library-plan.md).
