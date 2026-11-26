package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;

/** SetZonesT8 - strefy fal dopasowane do lambda 100 m w domenie x -31,2..78,0 m (plat w x 0):
 *  forsowanie na wlocie 15,6 -> 25,0 m (konczy sie 6 m = 19 cieciw przed platem),
 *  tlumienie na wylocie 31,2 -> 60,0 m (zaczyna sie 18 m za platem). Bylo: 0,4 i 0,8 lambda fali T 5 s.
 *  Zapis w miejscu: GODO_OVERSET_SETUP_T8.sim + ZONES.txt */
public class SetZonesT8 extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  try{
   Region r=s.getRegionManager().getRegion("MINI_water_air");
   for(Boundary bd:r.getBoundaryManager().getBoundaries()){
    for(Object v:bd.getValues().getObjects()){
     String cn=v.getClass().getSimpleName(); double L=-1;
     if(cn.equals("VofWaveForcingLength"))L=25.0; else if(cn.equals("VofWaveDampingLength"))L=60.0; else continue;
     ScalarPhysicalQuantity q=((ScalarProfile)v).getMethod(ConstantScalarProfileMethod.class).getQuantity();
     double l0=q.getSIValue(); q.setValue(L);
     b.append(bd.getPresentationName()).append(" ").append(cn).append(": ").append(l0).append(" -> ").append(q.getSIValue()).append(" m\n");
    }
   }
   s.saveState(out.resolve("GODO_OVERSET_SETUP_T8.sim").toString()); b.append("zapisano\n");
  }catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); }
  try{Files.writeString(out.resolve("ZONES.txt"),b.toString());}catch(Exception e){}
 }
}