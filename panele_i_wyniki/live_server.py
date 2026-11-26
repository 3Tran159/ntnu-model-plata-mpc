"""Live dashboard for the Godo-control work: STAR runs + surrogate + DRL training.  http://127.0.0.1:8792/
Read-only: it only reads files written by the runs and the training scripts.
"""
import csv, glob, json, os, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109")
RUNS, LEARN = ROOT / "30_runs", ROOT / "50_learning"
HERE = Path(__file__).parent


def tail_csv(path, cols, every=1, maxrows=4000):
    out = {c: [] for c in cols}
    try:
        with open(path, encoding="utf8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return out
    rows = rows[-maxrows * every:][::every]
    for r in rows:
        try:
            vals = [float(r[c]) for c in cols]
        except Exception:
            continue
        for c, v in zip(cols, vals):
            out[c].append(v)
    return out


def star_runs():
    res = []
    for d in sorted(RUNS.iterdir()):
        if not d.is_dir() or not (d / "history.csv").exists():
            continue
        st = {}
        try:
            st = json.loads((d / "FC_STATE.json").read_text())
        except Exception:
            pass
        done = (d / "FC_RESULT.json").exists()
        age = time.time() - (d / "history.csv").stat().st_mtime
        res.append({"name": d.name, "mode": st.get("mode"), "step": st.get("step"), "of": st.get("of"),
                    "done": done, "error": (d / "ERROR.json").exists(), "age_s": round(age),
                    "series": tail_csv(d / "history.csv", ["time_s", "CL", "CD", "cmd_deg"], every=2, maxrows=1900)})
    return res


def training():
    res = []
    for prog in sorted(glob.glob(str(LEARN / "runs" / "*" / "progress.csv"))):
        p = Path(prog)
        snap = {}
        try:
            snap = json.loads((p.parent / "policy_snapshot.json").read_text())
        except Exception:
            pass
        res.append({"name": p.parent.name, "progress": tail_csv(p, ["env_steps", "ep_return", "mean_CL", "mean_CD", "cfd_periods"]),
                    "snapshot": snap})
    return res


def surrogate():
    s = {}
    try:
        s["eval"] = json.loads((LEARN / "surrogate" / "EVAL.json").read_text())
    except Exception:
        return s
    s["rollouts"] = {}
    for f in glob.glob(str(LEARN / "surrogate" / "rollout_*.csv")):
        s["rollouts"][Path(f).stem[8:]] = tail_csv(f, ["t", "delta", "CL", "CL_pred", "CD", "CD_pred", "ens_spread_CL"])
    return s


NIGHT = ROOT / "70_godo_case"


def night():
    r = {"status": None, "variants": []}
    try:
        r["status"] = json.loads((NIGHT / "NIGHT_STATUS.json").read_text())
    except Exception:
        pass
    for d in sorted((NIGHT / "night").glob("*")) if (NIGHT / "night").exists() else []:
        if not d.is_dir():
            continue
        v = {"name": d.name, "done": (d / "FINAL.sim").exists(), "state": None}
        try:
            v["state"] = json.loads((d / "RUN_STATE.json").read_text())
        except Exception:
            pass
        v["series"] = tail_csv(d / "history.csv", ["time_s", "AF_CL", "AF_CD", "GODO_eta_upstream_quarter_lambda", "GODO_yplus_mean",
                                                   "GODO_interfaceCFL", "solver_s"], every=5, maxrows=3000)
        r["variants"].append(v)
    return r


OVR = NIGHT / "overset_runs"
OV_COLS = ["time_s", "solver_s", "theta_deg", "theta_cmd_deg", "z_m", "v_m_s", "P_act_W", "P_drag_W", "AF_CL", "AF_CD",
           "GODO_lift_over_weight", "GODO_M_pivot", "GODO_interfaceCFL", "GODO_eta_upstream_quarter_lambda", "GODO_eta_at_LE",
           "GODO_yplus_mean"]


def overset(run=None):
    runs = sorted([d for d in OVR.iterdir() if d.is_dir() and (d / "history.csv").exists()], key=lambda d: (d / "history.csv").stat().st_mtime) if OVR.exists() else []
    r = {"runs": [d.name for d in runs], "run": None}
    if not runs:
        return r
    d = next((x for x in runs if x.name == run), runs[-1])
    r["run"] = d.name
    for f in ("RUN_STATE.json", "RUN_RESULT.json", "RUN_ERROR.json", "RUN_WARN.json"):
        try:
            r[f[:-5].lower()] = json.loads((d / f).read_text())
        except Exception:
            pass
    try:
        r["session_log"] = (d / "session.log").read_text().splitlines()[-6:]
        r["props"] = dict(l.split("=", 1) for l in (d / "run.properties").read_text().splitlines() if "=" in l)
    except Exception:
        pass
    r["age_s"] = round(time.time() - (d / "history.csv").stat().st_mtime)
    rows = {}
    try:
        with open(d / "history.csv", encoding="utf8") as f:
            for row in csv.DictReader(f):
                try:
                    rows[round(float(row["time_s"]), 6)] = row      # dedupe restarts (last write wins)
                except Exception:
                    pass
    except Exception:
        pass
    keys = sorted(rows)
    every = max(1, len(keys) // 3000)
    s = {c: [] for c in OV_COLS}
    for k in keys[::every]:
        for c in OV_COLS:
            try:
                s[c].append(float(rows[k][c]))
            except Exception:
                s[c].append(None)
    r["series"] = s
    try:
        r["mesh_study"] = json.loads((NIGHT / "MESH_STUDY.json").read_text())["comparisons"]
    except Exception:
        pass
    return r


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        b = body.encode("utf8") if isinstance(body, str) else body
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/overset"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            self._send(json.dumps(overset(q.get("run", [None])[0])), "application/json")
        elif self.path.startswith("/overset"):
            self._send((HERE / "overset.html").read_text(encoding="utf8"), "text/html; charset=utf-8")
        elif self.path.startswith("/api"):
            data = {"time": time.strftime("%H:%M:%S"), "star": star_runs(), "training": training(), "surrogate": surrogate(),
                    "night": night()}
            self._send(json.dumps(data), "application/json")
        else:
            self._send((HERE / "index.html").read_text(encoding="utf8"), "text/html; charset=utf-8")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8792), H).serve_forever()
