# Walidacja modelu wirowego w URANS (przypadek Godo, overset)

Stan: przygotowane, NIE uruchamiane (czeka na stabilny przypadek overset).

1. `python prepare.py` - buduje tu `GodoOversetRun.java` z trybem `hold_sine` i `run_vv_ctrl.py` z aktualnych plikow w 70_godo_case (oryginalow nie zmienia).
2. `python run_validation.py <SETUP.sim> <rdzenie np. 14,15,16 | gpu>` - kolejka V0..V4 bez nadzoru, wyniki w `runs/<TAG>/`.
3. `python analyze_validation.py` - porownanie z modelem -> `VALIDATION.json`.

Przypadki (plat zamocowany w pionie, theta = trim + A*sin, faza wzgledem fali dopasowana z V0):
V0 staly | V1 +-1,83 deg w fazie | V2 +-3,67 deg w fazie | V3 +-7,5 deg w fazie | V4 +-3,67 deg w przeciwfazie.
"W fazie" = maksimum "nos do gory", gdy woda idzie w gore (ok. cwierc okresu przed grzbietem, wyprzedzenie 5,3 deg).

Model wirowy: `model/` (uvm2d.py, study.py, study_godo.py, validate.py, results_godo.json).
