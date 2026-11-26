package macro;
import star.motion.*;import star.meshing.*;import star.common.*;import star.vis.*;import star.post.*;import star.metrics.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.material.*;import star.segregatedflow.*;import star.turbulence.*;import star.kwturb.*;import star.vof.*;import star.mixturemultiphase.*;import star.vis.*;import java.nio.file.*;import java.io.*;import java.util.*;import star.prismmesher.*;import star.resurfacer.*;import star.sweptmesher.*;import star.twodmesher.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * BuildGodoCase - native STAR-CCM+ case in Godø's conditions (c = 0.312 m, U = 12.347 m/s, H = 1.5 m, lambda = 39.03 m,
 * calm surface 1.09 m above the foil), built on a COPY of the verified Mini-VOF physics (VOF water/air, SST k-omega
 * All y+, 5th-order Stokes wave, forcing/damping zones, AF_* reports).
 *
 * Everything is native and editable in the GUI:
 *  - geometry part "Godø fluid domain" (STL with named patches, same patch names as Mini)
 *  - mesh operation "GODO Directed mesh" (2D polygonal + prism source, one span layer) whose custom controls are ALL
 *    relative to one Base Size -> changing Base Size refines the whole mesh consistently (mesh-convergence study).
 *  - wave "CB_StokesV": lambda, H, depth, current; forcing / damping lengths on inlet / outlet
 *  - AF_CL / AF_CD redefined with Godø's dynamic pressure basis and the foil buoyancy.
 * Modes (control.properties): mode=mesh  -> mesh + audit + save GODO_MESH_B<base>.sim
 *                             mode=probe -> mesh + physics + initialise from the wave + N steps timing -> COST_PROBE.json
 */
