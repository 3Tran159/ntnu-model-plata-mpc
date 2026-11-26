# Buduje lekkie repo projektu przez KOPIOWANIE (niczego nie przenosi ani nie kasuje).
# python zbuduj_repo.py <nazwa_repo>        nazwy: patrz REPOS nizej
# Repo = kod, ustawienia, wyniki (csv/json/png/mp4), dokumenty. Ciezkie pliki -> ARCHIWUM_DANYCH_inwentarz.csv
import shutil, sys, json, csv, re, datetime, os, fnmatch
from pathlib import Path

NT = Path(r"T:\NTNU_GODO_CONTROL_20261109")
WS = NT / "95_WARSZTAT_KOORDYNATOR" / "warsztat"
FC = Path(r"F:\20_DANE_OBLICZEN\NTNU_flap_control_i_siatki_2026-10")
HA = Path(r"H:\10_ARCHIWUM_PROJEKTOW\NTNU_RESEARCH_ARCHIVE")
EP = Path(r"E:\20_DANE_OBLICZEN_PRZELEW")
SL = Path(r"T:\10_PROJEKTY_AKTYWNE\KORAB_POL42_SLAMMING_SPH_20261119")
SLF = Path(r"F:\20_DANE_OBLICZEN\CFD_KORAB_i_praca_inz\POL42_SLAMMING_20261119")
ZA = Path(r"T:\10_PROJEKTY_AKTYWNE\KORAB_PLAT_T_ZANURZENIE_20261116")

# (zrodlo, cel w repo, wykluczenia glob wzgledem zrodla)
REPOS = {
 "ntnu-drl-archiwum": dict(
   dst=r"F:\20_DANE_OBLICZEN\NTNU_REPO\ntnu-drl-archiwum", max_csv_mb=0.3,
   take=[(FC / "flap_control", "flap_control_2026-10", ["checkpoints*"]),
         (FC / "mesh_screening_20261028", "siatka/screening_20261028", []),
         (FC / "geometry_012_20261029", "siatka/geometria_012_20261029", []),
         (FC / "phase2_012_20261029", "siatka/phase2_012_20261029", []),
         (FC / "wave_depth_20261029", "fale/wave_depth_20261029", []),
         (FC / "XFOIL_validation_20261104", "walidacja_XFOIL_20261104", ["MIT_XFOIL*"]),
         (NT / "90_ARCHIWUM", "mini_vof_i_drl_2026-11", []),
         (NT / "40_MODEL_WIROWY_I_STEROWANIE" / "vortex_env" / "runs", "td3_sac_na_modelu_wirowym/runs", []),
         (NT / "40_MODEL_WIROWY_I_STEROWANIE" / "surrogate", "td3_sac_na_modelu_wirowym/surrogate", []),
         (NT / "30_URANS_STAR" / "overset_runs", "urans_polityki_TD3", [], ["OVS_POL_TD3*"]),
         (WS / "20261117_td3_komfort", "td3_komfort_20261117", [])],
   files=[(FC / "Q2D_012_20261029_START_HERE.txt", "siatka/Q2D_012_20261029_START_HERE.txt"),
          (FC / "HF_mesh_v3_25mln_mesh_settings.html", "siatka/HF_mesh_v3_25mln_mesh_settings.html")],
   inv=[FC, NT / "90_ARCHIWUM", HA / "Active_Flaps", HA / "Active Flaps", HA / "2026-11-04_C_cleanout_FINALS_ONLY",
        HA / "2026-11-04_EF_cleanout_FINALS_ONLY"],
   inv_glob={NT / "30_URANS_STAR" / "overset_runs": ["OVS_POL_TD3*"]}),
 "ntnu-model-plata-mpc": dict(
   dst=r"F:\20_DANE_OBLICZEN\NTNU_REPO\ntnu-model-plata-mpc",
   take=[(NT / "00_START", "00_START", ["RESUME_*", "*.przed_*"]),
         (NT / "10_STAR_MAKRA", "star/makra", []),
         (NT / "20_NARZEDZIA", "narzedzia", []),
         (NT / "30_URANS_STAR", "urans_star", ["overset_runs/OVS_POL_TD3*"]),
         (NT / "40_MODEL_WIROWY_I_STEROWANIE", "model", ["vortex_env/runs*", "surrogate*"]),
         (NT / "50_ANALIZY", "analizy", []),
         (NT / "60_PANELE_I_WYNIKI", "panele_i_wyniki", []),
         (WS / "20261114_ablacja_trzy_platy", "warsztat/20261114_ablacja_trzy_platy", []),
         (WS / "20261117_mpc_komfort", "warsztat/20261117_mpc_komfort", [])],
   files=[], inv=[NT / "30_URANS_STAR", NT / "40_MODEL_WIROWY_I_STEROWANIE", NT / "60_PANELE_I_WYNIKI",
                  NT / "01_BRIEF_I_ZRODLA", EP / "NTNU_GODO_CONTROL_20261109_przeniesione", HA / "PITCH_OVERSET_20261110"]),
 "comfort-celling": dict(
   dst=r"F:\20_DANE_OBLICZEN\NTNU_REPO\comfort-celling",
   take=[(WS / "20261117_urans_30s", "bilans_klockow_urans_30s", []),
         (WS / "20261124_autoresearch", "autoresearch_okna_20261124", []),
         (WS / "20261126_dataset_sverre", "dataset_sverre_20261126", [])],
   files=[], inv=[WS / "20261126_dataset_sverre"]),
 "korab-pol42-slamming-fsi": dict(
   dst=r"F:\20_DANE_OBLICZEN\CFD_KORAB_i_praca_inz\korab-pol42-slamming-fsi",
   take=[(SL, "", ["99_DO_UPORZADKOWANIA*", "02_LITERATURA*"])],
   files=[], inv=[SL, SLF]),
 "korab-plat-T-zanurzenie": dict(
   dst=r"F:\20_DANE_OBLICZEN\CFD_KORAB_i_praca_inz\korab-plat-T-zanurzenie",
   take=[(ZA, "", [])], files=[], inv=[ZA]),
}

