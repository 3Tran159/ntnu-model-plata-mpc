package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import java.nio.file.*;import java.util.*;

/** Where is the interface Courant number high? Prints x/y/region of cells with interface CFL > thr, plus cell size there. */
public class DiagCFL extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  StringBuilder b=new StringBuilder();
  double thr=1.0;
  FieldFunctionManager fm=s.getFieldFunctionManager();
  String hot="($GODO_interface_Courant>"+thr+")";
  String[][] defs={{"DIAG_hot_y_max",hot+" ? $${Position}[1] : -1e9"},{"DIAG_hot_y_min",hot+" ? -$${Position}[1] : -1e9"},
                   {"DIAG_hot_x_max",hot+" ? $${Position}[0] : -1e9"},{"DIAG_hot_x_min",hot+" ? -$${Position}[0] : -1e9"},
                   {"DIAG_hot_size",hot+" ? pow($Volume/0.02,0.5) : -1e9"},{"DIAG_hot_minsize",hot+" ? -pow($Volume/0.02,0.5) : -1e9"},
                   {"DIAG_hot_speed",hot+" ? mag($$Velocity) : -1e9"}};
  List<MaxReport> reps=new ArrayList<>();
  for(String[] d:defs){
   UserFieldFunction f=fm.createFieldFunction();f.setPresentationName(d[0]);f.setFunctionName(d[0]);f.setDefinition(d[1]);
   for(Region r:s.getRegionManager().getRegions()){
    MaxReport m=s.getReportManager().createReport(MaxReport.class);m.setPresentationName(d[0]+" "+r.getPresentationName());m.setFieldFunction(f);m.getParts().setObjects(r);reps.add(m);}
  }
  for(int k=0;k<3;k++){
   if(k>0)s.getSimulationIterator().step(1);
   b.append("t=").append(s.getSolution().getPhysicalTime()).append("\n");
   for(MaxReport m:reps)b.append("  ").append(m.getPresentationName()).append(" = ").append(m.getReportMonitorValue()).append("\n");
  }
  try{Files.writeString(out.resolve("DIAG_CFL.txt"),b.toString());}catch(Exception e){}
 }
}
