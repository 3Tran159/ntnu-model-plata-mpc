package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** SetWaveT8 - kopia setupu overset (ta sama siatka, prad, glebokosc 1,09 m, strefy forsowania/tlumienia) z inna fala:
 *  T = 8 s (lambda = g T^2 / 2 pi = 99,93 m, woda gleboka jak SetWaveT4), H = 1.5 m (jak fala Godo).
 *  23.11 (Julek: "niech cos liczy"), test wzoru ujednoliconego na dlugiej fali czolowej: g/(U*omega_e) = 0,51.
 *  Dodatkowo wypisuje dlugosci stref forsowania/tlumienia (sprawdzenie wzgledem lambda).
 *  Zapis: GODO_OVERSET_SETUP_T8.sim + SET_WAVE.txt */
public class SetWaveT8 extends StarMacro {
 static void dump(Object o,StringBuilder b,String ind){
  if(o==null)return;
  for(Method m:o.getClass().getMethods()){
   if(m.getParameterCount()!=0||!m.getName().startsWith("get"))continue;
   String n=m.getName(); if(!(n.contains("Length")||n.contains("Value")||n.contains("Depth")))continue;
   try{Object r=m.invoke(o); String v=String.valueOf(r);
    try{Method e=r.getClass().getMethod("evaluate"); v=v+" = "+e.invoke(r);}catch(Throwable t){}
    b.append(ind).append(n).append(" -> ").append(v).append("\n");}catch(Throwable t){}
  }
 }
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  double T=8.0,H=1.5,lam=9.80665*T*T/(2*Math.PI);
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
  b.append("== strefy fal (getValues regionow i granic)\n");
  for(Region r:s.getRegionManager().getRegions()){
   try{ for(Object v:r.getValues().getObjects()){ String cn=v.getClass().getSimpleName();
     if(cn.contains("Forcing")||cn.contains("Damping")){ b.append(r.getPresentationName()).append(" ").append(cn).append("\n"); dump(v,b,"   "); } } }catch(Throwable e){}
   try{ for(Boundary bd:r.getBoundaryManager().getBoundaries()){ for(Object v:bd.getValues().getObjects()){ String cn=v.getClass().getSimpleName();
     if(cn.contains("Forcing")||cn.contains("Damping")){ b.append("  granica ").append(bd.getPresentationName()).append(" ").append(cn).append("\n"); dump(v,b,"     "); } } } }catch(Throwable e){}
  }
  try{Files.writeString(out.resolve("SET_WAVE.txt"),b.toString());}catch(Exception e){}
  s.saveState(out.resolve("GODO_OVERSET_SETUP_T8.sim").toString());
 }
}
