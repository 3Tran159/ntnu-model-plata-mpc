package macro;
import star.common.*;import star.base.neo.*;import star.vof.*;
import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** ProbeSup - rozpoznanie API fali superpozycji (nic nie zapisuje do .sim). Wynik: PROBE.txt */
public class ProbeSup extends StarMacro {
 StringBuilder b=new StringBuilder();
 void meth(Class<?> c){ b.append("== ").append(c.getName()).append("\n"); TreeSet<String> t=new TreeSet<>(); for(Method m:c.getMethods()){ if(m.getDeclaringClass().getName().startsWith("star.vof")||m.getDeclaringClass()==c) t.add(m.getName()+Arrays.toString(m.getParameterTypes()).replace("class ","")+" -> "+m.getReturnType().getSimpleName()); } for(String s:t) b.append("  ").append(s).append("\n"); }
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{
   for(PhysicsContinuum pc:s.getContinuumManager().getObjectsOf(PhysicsContinuum.class)){
    VofWaveModel vm;try{vm=pc.getModelManager().getModel(VofWaveModel.class);}catch(Throwable e){continue;}
    if(vm==null)continue;
    b.append("continuum ").append(pc.getPresentationName()).append("\n");
    for(Object o:vm.getVofWaveManager().getObjects()) b.append(" wave ").append(o.getClass().getName()).append(" ").append(((NamedObject)o).getPresentationName()).append("\n");
    meth(VofWaveManager.class);
    SuperpositionVofWave sw=vm.getVofWaveManager().createVofWave(SuperpositionVofWave.class,"SuperpositionVofWave");
    meth(SuperpositionVofWave.class);
    Object mgr=null; for(Method m:SuperpositionVofWave.class.getMethods()) if(m.getName().toLowerCase().contains("manager")&&m.getParameterCount()==0){ mgr=m.invoke(sw); b.append("manager via ").append(m.getName()).append(": ").append(mgr.getClass().getName()).append("\n"); meth(mgr.getClass()); }
    meth(FirstOrderSuperposingVofWave.class);
    meth(FifthOrderVofWave.class);
   }
   b.append("== field functions z 'Wave' w nazwie\n");
   for(FieldFunction f:s.getFieldFunctionManager().getObjects()) if(f.getPresentationName().toLowerCase().contains("wave")) b.append("  ").append(f.getPresentationName()).append(" | ").append(f.getFunctionName()).append("\n");
  }catch(Throwable e){ b.append("BLAD ").append(e).append("\n"); for(StackTraceElement x:e.getStackTrace()) b.append("   ").append(x).append("\n"); }
  try{Files.writeString(out.resolve("PROBE.txt"),b.toString());}catch(Exception e){}
 }
}
