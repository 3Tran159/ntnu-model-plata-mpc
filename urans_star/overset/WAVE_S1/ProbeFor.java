package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** ProbeFor - na GODO_OVERSET_SETUP_S1.sim: metody i stan obiektow forsowania/strefy fali (ktora fala jest wybrana). Nic nie zapisuje. Wynik: PROBE_FOR.txt */
public class ProbeFor extends StarMacro {
 StringBuilder b=new StringBuilder(); Set<Object> seen=Collections.newSetFromMap(new IdentityHashMap<>());
 String nm(Object o){ try{ return o instanceof NamedObject n? n.getPresentationName(): String.valueOf(o);}catch(Throwable e){return "?";} }
 void walk(Object o,int d){
  if(o==null||d>8||!seen.add(o))return;
  String c=o.getClass().getSimpleName();
  if(c.contains("Forcing")||c.contains("WaveZone")||c.contains("Damping")){
   b.append(c).append(" '").append(nm(o)).append("'\n");
   for(Method m:o.getClass().getMethods()){ if(m.getDeclaringClass().getName().startsWith("star.vof")||m.getName().toLowerCase().contains("wave")){
     String sig=m.getName()+Arrays.toString(m.getParameterTypes()).replace("class ","");
     if(m.getParameterCount()==0 && m.getName().startsWith("get")){ try{ Object r=m.invoke(o); sig+=" = "+(r==null?"null":r.getClass().getSimpleName()+":"+nm(r)); }catch(Throwable e){} }
     b.append("   ").append(sig).append("\n"); } }
  }
  for(String cn:new String[]{"getChildren","getValues","getConditions"}){ try{ Object x=o.getClass().getMethod(cn).invoke(o); if(x instanceof Collection<?> cc) for(Object y:cc) walk(y,d+1); else if(x!=null&&x!=o) walk(x,d+1);}catch(Throwable e){} }
 }
 public void execute(){
  Simulation s=getActiveSimulation(); Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{ for(Region r:s.getRegionManager().getRegions()){ b.append("REGION ").append(r.getPresentationName()).append("\n"); walk(r,0); for(Boundary bd:r.getBoundaryManager().getBoundaries()) walk(bd,0);} }
  catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); }
  try{Files.writeString(out.resolve("PROBE_FOR.txt"),b.toString());}catch(Exception e){}
 }
}
