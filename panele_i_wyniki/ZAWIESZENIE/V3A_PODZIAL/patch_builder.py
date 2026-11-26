"""BuildGodoSplit.java = kopia 30_URANS_STAR/BuildGodoCase.java (oryginal tylko czytany) z lataniem:
 - rozmiar powierzchni platu i strefa otoczenia skalowane cieciwa (foil_size_scale), strefa dla kazdego platu (foil_y_offsets),
 - wysokosc fali z wave_H_m (woda spokojna 1e-4 m), pas siatki przy powierzchni nadal z H_m."""
from pathlib import Path
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\BuildGodoCase.java")
t = SRC.read_text(encoding="utf-8")
R = [
 ("public class BuildGodoCase extends", "public class BuildGodoSplit extends"),
 ('foil.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*.00236);',
  'foil.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*.00236*d("foil_size_scale",1.0));'),
 ('foil.getCustomValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026);',
  'foil.getCustomValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026*d("foil_size_scale",1.0));'),
 ('volume(a,"GODO foil neighbourhood (0.66 % B)",new double[]{-.0786,-.0865,-.01},new double[]{.388,.102,.03},100*.0066);',
  '{double fs0=d("foil_size_scale",1.0);int kk=0;for(String yo:cfg.getProperty("foil_y_offsets","0").split(";")){double oy=Double.parseDouble(yo.trim());'
  'volume(a,"GODO foil neighbourhood "+(++kk)+" (0.66 % B x chord scale)",new double[]{-.0786*fs0,oy-.0865*fs0,-.01},new double[]{.388*fs0,oy+.102*fs0,.03},100*.0066*fs0);}}'),
 ("wave.getWaveHeight().setValue(H);", 'wave.getWaveHeight().setValue(d("wave_H_m",H));'),
 # kryterium ustalenia sil: srednia Fx i Fz z ostatniego okna W krokow vs poprzedniego okna, |zmiana|/|srednia| < tol
 # dwa razy pod rzad (sprawdzane co 200 krokow, nie wczesniej niz min_steps); probe_steps = limit gorny
 ("List<Double> sec=new ArrayList<>(); double t0=s.getSolution().getPhysicalTime();",
  "List<Double> sec=new ArrayList<>(); double t0=s.getSolution().getPhysicalTime(); List<Double> fxH=new ArrayList<>(),fzH=new ArrayList<>(); int okc=0; log.put(\"converged\",false);"),
 ('if(!Double.isFinite(cl+cd))throw new IllegalStateException("non-finite forces at step "+k);',
  'if(!Double.isFinite(cl+cd))throw new IllegalStateException("non-finite forces at step "+k);'
  'fxH.add(s.getReportManager().getReport("AF_Fx").getReportMonitorValue());fzH.add(s.getReportManager().getReport("AF_Fz").getReportMonitorValue());'
  '{int W=i("conv_window",1000);double tol=d("conv_tol",0.0025);'
  'if(k>=Math.max(i("min_steps",3000),2*W)&&k%200==0){'
  'double qa1=fxH.subList(k-W,k).stream().mapToDouble(x->x).average().getAsDouble(),qa0=fxH.subList(k-2*W,k-W).stream().mapToDouble(x->x).average().getAsDouble();'
  'double qb1=fzH.subList(k-W,k).stream().mapToDouble(x->x).average().getAsDouble(),qb0=fzH.subList(k-2*W,k-W).stream().mapToDouble(x->x).average().getAsDouble();'
  'double rx=Math.abs(qa1-qa0)/Math.abs(qa1),rz=Math.abs(qb1-qb0)/Math.abs(qb1);'
  'log.put("conv_last_step",k);log.put("conv_rel_Fx",rx);log.put("conv_rel_Fz",rz);log.put("Fx_mean_last_window_N",qa1);log.put("Fz_mean_last_window_N",qb1);write("CONV.json",log);'
  'if(rx<tol&&rz<tol){okc++;if(okc>=2){log.put("converged",true);log.put("converged_step",k);break;}}else okc=0;}}'),
]
for a, b in R:
    n = t.count(a)
    assert n == 1, (n, a[:60])
    t = t.replace(a, b)
Path(__file__).with_name("BuildGodoSplit.java").write_text(t, encoding="utf-8")
print("ok", len(t))
