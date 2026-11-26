package macro;
import star.motion.*;import star.meshing.*;import star.common.*;import star.vis.*;import star.metrics.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.vof.*;import star.sixdof.*;import star.prismmesher.*;import star.resurfacer.*;import star.sweptmesher.*;import star.twodmesher.*;
import java.io.*;import java.nio.file.*;import java.util.*;

/**
 * BuildGodoOverset - Godø reproduction with a ROTATING WHOLE FOIL and FREE HEAVE, native STAR-CCM+ (2606), built on a copy
 * of the verified fixed-foil Godø setup (same VOF / SST / 5th-order Stokes wave / forcing+damping / reports).
 *
 * GUI objects created (all editable):
 *  Regions      "GODO background" (wave tank, old region renamed) + "GODO overset (foil)" ; interface "GODO overset interface"
 *  Mesh ops     "GODO-OS background directed mesh" (travel-zone refinement covering heave +-0.75 m) and
 *               "GODO-OS overset directed mesh" (foil prisms, wake) - both sized relative to their Base Size
 *  DFBI         body "GODO foil body" : 1-DOF translating (heave, +y), mass = strip of Godø's 12.5 t vessel
 *               motion "GODO heave (DFBI)" on the overset region, superposed rotation "GODO pitch (controller)"
 *  Parameters   GODO_Pitch_Prev_deg, GODO_Pitch_Next_deg, GODO_Pitch_T0_s, GODO_Pitch_Tick_s  (controller writes these)
 *  Field fns    GODO_Pitch_Cmd_deg (linear between ticks), GODO_Pitch_Rate_rad_s (rotation rate of the superposed motion,
 *               positive = nose up)
 *  Reports      AF_Fx/AF_Fz/AF_CL/AF_CD on the foil, AF_Mh = moment about the pivot (body frame), GODO_heave_m,
 *               GODO_Pitch_Cmd_deg, GODO_P_act_W = max(0, -Mh*rate), y+ reports, interface CFL, wave gauges
 * Modes: mode=mesh (build + save GODO_OS_SETUP_B<B>.sim) ; mode=probe (+ initialise + probe_steps steps -> OS_PROBE.json)
 */
