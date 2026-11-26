# 17.11 15:10: S7 - tlo VOF na tej samej plaszczyznie co linie pradu dawalo z-fighting (linie przerywane) -> bez tla;
# S8 - wektory jako glify byly ogromne -> tryb LIC (line integral convolution: tekstura linii pradu na calym przekroju).
from pathlib import Path
f = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\makro_mpcf\GodoOversetRun.java")
s = f.read_text(encoding="utf-8")
a1 = '    star.vis.ScalarDisplayer bg=s7.getDisplayerManager().createScalarDisplayer("Woda"); bg.getInputParts().setObjects(scp); bg.getScalarDisplayQuantity().setFieldFunction(fm.getFunction("VolumeFractionwater")); bg.setOpacity(0.35);\n'
a2 = '   s7.getCurrentView().setInput('
b2 = ('   { java.util.List<Object> rm=new java.util.ArrayList<>(); for(Object dO:s7.getDisplayerManager().getObjects()) if(dO instanceof star.vis.ScalarDisplayer b2&&b2.getPresentationName().equals("Woda")) rm.add(dO);\n'
      '     for(Object o:rm) s7.getDisplayerManager().removeObjects((star.vis.Displayer)o); }\n' + a2)
a3 = '   s8.getCurrentView().setInput('
b3 = '   for(Object dO:s8.getDisplayerManager().getObjects()) if(dO instanceof star.vis.VectorDisplayer v2) v2.setDisplayMode(star.vis.VectorDisplayMode.VECTOR_DISPLAY_MODE_LIC);\n' + a3
for a, b in ((a1, ""), (a2, b2), (a3, b3)):
    assert s.count(a) == 1, a[:50]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8"); print("ok")
