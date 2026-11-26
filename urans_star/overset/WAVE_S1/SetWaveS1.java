package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** SetWaveS1 - 20.11 22:20 (Julek 21:54: "choc jedna walidacja naszej nieregularnej w URANS").
 *  Kopia setupu overset (ta sama siatka, prad, strefy forsowania/tlumienia) z fala NIEREGULARNA S1 (JONSWAP Hs 1,5 m, Tp 5 s, gamma 3,3):
 *  natywna fala superpozycji (SuperpositionVofWave) z 59 skladowych pierwszego rzedu - ta sama realizacja co w modelu Faltinsena (seed 100),
 *  pasmo okresow 2-7,5 s (98,8 % energii). Skladowe z S1_SKLADOWE.json. Wszystkie odwolania do fal CB_StokesV 1 (field functions w warunkach
 *  brzegowych, poczatkowych i strefach forsowania) przepiete na nowa fale. Zapis: GODO_OVERSET_SETUP_S1.sim + SET_WAVE.txt (log). */
public class SetWaveS1 extends StarMacro {
 StringBuilder b=new StringBuilder(); Set<Object> seen=Collections.newSetFromMap(new IdentityHashMap<>()); int nff=0, nsw=0;
 Simulation s; String OLD="CB_StokesV 1"; SuperpositionVofWave sw; String NEW;
 String nm(Object o){ try{ return o instanceof NamedObject n? n.getPresentationName(): String.valueOf(o);}catch(Throwable e){return "?";} }
 void fix(Object o,int d){
  if(o==null||d>8||!seen.add(o))return;
  try{ Method g=o.getClass().getMethod("getFieldFunction"); Object ff=g.invoke(o);
   if(ff instanceof FieldFunction f && f.getPresentationName().contains(OLD)){
    String n2=f.getPresentationName().replace(OLD,NEW); FieldFunction f2=s.getFieldFunctionManager().getFunction(f.getFunctionName()); f2=null;
    for(FieldFunction x:s.getFieldFunctionManager().getObjects()) if(x.getPresentationName().equals(n2)) f2=x;
    if(f2!=null){ o.getClass().getMethod("setFieldFunction",FieldFunction.class).invoke(o,f2); nff++; b.append("  FF: ").append(f.getPresentationName()).append(" -> ").append(n2).append("\n"); }
    else b.append("  BRAK FF ").append(n2).append("\n");
   }}catch(NoSuchMethodException e){}catch(Throwable e){ b.append("  blad FF ").append(e).append("\n"); }
  for(Method m:o.getClass().getMethods()){
   if(m.getParameterCount()==1 && m.getName().startsWith("set") && m.getName().toLowerCase().contains("wave") && VofWave.class.isAssignableFrom(m.getParameterTypes()[0])){
    try{ Method g=null; try{ g=o.getClass().getMethod("g"+m.getName().substring(1)); }catch(Throwable e){}
     Object cur=g!=null? g.invoke(o): null;
     if(cur==null || nm(cur).equals(OLD)){ m.invoke(o,sw); nsw++; b.append("  ").append(o.getClass().getSimpleName()).append(".").append(m.getName()).append(": ").append(nm(cur)).append(" -> ").append(NEW).append("\n"); }
    }catch(Throwable e){ b.append("  blad ").append(m.getName()).append(" ").append(e).append("\n"); }
   }
  }
  for(String cn:new String[]{"getChildren","getValues","getConditions","getObjects"}){
   try{ Object c=o.getClass().getMethod(cn).invoke(o); if(c instanceof Collection<?> cc) for(Object x:cc) fix(x,d+1); else if(c!=null && c!=o) fix(c,d+1); }catch(Throwable e){}
  }
 }
 public void execute(){
  s=getActiveSimulation(); Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  try{
   String js=Files.readString(out.resolve("S1_SKLADOWE.json"));
   List<double[]> comp=new ArrayList<>();
   int i0=js.indexOf("\"skladowe\""); String body=js.substring(i0);
   for(String part:body.split("\\{")){ if(!part.contains("\"a\""))continue; double a=num(part,"a"),eps=num(part,"eps"),lam=num(part,"lam"); comp.add(new double[]{a,eps,lam}); }
   VofWaveModel vm=null; PhysicsContinuum pcw=null;
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)) try{ VofWaveModel v=pc.getModelManager().getModel(VofWaveModel.class); if(v!=null){vm=v;pcw=pc;} }catch(Throwable e){}
   FifthOrderVofWave w=(FifthOrderVofWave)vm.getVofWaveManager().getVofWave(OLD);
   sw=vm.getVofWaveManager().createVofWave(SuperpositionVofWave.class,"S1_JONSWAP_seed100"); NEW=sw.getPresentationName();
   DoubleVector cu=w.getCurrentVector(), pl=w.getPointOnLevelVector(), vd=w.getVerticalDirectionVector();
   sw.getCurrent().setComponents(cu.get(0),cu.get(1),cu.get(2)); sw.getPointOnLevel().setComponents(pl.get(0),pl.get(1),pl.get(2)); sw.getVerticalDirection().setComponents(vd.get(0),vd.get(1),vd.get(2));
   sw.getHeavyFluidDensity().setValue(w.getHeavyFluidDensity().evaluate()); sw.getLightFluidDensity().setValue(w.getLightFluidDensity().evaluate()); sw.setDeepWaterApproximation(true);
   b.append("nowa fala ").append(NEW).append(", skladowych ").append(comp.size()).append(", prad ").append(cu).append(", poziom ").append(pl).append(", glebia: przyblizenie glebokiej wody\n");
   String phu=null; int k=0;
   for(double[] c:comp){
    FirstOrderSuperposingVofWave f=(FirstOrderSuperposingVofWave)sw.getSuperposingVofWaveManager().createSuperposingVofWave(FirstOrderSuperposingVofWave.class,String.format("S1_%02d",k++));
    f.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
    f.getVofWaveSpecification().getWaveLength().setValue(c[2]);
    f.getAmplitude().setValue(c[0]);
    if(phu==null) phu=f.getPhase().getUnits().getPresentationName();
    double ph=phu.toLowerCase().startsWith("deg")? Math.toDegrees(c[1]): c[1]; f.getPhase().setValue(ph);
    f.getAdvancingDirection().setComponents(1.0,0.0,0.0);
   }
   b.append("jednostka fazy: ").append(phu).append("\n");
   for(Region r:s.getRegionManager().getRegions()){ fix(r,0); for(Boundary bd:r.getBoundaryManager().getBoundaries()) fix(bd,0); }
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){ fix(pc.getInitialConditions(),0); fix(pc,0); }
   b.append("przepiete field functions: ").append(nff).append(", przepiete wybory fali: ").append(nsw).append("\n");
  }catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); for(StackTraceElement x:e.getStackTrace()) b.append("   ").append(x).append("\n"); }
  try{Files.writeString(out.resolve("SET_WAVE.txt"),b.toString());}catch(Exception e){}
  if(!b.toString().contains("BLAD ")) s.saveState(out.resolve("GODO_OVERSET_SETUP_S1.sim").toString());
 }
 static double num(String p,String key){ int i=p.indexOf("\""+key+"\""); int c=p.indexOf(':',i); int e=c+1; while(e<p.length()&&"-+.0123456789eE ".indexOf(p.charAt(e))>=0)e++; return Double.parseDouble(p.substring(c+1,e).trim()); }
}
