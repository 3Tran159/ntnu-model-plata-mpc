package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import java.nio.file.*;import java.util.*;

/** ProbeDom - tylko odczyt (bez zapisu .sim): zakres x i y regionow (raporty Min/Max tworzone tymczasowo w pamieci). Wynik: PROBE_DOM.txt */
public class ProbeDom extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();StringBuilder b=new StringBuilder();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{
   PrimitiveFieldFunction pos=(PrimitiveFieldFunction)s.getFieldFunctionManager().getFunction("Centroid");
   for(Region r:s.getRegionManager().getRegions()){
    for(int k=0;k<2;k++){
     MinReport mn=s.getReportManager().createReport(MinReport.class); mn.setFieldFunction(pos.getComponentFunction(k)); mn.getParts().setObjects(r);
     MaxReport mx=s.getReportManager().createReport(MaxReport.class); mx.setFieldFunction(pos.getComponentFunction(k)); mx.getParts().setObjects(r);
     b.append(r.getPresentationName()).append(k==0?" x: ":" y: ").append(mn.getReportMonitorValue()).append(" .. ").append(mx.getReportMonitorValue()).append(" m\n");
    }
   }
  }catch(Throwable e){ b.append("blad "+e+"\n"); }
  try{Files.writeString(out.resolve("PROBE_DOM.txt"),b.toString());}catch(Exception e){}
 }
}