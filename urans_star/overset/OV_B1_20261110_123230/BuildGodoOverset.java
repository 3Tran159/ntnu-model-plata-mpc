package macro;
import star.motion.*;import star.meshing.*;import star.common.*;import star.vis.*;import star.post.*;import star.metrics.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.material.*;import star.vof.*;import star.sixdof.*;import star.prismmesher.*;import star.sweptmesher.*;import star.twodmesher.*;import star.resurfacer.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * BuildGodoOverset - GodÃƒÂ¸'s actuation in URANS-VOF: the WHOLE foil rotates (about c/4) and the foil is free in heave.
 * Built natively on a copy of GODO_SETUP_B*.sim (verified GodÃƒÂ¸-condition physics: VOF, SST k-omega, 5th-order Stokes
 * wave with forcing/damping, AF_* force reports):
 *  - background region  = the existing region "MINI_water_air" relinked to GodoBackground.stl (no foil)
 *  - overset region     = new region "GODO overset foil" (GodoOverset.stl: box around the foil) + Overset Mesh interface
 *  - two Directed Mesh operations, all sizes relative to Base Size; background has a refined overset-travel zone
 *  - DFBI body "GODO foil body" (mass per 0.02 m span from GodÃƒÂ¸'s 12.5 t / 7.99 m span), free in heave only,
 *    with a SUPERPOSED rotation (angle = field function GODO_PitchAngle_rad, driven by the controller parameters)
 *  - reports: GODO_heave_m, GODO_heave_velocity, GODO_pitch_deg, GODO_M_pivot, GODO_Fy, plus all AF_* re-pointed
 * Modes: mode=mesh  -> build + mesh + save GODO_OVERSET_SETUP_B<base>.sim
 *        mode=probe -> + initialise + N steps with a small pitch ramp (overset + DFBI smoke test) -> OVERSET_PROBE.json
 */
public class BuildGodoOverset extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties(); Units m;
 Map<String,Object> log=new LinkedHashMap<>();
 double d(String k,double v){return Double.parseDouble(cfg.getProperty(k,""+v));}
 int i(String k,int v){return Integer.parseInt(cfg.getProperty(k,""+v));}
 static String q(String x){return "\""+x.replace("\\","/").replace("\"","'")+"\"";}
 String json(Object a){
  if(a==null)return "null";
  if(a instanceof Number){double x=((Number)a).doubleValue();return Double.isFinite(x)?a.toString():"null";}
  if(a instanceof Boolean)return a.toString();
  if(a instanceof Map<?,?> mm){StringBuilder b=new StringBuilder("{");boolean f=true;for(Map.Entry<?,?> e:mm.entrySet()){if(!f)b.append(",");f=false;b.append(q(String.valueOf(e.getKey()))).append(":").append(json(e.getValue()));}return b.append("}").toString();}
  if(a instanceof Collection<?> c){StringBuilder b=new StringBuilder("[");boolean f=true;for(Object o:c){if(!f)b.append(",");f=false;b.append(json(o));}return b.append("]").toString();}
  return q(String.valueOf(a));
 }
 void write(String n,Object v)throws Exception{Path p=out.resolve(n),t=out.resolve(n+".tmp");Files.writeString(t,json(v));Files.move(t,p,StandardCopyOption.REPLACE_EXISTING);}
 FieldFunction ff(String n){FieldFunction f=s.getFieldFunctionManager().getFunction(n);if(f==null)throw new IllegalStateException("Missing field "+n);return f;}
 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 String nm(Object o){try{return ((NamedObject)o).getPresentationName();}catch(Throwable e){return "";}}
 boolean drop(Object mgr,Object obj){
  for(String mth:new String[]{"removeObjects","remove","deleteChildren"})
   for(java.lang.reflect.Method mm:mgr.getClass().getMethods()){
    if(!mm.getName().equals(mth)||mm.getParameterCount()!=1)continue;
    try{Class<?> pt=mm.getParameterTypes()[0];
     if(pt.isArray()){Object arr=java.lang.reflect.Array.newInstance(pt.getComponentType(),1);java.lang.reflect.Array.set(arr,0,obj);mm.invoke(mgr,arr);}
     else if(Collection.class.isAssignableFrom(pt))mm.invoke(mgr,List.of(obj));
     else if(pt.isInstance(obj))mm.invoke(mgr,obj);else continue;
     return true;}catch(Throwable e){}
   }
  return false;
 }
 ScalarGlobalParameter param(String name,double v){
  GlobalParameterManager gm=s.get(GlobalParameterManager.class);
  ScalarGlobalParameter p=gm.has(name)?(ScalarGlobalParameter)gm.getObject(name):(ScalarGlobalParameter)gm.createGlobalParameter(ScalarGlobalParameter.class,"Scalar");
  p.setPresentationName(name);p.getQuantity().setValue(v);return p;
 }
 UserFieldFunction uff(String name,String def){
  FieldFunctionManager fm=s.getFieldFunctionManager();
  UserFieldFunction f=fm.has(name)?(UserFieldFunction)fm.getFunction(name):fm.createFieldFunction();
  f.setPresentationName(name);f.setFunctionName(name);f.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);f.setDefinition(def);return f;
 }
 GeometryPart importStl(String file,String name){
  SimulationPartManager pm=s.get(SimulationPartManager.class);
  Set<GeometryPart> before=new HashSet<>(pm.getLeafParts());
  s.get(PartImportManager.class).importStlPart(out.resolve(file).toString(),"OneSurfacePerPatch",m,true,1e-8);
  List<GeometryPart> added=new ArrayList<>(pm.getLeafParts());added.removeAll(before);
  if(added.size()!=1)throw new IllegalStateException("Expected one new part from "+file);
  added.get(0).setPresentationName(name);return added.get(0);
 }
 Map<String,PartSurface> surfaces(GeometryPart p){Map<String,PartSurface> r=new LinkedHashMap<>();for(PartSurface x:p.getPartSurfaces())r.put(x.getPresentationName(),x);return r;}

 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  String stage="init";
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   m=s.getUnitsManager().getObject("m");
   Region bg=s.getRegionManager().getRegion("MINI_water_air");
   if(!s.getReportManager().has("GODO_interfaceCFL"))throw new IllegalStateException("source must be a GODO_SETUP_B*.sim");
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   s.getSolution().clearSolution(Solution.Clear.Fields,Solution.Clear.History);
   double B=d("base_size_m",1.0),C=d("chord_m",.312),yfs=d("free_surface_y_m",1.09),H=d("H_m",1.5);
   double px=d("pivot_x_m",.078),py=d("pivot_y_m",0.0),zmid=.01;

   stage="geometry";
   Map<String,Boundary> ob=new LinkedHashMap<>();for(Boundary b:bg.getBoundaryManager().getBoundaries())ob.put(b.getPresentationName().toLowerCase(Locale.ROOT),b);
   List<Object> oldParts=new ArrayList<>(s.get(SimulationPartManager.class).getLeafParts());
   GeometryPart bgp=importStl("GodoBackground.stl","GODO background - domain without foil");
   GeometryPart ovp=importStl("GodoOverset.stl","GODO overset - box around the foil");
   Map<String,PartSurface> bs=surfaces(bgp),os=surfaces(ovp);
   bg.getPartGroup().setObjects(List.of(bgp));
   Map<String,String> links=Map.of("inlet","Inlet","outlet","Outlet","bottom","Bottom","top","Top","span_front","Span0","span_back","Span1");
   for(var e:links.entrySet())ob.get(e.getKey()).getPartSurfaceGroup().setObjects(bs.get(e.getValue()));
   Boundary oldMain=ob.get("main"),oldFlap=ob.get("flap");
   oldMain.getPartSurfaceGroup().setObjects();oldFlap.getPartSurfaceGroup().setObjects();
   int gone=0;for(Object o:s.get(MeshOperationManager.class).getObjects().toArray())if(drop(s.get(MeshOperationManager.class),o))gone++;
   for(Object o:oldParts)if(drop(s.get(SimulationPartManager.class),o))gone++;
   log.put("old_mesh_ops_and_parts_removed",gone);

   stage="overset region";
   Region ov=s.getRegionManager().createEmptyRegion();ov.setPresentationName("GODO overset foil");
   ov.setPhysicsContinuum(bg.getPhysicsContinuum());ov.getPartGroup().setObjects(List.of(ovp));
   BoundaryManager bm=ov.getBoundaryManager();
   List<Object> defaults=new ArrayList<>(bm.getBoundaries());
   Boundary fMain=bm.createEmptyBoundary("foil_main"),fFlap=bm.createEmptyBoundary("foil_flap"),sp0=bm.createEmptyBoundary("ov_span_front"),sp1=bm.createEmptyBoundary("ov_span_back"),ovb=bm.createEmptyBoundary("overset");
   fMain.copyProperties(oldMain);fFlap.copyProperties(oldFlap);sp0.copyProperties(ob.get("span_front"));sp1.copyProperties(ob.get("span_back"));
   ovb.setBoundaryType(OversetMeshBoundary.class);
   fMain.getPartSurfaceGroup().setObjects(os.get("Main"));fFlap.getPartSurfaceGroup().setObjects(os.get("Flap"));
   sp0.getPartSurfaceGroup().setObjects(os.get("Span0"));sp1.getPartSurfaceGroup().setObjects(os.get("Span1"));ovb.getPartSurfaceGroup().setObjects(os.get("Overset"));
   for(Object o:defaults)drop(bm,o);
   log.put("overset_boundaries",bm.getBoundaries().stream().map(b->b.getPresentationName()+":"+b.getBoundaryType().getClass().getSimpleName()).toList());

   stage="reports re-point";
   int rp=0;List<String> rpn=new ArrayList<>();
   for(Report r:s.getReportManager().getObjects()){
    try{Object g=r.getClass().getMethod("getParts").invoke(r);
     Collection<?> cur=(Collection<?>)g.getClass().getMethod("getObjects").invoke(g);
     if(cur.contains(oldMain)||cur.contains(oldFlap)||cur.contains(bg)&&r.getPresentationName().equals("GODO_interfaceCFL")){
      List<NamedObject> nw=new ArrayList<>();
      for(Object o:cur){if(o==oldMain)nw.add(fMain);else if(o==oldFlap)nw.add(fFlap);else nw.add((NamedObject)o);}
      if(r.getPresentationName().equals("GODO_interfaceCFL"))nw.add(ov);
      g.getClass().getMethod("setObjects",Collection.class).invoke(g,nw);rp++;rpn.add(r.getPresentationName());}
    }catch(NoSuchMethodException e){}catch(Throwable e){log.put("repoint_"+r.getPresentationName(),e.toString());}
   }
   log.put("reports_repointed",rpn);
   for(Boundary b:List.of(oldMain,oldFlap))if(!drop(bg.getBoundaryManager(),b))log.put("old_boundary_left",b.getPresentationName());

   stage="mesh";
   double x0=d("x0_m",-46.839),xd=d("band_x1_m",78.06);
   // background: polygonal only (no walls), refined free-surface band + overset travel zone (heave +-0.75 m + box)
   DirectedMeshOperation mb=directed(bgp,bs,"GODO background directed mesh (Base Size)",false,B);
   DirectedAutoSourceMesh ab=lastSource(mb);
   ab.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100);
   ab.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*d("bg_min_pct",.005));
   ab.getDefaultValues().get(SurfaceGrowthRate.class).setGrowthRate(1.2);
   double tz=d("travel_cell_pct",1.0);
   volume(ab,"GODO free-surface band (7.5 % B)",new double[]{x0-1,yfs-0.8*H,-.01},new double[]{xd,yfs+0.8*H,.03},100*.075);
   volume(ab,"GODO free-surface transition (15 % B)",new double[]{x0-1,yfs-1.6*H,-.01},new double[]{xd+15,yfs+1.6*H,.03},100*.15);
   volume(ab,"GODO overset travel zone ("+tz+" % B)",new double[]{d("tz_x0",-.35),d("tz_y0",-.95),-.01},new double[]{d("tz_x1",1.0),d("tz_y1",.95),.03},tz);
   volume(ab,"GODO travel-zone transition ("+(2*tz)+" % B)",new double[]{d("tz_x0",-.35)-.4,d("tz_y0",-.95)-.3,-.01},new double[]{d("tz_x1",1.0)+1.5,d("tz_y1",.95)+.3,.03},2*tz);
   ab.updateAutoSourceMesh();mb.stopEditingDirectedMeshOperation();
   // overset: foil prisms (y+ ~50, same as fixed-foil study), foil neighbourhood, outer cells = travel-zone size
   DirectedMeshOperation mo=directed(ovp,os,"GODO overset directed mesh (Base Size)",true,B);
   DirectedAutoSourceMesh ao=lastSource(mo);
   ao.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(tz);
   ao.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026);
   ao.getDefaultValues().get(SurfaceGrowthRate.class).setGrowthRate(1.15);
   ao.getDefaultValues().get(NumPrismLayers.class).setNumLayers(3);
   ao.getDefaultValues().get(PrismThickness.class).setAbsoluteSize(d("prism_total_m",6.79e-4),m);
   ao.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.18);
   SurfaceCustomMeshControl foil=ao.getCustomMeshControls().createSurfaceControl();foil.setPresentationName("GODO foil wall size (0.236 % B)");foil.getGeometryObjects().setObjects(os.get("Main"),os.get("Flap"));
   foil.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
   foil.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*.00236);
   SurfaceCustomMeshControl nop=ao.getCustomMeshControls().createSurfaceControl();nop.setPresentationName("GODO no prisms on overset/span");nop.getGeometryObjects().setObjects(os.get("Overset"),os.get("Span0"),os.get("Span1"));
   nop.getCustomConditions().get(PartsCustomizePrismMesh.class).getCustomPrismOptions().setSelected(PartsCustomPrismsOption.Type.DISABLE);
   volume(ao,"GODO foil neighbourhood (0.66 % B)",new double[]{-.0786,-.06,-.01},new double[]{.40,.06,.03},100*.0066);
   ao.updateAutoSourceMesh();mo.stopEditingDirectedMeshOperation();
   long t0=System.nanoTime();mb.execute();mo.execute();log.put("mesh_seconds",(System.nanoTime()-t0)/1e9);
   FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   log.put("cells_total",fv.getCellCount());


   stage="interface";
   Object itf=s.getInterfaceManager().createIndirectRegionInterface(bg,ov,"Overset Mesh",false);
   ((NamedObject)itf).setPresentationName("GODO overset interface");
   log.put("interface",itf.getClass().getSimpleName());

   stage="dfbi";
   double mass=d("mass_kg",12500.0/(25.6*.312)*.02);
   param("GODO_Pitch_trim_deg",d("pitch_trim_deg",0));
   if(!s.getFieldFunctionManager().has("AF_Cycle_Command"))uff("AF_Cycle_Command","0");
   // nose-up positive pitch [deg] = trim + controller command; STAR +z rotation lifts the trailing edge (nose-down)
   uff("GODO_Pitch_deg","${GODO_Pitch_trim_deg}+$AF_Cycle_Command");
   UserFieldFunction ang=uff("GODO_PitchAngle_rad","-$GODO_Pitch_deg*3.141592653589793/180");
   BodyManager bman;
   try{bman=s.get(BodyManager.class);}catch(Throwable e){bman=(BodyManager)s.get(DfbiManager.class).getChild(DfbiChild.ChildType.BODY_MANAGER);}
   ContinuumBody body=bman.createContinuumBody(true);body.setPresentationName("GODO foil body");
   body.getBodySurface().setObjects(fMain,fFlap);
   body.getBodyProperties().setMass(mass);
   body.getBodyProperties().setReleaseTime(d("release_time_s",1.9368));
   body.getBodyProperties().setRampTime(d("ramp_time_s",0.5));
   body.setInitialCMS(new DoubleVector(new double[]{px,py,zmid}));
   body.setMomentsOfInertia(new DoubleVector(new double[]{1,1,1}));
   body.getMotionOption().setSelected(BodyMotionOption.Type.FREE_MOTION);
   BodyFreeMotion fr=(BodyFreeMotion)body.getMotionType();
   fr.setFreeTranslationX(false);fr.setFreeTranslationY(true);fr.setFreeTranslationZ(false);
   fr.setFreeRotationX(false);fr.setFreeRotationY(false);fr.setFreeRotationZ(false);
   Motion bmot=body.createSixDofBodyMotion();
   ov.getValues().get(MotionSpecification.class).setMotion(bmot);
   SuperposingRotatingMotion sr=((SixDofMotion)bmot).getSuperposingMotionManager().createSuperposingMotion(SuperposingRotatingMotion.class,"GODO foil pitch (superposed, angle from controller)");
   sr.getRotationSpecificationOption().setSelected(RotationSpecificationOption.Type.RotationAngle);
   ((RotationAngle)sr.getRotationSpecification()).setRotationAngleFunction(ang);
   sr.setCoordinateSystem(body.getCurrentCoordinateSystem());
   sr.getAxisDirection().setComponents(0,0,1);sr.getAxisOrigin().setComponents(0,0,0);
   log.put("dfbi",Map.of("mass_kg",mass,"release_s",d("release_time_s",1.9368),"motion",bmot.getPresentationName(),"superposed",sr.getPresentationName(),"body_cs",body.getCurrentCoordinateSystem().getPresentationName()));

   stage="reports";
   List<Monitor> mons=new ArrayList<>();
   TranslationReport tr=s.getReportManager().createReport(TranslationReport.class);tr.setPresentationName("GODO_heave_m");tr.setBody(body);tr.getDirection().setComponents(0,1,0);mons.add(mon(tr));
   LinearVelocityReport lv=s.getReportManager().createReport(LinearVelocityReport.class);lv.setPresentationName("GODO_heave_velocity");lv.setBody(body);lv.getDirection().setComponents(0,1,0);mons.add(mon(lv));
   ExpressionReport pr=s.getReportManager().createReport(ExpressionReport.class);pr.setPresentationName("GODO_pitch_deg");pr.setDefinition("${GODO_Pitch_trim_deg}+$AF_Cycle_Command");mons.add(mon(pr));
   MomentReport mp=s.getReportManager().createReport(MomentReport.class);mp.setPresentationName("GODO_M_pivot");mp.getParts().setObjects(fMain,fFlap);
   mp.setCoordinateSystem(body.getCurrentCoordinateSystem());mp.getOrigin().setComponents(0,0,0);mp.getDirection().setComponents(0,0,-1);mons.add(mon(mp));   // + = nose-up moment
   ForceReport fy=s.getReportManager().createReport(ForceReport.class);fy.setPresentationName("GODO_Fy_fluid");fy.getParts().setObjects(fMain,fFlap);fy.getDirection().setComponents(0,1,0);mons.add(mon(fy));
   ExpressionReport wt=s.getReportManager().createReport(ExpressionReport.class);wt.setPresentationName("GODO_lift_over_weight");wt.setDefinition("${GODO_Fy_fluidReport}/"+(mass*9.81));mons.add(mon(wt));
   try{s.getPlotManager().createMonitorPlot(List.of(mons.get(0),mons.get(1)),"GODO 01 - heave [m] and heave velocity [m/s]");
       s.getPlotManager().createMonitorPlot(List.of(mons.get(2)),"GODO 02 - pitch angle [deg, nose-up +]");
       s.getPlotManager().createMonitorPlot(List.of(mons.get(3)),"GODO 03 - pitching moment about pivot [N m, nose-up +]");
       s.getPlotManager().createMonitorPlot(List.of(mons.get(5)),"GODO 04 - lift / weight");}catch(Throwable e){log.put("plot_warning",e.toString());}
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);us.getTimeStep().setValue(d("dt_s",1e-3));
   s.saveState(out.resolve("GODO_OVERSET_SETUP_B"+B+".sim").toString());
   write("GODO_OVERSET.json",log);
   if(!cfg.getProperty("mode","mesh").equals("probe"))return;

   stage="probe";
   body.getBodyProperties().setReleaseTime(d("probe_release_s",0.005));
   s.getSolution().initializeSolution();
   GlobalParameterManager gm=s.get(GlobalParameterManager.class);
   int n=i("probe_steps",40);List<Double> sec=new ArrayList<>();
   try(BufferedWriter h=Files.newBufferedWriter(out.resolve("overset_probe.csv"))){
    h.write("step,time_s,solver_s,pitch_deg,heave_m,heave_v,CL,CD,M_pivot,lift_over_weight,interfaceCFL\n");
    for(int k=1;k<=n;k++){
     double tt=s.getSolution().getPhysicalTime();
     double cmd=Math.min(1.0,tt/0.02)*d("probe_pitch_deg",1.0);       // 1 deg nose-up ramp in 20 ms (50 deg/s)
     if(gm.has("FC_Delta_Prev_deg")){param("FC_Delta_Prev_deg",cmd);param("FC_Delta_Next_deg",cmd);}
     else uff("AF_Cycle_Command",""+cmd);
     long b0=System.nanoTime();s.getSimulationIterator().step(1);double w=(System.nanoTime()-b0)/1e9;sec.add(w);
     h.write(k+","+s.getSolution().getPhysicalTime()+","+w+","+rv("GODO_pitch_deg")+","+rv("GODO_heave_m")+","+rv("GODO_heave_velocity")+","+rv("AF_CL")+","+rv("AF_CD")+","+rv("GODO_M_pivot")+","+rv("GODO_lift_over_weight")+","+rv("GODO_interfaceCFL")+"\n");h.flush();
     if(!Double.isFinite(rv("AF_CL")))throw new IllegalStateException("non-finite CL at step "+k);
    }
   }
   double mean=sec.subList(Math.min(5,sec.size()-1),sec.size()).stream().mapToDouble(x->x).average().orElse(Double.NaN);
   log.put("probe_steps",n);log.put("solver_s_per_step",mean);log.put("final_pitch_deg",rv("GODO_pitch_deg"));log.put("final_heave_m",rv("GODO_heave_m"));log.put("lift_over_weight",rv("GODO_lift_over_weight"));
   write("OVERSET_PROBE.json",log);
   s.saveState(out.resolve("GODO_OVERSET_PROBE_END_B"+B+".sim").toString());
  }catch(Throwable e){
   try{log.put("stage",stage);log.put("error",e.toString());StringWriter sw=new StringWriter();e.printStackTrace(new PrintWriter(sw));log.put("trace",sw.toString().substring(0,Math.min(2500,sw.toString().length())));write("ERROR.json",log);}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
 ReportMonitor mon(Report r){ReportMonitor rm=r.createMonitor();rm.setPresentationName(r.getPresentationName()+" Monitor");
  try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){}return rm;}
 DirectedMeshOperation directed(GeometryPart p,Map<String,PartSurface> sf,String name,boolean prisms,double B){
  DirectedMeshOperation mesh=(DirectedMeshOperation)s.get(MeshOperationManager.class).createDirectedMeshOperation(List.of(p));
  mesh.setPresentationName(name);mesh.getSourceSurfaceGroup().setObjects(sf.get("Span0"));mesh.getTargetSurfaceGroup().setObjects(sf.get("Span1"));
  mesh.editDirectedMeshOperation();
  List<DirectedMeshPartCollection> col=new ArrayList<>(mesh.getDirectedMeshPartCollectionManager().getObjects());
  for(DirectedMeshPartCollection c:col){c.setTargetSmoothOption(false);c.setEnhanceCellQualityOption(false);}
  List<String> meshers=prisms?List.of("star.twodmesher.DualAutoMesher2d","star.prismmesher.PrismAutoMesher"):List.of("star.twodmesher.DualAutoMesher2d");
  DirectedAutoSourceMesh a=mesh.getDirectedSurfaceMeshBaseManager().createAutoSourceMesh(meshers,col);
  a.setPresentationName(name+" - source");a.getDefaultValues().get(BaseSize.class).setValue(B);
  DirectedMeshDistribution dist=mesh.getDirectedMeshDistributionManager().createDirectedMeshDistribution(col);
  dist.getDefaultValues().get(DirectedMeshNumLayers.class).setNumLayers(1);
  return mesh;
 }
 DirectedAutoSourceMesh lastSource(DirectedMeshOperation mesh){
  DirectedAutoSourceMesh r=null;for(Object o:mesh.getDirectedSurfaceMeshBaseManager().getObjects())if(o instanceof DirectedAutoSourceMesh a)r=a;return r;
 }
 void volume(DirectedAutoSourceMesh a,String name,double[] lo,double[] hi,double pct){
  SimpleBlockPart p=s.get(MeshPartFactory.class).createNewBlockPart(s.getGeometryPartManager());
  p.setPresentationName(name);p.setCorners(new DoubleVector(lo),new DoubleVector(hi));p.rebuildSimpleShapePart();
  VolumeCustomMeshControl c=a.getCustomMeshControls().createVolumeControl();
  c.setPresentationName(name);c.getGeometryObjects().setObjects(p);
  for(Object v:c.getCustomConditions().getChildren())if(v instanceof VolumeControlBase st)st.setVolumeControlBaseSizeOption(true);
  c.getCustomValues().get(VolumeControlSize.class).setRelativeSize(pct);
 }
}
