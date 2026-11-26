# faltinsen_model – Krok 2 (zlecenie C), 13.11.2026

Model płata Godø w fali według Faltinsena (2005), rozdz. 6. Bez dopasowania do przebiegów URANS w fali.
Opis, równania i tabele: dokument w projekcie „Krok 2: model Faltinsena”.

| Plik | Co robi |
|---|---|
| `faltinsen_eqs.py` | wzory zamknięte z książki, każdy z numerem równania i stroną |
| `faltinsen_plant.py` | model (`FaltinsenPlant`); interfejs jak `vortex_plant.Plant` (`step`, `heave_update` do nadpisania przez zawieszenie) |
| `uvm2d.py` | kopia solvera wirowego (bez zmian) |
| `verify_theory.py` → `VERIFY_THEORY.json` | solver vs wzory (6.187) i (6.144) |
| `validate_urans.py` → `VALIDATION.json`, `validate.log` | pętla zamknięta i odtworzenie ruchu vs URANS (PID1, PID2, PID3, TD3); zapis po każdym przypadku, ponowne uruchomienie pomija gotowe (`--force` liczy od nowa) |
| `diagnose_channels.py` → `DIAGNOSE_*.json` | rozkład siły nośnej na falę / kąt / nurzanie (tylko diagnoza) |
| `slope_from_calm.py` → `SLOPE_CALM.json` | nachylenie CL(α) z URANS w wodzie spokojnej |
| `fit_polar.py` → `POLAR_FIT.json` | brakujący opór z URANS: identyfikacja na BASE2/PRBS1/SINE_A2, sprawdzenie na PID1/2/3 i TD3 |
| `nwar_check.py`, `nwar_plot.py` → `NWAR_CHECK.json`, `NWAR_FIT.json`, `NWAR_CHECK.png` | 14 przypadków NWAR (płat nieruchomy) w modelu B vs URANS; `NWAR_mech.csv` = kopia tabeli z raportu NWAR |
| `suspension_plant.py` (`TwoMassPlant`, `Suspension`, `calm_reference`) | model dwumasowy płat + kadłub z elementem F = f(ugięcie, prędkość, t); opis interfejsu: dokument Kroku 2, pkt 7 |
| `test_suspension.py` → `TEST_SUSPENSION.json` | testy: sztywne = model B, twarda sprężyna, woda spokojna 100/90 %, fala nieregularna |
| `review_checks.py` → `REVIEW_CHECKS.json` | odpowiedź na recenzję: test na TD3_C338, reszta oporu a ruch |
| `plot_validation.py` → `VALIDATION.png` | rysunek |
| `policy_TD3_GODO.json` | kopia polityki TD3 (do pętli zamkniętej) |

Uruchomienie: `.venv\Scripts\python validate_urans.py` (1 rdzeń, ok. 1 min). Potrzebne: numpy, scipy, matplotlib.
Wyniki w tym folderze policzono 13.11 w chmurze (nie na laptopie); czyta tylko `30_URANS_STAR\overset_runs\OVS_*\history.csv` i `run.properties`.
