import json, numpy as np
from pathlib import Path
C=0.312
print("stan | W_A | srednie zanurzenie [m] | sigma_R wzgl. ruchu [m] | h_wym = c + 3 sigma | h_wym = c + 4 sigma | min zan. [m]")
for wa,d in (("0.3","viz_act57_wa0.3"),("1","viz_act57_wa1"),("3","viz_act57_wa3")):
    for s in ("S1","S2","S3","S4"):
        f=Path(d)/f"{s}__s0.json"
        if not f.exists(): continue
        j=json.loads(f.read_text()); A=np.array(j["data"]); cols=j["cols"]; t=A[:,0]; sub=A[:,cols.index("sub")]; m=t>30
        sm=sub[m].mean(); sr=sub[m].std()
        print(f"{s} | {wa} | {sm:.2f} | {sr:.3f} | {C+3*sr:.2f} | {C+4*sr:.2f} | {sub[m].min():.2f}")
