package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;

/** SetCalmWater - copy of the overset setup with the incident wave height reduced to 0.1 mm (calm water, same
 *  current, depth, forcing/damping and mesh), for Godø's calm-water reference D_cw.  Saves GODO_OVERSET_SETUP_CALM.sim */
public class SetCalmWater extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){
   VofWaveModel vm;try{vm=pc.getModelManager().getModel(VofWaveModel.class);}catch(Throwable e){continue;}
   if(vm==null)continue;
   for(Object o:vm.getVofWaveManager().getObjects()){
    if(o instanceof FifthOrderVofWave w){double h0=w.getWaveHeight().evaluate();w.getWaveHeight().setValue(1.0e-4);
     b.append(pc.getPresentationName()).append(": ").append(w.getPresentationName()).append(" H ").append(h0).append(" -> 1e-4 m\n");}
   }
  }
  try{Files.writeString(out.resolve("SET_CALM.txt"),b.toString());}catch(Exception e){}
  s.saveState(out.resolve("GODO_OVERSET_SETUP_CALM.sim").toString());
 }
}
