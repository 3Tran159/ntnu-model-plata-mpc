import json, numpy as np
U = 12.3467; R = json.load(open("DWA_PLATY_TS_rowno.json")); J = json.load(open("DWA_PLATY_TS_julek2.json"))
t = np.array(R["t"]); w = np.array(R["w"]); Te = 1.9368; om = 2 * np.pi / Te
i = np.where((w[:-1] < 0) & (w[1:] >= 0))[0][0]; t0 = t[i] - w[i] * (t[i + 1] - t[i]) / (w[i + 1] - w[i])
eta = -0.733 * np.cos(om * (t - t0))
X = lambda e: 80 + (e + 0.8) / 1.6 * 540; Y = lambda f: 40 + (26 - f) / 50 * 360
def path(F):
    F = np.append(F, F[0]); e = np.append(eta, eta[0])
    return "M" + " L".join(f"{X(a):.1f} {Y(b):.1f}" for a, b in zip(e, F))
out = {"rowno": path(np.array(R["PA"]) / U), "A": path(np.array(J["PA"]) / U), "B": path(np.array(J["PB"]) / U)}
for n, F in (("rowno", np.array(R["PA"]) / U), ("A", np.array(J["PA"]) / U), ("B", np.array(J["PB"]) / U)):
    k = 12; out[n + "_arr"] = [round(X(eta[k]), 1), round(Y(F[k]), 1), round(X(eta[k + 3]), 1), round(Y(F[k + 3]), 1)]
    out[n + "_mean"] = round(float(F.mean()), 2)
out["t0"] = round(float(t0), 3)
print(json.dumps(out))
