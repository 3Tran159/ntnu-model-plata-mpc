package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;

/** SetCalmT8 - 24.11 (Julek 14:39: "sprawdz to, zeby nie budzilo watpliwosci"): woda spokojna w TEJ SAMEJ domenie co OVS_CEL_005g_T8_90
 *  (siatka, prad, strefy fal 25/60 m z ZONES.txt, poziom 1,09 m). Jedyna zmiana: wysokosc fali 1,5 -> 0,0001 m (jak kontrole "spokojna" w modelu).
 *  Zapis: GODO_OVERSET_SETUP_T8_CALM.sim + SET_CALM.txt */
public class SetCalmT8 extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){
   VofWaveModel vm;try{vm=pc.getModelManager().getModel(VofWaveModel.class);}catch(Throwable e){continue;}
   if(vm==null)continue;
   for(Object o:vm.getVofWaveManager().getObjects()){
    if(o instanceof FifthOrderVofWave w){
     double h0=w.getWaveHeight().evaluate(); w.getWaveHeight().setValue(1.0e-4);
     b.append(pc.getPresentationName()).append(": ").append(w.getPresentationName()).append(" H ").append(h0).append(" -> 0.0001 m\n");
    }
   }
  }
  try{Files.writeString(out.resolve("SET_CALM.txt"),b.toString());}catch(Exception e){}
  s.saveState(out.resolve("GODO_OVERSET_SETUP_T8_CALM.sim").toString());
 }
}