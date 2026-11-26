package macro;
import star.common.*;import star.base.neo.*;import star.motion.*;import star.sixdof.*;import java.io.*;import java.lang.reflect.*;import java.util.*;

/** One-off API discovery for the overset + DFBI(heave) + superposed rotation build. Writes api_dump.txt, no save. */
public class ExploreApi extends StarMacro {
 PrintWriter w;
 void dump(String tag,Object o){
  if(o==null){w.println("## "+tag+": null");return;}
  w.println("## "+tag+" : "+o.getClass().getName());
  TreeSet<String> ms=new TreeSet<>();
  for(Method m:o.getClass().getMethods()){if(m.getDeclaringClass()==Object.class)continue;
   StringBuilder b=new StringBuilder(m.getName()).append("(");for(Class<?> p:m.getParameterTypes())b.append(p.getSimpleName()).append(",");b.append(")->").append(m.getReturnType().getSimpleName());ms.add(b.toString());}
  for(String m:ms)w.println("   "+m);w.flush();
 }
 Object call(Object o,String n,Object... a){
  for(Method m:o.getClass().getMethods())if(m.getName().equals(n)&&m.getParameterCount()==a.length){try{return m.invoke(o,a);}catch(Throwable e){w.println("   !! "+n+": "+e.getCause());}}
  w.println("   !! no "+n+"/"+a.length);return null;
 }
 public void execute(){
  Simulation s=getActiveSimulation();
  try{w=new PrintWriter(new FileWriter(new File(s.getSessionDir(),"api_dump.txt")));}catch(IOException e){throw new RuntimeException(e);}
  try{
   MotionManager mm=s.get(MotionManager.class); dump("MotionManager",mm);
   Motion hv=null;try{hv=mm.createMotion(OneDofTranslatingMotion.class,"Heave");}catch(Throwable e){w.println("create OneDof: "+e);}
   if(hv==null)try{hv=mm.createMotion(TwoDimensionalOneDofTranslatingMotion.class,"Heave2D");}catch(Throwable e){w.println("create 2D OneDof: "+e);}
   dump("heave motion",hv);
   if(hv!=null){Object sm=call(hv,"getSuperposingMotionManager");dump("SuperposingMotionManager",sm);
    if(sm!=null){Object r=null;try{r=sm.getClass().getMethod("createSuperposingMotion",Class.class,String.class).invoke(sm,SuperposingRotatingMotion.class,"Pitch");}catch(Throwable e){w.println("createSuperposingMotion: "+e);}
     dump("SuperposingRotatingMotion",r);
     if(r!=null){dump("rot.getRotationRate",call(r,"getRotationRate"));dump("rot.getAxisDirection",call(r,"getAxisDirection"));dump("rot.getAxisOrigin",call(r,"getAxisOrigin"));}}}
   BodyManager bm=s.get(BodyManager.class);dump("BodyManager",bm);
   Object body=null;
   for(Method m:bm.getClass().getMethods())if(m.getName().startsWith("create")){w.println("  try "+m);}
   try{body=bm.createBody(ContinuumBody.class);}catch(Throwable e){w.println("createBody(ContinuumBody): "+e);}
   dump("Body",body);
   if(body!=null){for(String g:new String[]{"getBodyProperties","getFreeMotion","getInitialValueManager","getExternalForceAndMomentManager","getCenterOfMass","getMass","getMomentOfInertia","getBodyMotionOption"}){Object o=call(body,g);if(o!=null)dump("body."+g,o);}}
   InterfaceManager im=s.getInterfaceManager();dump("InterfaceManager",im);
   Region reg=s.getRegionManager().getRegion("MINI_water_air");dump("Region",reg);
   dump("RegionValues",reg.getValues());
   for(Boundary b:reg.getBoundaryManager().getBoundaries()){w.println("boundary "+b.getPresentationName()+" type "+b.getBoundaryType().getClass().getSimpleName());}
   try{Class.forName("star.overset.OversetMeshBoundary");w.println("OversetMeshBoundary class ok (star.overset)");}catch(Throwable e){w.println("no star.overset.OversetMeshBoundary: "+e);}
   try{Class.forName("star.common.OversetMeshBoundary");w.println("star.common.OversetMeshBoundary ok");}catch(Throwable e){w.println("no star.common.OversetMeshBoundary");}
   SolverManager sv=s.getSolverManager();for(Solver so:sv.getObjects())w.println("solver "+so.getClass().getName());
  }catch(Throwable e){e.printStackTrace(w);}
  w.close();
 }
}
