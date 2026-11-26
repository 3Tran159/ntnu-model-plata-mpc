package macro;
import star.common.*;import star.base.neo.*;import star.motion.*;import star.sixdof.*;
import java.nio.file.*;import java.util.*;
/** Read-only check that the GUI-saved sim has a DFBI body + DFBI motion on the overset region. */
public class CheckDfbi extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  try{
   BodyManager bm=s.get(BodyManager.class);
   for(Object o:bm.getObjects()){Body bd=(Body)o;b.append("body: ").append(bd.getPresentationName()).append(" class=").append(bd.getClass().getSimpleName()).append("\n");}
  }catch(Throwable e){b.append("BodyManager error: ").append(e).append("\n");}
  for(Object o:s.get(MotionManager.class).getObjects())b.append("motion: ").append(((NamedObject)o).getPresentationName()).append(" ").append(o.getClass().getSimpleName()).append("\n");
  for(Region r:s.getRegionManager().getRegions()){
   try{b.append("region ").append(r.getPresentationName()).append(" motion=").append(r.getValues().get(MotionSpecification.class).getMotion().getPresentationName()).append("\n");}catch(Throwable e){b.append("region ").append(r.getPresentationName()).append(" ").append(e).append("\n");}
  }
  try{Files.writeString(Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir"))).resolve("CHECK_DFBI.txt"),b.toString());}catch(Exception e){}
 }
}
