# NTNU – sterowanie Godø · mapa folderu (stan 12.11.2026)

Plik znajdujesz po tym, co chcesz zrobić. Jedna rzecz ma jedno źródło.

| Folder | Co tu jest |
|---|---|
| `00_START` | ta mapa, skrypty wznowienia (`RESUME_after_move3.ps1`), plan recyrkulacji, dziennik migracji |
| `01_BRIEF_I_ZRODLA` | brief Sverre, dane wejściowe |
| `02_LITERATURA` | Godø 2024 (PDF + wyciąg metody), prace o sterowaniu RL, kod MBRL |
| `10_STAR_MAKRA` | makra Java sterowania (GodoControl + kopie zapasowe) |
| `20_NARZEDZIA` | starrun (licencja, przypinanie rdzeni), keep_awake, recyrkulacja, ten skrypt porządku |
| `30_URANS_STAR` | wszystko z STAR-CCM+: `night/` studium siatki, `overset/` przypadki bazowe, `overset_runs/` przebiegi PID w fali i wodzie spokojnej, `vorticity/` ślad, `strut_calm/` wspornik, `vortex_validation/` porównania z modelem |
| `40_MODEL_WIROWY_I_STEROWANIE` | `vortex_env/`: model wirowy, środowisko Godø, TD3/SAC (`runs/`), MPC, zawieszenie, eksport polityk |
| `50_ANALIZY` | skrypty analiz URANS (`urans_pid_summary.py` → `URANS_PID_SUMMARY.json`) |
| `60_PANELE_I_WYNIKI` | panele na żywo i serwer podglądu |
| `70_RAPORTY_SVERRE` | materiały na spotkania |
| `90_ARCHIWUM` | stare przebiegi Mini-VOF (9.11) |
| `99_DO_UPORZADKOWANIA` | luźne logi bez właściciela; przegląd co tydzień |

**Stare nazwy** (`50_learning`, `70_godo_case`, …) istnieją dalej jako ukryte dowiązania. Skrypty z twardymi ścieżkami działają bez zmian.

**Recyrkulacja.** W każdym przebiegu zostaje:
- plik startowy SETUP,
- ostatni END albo FINAL,
- ostatni CP, jeśli przebieg trwa,
- wszystkie wyniki (csv, json, log, png).

Nowe makra same usuwają poprzedni checkpoint. Plan robi `20_NARZEDZIA\retention_plan.py`, który tylko czyta i nic nie kasuje.
