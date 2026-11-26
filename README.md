# NTNU – model płata (wirowy 2D, Faltinsen) + MPC: opór na fali przy gładkiej jeździe

Projekt NTNU (staż, Trondheim, XI 2026), prowadzący: prof. Sverre Steen. Autor: Julek. Stan: w toku (od 13.11.2026).
Poprzedni etap (DRL) – [`ntnu-drl-archiwum`](https://github.com/3Tran159/ntnu-drl-archiwum); wzór na sufit zysku – [`comfort-celling`](https://github.com/3Tran159/comfort-celling); płat nieruchomy na fali – [`nwar`](https://github.com/3Tran159/nwar).

Pytanie: ile oporu płata można odzyskać z fali, jeśli kabina ma jechać gładko (z̈ RMS ≤ 0,05 g ≈ 0,49 m/s²) – i czy da się to przewidzieć prostym modelem fizycznym zamiast sieci neuronowej?

## Wynik w jednym zdaniu

Adaptacyjne MPC na modelu Faltinsena trafia w limit komfortu także w URANS: **−10,8 % oporu przy z̈ 0,49 m/s²**; siły przy tym samym ruchu model i URANS dają w granicach 3 %, ale z̈ w pętli zamkniętej URANS jest o ok. 40 % większe niż w modelu.

## Co pewne / co niepewne (model B Faltinsena vs URANS, stan 20.11.2026)

| Nr | Ustalenie | Liczby | Status |
|---|---|---|---|
| 1 | MPC (W_A 1,5): opór zgodny, z̈ nie | z̈: model 0,46, URANS 0,64 m/s² | pewne |
| 2 | Składowe siły przy tym samym ruchu (podmuch, obrót, nurzanie) | zgodność ≤ 3 % | pewne |
| 3 | Ruch i z̈ w URANS nie zależą od siatki (GC/H1/GF) | z̈ 0,47–0,51 m/s² | pewne |
| 4 | Adaptacyjne MPC w limicie komfortu (URANS) | −10,8 % przy 0,49 m/s² | pewne |
| 5 | Głębokość prawie nie zmienia oporu samego płata | +0,46 W/m (+0,2 %) | pewne |
| 6 | Płat + wspornik: głębiej = drożej | +21,6 W/m (wspornik 21,1) | pewne |
| 7 | Koszt komfortu od wypadkowej (z̈² + ẍ²) | ok. 9,9 % przy 0,49 m/s² | model |
| 8 | Błąd siatki w oporze | 5–7 % (GC/H1/GF: 53,8/54,8/57,7 W) | niepewne |
| 9 | Opór w spokojnej wodzie URANS dryfuje w czasie | 59,6 → 68,5 W (6–9 s → 12–29 s) | niepewne – porównywać w tym samym oknie |

Źródło: dokument projektu `pewne-niepewne.md` (spis w `docs/DOKUMENTY_PROJEKTU.md`).

## Kolejność prac (kroki)

| Krok | Co | Gdzie w repo |
|---|---|---|
| 0 | Odtworzenie sterowania Godø w URANS: overset, obrót całego płata wokół c/4, swobodne nurzanie, PID baseline | `star/makra/`, `urans_star/overset*` |
| 1 | Model wirowy 2D vs Godø 3D (redukcja 3D → 2D) | `analizy/KROK1_2D_vs_GODO_3D/` |
| 1b | Walidacja modelu wirowego na przebiegach PID z URANS | `urans_star/vortex_validation/` |
| 2 | Model płata wg Faltinsena (Hydrodynamics of High-Speed Marine Vehicles, rozdz. 6) | `model/faltinsen_model/` |
| 3 | Gładka jazda vs opór: zawieszenie (K0–K3, Wiener, pętla 3D), czujnik fali K0, MPC na widmie S1–S4, trzy płaty | `panele_i_wyniki/`, `warsztat/` |
| 3+ | MPC komfortowe i samouczące się (MPCA/MPCF/MPCL) potwierdzane w URANS | `urans_star/overset_runs/OVS_MPC*`, `OVS_CEL_*` |

## Struktura

| Folder | Co |
|---|---|
| `00_START/` | mapa folderu roboczego, plan retencji, backup na Google Drive |
| `star/makra/` | makra Java STAR-CCM+ (GodoOversetRun, sterowanie, raporty) – wszystko edytowalne w GUI |
| `narzedzia/` | uruchamianie STAR (rdzenie, licencja), keep-awake, retencja checkpointów |
| `urans_star/` | studium siatki (`night/`), przypadki bazowe (`overset/`), **przebiegi** (`overset_runs/<przypadek>/`: `run.properties`, `history.csv`, `RUN_RESULT.json`), wspornik (`strut_calm/`), ślad wirowy, walidacja modelu |
| `model/` | model wirowy (`vortex_env/`) i model Faltinsena (`faltinsen_model/`), MPC |
| `analizy/` | analizy URANS, Krok 1, MATLAB |
| `panele_i_wyniki/` | panele HTML i wyniki Kroku 3: `ZAWIESZENIE/`, `CZUJNIK_FALI_K0/`, `MPC_WIDMO/`, `WIDMO_S1S4/` |
| `warsztat/` | ablacja „trzy płaty” (14.11), MPC komfortowe (17.11) |
| `docs/` | spis dokumentów projektu claude.ai (raporty kroków, recenzje, karta stałych) |
| `ARCHIWUM_DANYCH_inwentarz.csv` | ciężkie pliki (.sim, .simh) z pełną ścieżką (567 plików, ok. 107 GB) |

## Nazewnictwo przebiegów URANS (`overset_runs/`)

`OVS_<sterownik>_<wariant>_<obciążenie>`: `PID1/2/3_GODO` – PID-y Godø; `K0_85` – czujnik fali, 85 %; `MPCA/MPCF/MPCL` – MPC adaptacyjne / pełny Faltinsen / samouczące; `CEL_<g>` – MPC z celem przyspieszenia kabiny (000g = równa jazda, 005g = 0,05 g), `S1`, `T4`, `T8` – widmo / okres fali; `LEVEL` – jazda bez oscylacji; `CALM` – woda spokojna (`Z-0.3` = 0,3 m głębiej); `GC/GF/H1` – siatka gruba / gęsta / bazowa; `_90` – płat niesie 90 % z 12,5 t; `_BLAD_*`, `_przerwany` – nieudane (zostawione jako dowód).

## Jak odtworzyć przebieg URANS

1. Plik startowy SETUP danego przypadku – ścieżka w `ARCHIWUM_DANYCH_inwentarz.csv` (kolumna `przypadek`).
2. Parametry: `urans_star/overset_runs/<przypadek>/run.properties`.
3. Uruchomienie: makro `GodoOversetRun.java` (STAR-CCM+ 2606, batch lub GUI); sterownik czytany z pliku (`.ctrl` / polityka).
4. Ocena: skrypty w `analizy/` czytają `history.csv` (usuwać zdublowane chwile po wznowieniu!).

## Wymagania i ograniczenia

STAR-CCM+ 2606 (Power-on-Demand – klucza nie ma w repo), Python 3.12 (numpy, scipy; pełna lista w importach skryptów), 16 rdzeni CPU + GPU 12 GB. Przypadek 2D (pasek 0,02 m), fala czołowa; brak wirów końcowych 3D; opór spokojnej wody w URANS dryfuje – liczyć zawsze w tym samym oknie. Ścieżki bezwzględne do `T:\NTNU_GODO_CONTROL_20261109`.

Odbudowa repo z dysków: `python skrypty/zbuduj_repo.py ntnu-model-plata-mpc`.