public class BuildGodoSplit extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties(); Units m;
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
 FieldFunction wf(NamedObject w,String prefix){for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getPresentationName().equals(prefix+w.getPresentationName()))return f;throw new IllegalStateException("Missing wave field "+prefix+w.getPresentationName());}
 Map<String,Object> log=new LinkedHashMap<>();

 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  String stage="init";
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   m=s.getUnitsManager().getObject("m");
   Region region=s.getRegionManager().getRegion("MINI_water_air");
   FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   if(fv.getCellCount()!=25617)throw new IllegalStateException("Source is not the verified Mini FIXED checkpoint (cells="+fv.getCellCount()+")");
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   for(SolutionHistory h:s.get(SolutionHistoryManager.class).getObjects()){h.setAutoRecord(false);h.setAutoRescan(false);}
   stage="geometry";
   s.getSolution().clearSolution(Solution.Clear.Fields,Solution.Clear.History);
   SimulationPartManager pm=s.get(SimulationPartManager.class);
   Set<GeometryPart> before=new HashSet<>(pm.getLeafParts());
   s.get(PartImportManager.class).importStlPart(out.resolve("GodoFluidDomain.stl").toString(),"OneSurfacePerPatch",m,true,1e-8);
   List<GeometryPart> added=new ArrayList<>(pm.getLeafParts()); added.removeAll(before);
   if(added.size()!=1)throw new IllegalStateException("Expected one new geometry part");
   GeometryPart domain=added.get(0); domain.setPresentationName("Godø fluid domain - c 0.312 m, 20 mm span");
   Map<String,PartSurface> sf=new LinkedHashMap<>(); for(PartSurface p:domain.getPartSurfaces())sf.put(p.getPresentationName(),p);
   Map<String,String> links=Map.of("main","Main","flap","Flap","inlet","Inlet","outlet","Outlet","bottom","Bottom","top","Top","span_front","Span0","span_back","Span1");
   Map<String,Boundary> bnd=new LinkedHashMap<>(); for(Boundary b:region.getBoundaryManager().getBoundaries())bnd.put(b.getPresentationName().toLowerCase(Locale.ROOT),b);
   if(!sf.keySet().equals(new HashSet<>(links.values()))||!bnd.keySet().equals(links.keySet()))throw new IllegalStateException("Patch/boundary mismatch "+sf.keySet()+" / "+bnd.keySet());
   region.getPartGroup().setObjects(List.of(domain));
   for(var e:links.entrySet())bnd.get(e.getKey()).getPartSurfaceGroup().setObjects(sf.get(e.getValue()));
   for(Object o:s.get(MeshOperationManager.class).getObjects())if(o instanceof NamedObject n&&!n.getPresentationName().startsWith("GODO"))((NamedObject)o).setPresentationName("OLD Mini - "+n.getPresentationName());

   stage="cleanup";
   cleanup(domain);
   stage="mesh";
   double B=d("base_size_m",1.0), C=d("chord_m",.312), yfs=d("free_surface_y_m",1.09), H=d("H_m",1.5), x0=d("x0_m",-46.839), xd=d("band_x1_m",78.06);
   DirectedMeshOperation mesh=(DirectedMeshOperation)s.get(MeshOperationManager.class).createDirectedMeshOperation(List.of(domain));
   mesh.setPresentationName("GODO Directed mesh - one span layer (all sizes relative to Base Size)");
   mesh.getSourceSurfaceGroup().setObjects(sf.get("Span0")); mesh.getTargetSurfaceGroup().setObjects(sf.get("Span1"));
   mesh.editDirectedMeshOperation();
   List<DirectedMeshPartCollection> col=new ArrayList<>(mesh.getDirectedMeshPartCollectionManager().getObjects());
   for(DirectedMeshPartCollection c:col){c.setTargetSmoothOption(false);c.setEnhanceCellQualityOption(false);}
   DirectedAutoSourceMesh a=mesh.getDirectedSurfaceMeshBaseManager().createAutoSourceMesh(List.of("star.twodmesher.DualAutoMesher2d","star.prismmesher.PrismAutoMesher"),col);
   a.setPresentationName("GODO polygonal source - foil prisms, wake, free-surface band");
   a.getDefaultValues().get(BaseSize.class).setValue(B);
   // percentages of Base Size (medium mesh B = 1 m): Mini sizes scaled by c/1.19, free-surface band H/20
   a.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100);
   a.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026);
   a.getDefaultValues().get(SurfaceGrowthRate.class).setGrowthRate(1.25);
   a.getDefaultValues().get(NumPrismLayers.class).setNumLayers(3);
   a.getDefaultValues().get(PrismThickness.class).setAbsoluteSize(d("prism_total_m",6.79e-4),m);   // y+ ~50, fixed for all meshes
   a.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.18);
   List<PartSurface> skin=List.of(sf.get("Main"),sf.get("Flap"));
   SurfaceCustomMeshControl foil=a.getCustomMeshControls().createSurfaceControl(); foil.setPresentationName("GODO foil wall size (0.236 % B)"); foil.getGeometryObjects().setObjects(skin);
   foil.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
   foil.getCustomConditions().get(PartsMinimumSurfaceSizeOption.class).setSelected(PartsMinimumSurfaceSizeOption.Type.CUSTOM);
   foil.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*.00236*d("foil_size_scale",1.0));
   foil.getCustomValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*.00026*d("foil_size_scale",1.0));
   List<PartSurface> outer=new ArrayList<>(sf.values()); outer.removeAll(skin);
   SurfaceCustomMeshControl far=a.getCustomMeshControls().createSurfaceControl(); far.setPresentationName("GODO no prisms outside foil"); far.getGeometryObjects().setObjects(outer);
   far.getCustomConditions().get(PartsCustomizePrismMesh.class).getCustomPrismOptions().setSelected(PartsCustomPrismsOption.Type.DISABLE);
   {double fs0=d("foil_size_scale",1.0);int kk=0;for(String yo:cfg.getProperty("foil_y_offsets","0").split(";")){double oy=Double.parseDouble(yo.trim());volume(a,"GODO foil neighbourhood "+(++kk)+" (0.66 % B x chord scale)",new double[]{-.0786*fs0,oy-.0865*fs0,-.01},new double[]{.388*fs0,oy+.102*fs0,.03},100*.0066*fs0);}}
   volume(a,"GODO free-surface band (7.5 % B = H/20 at B=1 m)",new double[]{x0-1,yfs-0.8*H,-.01},new double[]{xd,yfs+0.8*H,.03},100*.075);
   volume(a,"GODO free-surface transition (15 % B)",new double[]{x0-1,yfs-1.6*H,-.01},new double[]{xd+15,yfs+1.6*H,.03},100*.15);
   SurfaceCustomMeshControl wake=a.getCustomMeshControls().createSurfaceControl(); wake.setPresentationName("GODO wake refinement"); wake.getGeometryObjects().setObjects(List.of(sf.get("Flap")));
   boolean wakeOn=false;
   for(Object v:wake.getCustomConditions().getChildren()){
    if(v instanceof PartsRemesherTetPolyWakeRefinementOption w){w.setPartsWakeRefinementOption(true);wakeOn=w.getPartsWakeRefinementOption();}
    else if(v instanceof PartsWakeRefinementOption w){w.setPartsWakeRefinementOption(true);wakeOn=w.getPartsWakeRefinementOption();}
   }
   if(wakeOn){
    PartsWakeRefinementValuesManager w=wake.getCustomValues().get(PartsWakeRefinementValuesManager.class);
    w.getRelativeOrAbsoluteOption().setSelected(RelativeOrAbsoluteOption.Type.RELATIVE);
    w.getDirection().setComponents(1,0,0); w.getDistance().setValue(1.6*C/1.19);
    w.getSpreadAngle().setUnits(s.getUnitsManager().getObject("deg")); w.getSpreadAngle().setValue(6);
    w.getIsotropicSize().setRelativeSize(100*.0105);
   }
   DirectedMeshDistribution dist=mesh.getDirectedMeshDistributionManager().createDirectedMeshDistribution(col);
   dist.getDefaultValues().get(DirectedMeshNumLayers.class).setNumLayers(1);
   a.updateAutoSourceMesh(); mesh.stopEditingDirectedMeshOperation();
   long tm=System.nanoTime(); mesh.execute(); double meshSec=(System.nanoTime()-tm)/1e9;
   List<Region> regs=List.of(region);
   int orient=s.get(MeshManager.class).checkFaceOrientation(regs); if(orient>0)s.get(MeshManager.class).repairFaceOrientation(regs);
   long cells=fv.getCellCount();
   double minQ=metric("CellQuality",region,true),minV=metric("Volume",region,true),minF=metric("FaceValidity",region,true);
   log.put("base_size_m",B);log.put("cells",cells);log.put("mesh_seconds",meshSec);log.put("min_cell_quality",minQ);log.put("min_volume_m3",minV);
   log.put("min_face_validity",minF);log.put("orientation_repaired",orient);log.put("wake_refinement",wakeOn);
   write("GODO_MESH.json",log);
   if(!(minV>0&&minQ>0&&minF>.5))throw new IllegalStateException("Mesh quality gate failed "+log);
   try{scene("GODO mesh 01 - free-surface band",bnd.get("span_front"),fv,0,yfs,6,"GODO_MESH_BAND.png");
       scene("GODO mesh 02 - foil",bnd.get("span_front"),fv,.16,0,.35,"GODO_MESH_FOIL.png");}catch(Exception e){log.put("scene_warning",e.toString());}

   stage="physics";
   PhysicsContinuum pc=region.getPhysicsContinuum();
   VofWaveModel vm=pc.getModelManager().getModel(VofWaveModel.class);
   double U=d("U_m_s",12.346666666666666), lam=d("lambda_m",39.03274979328733), y0=d("bottom_y_m",-39.03274979328733);
   FifthOrderVofWave wave=null; List<String> waves=new ArrayList<>();
   for(Object wo:vm.getVofWaveManager().getObjects()){
    NamedObject w=(NamedObject)wo;
    waves.add(w.getPresentationName()+":"+w.getClass().getSimpleName());
    try{Object pol=w.getClass().getMethod("getPointOnLevel").invoke(w);pol.getClass().getMethod("setComponents",double.class,double.class,double.class).invoke(pol,0.0,yfs,0.0);}catch(Throwable e){log.put("pol_"+w.getPresentationName(),e.toString());}
    try{w.getClass().getMethod("getCurrent").invoke(w).getClass().getMethod("setComponents",double.class,double.class,double.class).invoke(w.getClass().getMethod("getCurrent").invoke(w),U,0.0,0.0);}catch(Throwable e){log.put("cur_"+w.getPresentationName(),e.toString());}
    try{w.getClass().getMethod("getWind").invoke(w).getClass().getMethod("setComponents",double.class,double.class,double.class).invoke(w.getClass().getMethod("getWind").invoke(w),U,0.0,0.0);}catch(Throwable e){}
    if(wo instanceof FifthOrderVofWave f&&w.getPresentationName().startsWith("CB_StokesV"))wave=f;
   }
   Object active=region.getValues().get(ForcingVofWaveSpecification.class).getForcingVofWave();
   if(active instanceof FifthOrderVofWave f)wave=f;      // the wave the verified checkpoint actually forces with
   log.put("active_wave",wave==null?"none":wave.getPresentationName());
   log.put("waves",waves);
   if(wave==null)throw new IllegalStateException("CB_StokesV not found");
   wave.setWaterDepth(yfs-y0);
   wave.getSpecificationOption().setSelected(VofWaveSpecificationOption.Type.WAVE_LENGTH_SPECIFIED);
   wave.getVofWaveSpecification().getWaveLength().setValue(lam);
   wave.getWaveHeight().setValue(d("wave_H_m",H));
   for(Boundary b:region.getBoundaryManager().getBoundaries()){
    String n=b.getPresentationName();
    if(n.contains("inlet")){
     b.getConditions().get(VofWaveForcingBoundaryOption.class).setSelected(VofWaveForcingBoundaryOption.Type.YES);
     b.getValues().get(VofWaveForcingLength.class).setMethod(ConstantScalarProfileMethod.class);
     b.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(d("forcing_length_m",15.6));
     b.getValues().get(VelocityProfile.class).setMethod(FunctionVectorProfileMethod.class);
     b.getValues().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(wf(wave,"Velocity of "));
    }
    if(n.contains("outlet")){
     b.getConditions().get(VofWaveDampingBoundaryOption.class).setSelected(VofWaveDampingBoundaryOption.Type.YES);
     b.getValues().get(VofWaveDampingLength.class).setMethod(ConstantScalarProfileMethod.class);
     b.getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(d("damping_length_m",31.2));
    }
   }
   region.getConditions().get(VofWaveZoneOption.class).setSelected(VofWaveZoneOptionEnum.FORCING_DAMPING);
   region.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(wave);
   // initial field = the incident wave (velocity incl. current, hydrostatic pressure, volume fraction)
   pc.getInitialConditions().get(VelocityProfile.class).setMethod(FunctionVectorProfileMethod.class);
   pc.getInitialConditions().get(VelocityProfile.class).getMethod(FunctionVectorProfileMethod.class).setFieldFunction(wf(wave,"Velocity of "));
   pc.getInitialConditions().get(InitialPressureProfile.class).setMethod(FunctionScalarProfileMethod.class);
   pc.getInitialConditions().get(InitialPressureProfile.class).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(wf(wave,"Hydrostatic Pressure of Heavy Fluid of "));
   VolumeFractionProfile vfp=pc.getInitialConditions().get(VolumeFractionProfile.class);
   vfp.setMethod(CompositeArrayProfileMethod.class);
   vfp.getMethod(CompositeArrayProfileMethod.class).getProfile(0).setMethod(FunctionScalarProfileMethod.class);
   vfp.getMethod(CompositeArrayProfileMethod.class).getProfile(0).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(wf(wave,"Volume Fraction of Heavy Fluid of "));
   vfp.getMethod(CompositeArrayProfileMethod.class).getProfile(1).setMethod(FunctionScalarProfileMethod.class);
   vfp.getMethod(CompositeArrayProfileMethod.class).getProfile(1).getMethod(FunctionScalarProfileMethod.class).setFieldFunction(wf(wave,"Volume Fraction of Light Fluid of "));
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
   us.getTimeStep().setValue(d("dt_s",1e-3));
   InnerIterationStoppingCriterion inner=(InnerIterationStoppingCriterion)s.getSolverStoppingCriterionManager().getSolverStoppingCriterion("Maximum Inner Iterations");
   inner.setMaximumNumberInnerIterations(i("inner",12));
   // force coefficients on Godø's basis: q = 0.5 rho U^2 c span ; CL with the foil buoyancy removed
   double qd=0.5*1000*U*U*C*.02, fb=1000*9.81*d("foil_area_m2",.00795948899616472)*.02;
   Map<String,Object> defs=new LinkedHashMap<>();
   for(String[] r:new String[][]{{"AF_CL","(${AF_FzReport}-"+fb+")/"+qd},{"AF_CD","${AF_FxReport}/"+qd}}){
    Report rp=s.getReportManager().getReport(r[0]);
    if(rp instanceof ExpressionReport er){defs.put(r[0]+"_old",er.getDefinition());er.setDefinition(r[1]);defs.put(r[0]+"_new",r[1]);}
    else defs.put(r[0]+"_type",rp==null?"missing":rp.getClass().getSimpleName());
   }
   log.put("coefficient_basis",Map.of("q_N",qd,"buoyancy_N",fb,"defs",defs));
   yplusReports(bnd.get("main"),bnd.get("flap"));
   productionReports(region,yfs,y0);
   s.saveState(out.resolve("GODO_SETUP_B"+B+".sim").toString());
   write("GODO_MESH.json",log);
   if(!cfg.getProperty("mode","mesh").equals("probe"))return;

   stage="probe";
   s.getSolution().initializeSolution();
   int n=i("probe_steps",60); List<Double> sec=new ArrayList<>(); double t0=s.getSolution().getPhysicalTime(); List<Double> fxH=new ArrayList<>(),fzH=new ArrayList<>(); int okc=0; log.put("converged",false);
   try(BufferedWriter h=Files.newBufferedWriter(out.resolve("probe_history.csv"))){
    h.write("step,time_s,solver_s,CL,CD,Fx_N,Fz_N,interfaceCFL,pmin_Pa,yplus_min,yplus_mean,yplus_max,yplus_frac_30_70\n");
    for(int k=1;k<=n;k++){
     long b0=System.nanoTime(); s.getSimulationIterator().step(1); double dtw=(System.nanoTime()-b0)/1e9; sec.add(dtw);
     double cl=s.getReportManager().getReport("AF_CL").getReportMonitorValue(),cd=s.getReportManager().getReport("AF_CD").getReportMonitorValue();
     double cfl=Double.NaN,pmin=Double.NaN;
     try{cfl=s.getReportManager().getReport("NN_interfaceCFL").getReportMonitorValue();}catch(Throwable e){}
     try{pmin=s.getReportManager().getReport("NN_pmin").getReportMonitorValue();}catch(Throwable e){}
     h.write(k+","+s.getSolution().getPhysicalTime()+","+dtw+","+cl+","+cd+","+s.getReportManager().getReport("AF_Fx").getReportMonitorValue()+","+s.getReportManager().getReport("AF_Fz").getReportMonitorValue()+","+cfl+","+pmin+","+rv("GODO_yplus_min")+","+rv("GODO_yplus_mean")+","+rv("GODO_yplus_max")+","+rv("GODO_yplus_frac_30_70")+"\n"); h.flush();
     if(!Double.isFinite(cl+cd))throw new IllegalStateException("non-finite forces at step "+k);fxH.add(s.getReportManager().getReport("AF_Fx").getReportMonitorValue());fzH.add(s.getReportManager().getReport("AF_Fz").getReportMonitorValue());{int W=i("conv_window",1000);double tol=d("conv_tol",0.0025);if(k>=Math.max(i("min_steps",3000),2*W)&&k%200==0){double qa1=fxH.subList(k-W,k).stream().mapToDouble(x->x).average().getAsDouble(),qa0=fxH.subList(k-2*W,k-W).stream().mapToDouble(x->x).average().getAsDouble();double qb1=fzH.subList(k-W,k).stream().mapToDouble(x->x).average().getAsDouble(),qb0=fzH.subList(k-2*W,k-W).stream().mapToDouble(x->x).average().getAsDouble();double rx=Math.abs(qa1-qa0)/Math.abs(qa1),rz=Math.abs(qb1-qb0)/Math.abs(qb1);log.put("conv_last_step",k);log.put("conv_rel_Fx",rx);log.put("conv_rel_Fz",rz);log.put("Fx_mean_last_window_N",qa1);log.put("Fz_mean_last_window_N",qb1);write("CONV.json",log);if(rx<tol&&rz<tol){okc++;if(okc>=2){log.put("converged",true);log.put("converged_step",k);break;}}else okc=0;}}
    }
   }
   List<Double> warm=sec.subList(Math.min(10,sec.size()-1),sec.size());
   double mean=warm.stream().mapToDouble(x->x).average().orElse(Double.NaN);
   double dtSim=d("dt_s",1e-3), te=d("encounter_period_s",1.9368);
   log.put("probe_steps",n);log.put("solver_s_per_step_after_warmup",mean);log.put("dt_s",dtSim);
   log.put("steps_per_encounter_period",te/dtSim);log.put("hours_per_encounter_period",mean*te/dtSim/3600);
   log.put("cores",cfg.getProperty("cores","?"));
   write("COST_PROBE.json",log);
   s.saveState(out.resolve("GODO_PROBE_END_B"+B+".sim").toString());
  }catch(Throwable e){
   try{log.put("stage",stage);log.put("error",e.toString());write("ERROR.json",log);}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }

 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 /** remove obj from whichever manager owns it (reflection: removeObjects / remove / deleteChildren); false if refused (still referenced) */
 boolean drop(Object mgr,Object obj){
  for(String mth:new String[]{"removeObjects","remove","deleteChildren"}){
   for(java.lang.reflect.Method mm:mgr.getClass().getMethods()){
    if(!mm.getName().equals(mth)||mm.getParameterCount()!=1)continue;
    try{
     Class<?> pt=mm.getParameterTypes()[0];
     if(pt.isArray()){Object arr=java.lang.reflect.Array.newInstance(pt.getComponentType(),1);java.lang.reflect.Array.set(arr,0,obj);mm.invoke(mgr,arr);}
     else if(Collection.class.isAssignableFrom(pt))mm.invoke(mgr,List.of(obj));
     else if(pt.isInstance(obj))mm.invoke(mgr,obj);
     else continue;
     return true;
    }catch(Throwable e){}
   }
  }
  return false;
 }
 boolean keepReport(String n){
  return n.startsWith("AF_")||n.equals("NN_interfaceCFL")||n.equals("NN_pmin")||n.equals("NN_CFL")||n.equals("NN_pflap")||n.equals("NN_pbody");
 }
 int sweep(Object mgr,java.util.function.Predicate<Object> del,int passes){
  int total=0;
  for(int p=0;p<passes;p++){int n=0;
   List<Object> objs; try{objs=new ArrayList<>((Collection<?>)mgr.getClass().getMethod("getObjects").invoke(mgr));}catch(Throwable e){return total;}
   for(Object o:objs){try{if(del.test(o)&&drop(mgr,o))n++;}catch(Throwable e){}}
   total+=n; if(n==0)break;}
  return total;
 }
 String nm(Object o){try{return ((NamedObject)o).getPresentationName();}catch(Throwable e){return "";}}
 void cleanup(GeometryPart keep){
  Map<String,Integer> c=new LinkedHashMap<>();
  c.put("scenes",sweep(s.getSceneManager(),o->true,1));
  c.put("plots",sweep(s.getPlotManager(),o->true,1));
  c.put("tables",sweep(s.getTableManager(),o->true,1));
  c.put("monitors",sweep(s.getMonitorManager(),o->{if(o instanceof ResidualMonitor)return false;if(o instanceof ReportMonitor rm){try{return !keepReport(rm.getReport().getPresentationName());}catch(Throwable e){return false;}}return true;},1));
  c.put("reports",sweep(s.getReportManager(),o->!keepReport(nm(o)),6));
  c.put("derived_parts",sweep(s.getPartManager(),o->true,4));
  c.put("mesh_operations",sweep(s.get(MeshOperationManager.class),o->true,1));
  int g=0; for(Object o:new ArrayList<>(s.get(SimulationPartManager.class).getLeafParts())){try{if(o!=keep&&drop(s.get(SimulationPartManager.class),o))g++;}catch(Throwable e){}}
  c.put("geometry_parts",g);
  c.put("user_field_functions",sweep(s.getFieldFunctionManager(),o->o instanceof UserFieldFunction&&!nm(o).startsWith("AF_")&&!nm(o).startsWith("CB_"),3));
  for(Object o:s.getMonitorManager().getObjects())
   if(o instanceof ReportMonitor rm)try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){}
  c.put("reports_left",s.getReportManager().getObjects().size());c.put("monitors_left",s.getMonitorManager().getObjects().size());
  log.put("cleanup",c);
 } void yplusReports(Boundary main,Boundary flap){
  List<Boundary> w=List.of(main,flap);
  MinReport mn=s.getReportManager().createReport(MinReport.class);mn.setPresentationName("GODO_yplus_min");mn.setFieldFunction(ff("WallYplus"));mn.getParts().setObjects(w);
  MaxReport mx=s.getReportManager().createReport(MaxReport.class);mx.setPresentationName("GODO_yplus_max");mx.setFieldFunction(ff("WallYplus"));mx.getParts().setObjects(w);
  AreaAverageReport av=s.getReportManager().createReport(AreaAverageReport.class);av.setPresentationName("GODO_yplus_mean");av.setFieldFunction(ff("WallYplus"));av.getParts().setObjects(w);
  UserFieldFunction in=s.getFieldFunctionManager().createFieldFunction();in.setPresentationName("GODO_yplus_in_30_70");in.setFunctionName("GODO_yplus_in_30_70");
  in.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);in.setDefinition("($WallYplus>=30 && $WallYplus<=70) ? 1 : 0");
  AreaAverageReport fr=s.getReportManager().createReport(AreaAverageReport.class);fr.setPresentationName("GODO_yplus_frac_30_70");fr.setFieldFunction(in);fr.getParts().setObjects(w);
  List<Monitor> ms=new ArrayList<>();
  for(Report r:List.of(mn,mx,av,fr)){ReportMonitor rm=r.createMonitor();rm.setPresentationName(r.getPresentationName()+" Monitor");
   try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){}ms.add(rm);}
  try{s.getPlotManager().createMonitorPlot(ms,"GODO y+ on the foil (target 30-70)");}catch(Throwable e){log.put("yplus_plot_warning",e.toString());}
 }

 /** Native: max interface Courant number (cells with 0.01<alpha<0.99) and wave gauges eta(x) from a vertical plane:
  *  eta = (integral of water volume fraction over the plane)/span + y_bottom - y_calm.  Gauges: lambda/4 upstream, LE, hinge. */
 void productionReports(Region region,double yfs,double y0){
  UserFieldFunction ic=s.getFieldFunctionManager().createFieldFunction();ic.setPresentationName("GODO_interface_Courant");ic.setFunctionName("GODO_interface_Courant");
  ic.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);ic.setDefinition("($VolumeFractionwater>0.01 && $VolumeFractionwater<0.99) ? $CourantNumber : 0");
  MaxReport cf=s.getReportManager().createReport(MaxReport.class);cf.setPresentationName("GODO_interfaceCFL");cf.setFieldFunction(ic);cf.getParts().setObjects(region);
  List<Monitor> ms=new ArrayList<>();
  double lam=d("lambda_m",39.03274979328733);
  double[][] gx={{-lam/4},{0},{0.8*d("chord_m",.312)}};
  String[] gn={"GODO_eta_upstream_quarter_lambda","GODO_eta_at_LE","GODO_eta_at_hinge"};
  for(int k=0;k<3;k++){
   PlaneSection pl=s.getPartManager().createPlaneSection();pl.setPresentationName(gn[k]+" plane");pl.getInputParts().setObjects(region);
   pl.setOrigin(new DoubleVector(new double[]{gx[k][0],0,.01}));pl.setOrientation(new DoubleVector(new double[]{1,0,0}));
   SurfaceIntegralReport si=s.getReportManager().createReport(SurfaceIntegralReport.class);si.setPresentationName(gn[k]+"_SI");si.setFieldFunction(ff("VolumeFractionwater"));si.getParts().setObjects(pl);si.setSmooth(false);
   ExpressionReport e=s.getReportManager().createReport(ExpressionReport.class);e.setPresentationName(gn[k]);
   e.setDefinition("${"+gn[k]+"_SIReport}/<0.02 m>+<"+y0+" m>-<"+yfs+" m>");
   ReportMonitor rm=e.createMonitor();rm.setPresentationName(gn[k]+" Monitor");
   try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}
   ms.add(rm);
  }
  ReportMonitor cm=cf.createMonitor();cm.setPresentationName("GODO_interfaceCFL Monitor");
  try{cm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}
  try{s.getPlotManager().createMonitorPlot(ms,"GODO wave gauges eta [m]");s.getPlotManager().createMonitorPlot(List.of(cm),"GODO interface Courant");}catch(Throwable x){}
  for(String n:new String[]{"AF_CL","AF_CD","AF_Mh"})
   try{for(Object o:s.getMonitorManager().getObjects())if(o instanceof ReportMonitor r&&r.getReport().getPresentationName().equals(n))r.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}
 }
 double metric(String name,NamedObject part,boolean minimum){
  AnalysisReport q2=minimum?s.getReportManager().createReport(MinReport.class):s.getReportManager().createReport(MaxReport.class);
  FieldFunction f=ff(name);
  if(q2 instanceof MinReport low)low.setFieldFunction(f);else ((MaxReport)q2).setFieldFunction(f);
  q2.getParts().setObjects(part);q2.setSmooth(false);q2.setPresentationName("GODO mesh "+(minimum?"min ":"max ")+name);
  return q2.getReportMonitorValue();
 }
 void volume(DirectedAutoSourceMesh a,String name,double[] lo,double[] hi,double pct){
  SimpleBlockPart p=s.get(MeshPartFactory.class).createNewBlockPart(s.getGeometryPartManager());
  p.setPresentationName(name);p.setCorners(new DoubleVector(lo),new DoubleVector(hi));p.rebuildSimpleShapePart();
  VolumeCustomMeshControl c=a.getCustomMeshControls().createVolumeControl();
  c.setPresentationName(name);c.getGeometryObjects().setObjects(p);
  for(Object v:c.getCustomConditions().getChildren())if(v instanceof VolumeControlBase st)st.setVolumeControlBaseSizeOption(true);
  c.getCustomValues().get(VolumeControlSize.class).setRelativeSize(pct);
 }
 void scene(String name,Boundary cap,FvRepresentation fv,double x,double y,double scale,String png)throws Exception{
  Scene sc=s.getSceneManager().createScene(name);sc.setPresentationName(name);sc.initializeAndWait();
  PartDisplayer pd=sc.getDisplayerManager().createPartDisplayer("Span face and mesh");
  pd.getInputParts().setObjects(cap);pd.setRepresentation(fv);pd.setMesh(true);pd.setOutline(true);
  sc.getCurrentView().setInput(new DoubleVector(new double[]{x,y,0}),new DoubleVector(new double[]{x,y,5}),new DoubleVector(new double[]{0,1,0}),scale,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
  sc.printAndWait(out.resolve(png).toString(),1,1600,900);
 }
}
