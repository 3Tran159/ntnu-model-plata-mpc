package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * ConvertOverset2D - converts the one-cell-thick overset GodÃ¸ case (GODO_OVERSET_SETUP_B*.sim) into a true 2D case
 * (STAR-CCM+ 2D solver, per unit span = 1 m). Native STAR operation: Mesh > Convert to 2D on both regions.
 * Afterwards all quantities are per 1 m span, so the report bases are rescaled:
 *   AF_CL, AF_CD: q = 0.5 rho U^2 c (per m), foil buoyancy per m;  wave gauges: integral over the line / 1 m;
 *   GODO_lift_over_weight: weight per m = 12.5 t / 7.99 m * g.     Saves GODO_OVERSET2D_SETUP.sim
 * Note: re-running the (3D) Directed Mesh operations regenerates the 3D mesh; convert again afterwards.
 */
public class ConvertOverset2D extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  Map<String,String> log=new LinkedHashMap<>();
  try{
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   Region bg=s.getRegionManager().getRegion("MINI_water_air"),ov=s.getRegionManager().getRegion("GODO overset foil");
   long c3=((FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh")).getCellCount();
   s.getMeshManager().convertTo2d(1.0E-6,List.of(bg,ov),true);
   long c2=((FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh")).getCellCount();
   log.put("cells_3d",""+c3);log.put("cells_2d",""+c2);
   for(Region r:s.getRegionManager().getRegions())if(r.getPresentationName().startsWith("MINI_water_air"))bg=r;
   List<String> regs=new ArrayList<>();for(Region r:s.getRegionManager().getRegions())regs.add(r.getPresentationName()+":"+r.getBoundaryManager().getBoundaries().size());
   log.put("regions",regs.toString());
   double U=12.346666666666666,C=.312,qd=0.5*1000*U*U*C,fb=1000*9.81*.00795948899616472;
   double W=12500.0/(25.6*.312)*9.81;
   ((ExpressionReport)s.getReportManager().getReport("AF_CL")).setDefinition("(${AF_FzReport}-"+fb+")/"+qd);
   ((ExpressionReport)s.getReportManager().getReport("AF_CD")).setDefinition("${AF_FxReport}/"+qd);
   ((ExpressionReport)s.getReportManager().getReport("GODO_lift_over_weight")).setDefinition("${GODO_Fy_fluidReport}/"+W);
   for(String g:new String[]{"GODO_eta_upstream_quarter_lambda","GODO_eta_at_LE","GODO_eta_at_hinge"}){
    ExpressionReport e=(ExpressionReport)s.getReportManager().getReport(g);
    String def=e.getDefinition().replace("/<0.02 m>","/<1 m>");e.setDefinition(def);log.put(g,def);
    // the plane sections become lines after conversion: re-point them to the 2D background region
    try{for(Object o:s.getPartManager().getObjects())if(o instanceof star.vis.PlaneSection p&&p.getPresentationName().startsWith(g))p.getInputParts().setObjects(bg);}catch(Throwable x){log.put("plane_"+g,x.toString());}
   }
   try{((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject("GODO_Mass_kg")).getQuantity().setValue(12500.0/(25.6*.312));}catch(Throwable x){}
   log.put("q_per_m_N",""+qd);log.put("weight_per_m_N",""+W);
   s.saveState(out.resolve("GODO_OVERSET2D_SETUP.sim").toString());
   Files.writeString(out.resolve("CONVERT2D.json"),log.toString());
  }catch(Throwable e){
   try{log.put("error",e.toString());Files.writeString(out.resolve("ERROR.json"),log.toString());}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
}
