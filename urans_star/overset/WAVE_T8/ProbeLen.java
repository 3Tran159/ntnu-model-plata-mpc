package macro;
import star.common.*;import star.base.neo.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** ProbeLen - tylko odczyt (bez zapisu .sim): dlugosci stref forsowania/tlumienia na granicach inlet/outlet + zakres x siatki. Wynik: PROBE_LEN.txt */
public class ProbeLen extends StarMacro {
 static void dump(Object o,StringBuilder b,String ind,int lev){
  if(o==null||lev>2)return;
  for(Method m:o.getClass().getMethods()){
   if(m.getParameterCount()!=0||!m.getName().startsWith("get")||m.getDeclaringClass()==Object.class)continue;
   String n=m.getName(); if(n.equals("getClass")||n.equals("getParent")||n.equals("getSimulation")||n.equals("getBeanDisplayName"))continue;
   try{Object r=m.invoke(o); String v=String.valueOf(r); if(v.length()>160)v=v.substring(0,160);
    try{Method e=r.getClass().getMethod("evaluate"); v=v+" = "+e.invoke(r);}catch(Throwable t){}
    try{Method e=r.getClass().getMethod("getValue"); v=v+" val "+e.invoke(r);}catch(Throwable t){}
    b.append(ind).append(n).append(" -> ").append(v).append("\n");
    if(r!=null&&(r.getClass().getSimpleName().contains("Quantity")||r.getClass().getSimpleName().contains("Length")))dump(r,b,ind+"   ",lev+1);
   }catch(Throwable t){}
  }
 }
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  for(Region r:s.getRegionManager().getRegions()){
   try{ for(Boundary bd:r.getBoundaryManager().getBoundaries()){ for(Object v:bd.getValues().getObjects()){ String cn=v.getClass().getSimpleName();
     if(cn.contains("Forcing")||cn.contains("Damping")){ b.append(r.getPresentationName()).append(" / ").append(bd.getPresentationName()).append(" ").append(cn).append("\n"); dump(v,b,"   ",0); try{ ScalarProfile sp=(ScalarProfile)v; b.append("   STALA = ").append(sp.getMethod(ConstantScalarProfileMethod.class).getQuantity().getSIValue()).append(" m\n"); }catch(Throwable e){ b.append("   brak stalej: "+e+"\n"); } } } } }catch(Throwable e){ b.append("blad "+e+"\n"); }
  }
  try{Files.writeString(out.resolve("PROBE_LEN.txt"),b.toString());}catch(Exception e){}
 }
}

