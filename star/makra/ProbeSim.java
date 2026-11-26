package macro;
import star.motion.*;import star.meshing.*;import star.common.*;import star.vis.*;import star.post.*;import star.metrics.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.material.*;import star.segregatedflow.*;import star.turbulence.*;import star.kwturb.*;import star.vof.*;import star.mixturemultiphase.*;import star.vis.*;import java.nio.file.*;import java.io.*;import java.util.*;
public class ProbeSim extends StarMacro {
 StringBuilder sb=new StringBuilder();
 void kv(String k,Object v){
  String val=(v instanceof Number||v instanceof Boolean)?String.valueOf(v):"\""+String.valueOf(v).replace("\\","/").replace("\"","'")+"\"";
  sb.append("\"").append(k).append("\":").append(val).append(",\n");
 }
 public void execute(){
  Simulation s=getActiveSimulation();
  String out=System.getProperty("probe.out","T:/NTNU_GODO_CONTROL_20261109/30_runs/PROBE/probe.json");
  try{
   kv("title",s.getPresentationName());
   kv("time_s",s.getSolution().getPhysicalTime());
   try{kv("dt_s",s.getSolverManager().getSolver(ImplicitUnsteadySolver.class).getTimeStep().evaluate());}catch(Throwable e){kv("dt_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Region g:s.getRegionManager().getRegions()){r.append(g.getPresentationName()).append(":[");for(Boundary q:g.getBoundaryManager().getBoundaries())r.append(q.getPresentationName()).append("|");r.append("] ");}kv("regions",r);}catch(Throwable e){kv("regions_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Report q:s.getReportManager().getObjects()){String v="?";try{v=String.valueOf(q.getReportMonitorValue());}catch(Throwable e){v="ERR";}r.append(q.getPresentationName()).append("=").append(v).append(" ; ");}kv("reports",r);}catch(Throwable e){kv("reports_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f instanceof UserFieldFunction u){String d="";try{d=u.getDefinition();}catch(Throwable e){}r.append(u.getPresentationName()).append(" := ").append(d.length()>160?d.substring(0,160):d).append(" ;; ");}kv("user_fields",r);}catch(Throwable e){kv("ff_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Object m:s.get(MotionManager.class).getObjects())r.append(((NamedObject)m).getPresentationName()).append(" (").append(m.getClass().getSimpleName()).append(") ; ");kv("motions",r);}catch(Throwable e){kv("motion_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Object m:s.get(GlobalParameterManager.class).getObjects())r.append(((NamedObject)m).getPresentationName()).append(" (").append(m.getClass().getSimpleName()).append(") ; ");kv("global_parameters",r);}catch(Throwable e){kv("gp_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Monitor m:s.getMonitorManager().getObjects())if(m.getPresentationName().startsWith("AF"))r.append(m.getPresentationName()).append(" ; ");kv("monitors_AF",r);}catch(Throwable e){kv("mon_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Object c:s.getSolverStoppingCriterionManager().getObjects())r.append(((NamedObject)c).getPresentationName()).append(" ; ");kv("stopping",r);}catch(Throwable e){kv("stop_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(Object m:s.getTableManager().getObjects())r.append(((NamedObject)m).getPresentationName()).append(" ; ");kv("tables",r);}catch(Throwable e){kv("tbl_err",e.toString());}
   try{StringBuilder r=new StringBuilder();for(SolutionHistory h:s.get(SolutionHistoryManager.class).getObjects())r.append(h.getPresentationName()).append(" states=").append(h.getNumberOfStates()).append(" ; ");kv("solution_histories",r);}catch(Throwable e){kv("sh_err",e.toString());}
  }catch(Throwable e){kv("fatal",e.toString());}
  try{
   java.nio.file.Path p=java.nio.file.Paths.get(out);
   java.nio.file.Files.createDirectories(p.getParent());
   java.nio.file.Files.writeString(p,"{\n"+sb+"\"end\":true}\n");
  }catch(Exception e){throw new RuntimeException(e);}
 }
}
