package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;

/** SetWaveT4 - kopia setupu overset (ta sama siatka, prad, glebokosc, strefy forsowania/tlumienia) z inna fala:
 *  T = 4 s (lambda = g T^2 / 2 pi = 24.98 m), H = 1.0 m (jak S2). 18.11, druga fala do walidacji modelu Faltinsena B (PID1).
 *  Zapis: GODO_OVERSET_SETUP_T4.sim + SET_WAVE.txt */
public class SetWaveT4 extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  double T=4.0,H=1.0,lam=9.80665*T*T/(2*Math.PI);
  for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){
   VofWaveModel vm;try{vm=pc.getModelManager().getModel(VofWaveModel.class);}catch(Throwable e){continue;}
   if(vm==null)continue;
   for(Object o:vm.getVofWaveManager().getObjects()){
    if(o instanceof FifthOrderVofWave w){
     double h0=w.getWaveHeight().evaluate();
     w.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
     w.getVofWaveSpecification().getWaveLength().setValue(lam);
     w.getWaveHeight().setValue(H);
     b.append(pc.getPresentationName()).append(": ").append(w.getPresentationName()).append(" H ").append(h0).append(" -> ").append(H)
      .append(" m, lambda -> ").append(lam).append(" m\n");
    }
   }
  }
  try{Files.writeString(out.resolve("SET_WAVE.txt"),b.toString());}catch(Exception e){}
  s.saveState(out.resolve("GODO_OVERSET_SETUP_T4.sim").toString());
 }
}
