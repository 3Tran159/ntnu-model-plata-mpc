"""GodoControl.java: make the flap kinematics geometry-parametric so the same native controller runs on the Mini case
(c = 1.19 m, hinge (0.952, 0.02128)) and on the Godø case (c = 0.312 m, hinge scaled by 0.312/1.19).
New control.properties keys (defaults = Mini): hinge_x_m, hinge_y_m, geom_scale (blend lengths x scale),
expected_dt_s (dt check), cfl_report, initialize_if_t0 (true -> initialise the solution when t = 0, Godø setup .sim).
"""
p = r"T:\NTNU_GODO_CONTROL_20261109\10_macros\GodoControl.java"
t = open(p, encoding="utf-8").read()
assert "geom_scale" not in t


def rep(old, new, n=1):
    global t
    assert t.count(old) >= n, "missing: " + old[:70]
    t = t.replace(old, new) if n == 0 else t.replace(old, new, n)


rep(" final double HX=.952, HY=.02128173276777;", " double HX=.952, HY=.02128173276777, GS=1.0;   // set from control.properties in execute()")
rep('String blend=smooth(x+"/<.035 m>");', 'String blend=smooth(x+"/<"+(.035*GS)+" m>");')
rep('smooth("(<1.40 m>-"+radius+")/<1.10 m>")', 'smooth("(<"+(1.40*GS)+" m>-"+radius+")/<"+(1.10*GS)+" m>")')
rep('angle.setDefinition("("+xs+">.20) ?', 'angle.setDefinition("("+xs+">"+(.20*GS)+") ?')
rep('||Math.abs(dt-5e-4)>1e-12)', '||Math.abs(dt-d("expected_dt_s",5e-4))>1e-12)')
rep('   reg=s.getRegionManager().getRegion("MINI_water_air");',
    '   HX=d("hinge_x_m",HX);HY=d("hinge_y_m",HY);GS=d("geom_scale",1.0);\n'
    '   if(Boolean.parseBoolean(cfg.getProperty("initialize_if_t0","false"))&&start<1e-12)s.getSolution().initializeSolution();\n'
    '   reg=s.getRegionManager().getRegion("MINI_water_air");')
rep('cfl=rd("NN_interfaceCFL")', 'cfl=rd(str("cfl_report","NN_interfaceCFL"))')
open(p, "w", encoding="utf-8").write(t)
print("geometry-parametric GodoControl patched")
