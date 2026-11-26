package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;

/** FixForcing - w GODO_OVERSET_SETUP_S1.sim strefa forsowania regionu MINI_water_air forsuje do fali S1 (zamiast CB_StokesV 1). Zapis w miejscu + FIX.txt */
public class FixForcing extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation(); Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir"))); StringBuilder b=new StringBuilder();
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  try{
   VofWaveModel vm=null; for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)) try{ VofWaveModel v=pc.getModelManager().getModel(VofWaveModel.class); if(v!=null)vm=v; }catch(Throwable e){}
   ManagedVofWave nw=vm.getVofWaveManager().getVofWave("S1_JONSWAP_seed100 1");
   for(Region r:s.getRegionManager().getRegions()){
    try{ ForcingVofWaveSpecification f=r.getValues().get(ForcingVofWaveSpecification.class);
     b.append(r.getPresentationName()).append(": ").append(f.getForcingVofWave().getPresentationName());
     f.setForcingVofWave(nw); b.append(" -> ").append(f.getForcingVofWave().getPresentationName()).append("\n");
    }catch(Throwable e){ b.append(r.getPresentationName()).append(": brak (").append(e.getClass().getSimpleName()).append(")\n"); }
   }
   s.saveState(out.resolve("GODO_OVERSET_SETUP_S1.sim").toString()); b.append("zapisano\n");
  }catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); }
  try{Files.writeString(out.resolve("FIX.txt"),b.toString());}catch(Exception e){}
 }
}
