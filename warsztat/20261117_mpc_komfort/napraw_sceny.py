# 17.11: sceny byly puste - ScalarDisplayer dostawal regiony (objetosci); w pasku 3D trzeba przekroju. Dodajemy plaszczyzne z = 0,01 m
# (GODO_scene_plane, natywny PlaneSection widoczny w GUI) i podpinamy ja do displayera, takze w scenach juz zapisanych w .sim.
from pathlib import Path
f = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\makro_mpcf\GodoOversetRun.java")
s = f.read_text(encoding="utf-8")
a1 = "  java.util.Collection<Region> regs=s.getRegionManager().getRegions(); FieldFunctionManager fm=s.getFieldFunctionManager();\n"
b1 = a1 + ("  star.vis.PlaneSection scp=null; for(Object o:s.getPartManager().getObjects()) if(o instanceof star.vis.PlaneSection pp&&pp.getPresentationName().equals(\"GODO_scene_plane\")) scp=pp;\n"
           "  if(scp==null){ scp=s.getPartManager().createPlaneSection(); scp.setPresentationName(\"GODO_scene_plane\"); scp.getInputParts().setObjects(regs);\n"
           "   scp.setOrigin(new DoubleVector(new double[]{0,0,0.01})); scp.setOrientation(new DoubleVector(new double[]{0,0,1})); }   // srodek paska 0,02 m\n")
a2 = 'star.vis.ScalarDisplayer sd=sc.getDisplayerManager().createScalarDisplayer("Skalar"); sd.getInputParts().setObjects(regs);'
b2 = 'star.vis.ScalarDisplayer sd=sc.getDisplayerManager().createScalarDisplayer("Skalar"); sd.getInputParts().setObjects(scp);'
a3 = "   double x=Double.parseDouble(q[2]),y=Double.parseDouble(q[3]),wd=Double.parseDouble(q[4]);"
b3 = "   for(Object dO:sc.getDisplayerManager().getObjects()) if(dO instanceof star.vis.ScalarDisplayer d2) d2.getInputParts().setObjects(scp);   // takze sceny juz zapisane\n" + a3
for a, b in ((a1, b1), (a2, b2), (a3, b3)):
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
q = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\policy_queue14.ps1"); t = q.read_text(encoding="utf-8")
if 'Remove-Item "$case\\STOP"' not in t:
    t = t.replace('Remove-Item "$case\\MPC_STOP" -EA SilentlyContinue', 'Remove-Item "$case\\MPC_STOP" -EA SilentlyContinue\nRemove-Item "$case\\STOP" -EA SilentlyContinue')
    q.write_text(t, encoding="utf-8")
print("ok", 'Remove-Item "$case\\STOP"' in q.read_text(encoding="utf-8"))
