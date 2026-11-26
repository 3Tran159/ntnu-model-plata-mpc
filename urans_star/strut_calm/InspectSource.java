package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;import star.flow.*;import star.meshing.*;import star.base.report.*;
import java.nio.file.*;import java.util.*;

/** InspectSource - read-only: lists region, boundaries (type + profile methods), continuum models, waves, forcing.
 *  Writes INSPECT.txt into MINI_CASE_DIR. Nothing is saved to the .sim. */
public class InspectSource extends StarMacro {
 StringBuilder b=new StringBuilder();
 void p(String x){b.append(x).append('\n');}
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{
   for(Region r:s.getRegionManager().getRegions()){
    p("REGION "+r.getPresentationName()+" continuum="+r.getPhysicsContinuum().getPresentationName()+" parts="+r.getPartGroup().getObjects());
    for(Object c:r.getConditions().getObjects())p("  rcond "+c.getClass().getSimpleName()+" = "+val(c));
    for(Object v:r.getValues().getObjects())p("  rval "+v.getClass().getSimpleName()+" = "+val(v));
    for(Boundary bd:r.getBoundaryManager().getBoundaries()){
     p(" BND "+bd.getPresentationName()+" type="+bd.getBoundaryType().getClass().getSimpleName()+" surf="+bd.getPartSurfaceGroup().getObjects());
     for(Object c:bd.getConditions().getObjects())p("    cond "+c.getClass().getSimpleName()+" = "+val(c));
     for(Object v:bd.getValues().getObjects())p("    val "+v.getClass().getSimpleName()+" = "+val(v));
    }
   }
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){
    p("CONT "+pc.getPresentationName());
    for(Object m:pc.getModelManager().getObjects())p("  model "+m.getClass().getName());
    for(Object ic:pc.getInitialConditions().getObjects())p("  init "+ic.getClass().getSimpleName()+" = "+val(ic));
    try{VofWaveModel vm=pc.getModelManager().getModel(VofWaveModel.class);
     for(Object w:vm.getVofWaveManager().getObjects())p("  wave "+((NamedObject)w).getPresentationName()+" "+w.getClass().getSimpleName());}catch(Throwable e){p("  nowave "+e);}
   }
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class))for(Object rv:pc.getReferenceValues().getObjects())p("  ref "+rv.getClass().getSimpleName()+" = "+val(rv));
   p("FIELDS");for(FieldFunction f:s.getFieldFunctionManager().getObjects()){String n=f.getFunctionName();if(n.startsWith("VolumeFraction")||n.contains("Flat 1")||n.contains("CB_StokesV"))p("  "+n+" | "+f.getPresentationName());}
   p("SOLVERS");for(Object so:s.getSolverManager().getObjects())p("  "+so.getClass().getSimpleName());
   try{ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);p("  dt="+us.getTimeStep().getValue()+" order="+us.getTimeDiscretizationOption().getSelectedElement());}catch(Throwable e){p("  "+e);}
   p("REPORTS");for(Report r:s.getReportManager().getObjects())p("  "+r.getPresentationName()+" "+r.getClass().getSimpleName());
   p("MESHOPS");for(Object o:s.get(MeshOperationManager.class).getObjects())p("  "+((NamedObject)o).getPresentationName()+" "+o.getClass().getSimpleName());
   p("PARTS");for(GeometryPart g:s.get(SimulationPartManager.class).getLeafParts())p("  "+g.getPresentationName()+" "+g.getClass().getSimpleName());
  }catch(Throwable e){p("ERROR "+e);}
  try{Files.writeString(out.resolve("INSPECT.txt"),b.toString());}catch(Exception e){}
 }
 String val(Object o){
  try{
   java.lang.reflect.Method gm=null;try{gm=o.getClass().getMethod("getMethod");}catch(Throwable e){}
   if(gm!=null){Object m=gm.invoke(o);String x=m.getClass().getSimpleName();
    try{x+=" ff="+((FieldFunction)m.getClass().getMethod("getFieldFunction").invoke(m)).getPresentationName();}catch(Throwable e){}
    try{Object q=m.getClass().getMethod("getQuantity").invoke(m);x+=" q="+q.getClass().getMethod("getDefinition").invoke(q);}catch(Throwable e){}
    return x;}
   for(String g:new String[]{"getSelectedElement","getSelected","getValue","getDefinition"}){
    try{return String.valueOf(o.getClass().getMethod(g).invoke(o));}catch(Throwable e){}
   }
  }catch(Throwable e){}
  return "?";
 }
}
