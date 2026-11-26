package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.vof.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** SetLevelS1 - 21.11 (Julek 10:55, opcja A): w setupie S1 poziom spokojnej wody podniesiony o 0,3 m (1,09 -> 1,39 m nad osia plata),
 *  czyli plat startuje 1,39 m pod powierzchnia (tam, gdzie MPC lata na S1 w modelu). Zmiana: "Point on Level" fali S1 i wszystkich fal plaskich.
 *  Do LEVEL.txt wypisuje definicje raportow i field functions z "eta"/"1.09" (sprawdzenie, wzgledem czego mierzona jest eta przy LE).
 *  Zapis: GODO_OVERSET_SETUP_S1_L139.sim */
public class SetLevelS1 extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation(); Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir"))); StringBuilder b=new StringBuilder();
  s.getSimulationIterator().getAutoSave().setEnabled(false); double Y=1.39;
  try{
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){
    VofWaveModel vm=null; try{ vm=pc.getModelManager().getModel(VofWaveModel.class);}catch(Throwable e){}
    if(vm==null)continue; int n=0;
    for(Object o:vm.getVofWaveManager().getObjects()){
     try{ Method g=o.getClass().getMethod("getPointOnLevel"); VectorPhysicalQuantity v=(VectorPhysicalQuantity)g.invoke(o); DoubleVector d=v.evaluate();
      if(Math.abs(d.get(1)-1.09)<1e-6){ v.setComponents(d.get(0),Y,d.get(2)); n++; } else b.append("  inny poziom: ").append(((NamedObject)o).getPresentationName()).append(" ").append(d).append("\n");
     }catch(Throwable e){ b.append("  ").append(e).append("\n"); }
    }
    b.append(pc.getPresentationName()).append(": poziom 1,09 -> ").append(Y).append(" m w ").append(n).append(" falach\n");
   }
   b.append("== raporty\n");
   for(Report r:s.getReportManager().getObjects()){ String nm=r.getPresentationName(); if(!nm.toLowerCase().contains("eta"))continue;
    b.append("  ").append(nm).append(" [").append(r.getClass().getSimpleName()).append("]");
    for(String mn:new String[]{"getDefinition","getFieldFunction","getScalar"}){ try{ Object x=r.getClass().getMethod(mn).invoke(r); b.append(" ").append(mn).append("=").append(x instanceof NamedObject no? no.getPresentationName(): String.valueOf(x)); }catch(Throwable e){} }
    b.append("\n"); }
   b.append("== field functions uzytkownika z eta / 1.09 / free\n");
   for(FieldFunction f:s.getFieldFunctionManager().getObjects()){ if(f instanceof UserFieldFunction u){ String d=u.getDefinition(); String nm=u.getPresentationName();
     if(nm.toLowerCase().contains("eta")||d.contains("1.09")||nm.toLowerCase().contains("free")||nm.toLowerCase().contains("surf")) b.append("  ").append(nm).append(" := ").append(d).append("\n"); } }
   s.saveState(out.resolve("GODO_OVERSET_SETUP_S1_L139.sim").toString()); b.append("zapisano GODO_OVERSET_SETUP_S1_L139.sim\n");
  }catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); for(StackTraceElement x:e.getStackTrace()) b.append("   ").append(x).append("\n"); }
  try{Files.writeString(out.resolve("LEVEL.txt"),b.toString());}catch(Exception e){}
 }
}
