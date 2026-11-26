p = 'run_p3d.py'; t = open(p, encoding='utf-8').read()
a = ('    before = star_pids()\n'
     '    res = starrun.launch(sim, cd / "BuildPetla3D.java", cd, cpus=cpus, np_=np_, timeout_s=timeout, gpu=gpu)\n'
     '    time.sleep(5)\n'
     '    for pid in star_pids() - before:                      # tylko procesy powstale w tym uruchomieniu\n'
     '        try: psutil.Process(pid).kill()\n'
     '        except Exception: pass\n')
b = ('    res = starrun.launch(sim, cd / "BuildPetla3D.java", cd, cpus=cpus, np_=np_, timeout_s=timeout, gpu=gpu)\n'
     '    time.sleep(5)\n'
     '    for pid, _n in res.get("bound") or []:                # tylko drzewo procesow TEGO uruchomienia (rownolegle siatka/GPU)\n'
     '        try: psutil.Process(int(pid)).kill()\n'
     '        except Exception: pass\n')
assert t.count(a) == 1
open(p, 'w', encoding='utf-8', newline='').write(t.replace(a, b)); print('ok')
