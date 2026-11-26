"""jmethods.py - lista metod publicznych klas z pliku .jar (parser class-file, bez JDK). Uzycie: jmethods.py JAR wzorzec_klasy [filtr_metody]"""
import sys, zipfile, struct, re

def parse(b):
    p = 10; n = struct.unpack(">H", b[8:10])[0]; cp = [None] * n; i = 1
    while i < n:
        t = b[p]
        if t == 1:
            l = struct.unpack(">H", b[p+1:p+3])[0]; cp[i] = b[p+3:p+3+l].decode("utf8", "replace"); p += 3 + l
        elif t in (3, 4): p += 5
        elif t in (5, 6): p += 9; i += 1
        elif t == 7: cp[i] = ("C", struct.unpack(">H", b[p+1:p+3])[0]); p += 3
        elif t in (8, 16, 19, 20): p += 3
        elif t in (9, 10, 11, 12, 17, 18): p += 5
        elif t == 15: p += 4
        else: raise ValueError(t)
        i += 1
    acc, this, sup = struct.unpack(">HHH", b[p:p+6]); p += 6
    supn = cp[cp[sup][1]] if sup else ""
    ni = struct.unpack(">H", b[p:p+2])[0]; p += 2 + 2 * ni
    meths = []
    for k in range(2):
        cnt = struct.unpack(">H", b[p:p+2])[0]; p += 2; out = []
        for _ in range(cnt):
            a, nm, de, ac = struct.unpack(">HHHH", b[p:p+8]); p += 8
            for _ in range(ac):
                l = struct.unpack(">I", b[p+2:p+6])[0]; p += 6 + l
            if a & 1: out.append(cp[nm] + cp[de])
        meths = out
    return supn, meths

jar, pat = sys.argv[1], sys.argv[2]; flt = sys.argv[3] if len(sys.argv) > 3 else ""
z = zipfile.ZipFile(jar)
for nmz in z.namelist():
    if nmz.endswith(".class") and re.search(pat, nmz) and ("$" not in nmz or "$" in pat):
        sup, ms = parse(z.read(nmz))
        print("==", nmz, "extends", sup)
        for m in ms:
            if re.search(flt, m): print("   ", m)
