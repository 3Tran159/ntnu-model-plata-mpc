"""replay_td3.py - 13.11 rano, pytanie Julka: jaki opor dalby model wirowy (panele + slad) na fali i ruchu z CFD?
Odtwarza przebieg URANS (zadany ruch z, kat; fala dopasowana do eta przy LE z URANS) w modelu wirowym (mbpo_residual.replay_run),
porownuje opor modelu z URANS. Ostatnie 3 okresy spotkania. Woda spokojna 61,1 W na pasek 0,02 m (oba)."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mbpo_residual as M
from vortex_plant import SPAN, U
for run in sys.argv[1:]:
    M.OVR = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs")
    r = M.replay_run(run)
    A = r["A"]; t = A[:, 0]; w = t >= t[-1] - 3 * 1.9368
    Pm = U * A[w, 11].mean() * SPAN; Pu = U * A[w, 12].mean() * SPAN
    print(f"{run}: fala dopasowana A {r['a']:.3f} m | URANS {Pu:.1f} W ({100*(Pu/61.1-1):+.1f} %) | model wirowy na tym ruchu i fali {Pm:.1f} W ({100*(Pm/61.1-1):+.1f} %) | sila nosna RMS-dev URANS {A[w,10].std():.1f} model {A[w,9].std():.1f} N/m", flush=True)
