# Źródła, pobieranie i odczyt danych

## Skąd pochodzą identyfikatory i pliki

Punktem wyjścia jest [opis zadania](../references/AminorsMSA_Main.docx).
Dokument znajduje się w udostępnionym przez Baulina
[folderze AminorsMSA](https://drive.google.com/drive/folders/1ZFsVgR5ueOf8TyxznjYAWOPkJFGbAkzK),
a trzy wejścia są podlinkowane z jego treści:

- [Tabela przydziałów rodzin do uczestników](https://drive.google.com/file/d/1ZhCRWFckRPst--E7Lul3MupgxLOpWuyZ/view) → `data/config/rfam-family-student.tsv`.
- [Katalog Rfam–PDB](https://drive.google.com/file/d/1NyTtZhizrozU9K6jEFwFu6ZuujoVLGd3/view) → `data/rfam/raw/Rfam.pdb`.
- [Gotowe raporty DSSR](https://drive.google.com/file/d/1749UkWDHi_kVs1KBe6oqGl2TVycXV5eu/view) → `data/dssr/raw/dssr_out_261003.zip`.

Najpierw odczytujemy katalogi, w celu zrobienia odpowiednich manifestów:
- [manifests/families.py](../scripts/download/manifests/families.py) przepisuje przydziały do `data/config/families.csv`.
- [manifests/planning.py](../scripts/download/manifests/planning.py) czyta z niego identyfikatory `RFxxxxx`. Następnie przegląda wiersze `Rfam.pdb`: pierwsza kolumna wskazuje rodzinę, druga PDB, trzecia
łańcuch. Wybiera wiersze należące do wybranych rodzin i usuwa powtórzenia
**identyfikatorów PDB**, żeby wspólnej struktury nie pobierać wielokrotnie.
Oryginalne powiązania z łańcuchami pozostają w katalogu `Rfam.pdb`.


Dla każdego identyfikatora skrypt tworzy poniższe adresy. Przykłady można
otworzyć samodzielnie; URL-e są też jawnie zapisane w kodzie downloadera.

| Plik | Przykładowy adres źródłowy | Lokalna ścieżka |
| --- | --- | --- |
| SEED MSA, w tym adnotacje kolumn `SS_cons`/`RF`, jeśli występują | [Rfam Stockholm](https://rfam.org/family/RF02683/alignment/stockholm?gzip=1) | `data/rfam/raw/RF02683/seed.sto.gz` |
| Model kowariancyjny Infernal | [Rfam CM](https://rfam.org/family/RF02683/cm) | `data/rfam/raw/RF02683/model.cm` |
| Opis i metadane rodziny | [Rfam JSON](https://rfam.org/family/RF02683?content-type=application/json) | `data/rfam/raw/RF02683/family.json` |
| Pełna struktura mmCIF | [RCSB mmCIF](https://files.rcsb.org/download/4rum.cif.gz) | `data/pdb/raw/4rum.cif.gz` |

Sposób dostępu opisują [Rfam API](https://docs.rfam.org/en/latest/api.html)
i [RCSB file downloads](https://www.rcsb.org/docs/programmatic-access/file-download-services).
Pobieramy **SEED wybranych rodzin**, nie wszystkie sekwencje FULL ani całą bazę PDB.
DSSR jest dostarczonym archiwum wyników; downloader go nie wylicza ze struktur.

## Jak pobrać ponownie

Z katalogu głównego projektu:

```bash
uv run python -m assets.scripts.download
```

Komenda przywraca materiały według `data/config/sources.csv`, tworzy
`data/config/families.csv`, jeśli go brakuje, pobiera dane z Rfam/RCSB. Istniejący manifest rodzin zachowuje; `--refresh-manifest` odbudowuje go
z przydziałów. Podsumowania pobierania wypisuje w terminalu.

`sources.csv` zawiera nazwę materiału, URL, docelową ścieżkę i SHA-256.
Dla dodatkowych plików z folderu PDF/DOCX trafiają do `assets/references`,
a pozostałe do `assets/materials`, z zachowaniem podkatalogów.
`--refresh-sources` ponownie odczytuje zawartość folderu. Domyślnie korzystamy
z zachowanego manifestu; nie potrzebujemy `tmp` ani nowego mirroru danych.

Folder i podlinkowane wejścia wymagają dostępu do konta, któremu je udostępniono.
Na nowej maszynie można przekazać `gdown` cookies tego konta w formacie Netscape
(plik poza repozytorium) albo zaimportować pobrane materiały lokalnie:

```bash
uv run python -m assets.scripts.download --drive-cookies /path/to/google.cookies.txt
uv run python -m assets.scripts.download --source-dir /path/to/materials
```

Anonimowe pobieranie tych materiałów nie jest dostępne; samo połączenie konta
Drive w aplikacji nie loguje lokalnego skryptu. Działanie transferu z cookies
zależy od dostępu konta i zasad Google; lokalny import jest niezależną drogą.

### Cookies: szybkie przygotowanie

Plik Netscape zawiera cookies sesji zalogowanego konta. `gdown` wysyła je przy
żądaniach do Google i może zapisywać ich aktualizacje w tym samym pliku.
To nie konfiguracja projektu: **nie commituj go, nie udostępniaj i nie umieszczaj
w katalogu materiałów do importu**. Eksport obejmuje sesję `google.com`, nie
tylko uprawnienie do jednego folderu; traktuj plik jak hasło.

1. W Firefox zaloguj się na konto, które ma dostęp do folderu Baulina, i sprawdź,
   czy możesz otworzyć folder. Użyj domyślnego profilu tej przeglądarki.
2. Na tej samej maszynie uruchom poniższe polecenia. Zainstalowany `gdown 6.4.1`
   eksportuje cookies przeglądarki bez dodatku; `--json` tylko sprawdza listę
   folderu, wynik odrzucamy — nie pobiera całego ZIP.

```bash
mkdir -p "$HOME/.config/aminor-msa"
chmod 700 "$HOME/.config/aminor-msa"
uv run gdown --cookies-from-browser firefox \
  --cookies "$HOME/.config/aminor-msa/google.cookies.txt" --json \
  'https://drive.google.com/drive/folders/1ZFsVgR5ueOf8TyxznjYAWOPkJFGbAkzK' > /dev/null
chmod 600 "$HOME/.config/aminor-msa/google.cookies.txt"
uv run python -m assets.scripts.download \
  --drive-cookies "$HOME/.config/aminor-msa/google.cookies.txt"
```

Folder leży poza repo. `.gitignore` dodatkowo ignoruje typowe nazwy cookies;
to nie zabezpiecza pliku o dowolnej innej nazwie przed przypadkowym commitem.
Argument `--drive-cookies` trafia do `gdown`, nie do manifestu materiałów.
Każda osoba tworzy własny plik; nie wymieniamy sesji między członkami zespołu.
Po wygaśnięciu sesji zaloguj się ponownie i powtórz eksport. Przy odmowie dostępu
sprawdź konto/uprawnienia; cookies nie nadają uprawnień, których konto nie ma.
Sam eksport nie gwarantuje pobrania prywatnych zasobów — Google może odmówić;
wtedy użyj opisanego wyżej `--source-dir` z plikami pobranymi w przeglądarce.

Na Linuxie Chrome/Chromium może wymagać dodatkowego `gdown[secretstorage]`;
wybraliśmy Firefox, który go nie potrzebuje. Szczegóły i obsługiwane przeglądarki:
[oficjalna instrukcja gdown](https://github.com/wkentaro/gdown#download-still-fails-even-with-anyone-with-the-link).
Usunięcie pliku usuwa lokalną kopię, a nie sesję Google. Jeśli plik ujawniono,
wyloguj powiązaną sesję i usuń kopie; następnie utwórz nowy eksport.

Wszystkie etapy mają ten sam publiczny punkt wejścia. Kod w `assets/scripts/download/`
jest podzielony na `sources/` (Drive i import), `manifests/` (przydziały i plan),
`core/` (modele żądań, walidacja, transfer i rekordy), `integrity/` (sumy kontrolne)
oraz `cli/` (obsługa argumentów). `__main__.py` uruchamia koordynator.

Można uruchamiać etapy osobno:

```bash
uv run python -m assets.scripts.download --stage sources
uv run python -m assets.scripts.download --stage manifest
uv run python -m assets.scripts.download --stage database --workers 6
uv run python -m assets.scripts.download --dry-run
```

Powtórne uruchomienie pobiera brakujące lub uszkodzone pliki. Rfam i PDB są
pobierane bezpośrednio z baz; gotowy ZIP DSSR przywracamy z materiałów Baulina.

Selekcja i własna konfiguracja:

```bash
uv run python -m assets.scripts.download --stage database --participant olejnik --participant janowiak
uv run python -m assets.scripts.download --stage database --family RF02683
uv run python -m assets.scripts.download --stage database --manifest /path/to/families.tsv
```

CSV/TSV wymaga kolumny `rfam_acc`. Opcjonalne flagi `download_seed_alignment`,
`download_covariance_model`, `download_family_metadata`, `download_pdb_structures`
przyjmują `true`/`false`; pominięte są włączone. Filtr uczestnika korzysta
z dokładnego `participant_id`, np. `olejnik` lub `janowiak` (w przeciwieństwie
do podciągu używanego w filtrze biblioteki). Filtry rodzin i uczestników użyte razem dają przecięcie.

## Jak sprawdzić pobranie

```bash
uv run python -m assets.scripts.download --stage supplied --verify
uv run python -m assets.scripts.download --stage database --verify --workers 4
uv run python -m assets.scripts.download --stage checksums
(cd data && sha256sum --check --quiet downloads/checksums.sha256)
```

Weryfikacja działa offline: SHA-256, rozmiar, pełna dekompresja gzip i CRC,
accession oraz podstawowe warunki formatu. ZIP sprawdzamy przez hash i katalog
archiwum; mmCIF przez blok `data_<PDB>`, bez pełnej walidacji semantycznej.
Rekordy w `data/downloads/records/` obsługują wznowienie i kontrolę integralności;
nie trzeba ich ręcznie czytać. `family.json` jest opisem rodziny z Rfam.
Aktualizowane serwery mogą później zwrócić inną wersję danych pod tym samym URL.

## Odczyt i powiązania

Biblioteka ma parsery Stockholm, metadanych Rfam, nagłówka Infernal, mmCIF
i tekstowych raportów DSSR. `DataStore` ładuje wybrany plik na żądanie,
bez rozpakowania całego ZIP. [Instrukcja readera](reader.md) opisuje
wyniki parserów, klucze relacji, filtrowanie, ograniczony odczyt równoległy
i podgląd w notebooku. Mapowanie reszta → kolumna MSA jest kolejnym etapem.

[Notebooki podstaw biblioteki](../analysis/base_functionality/26_10_06/README.md) pokazują odczyt i kontrolę pobranych plików na małym przykładzie.
