import star.common.*;
import star.base.neo.*;
import star.vis.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * ExportVorticity - stopklatka wirowosci z zapisanego stanu URANS (bez liczenia krokow).
 * Natywnie w GUI: tworzy scene "GODO vorticity" (skalarny displayer wirowosci z na scianach span_front obu regionow,
 * zakres +-VMAX 1/s) i dwie tabele XYZ (komorki obu regionow: wirowosc z, udzial wody, status overset),
 * zapisuje zrzuty sceny i kopie .sim ze scena (vort_scene.sim) w katalogu MINI_CASE_DIR.
 * Plik wejsciowy to KOPIA stanu z overset_runs (oryginaly nietkniete).
 */
public class ExportVorticity extends StarMacro {
  Simulation s; Path out; Map<String,String> log = new LinkedHashMap<>();
  public void execute() {
    s = getActiveSimulation();
    out = Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR", s.getSessionDir()));
    try { run(); } catch (Throwable e) { log.put("ERROR", e.toString()); }
    try { StringBuilder b = new StringBuilder("{\n"); for (Map.Entry<String,String> e : log.entrySet()) b.append(" \"").append(e.getKey()).append("\": \"").append(e.getValue().replace("\\","/").replace("\"","'")).append("\",\n");
          b.append(" \"done\": \"1\"\n}\n"); Files.write(out.resolve("EXPORT_LOG.json"), b.toString().getBytes("UTF-8")); } catch (Exception e) {}
  }
  void run() throws Exception {
    double vmax = 60.0;
    log.put("time_s", "" + s.getSolution().getPhysicalTime());
    StringBuilder ff = new StringBuilder();
    for (FieldFunction f : s.getFieldFunctionManager().getObjects()) ff.append(f.getFunctionName()).append(" | ").append(f.getPresentationName()).append("\n");
    Files.write(out.resolve("field_functions.txt"), ff.toString().getBytes("UTF-8"));
    PrimitiveFieldFunction vort = (PrimitiveFieldFunction) s.getFieldFunctionManager().getFunction("VorticityVector");
    FieldFunction vz = vort.getComponentFunction(2);
    List<Object> fns = new ArrayList<>(); fns.add(vz);
    for (FieldFunction f : s.getFieldFunctionManager().getObjects()) {
      String n = f.getFunctionName();
      if ((n.startsWith("VolumeFraction") && n.toLowerCase().contains("water")) || n.toLowerCase().contains("overset")) { fns.add(f); log.put("ff_" + n, f.getPresentationName()); }
    }
    Region bg = s.getRegionManager().getRegion("MINI_water_air"), ov = s.getRegionManager().getRegion("GODO overset foil");
    for (Region r : new Region[]{bg, ov}) {
      XyzInternalTable t = (XyzInternalTable) s.getTableManager().createTable(XyzInternalTable.class);
      t.setPresentationName("GODO vorticity cells - " + r.getPresentationName());
      t.setFieldFunctions(new NeoObjectVector(fns.toArray()));
      t.getParts().setObjects(r);
      t.extract();
      String fn = (r == bg ? "vort_background.csv" : "vort_overset.csv");
      t.export(out.resolve(fn).toString(), ",");
      log.put("table_" + fn, "ok");
    }
    Boundary b1 = bg.getBoundaryManager().getBoundary("span_front"), b2 = ov.getBoundaryManager().getBoundary("ov_span_front");
    Scene sc = s.getSceneManager().createScene("GODO vorticity");
    sc.setPresentationName("GODO vorticity"); sc.initializeAndWait();
    ScalarDisplayer sd = sc.getDisplayerManager().createScalarDisplayer("Vorticity z");
    sd.getInputParts().setObjects(b1, b2);
    sd.getScalarDisplayQuantity().setFieldFunction(vz);
    sd.getScalarDisplayQuantity().setClip(ClipMode.NONE);
    sd.getScalarDisplayQuantity().setAutoRange(AutoRangeMode.NONE);
    sd.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{-vmax, vmax}));
    try { sd.getLegend().setLookupTable(s.get(LookupTableManager.class).getObject("blue-red")); } catch (Throwable e) { log.put("lut", e.toString()); }
    double[][] views = {{0.6, 0.0, 0.9}, {5.0, 0.0, 5.5}};
    String[] names = {"VORT_near.png", "VORT_wake.png"};
    for (int i = 0; i < 2; i++) {
      sc.getCurrentView().setInput(new DoubleVector(new double[]{views[i][0], views[i][1], 0}), new DoubleVector(new double[]{views[i][0], views[i][1], 10}),
          new DoubleVector(new double[]{0, 1, 0}), views[i][2], 1, s.getCoordinateSystemManager().getLabCoordinateSystem(), false);
      sc.printAndWait(out.resolve(names[i]).toString(), 1, 1800, 700);
    }
    s.saveState(out.resolve("vort_scene.sim").toString());
    log.put("saved", "vort_scene.sim");
  }
}