LIGHT = {".py", ".java", ".js", ".cjs", ".html", ".css", ".json", ".jsonl", ".csv", ".tsv", ".md", ".txt", ".ps1",
         ".vbs", ".bat", ".cmd", ".svg", ".png", ".pdf", ".docx", ".properties", ".ctrl", ".mp4", ".gif", ".xlsx",
         ".m", ".lean", ".yaml", ".yml", ".toml", ".ipynb", ".bdf", ".f06", ".log", ".out", ".err", ".dat"}
HEAVY = {".sim", ".simh", ".sim~", ".zip", ".cgns", ".mat", ".npz", ".npy", ".h5", ".op2", ".xdb", ".pt", ".pth",
         ".ckpt", ".stl", ".step", ".stp", ".x_t", ".prt", ".msi", ".gz", ".7z", ".nas", ".csv"}
MAXB = 5 * 2**20          # pojedynczy lekki plik
MAXB_MEDIA = 25 * 2**20   # mp4/gif
MAXB_LOG = 256 * 2**10    # logi: tylko male
MAXB_CSV = MAXB
MAX_PNG_DIR = 40          # katalog z wiecej png = klatki animacji -> nie do repo
SKIP_DIRS = {"__pycache__", ".mplconfig", ".venv", "venv", "site-packages", "node_modules", "compiled", ".git",
             "profile", "qa_browser_profile", "_backup", "backups", "render", "frames", "klatki"}
SKIP_DIR_RE = re.compile(r"(_qa_|_qa$|^qa_|_cache$|snapshots|deps|dependencies|site.packages|^lib$|^Lib$|browser_profile|^render_|^frames|^klatki|^backup|_backup$)", re.I)
SKIP_NAME = re.compile(r"(^residual_|hash_cache\.json|\.stale\.|_before_|\.przed_|\.lock$|AGENTS\.md|\.pyc$|\.class$)", re.I)
SECRET_RE = re.compile(r"(podkey|pod_key|POD[_ ]?KEY|licen[cs]e[_ ]?key|api[_-]?key|token|password|haslo)\s*[:=]", re.I)

def excluded(rel, excl):
    s = rel.as_posix()
    return any(fnmatch.fnmatch(s, p) or fnmatch.fnmatch(s.split("/")[0], p) for p in excl)

def light_ok(f, s):
    e = f.suffix.lower()
    if SKIP_NAME.search(f.name) or e not in LIGHT or s == 0:
        return False
    if e in {".log", ".out", ".err"}:
        return s <= MAXB_LOG
    if e in {".csv", ".tsv", ".dat"}:
        return s <= MAXB_CSV
    if e in {".mp4", ".gif"}:
        return s <= MAXB_MEDIA
    return s <= MAXB