public class BuildGodoOverset extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties(); Units m; Map<String,Object> log=new LinkedHashMap<>();
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
 boolean drop(Object mgr,Object obj){
  for(String mth:new String[]{"removeObjects","remove","deleteChildren","removeBoundaries"}){
   for(java.lang.reflect.Method mm:mgr.getClass().getMethods()){
    if(!mm.getName().equals(mth)||mm.getParameterCount()!=1)continue;
    try{Class<?> pt=mm.getParameterTypes()[0];
     if(pt.isArray()){Object arr=java.lang.reflect.Array.newInstance(pt.getComponentType(),1);java.lang.reflect.Array.set(arr,0,obj);mm.invoke(mgr,arr);}
     else if(Collection.class.isAssignableFrom(pt))mm.invoke(mgr,List.of(obj));
     else if(pt.isInstance(obj))mm.invoke(mgr,obj); else continue;
     return true;}catch(Throwable e){}
   }}
  return false;
 }
 ScalarGlobalParameter param(String name,double v,String unit){
  GlobalParameterManager gm=s.get(GlobalParameterManager.class);
  ScalarGlobalParameter p=gm.has(name)?(ScalarGlobalParameter)gm.getObject(name):(ScalarGlobalParameter)gm.createGlobalParameter(ScalarGlobalParameter.class,"Scalar");
  p.setPresentationName(name);
  if(unit!=null){p.setDimensions(unit.equals("s")?Dimensions.Builder().time(1).build():Dimensions.Builder().build());}
  p.getQuantity().setValue(v);return p;
 }
 UserFieldFunction uff(String name,String def){
  FieldFunctionManager fm=s.getFieldFunctionManager();
  UserFieldFunction f=fm.has(name)?(UserFieldFunction)fm.getFunction(name):fm.createFieldFunction();
  f.setPresentationName(name);f.setFunctionName(name);f.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);f.setDefinition(def);return f;
 }
 ReportMonitor mon(Report r){ReportMonitor rm=r.createMonitor();rm.setPresentationName(r.getPresentationName()+" Monitor");
  try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){}return rm;}
 GeometryPart importPart(String stl,String name){
  SimulationPartManager pm=s.get(SimulationPartManager.class);
  Set<GeometryPart> before=new HashSet<>(pm.getLeafParts());
  s.get(PartImportManager.class).importStlPart(out.resolve(stl).toString(),"OneSurfacePerPatch",m,true,1e-8);
  List<GeometryPart> added=new ArrayList<>(pm.getLeafParts());added.removeAll(before);
  if(added.size()!=1)throw new IllegalStateException("Expected one new part from "+stl);
  added.get(0).setPresentationName(name);return added.get(0);
 }
 Map<String,PartSurface> surf(GeometryPart p){Map<String,PartSurface> m2=new LinkedHashMap<>();for(PartSurface ps:p.getPartSurfaces())m2.put(ps.getPresentationName(),ps);return m2;}
 void volume(DirectedAutoSourceMesh a,String name,double[] lo,double[] hi,double pct){
  SimpleBlockPart p=s.get(MeshPartFactory.class).createNewBlockPart(s.getGeometryPartManager());
  p.setPresentationName(name);p.setCorners(new DoubleVector(lo),new DoubleVector(hi));p.rebuildSimpleShapePart();
  VolumeCustomMeshControl c=a.getCustomMeshControls().createVolumeControl();
  c.setPresentationName(name);c.getGeometryObjects().setObjects(p);
  for(Object v:c.getCustomConditions().getChildren())if(v instanceof VolumeControlBase st)st.setVolumeControlBaseSizeOption(true);
  c.getCustomValues().get(VolumeControlSize.class).setRelativeSize(pct);
 }
 DirectedMeshOperation directed(String name,GeometryPart part,PartSurface src,PartSurface tgt){
  DirectedMeshOperation op=(DirectedMeshOperation)s.get(MeshOperationManager.class).createDirectedMeshOperation(List.of(part));
  op.setPresentationName(name);op.getSourceSurfaceGroup().setObjects(src);op.getTargetSurfaceGroup().setObjects(tgt);
  op.editDirectedMeshOperation();return op;
 }
 double metric(String name,NamedObject part,boolean minimum){
  AnalysisReport q2=minimum?s.getReportManager().createReport(MinReport.class):s.getReportManager().createReport(MaxReport.class);
  FieldFunction f=ff(name);if(q2 instanceof MinReport low)low.setFieldFunction(f);else ((MaxReport)q2).setFieldFunction(f);
  q2.getParts().setObjects(part);q2.setSmooth(false);q2.setPresentationName("GODO-OS mesh "+(minimum?"min ":"max ")+name+" "+part.getPresentationName());
  return q2.getReportMonitorValue();
 }
 void scene(String name,List<Boundary> caps,FvRepresentation fv,double x,double y,double scale,String png){
  try{Scene sc=s.getSceneManager().createScene(name);sc.setPresentationName(name);sc.initializeAndWait();
   PartDisplayer pd=sc.getDisplayerManager().createPartDisplayer("Span faces and mesh");
   pd.getInputParts().setObjects(caps);pd.setRepresentation(fv);pd.setMesh(true);pd.setOutline(true);
   sc.getCurrentView().setInput(new DoubleVector(new double[]{x,y,0}),new DoubleVector(new double[]{x,y,5}),new DoubleVector(new double[]{0,1,0}),scale,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
   sc.printAndWait(out.resolve(png).toString(),1,1600,900);}catch(Throwable e){log.put("scene_"+png,e.toString());}
 }

 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  String stage="init";
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   m=s.getUnitsManager().getObject("m");
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   Region bg=s.getRegionManager().getRegion("MINI_water_air");
   if(bg==null)throw new IllegalStateException("source is not a GODO_SETUP sim");
   FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   PhysicsContinuum pc=bg.getPhysicsContinuum();
   double B=d("base_size_m",1.0),C=d("chord_m",.312),yfs=d("free_surface_y_m",1.09),H=d("H_m",1.5);
   double x0=d("x0_m",-46.839),xd=d("band_x1_m",78.06),U=d("U_m_s",12.346666666666666);
   double px=d("pivot_x_m",.078),py=d("pivot_y_m",0),mass=d("strip_mass_kg",31.30008),hov=d("overset_cell_pct",.66);
   double[] tz={d("travel_x0_m",-.25),d("travel_x1_m",.65),d("travel_y0_m",-.95),d("travel_y1_m",.95)};
   s.getSolution().clearSolution(Solution.Clear.Fields,Solution.Clear.History);

   stage="geometry";
   Set<GeometryPart> oldParts=new HashSet<>(s.get(SimulationPartManager.class).getLeafParts());
   GeometryPart bgp=importPart("GodoBackground.stl","GODO-OS background tank (no foil)");
   GeometryPart ovp=importPart("GodoOverset.stl","GODO-OS overset block with Godø section (66-012 MOD + a=0.8, CLi 0.63)");
   Map<String,PartSurface> sb=surf(bgp),so=surf(ovp);
   Map<String,Boundary> bnd=new LinkedHashMap<>();for(Boundary b:bg.getBoundaryManager().getBoundaries())bnd.put(b.getPresentationName().toLowerCase(Locale.ROOT),b);
   bg.setPresentationName("GODO background");
   bg.getPartGroup().setObjects(List.of(bgp));
   Map<String,String> links=Map.of("inlet","Inlet","outlet","Outlet","bottom","Bottom","top","Top","span_front","Span0","span_back","Span1");
   for(var e:links.entrySet())bnd.get(e.getKey()).getPartSurfaceGroup().setObjects(sb.get(e.getValue()));

   stage="overset region";
   Region ov=s.getRegionManager().createEmptyRegion();ov.setPresentationName("GODO overset (foil)");ov.setPhysicsContinuum(pc);
   ov.getPartGroup().setObjects(List.of(ovp));
   BoundaryManager obm=ov.getBoundaryManager();
   Boundary foil=obm.createEmptyBoundary("Foil");foil.getPartSurfaceGroup().setObjects(so.get("Foil"));
   Boundary ob=obm.createEmptyBoundary("Overset");ob.getPartSurfaceGroup().setObjects(so.get("Overset"));ob.setBoundaryType(OversetMeshBoundary.class);
   Boundary s0=obm.createEmptyBoundary("span_front");s0.getPartSurfaceGroup().setObjects(so.get("Span0"));
   Boundary s1=obm.createEmptyBoundary("span_back");s1.getPartSurfaceGroup().setObjects(so.get("Span1"));
   s0.setBoundaryType(bnd.get("span_front").getBoundaryType().getClass());s1.setBoundaryType(bnd.get("span_back").getBoundaryType().getClass());
   log.put("span_type",bnd.get("span_front").getBoundaryType().getClass().getSimpleName());
   try{for(Boundary b0:obm.getBoundaries())if(b0.getPartSurfaceGroup().getObjects().isEmpty()&&b0!=foil&&b0!=ob&&b0!=s0&&b0!=s1)drop(obm,b0);}catch(Throwable e){}

   stage="reports to foil";
   List<Boundary> fl=List.of(foil);
   for(Report r:s.getReportManager().getObjects()){
    try{if(r instanceof ForceReport fr){fr.getParts().setObjects(fl);}
     else if(r instanceof MomentReport mr){mr.getParts().setObjects(fl);}
     else if(r.getPresentationName().startsWith("GODO_yplus")||r.getPresentationName().equals("AF_Flap_pAbs_Min")){((AnalysisReport)r).getParts().setObjects(fl);}
     else if(r.getPresentationName().equals("GODO_interfaceCFL")){((AnalysisReport)r).getParts().setObjects(List.of(bg,ov));}
    }catch(Throwable e){log.put("report_"+r.getPresentationName(),e.toString());}
   }
   for(String k:new String[]{"main","flap"}){Boundary b0=bnd.get(k);if(b0!=null){b0.getPartSurfaceGroup().setObjects();if(!drop(bg.getBoundaryManager(),b0))log.put("drop_"+k,"refused");}}
   // remove the fixed-foil geometry + its mesh operation (not used any more)
   for(Object o:new ArrayList<>(s.get(MeshOperationManager.class).getObjects()))drop(s.get(MeshOperationManager.class),o);
   for(GeometryPart g:oldParts)if(!(g instanceof SimpleBlockPart))drop(s.get(SimulationPartManager.class),g);

   stage="mesh background";
   DirectedMeshOperation mb=directed("GODO-OS background directed mesh - one span layer (sizes relative to Base Size)",bgp,sb.get("Span0"),sb.get("Span1"));
   List<DirectedMeshPartCollection> cb=new ArrayList<>(mb.getDirectedMeshPartCollectionManager().getObjects());
   DirectedAutoSourceMesh ab=mb.getDirectedSurfaceMeshBaseManager().createAutoSourceMesh(List.of("star.twodmesher.DualAutoMesher2d"),cb);
   ab.setPresentationName("GODO-OS background polygonal source");
   ab.getDefaultValues().get(BaseSize.class).setValue(B);
   ab.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100);
   ab.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*hov/100*0.5);
   ab.getDefaultValues().get(SurfaceGrowthRate.class).setGrowthRate(1.2);
   volume(ab,"GODO-OS free-surface band (7.5 % B)",new double[]{x0-1,yfs-0.8*H,-.01},new double[]{xd,yfs+0.8*H,.03},100*.075);
   volume(ab,"GODO-OS free-surface transition (15 % B)",new double[]{x0-1,yfs-1.6*H,-.01},new double[]{xd+15,yfs+1.6*H,.03},100*.15);
   volume(ab,"GODO-OS overset travel zone (matches overset outer cells)",new double[]{tz[0],tz[2],-.01},new double[]{tz[1],tz[3],.03},hov);
   DirectedMeshDistribution db=mb.getDirectedMeshDistributionManager().createDirectedMeshDistribution(cb);
   db.getDefaultValues().get(DirectedMeshNumLayers.class).setNumLayers(1);
   ab.updateAutoSourceMesh();mb.stopEditingDirectedMeshOperation();

   stage="mesh overset";
   DirectedMeshOperation mo=directed("GODO-OS overset directed mesh - foil prisms (sizes relative to Base Size)",ovp,so.get("Span0"),so.get("Span1"));
   List<DirectedMeshPartCollection> co=new ArrayList<>(mo.getDirectedMeshPartCollectionManager().getObjects());
   for(DirectedMeshPartCollection c:co){c.setTargetSmoothOption(false);c.setEnhanceCellQualityOption(false);}
   DirectedAutoSourceMesh ao=mo.getDirectedSurfaceMeshBaseManager().createAutoSourceMesh(List.of("star.twodmesher.DualAutoMesher2d","star.prismmesher.PrismAutoMesher"),co);
   ao.setPresentationName("GODO-OS overset polygonal source - foil prisms, wake");
   ao.getDefaultValues().get(BaseSize.class).setValue(B);
   ao.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(hov);
   ao.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026);
   ao.getDefaultValues().get(SurfaceGrowthRate.class).setGrowthRate(1.2);
   ao.getDefaultValues().get(NumPrismLayers.class).setNumLayers(3);
   ao.getDefaultValues().get(PrismThickness.class).setAbsoluteSize(d("prism_total_m",6.79e-4),m);
   ao.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.18);
   SurfaceCustomMeshControl fw=ao.getCustomMeshControls().createSurfaceControl();fw.setPresentationName("GODO-OS foil wall size (0.236 % B)");fw.getGeometryObjects().setObjects(so.get("Foil"));
   fw.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
   fw.getCustomConditions().get(PartsMinimumSurfaceSizeOption.class).setSelected(PartsMinimumSurfaceSizeOption.Type.CUSTOM);
   fw.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*.00236);
   fw.getCustomValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026);
   SurfaceCustomMeshControl np=ao.getCustomMeshControls().createSurfaceControl();np.setPresentationName("GODO-OS no prisms on overset boundary / span");
   np.getGeometryObjects().setObjects(List.of(so.get("Overset"),so.get("Span0"),so.get("Span1")));
   np.getCustomConditions().get(PartsCustomizePrismMesh.class).getCustomPrismOptions().setSelected(PartsCustomPrismsOption.Type.DISABLE);
   SurfaceCustomMeshControl ob2=ao.getCustomMeshControls().createSurfaceControl();ob2.setPresentationName("GODO-OS overset boundary size (= travel zone)");ob2.getGeometryObjects().setObjects(so.get("Overset"));
   ob2.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
   ob2.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(hov);
   volume(ao,"GODO-OS foil neighbourhood (0.33 % B)",new double[]{-.03,-.03,-.01},new double[]{.40,.05,.03},hov/2);
   DirectedMeshDistribution dov=mo.getDirectedMeshDistributionManager().createDirectedMeshDistribution(co);
   dov.getDefaultValues().get(DirectedMeshNumLayers.class).setNumLayers(1);
   ao.updateAutoSourceMesh();mo.stopEditingDirectedMeshOperation();
   long tm=System.nanoTime();mb.execute();mo.execute();log.put("mesh_seconds",(System.nanoTime()-tm)/1e9);
   List<Region> regs=List.of(bg,ov);
   int orient=s.get(MeshManager.class).checkFaceOrientation(regs);if(orient>0)s.get(MeshManager.class).repairFaceOrientation(regs);
   log.put("cells_total",fv.getCellCount());
   for(Region r:regs){log.put("minQ_"+r.getPresentationName(),metric("CellQuality",r,true));log.put("minV_"+r.getPresentationName(),metric("Volume",r,true));}

   stage="overset interface";
   IndirectRegionInterface ifc=s.getInterfaceManager().createIndirectRegionInterface(bg,ov,"Overset Mesh",false);
   ifc.setPresentationName("GODO overset interface");
   log.put("interface",ifc.getClass().getSimpleName()+" / "+ifc.getInterfaceType().getClass().getSimpleName());

   stage="pitch command";
   param("GODO_Pitch_Prev_deg",0,null);param("GODO_Pitch_Next_deg",0,null);param("GODO_Pitch_T0_s",0,"s");param("GODO_Pitch_Tick_s",0.01,"s");
   String tau="($Time-${GODO_Pitch_T0_s})";
   uff("GODO_Pitch_Cmd_deg","${GODO_Pitch_Prev_deg}+(${GODO_Pitch_Next_deg}-${GODO_Pitch_Prev_deg})*min(1,max(0,"+tau+"/${GODO_Pitch_Tick_s}))");
   UserFieldFunction rate=uff("GODO_Pitch_Rate_rad_s","("+tau+">-1e-9 && "+tau+"<${GODO_Pitch_Tick_s}-1e-9) ? (${GODO_Pitch_Next_deg}-${GODO_Pitch_Prev_deg})/${GODO_Pitch_Tick_s}*0.017453292519943295 : 0");
   rate.setDimensions(Dimensions.Builder().time(-1).build());

   stage="dfbi";
   BodyManager bm=s.get(BodyManager.class);
   ContinuumBody body=bm.createContinuumBody(true);body.setPresentationName("GODO foil body");
   body.getBodySurface().setObjects(foil);
   body.getMotionOption().setSelected(BodyMotionOption.Type.ONE_DOF_TRANSLATING_MOTION);
   OneDofTranslatingMotion hv=(OneDofTranslatingMotion)body.getMotionType();
   hv.getTranslationDirection().setComponents(0,1,0);
   try{hv.setMotionLimits(true);hv.getMinimumPosition().setValue(d("heave_min_m",-0.9));hv.getMaximumPosition().setValue(d("heave_max_m",0.9));}catch(Throwable e){log.put("heave_limits",e.toString());}
   body.getBodyProperties().setMass(mass);
   body.getBodyProperties().setReleaseTime(d("release_time_s",0.0));
   body.getBodyProperties().setRampTime(d("ramp_time_s",0.0));
   body.setInitialCMS(new DoubleVector(new double[]{px,py,0.01}));
   body.setMomentsOfInertia(new DoubleVector(new double[]{1,1,1}));
   Motion bmo=body.createSixDofBodyMotion();bmo.setPresentationName("GODO heave (DFBI 1-DOF)");
   ov.getValues().get(MotionSpecification.class).setMotion(bmo);
   SuperposingRotatingMotion rot=((SixDofBodyMotion)bmo).getSuperposingMotionManager().createSuperposingMotion(SuperposingRotatingMotion.class,"GODO pitch (controller rate, + = nose up)");
   rot.getRotationSpecificationOption().setSelected(RotationSpecificationOption.Type.RotationRate);
   ((RotationRate)rot.getRotationSpecification()).getRotationRate().setDefinition("$GODO_Pitch_Rate_rad_s");
   rot.getAxisDirection().setComponents(0,0,-1);           // nose up = clockwise seen from +z (flow +x, LE at x = 0)
   rot.getAxisOrigin().setComponents(px,py,0.01);
   log.put("pitch_cs",rot.getCoordinateSystem()==null?"null":rot.getCoordinateSystem().getPresentationName());
   log.put("body_cs",body.getCurrentCoordinateSystem().getPresentationName());

   stage="reports";
   double qd=0.5*1000*U*U*C*.02, fb=d("foil_buoyancy_N",1.6037), W=mass*9.81;
   for(String[] r:new String[][]{{"AF_CL","(${AF_FzReport}-"+fb+")/"+qd},{"AF_CD","${AF_FxReport}/"+qd}}){Report rp=s.getReportManager().getReport(r[0]);if(rp instanceof ExpressionReport er)er.setDefinition(r[1]);}
   for(Report r:s.getReportManager().getObjects())if(r instanceof MomentReport mr){
    try{mr.setCoordinateSystem(body.getCurrentCoordinateSystem());mr.getOrigin().setComponents(0,0,0);mr.getDirection().setComponents(0,0,-1);log.put("moment_report",mr.getPresentationName()+" about body CS origin (pivot), +nose-up");}
    catch(Throwable e){log.put("moment_report_error",e.toString());}}
   AreaAverageReport hy=s.getReportManager().createReport(AreaAverageReport.class);hy.setPresentationName("GODO_foil_centroid_y_m");
   hy.setFieldFunction(((PrimitiveFieldFunction)ff("Position")).getComponentFunction(1));hy.getParts().setObjects(fl);
   ExpressionReport cmd=s.getReportManager().createReport(ExpressionReport.class);cmd.setPresentationName("GODO_Pitch_Cmd_deg");
   cmd.setDefinition("${GODO_Pitch_Prev_deg}+(${GODO_Pitch_Next_deg}-${GODO_Pitch_Prev_deg})*min(1,max(0,($Time-${GODO_Pitch_T0_s})/${GODO_Pitch_Tick_s}))");
   ExpressionReport pact=s.getReportManager().createReport(ExpressionReport.class);pact.setPresentationName("GODO_P_act_W");
   pact.setDefinition("max(0,-${AF_MhReport}*((($Time-${GODO_Pitch_T0_s})>-1e-9&&($Time-${GODO_Pitch_T0_s})<${GODO_Pitch_Tick_s}-1e-9)?(${GODO_Pitch_Next_deg}-${GODO_Pitch_Prev_deg})/${GODO_Pitch_Tick_s}*0.017453292519943295:0))");
   ExpressionReport lw=s.getReportManager().createReport(ExpressionReport.class);lw.setPresentationName("GODO_lift_minus_weight_N");lw.setDefinition("${AF_FzReport}-"+W);
   ExpressionReport pd=s.getReportManager().createReport(ExpressionReport.class);pd.setPresentationName("GODO_P_drag_W");pd.setDefinition(U+"*${AF_FxReport}");
   List<Monitor> ms=new ArrayList<>();for(Report r:List.of(hy,cmd,pact,lw,pd))ms.add(mon(r));
   try{s.getPlotManager().createMonitorPlot(List.of(ms.get(0)),"GODO-OS heave: foil centroid y [m]");
       s.getPlotManager().createMonitorPlot(List.of(ms.get(1)),"GODO-OS pitch command [deg]");
       s.getPlotManager().createMonitorPlot(List.of(ms.get(2),ms.get(4)),"GODO-OS power: actuator demand and drag power [W]");
       s.getPlotManager().createMonitorPlot(List.of(ms.get(3)),"GODO-OS lift - weight [N]");}catch(Throwable e){log.put("plots",e.toString());}
   log.put("strip_mass_kg",mass);log.put("strip_weight_N",W);log.put("q_N",qd);

   scene("GODO-OS mesh 01 - foil + overset block",List.of(s0,bnd.get("span_front")),fv,.18,0,.35,"OS_MESH_FOIL.png");
   scene("GODO-OS mesh 02 - travel zone and free surface",List.of(s0,bnd.get("span_front")),fv,.2,.6,2.5,"OS_MESH_ZONE.png");
   s.saveState(out.resolve("GODO_OS_SETUP_B"+B+".sim").toString());
   write("OS_SETUP.json",log);
   if(!cfg.getProperty("mode","mesh").equals("probe"))return;

   stage="probe";
   s.getSolution().initializeSolution();
   int n=i("probe_steps",30);double y0c=rv("GODO_foil_centroid_y_m");
   double amp=d("probe_pitch_deg",0),tick=d("tick_s",0.01);
   try(BufferedWriter h=Files.newBufferedWriter(out.resolve("os_probe_history.csv"))){
    h.write("step,time_s,solver_s,CL,CD,Fz_N,Mh_Nm,heave_m,pitch_cmd_deg,P_act_W,interfaceCFL\n");
    double prev=0;
    for(int k=1;k<=n;k++){
     double t=s.getSolution().getPhysicalTime();
     if(amp!=0&&(k-1)%Math.max(1,(int)Math.round(tick/1e-3))==0){   // scripted pitch ramp for the probe: 0 -> amp in 0.05 s, hold
      double next=Math.min(amp,prev+amp*tick/0.05);
      ((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject("GODO_Pitch_Prev_deg")).getQuantity().setValue(prev);
      ((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject("GODO_Pitch_Next_deg")).getQuantity().setValue(next);
      ((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject("GODO_Pitch_T0_s")).getQuantity().setValue(t);
      ((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject("GODO_Pitch_Tick_s")).getQuantity().setValue(tick);
      prev=next;}
     long b0=System.nanoTime();s.getSimulationIterator().step(1);double sec=(System.nanoTime()-b0)/1e9;
     h.write(k+","+s.getSolution().getPhysicalTime()+","+sec+","+rv("AF_CL")+","+rv("AF_CD")+","+rv("AF_Fz")+","+rv("AF_Mh")+","+(rv("GODO_foil_centroid_y_m")-y0c)+","+rv("GODO_Pitch_Cmd_deg")+","+rv("GODO_P_act_W")+","+rv("GODO_interfaceCFL")+"\n");h.flush();
    }
   }
   log.put("probe_steps",n);write("OS_PROBE.json",log);
   s.saveState(out.resolve("GODO_OS_PROBE_END_B"+B+".sim").toString());
  }catch(Throwable e){
   try{log.put("stage",stage);StringWriter sw=new StringWriter();e.printStackTrace(new PrintWriter(sw));log.put("error",e.toString());log.put("trace",sw.toString().substring(0,Math.min(3000,sw.toString().length())));write("ERROR.json",log);}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
}
