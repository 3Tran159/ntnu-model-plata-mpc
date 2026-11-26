"""k3_skok07.py - zlecenie D-Z5 (koordynator 14.11 07:45): K3 ze skokiem zawieszenia +-0,7 m (zamiast +-0,5 m, ktory dobijal w S3 i S4).
Przypadki: K3 skyhook; K3 skyhook + odzysk + K0 50 % (sonda 3 m, Wiener ogolny S1-S4 agenta C). Stany morza S3 i S4, 5 realizacji x 20 min.
Wszystko "w modelu" (Faltinsen B, 90 %). Ten sam run() co widmo_s1s4.py / k3_widmo.py; k3.py, k3_widmo.py, k3_wiener.py bez zmian (tylko import).
Wyniki: K3_SKOK07\\wyniki, log K3_SKOK07\\k3_widmo.log, zbiorczo K3_SKOK07\\K3_WIDMO.json. STOP: plik K3_SKOK07\\STOP.
Uzycie: python k3_skok07.py worker K N [rdzen0] | summary"""
import sys
from pathlib import Path
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import k3_wiener as KWW
KW = KWW.KW
S07 = dict(KW.S, stroke=0.7)
CASES = {
    "K3_sky_skok0.7":                       dict(susp=dict(S07, c_rel=0.0, c_sky=1.0)),
    "K3_sky+odzysk+K0_50_wiener3m_skok0.7": dict(susp=dict(S07, c_rel=0.5, c_sky=1.0, k_wave=0.5, probe_d=3.0, preview="wiener")),
}
OUT = HERE / "K3_SKOK07"


def install():
    KW.CASES.clear(); KW.CASES.update(CASES); KW.K3, KW.K0P = KWW.K3W, KWW.K0PW
    KW.OUT = OUT; KW.RES = OUT / "wyniki"; KW.LOG = OUT / "k3_widmo.log"; OUT.mkdir(exist_ok=True)
    KW.W.SEAS = {k: v for k, v in KW.W.SEAS.items() if k in ("S3", "S4")}


if __name__ == "__main__":
    install()
    if sys.argv[1] == "worker": KW.worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else None)
    elif sys.argv[1] == "summary": KW.summary()
