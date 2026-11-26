p = 'run_p3d.py'; t = open(p, encoding='utf-8').read()
R = [
 ('def save(): st_file.write_text(json.dumps(status, indent=1))',
  'def save():                                             # scal z plikiem (rownolegle procesy siatka / GPU)\n'
  '    cur = json.loads(st_file.read_text()) if st_file.exists() else {}\n'
  '    for c in cases:\n'
  '        if c in status: cur[c] = status[c]\n'
  '    st_file.write_text(json.dumps(cur, indent=1))'),
 ('BODIES.update({"P3D_AR8_jeden": "plat", "P3D_AR4_jeden": "plat"})',
  'MONO = json.loads((HERE / "GEOMETRIA_MONO.json").read_text()) if (HERE / "GEOMETRIA_MONO.json").exists() else {}\n'
  'BODIES.update({"P3D_AR8_jeden": "plat", "P3D_AR4_jeden": "plat"}); BODIES.update({k: "plat" for k in MONO})\n'
  'MESH_CPUS = tuple(int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "22,23").split(","))\n'
  'GPU_HOST = int(sys.argv[4]) if len(sys.argv) > 4 else 23'),
 ('        ex = {"foil_lev": f"0:{gap};0:0", "plate_x": "0:0",',
  '        sg = g.get("przesuniecie_m", 0.0)\n'
  '        ex = {"foil_lev": f"0:{gap};{sg}:0", "plate_x": f"0:{sg}",'),
 ('    elif case in ("P3D_AR8_jeden", "P3D_AR4_jeden"):',
  '    elif case in MONO:\n'
  '        hs, C = MONO[case]["pol_rozp_m"], MONO[case]["cieciwa_m"]; ex = {"foil_lev": "0:0.5"}\n'
  '    elif case in ("P3D_AR8_jeden", "P3D_AR4_jeden"):'),
 ('r = launch(case, "-new", (22, 23), 2, False, 3 * 3600)', 'r = launch(case, "-new", MESH_CPUS, len(MESH_CPUS), False, 3 * 3600)'),
 ('launch(case, sim, (23,), 1, True, 6 * 3600)', 'launch(case, sim, (GPU_HOST,), 1, True, 6 * 3600)'),
]
for a, b in R:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(t); print('ok')
