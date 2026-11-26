package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** ProbeRef - gdzie sa uzywane fale (CB_StokesV 1 i NN_OutletFlat) - regiony, granice, warunki poczatkowe. Nic nie zapisuje do .sim. Wynik: PROBE_REF.txt */
public class ProbeRef extends StarMacro {
 StringBuilder b=new StringBuilder(); Set<Object> seen=Collections.newSetFromMap(new IdentityHashMap<>());
 String nm(Object o){ try{ return o instanceof NamedObject n? n.getPresentationName(): o.toString(); }catch(Throwable e){return "?";} }
 void walk(Object o,String pre,int d){
  if(o==null||d>6||!seen.add(o))return;
  String extra="";
  for(String mn:new String[]{"getVofWave","getFieldFunction","getSelectedVofWave","getWave"}){
   try{ Method m=o.getClass().getMethod(mn); Object r=m.invoke(o); if(r!=null) extra+=" ["+mn+"="+nm(r)+"]"; }catch(Throwable e){}
  }
  String cls=o.getClass().getSimpleName();
  if(!extra.isEmpty()||cls.toLowerCase().contains("wave")) b.append(pre).append(cls).append(" '").append(nm(o)).append("'").append(extra).append("\n");
  try{ Method m=o.getClass().getMethod("getChildren"); Object c=m.invoke(o); if(c instanceof Collection<?> cc) for(Object x:cc) walk(x,pre+"  ",d+1); }catch(Throwable e){}
 }
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{
   for(Region r:s.getRegionManager().getRegions()){
    b.append("REGION ").append(r.getPresentationName()).append("\n"); walk(r,"  ",0);
    for(Boundary bd:r.getBoundaryManager().getBoundaries()){ b.append(" BOUNDARY ").append(bd.getPresentationName()).append(" ").append(bd.getBoundaryType().getPresentationName()).append("\n"); walk(bd,"   ",0); }
   }
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){ b.append("CONTINUUM ").append(pc.getPresentationName()).append("\n"); walk(pc.getInitialConditions(),"  ",0); walk(pc.getReferenceValues(),"  ",0); }
   VofWaveModel vm=null; for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)) try{ vm=pc.getModelManager().getModel(VofWaveModel.class);}catch(Throwable e){}
   FifthOrderVofWave w=(FifthOrderVofWave)vm.getVofWaveManager().getVofWave("CB_StokesV 1");
   b.append("StokesV: H ").append(w.getWaveHeight().evaluate()).append(" T ").append(w.getWavePeriod().evaluate()).append(" current ").append(w.getCurrentVector()).append(" dir ").append(w.getAdvancingDirectionVector())
    .append(" level ").append(w.getPointOnLevelVector()).append(" vert ").append(w.getVerticalDirectionVector()).append(" rhoH ").append(w.getHeavyFluidDensity().evaluate()).append(" depth ").append(w.getWaterDepth().evaluate())
    .append(" spec ").append(w.getSpecificationOption().getSelectedElement()).append(" add ").append(w.getAdditionalVelocity().evaluate()).append("\n");
   for(Object o:w.getChildren()) b.append("  child ").append(o.getClass().getSimpleName()).append(" ").append(nm(o)).append("\n");
  }catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); for(StackTraceElement x:e.getStackTrace()) b.append("   ").append(x).append("\n"); }
  try{Files.writeString(out.resolve("PROBE_REF.txt"),b.toString());}catch(Exception e){}
 }
}
