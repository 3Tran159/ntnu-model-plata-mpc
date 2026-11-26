package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.motion.*;import star.sixdof.*;import star.flow.*;
import java.io.*;import java.nio.file.*;import java.util.*;

/**
 * ConfigureDfbi - completes the native DFBI set-up of the overset GodÃ¸ case after Julek created, in the GUI,
 * the motion "DFBI Rotation and Translation" (on region "GODO overset foil") and the body "GODO foil body".
 *  - body surfaces foil_main + foil_flap, mass per 0.02 m span (12.5 t / 7.99 m), CoG at the pivot (c/4),
 *    free in heave only, release after one encounter period, short ramp
 *  - superposed rotation (rate = GODO_Rot_rate_radps, set by the controller each step) about z through the body origin
 *  - native reports GODO_heave_dfbi_m / GODO_heave_v_dfbi_ms (TranslationReport / LinearVelocityReport)
 * Saves GODO_OVERSET_DFBI_SETUP.sim.  All of this is visible/editable in the GUI.
 */
public class ConfigureDfbi extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  Map<String,String> log=new LinkedHashMap<>();
  try{
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   double mass=12500.0/(25.6*.312)*.02, px=.078, zmid=.01, rel=1.9368;
   Region ov=s.getRegionManager().getRegion("GODO overset foil");
   Boundary fm=ov.getBoundaryManager().getBoundary("foil_main"), ff=ov.getBoundaryManager().getBoundary("foil_flap");
   BodyManager bm=s.get(BodyManager.class);
   Body b0=null;for(Object o:bm.getObjects())b0=(Body)o;
   if(!(b0 instanceof ContinuumBody))throw new IllegalStateException("no ContinuumBody");
   ContinuumBody body=(ContinuumBody)b0;body.setPresentationName("GODO foil body");
   body.getBodySurface().setObjects(fm,ff);
   body.getBodyProperties().setMass(mass);
   body.getBodyProperties().setReleaseTime(rel);
   body.getBodyProperties().setRampTime(0.05);
   body.setInitialCMS(new DoubleVector(new double[]{px,0,zmid}));
   body.setMomentsOfInertia(new DoubleVector(new double[]{1,1,1}));
   body.getMotionOption().setSelected(BodyMotionOption.Type.FREE_MOTION);
   BodyFreeMotion fr=(BodyFreeMotion)body.getMotionType();
   fr.setFreeTranslationX(false);fr.setFreeTranslationY(true);fr.setFreeTranslationZ(false);
   fr.setFreeRotationX(false);fr.setFreeRotationY(false);fr.setFreeRotationZ(false);
   SixDofMotion mot=(SixDofMotion)ov.getValues().get(MotionSpecification.class).getMotion();
   log.put("region_motion",mot.getPresentationName());
   SuperposingRotatingMotion sr=null;
   for(Object o:mot.getSuperposingMotionManager().getObjects())if(o instanceof SuperposingRotatingMotion x)sr=x;
   if(sr==null)sr=mot.getSuperposingMotionManager().createSuperposingMotion(SuperposingRotatingMotion.class,"GODO foil pitch (superposed, rate from controller)");
   sr.getRotationSpecificationOption().setSelected(RotationSpecificationOption.Type.RotationRate);
   ((RotationRate)sr.getRotationSpecification()).getRotationRate().setDefinition("${GODO_Rot_rate_radps}");
   sr.setCoordinateSystem(body.getCurrentCoordinateSystem());
   sr.getAxisDirection().setComponents(0,0,1);sr.getAxisOrigin().setComponents(0,0,0);
   log.put("superposed",sr.getPresentationName());log.put("body_cs",body.getCurrentCoordinateSystem().getPresentationName());
   // controller-side heave parameters are not used by DFBI; keep them at 0 so the old motion (still defined) is inert
   for(String p:new String[]{"GODO_Heave_v_ms","GODO_Heave_z_m"})try{((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject(p)).getQuantity().setValue(0);}catch(Throwable x){}
   TranslationReport tr=s.getReportManager().createReport(TranslationReport.class);tr.setPresentationName("GODO_heave_dfbi_m");tr.setBody(body);tr.getDirection().setComponents(0,1,0);
   LinearVelocityReport lv=s.getReportManager().createReport(LinearVelocityReport.class);lv.setPresentationName("GODO_heave_v_dfbi_ms");lv.setBody(body);lv.getDirection().setComponents(0,1,0);
   for(Report r:List.of(tr,lv)){ReportMonitor m=r.createMonitor();m.setPresentationName(r.getPresentationName()+" Monitor");try{m.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}}
   // pivot moment origin follows the body (DFBI heave) instead of the controller parameter
   try{((MomentReport)s.getReportManager().getReport("GODO_M_pivot")).getOrigin().setDefinition("["+px+", ${GODO_heave_dfbi_mReport}, "+zmid+"]");}catch(Throwable x){log.put("moment_origin",x.toString());}
   log.put("mass_kg",""+mass);
   s.saveState(out.resolve("GODO_OVERSET_DFBI_SETUP.sim").toString());
   Files.writeString(out.resolve("CONFIGURE_DFBI.txt"),log.toString());
  }catch(Throwable e){
   try{StringWriter w=new StringWriter();e.printStackTrace(new PrintWriter(w));log.put("error",w.toString());Files.writeString(out.resolve("CONFIGURE_DFBI.txt"),log.toString());}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
}