def build(name):
    global MAXB_CSV
    cfg = REPOS[name]; DST = Path(cfg["dst"]); copied, frames, secrets = [], [], []
    MAXB_CSV = int(cfg.get("max_csv_mb", 5) * 2**20)
    def cp(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append([dst.relative_to(DST).as_posix(), str(src), src.stat().st_size])
    for t in cfg["take"]:
        src, rdst, excl = t[0], t[1], t[2]; incl = t[3] if len(t) > 3 else None
        if not src.exists():
            print("BRAK", src); continue
        for dp, dn, fn in os.walk(src):
            dpp = Path(dp); rel_d = dpp.relative_to(src)
            dn[:] = [d for d in dn if d not in SKIP_DIRS and not SKIP_DIR_RE.search(d)
                     and not os.path.islink(dpp / d)
                     and os.path.realpath(dpp / d).lower() == os.path.abspath(dpp / d).lower()
                     and not excluded(rel_d / d, excl)
                     and (incl is None or rel_d.parts or any(fnmatch.fnmatch(d, p) for p in incl))]
            if incl is not None and not rel_d.parts:
                fn = []
            npng = sum(1 for f in fn if f.lower().endswith(".png"))
            for f in fn:
                fp = dpp / f
                if excluded(rel_d / f, excl):
                    continue
                try: s = fp.stat().st_size
                except OSError: continue
                if f.lower().endswith(".png") and npng > MAX_PNG_DIR:
                    frames.append(str(dpp)); continue
                if light_ok(fp, s):
                    cp(fp, DST / rdst / rel_d / f)
    for src, rdst in cfg["files"]:
        if src.exists(): cp(src, DST / rdst)
    # inwentarz ciezkich danych
    inv = []
    roots = [(r, None) for r in cfg["inv"]] + [(r, g) for r, g in cfg.get("inv_glob", {}).items()]
    for r, g in roots:
        if not r.exists(): continue
        for dp, dn, fn in os.walk(r):
            dpp = Path(dp)
            dn[:] = [d for d in dn if d not in {".venv", "__pycache__", ".git"} and not os.path.islink(dpp / d)
                     and os.path.realpath(dpp / d).lower() == os.path.abspath(dpp / d).lower()]
            if g and dpp == r:
                dn[:] = [d for d in dn if any(fnmatch.fnmatch(d, p) for p in g)]; continue
            for f in fn:
                fp = dpp / f
                try: st = fp.stat()
                except OSError: continue
                if (fp.suffix.lower() in HEAVY and st.st_size > MAXB) or st.st_size > MAXB_MEDIA:
                    rel = fp.relative_to(r).parts
                    inv.append([str(r), rel[0] if len(rel) > 1 else "", fp.suffix.lower(), str(fp),
                                round(st.st_size / 2**30, 4), datetime.date.fromtimestamp(st.st_mtime).isoformat()])
    inv.sort(key=lambda x: -x[4])
    (DST / "skrypty").mkdir(parents=True, exist_ok=True)
    with open(DST / "ARCHIWUM_DANYCH_inwentarz.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["korzen", "przypadek", "typ", "plik", "GB", "data"]); w.writerows(inv)
    with open(DST / "skrypty" / "pochodzenie_plikow.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["w_repo", "zrodlo", "bajty"]); w.writerows(sorted(copied))
    shutil.copy2(__file__, DST / "skrypty" / "zbuduj_repo.py")
    # kontrola sekretow w skopiowanych plikach tekstowych
    for rel, _, _ in copied:
        p = DST / rel
        if p.suffix.lower() in {".py", ".java", ".ps1", ".bat", ".cmd", ".txt", ".md", ".json", ".properties", ".ctrl", ".log", ".out", ".err"}:
            try: t = p.read_text(encoding="utf-8", errors="ignore")
            except OSError: continue
            for m in SECRET_RE.finditer(t):
                secrets.append(f"{rel}: {t[max(0, m.start()-20):m.end()+30]!r}")
    tot = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file() and ".git" not in f.parts)
    big = sorted(((f.stat().st_size, f) for f in DST.rglob("*") if f.is_file() and ".git" not in f.parts), reverse=True)[:5]
    print(json.dumps({"repo": str(DST), "MB": round(tot / 2**20, 1), "plikow": len(copied),
                      "katalogi_klatek": len(set(frames)), "ciezkich": len(inv),
                      "ciezkie_GB": round(sum(r[4] for r in inv), 1), "sekrety?": secrets[:15],
                      "najwieksze": [f"{s/2**20:.1f} MB {p.relative_to(DST)}" for s, p in big]}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    for n in (sys.argv[1:] or REPOS):
        build(n)

