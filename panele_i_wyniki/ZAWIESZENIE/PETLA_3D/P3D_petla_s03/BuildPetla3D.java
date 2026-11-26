package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.meshing.*;import star.flow.*;import star.metrics.*;
import star.material.*;import star.segregatedflow.*;import star.turbulence.*;import star.kwturb.*;import star.vis.*;
import star.prismmesher.*;import star.resurfacer.*;import star.trimmer.*;
import java.nio.file.*;import java.io.*;import java.util.*;

/** BuildPetla3D - natywny przypadek STAR 3D (polowa rozpietosci, symetria y = 0), stacjonarny RANS SST k-omega, gleboka woda.
 *  Bryly z STL (domena + platy + plytka), operacje: Subtract -> Automated Mesh (resurfacer + trimmer + prism) z kontrolami
 *  wzglednymi do cieciwy, raporty sil na kazda bryle. Wszystko edytowalne w GUI.  Agent D, 15.11.2026.
 *  control.properties: mode=mesh (siatka, sceny PNG, PETLA_SETUP.sim) | mode=run (liczenie z zapisami, wznowienie od ostatniego zapisu) */
public class BuildPetla3D extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties(); Units m; Map<String,Object> log=new LinkedHashMap<>();
 double d(String k,double v){return Double.parseDouble(cfg.getProperty(k,""+v));}
 int i(String k,int v){return Integer.parseInt(cfg.getProperty(k,""+v));}
 void write(String n,String txt)throws Exception{Path t=out.resolve(n+".tmp");Files.writeString(t,txt);Files.move(t,out.resolve(n),StandardCopyOption.REPLACE_EXISTING);}
 String js(){StringBuilder b=new StringBuilder("{");boolean f=true;for(var e:log.entrySet()){if(!f)b.append(",");f=false;b.append("\"").append(e.getKey()).append("\":");
  Object v=e.getValue();b.append(v instanceof Number||v instanceof Boolean?v.toString():"\""+String.valueOf(v).replace("\\","/").replace("\"","'")+"\"");}return b.append("}").toString();}

 public void execute(){
  s=getActiveSimulation(); out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  String stage="init";
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   m=s.getUnitsManager().getObject("m");
   if(cfg.getProperty("mode","mesh").equals("mesh")){stage="build";build();}
   else{stage="run";run();}
  }catch(Throwable e){try{log.put("stage",stage);log.put("error",e.toString());write("ERROR.json",js());}catch(Exception x){}throw new RuntimeException(e);}
 }

 GeometryPart imp(String file)throws Exception{
  SimulationPartManager pm=s.get(SimulationPartManager.class); Set<GeometryPart> before=new HashSet<>(pm.getLeafParts());
  s.get(PartImportManager.class).importStlPart(out.resolve(file).toString(),"OneSurfacePerPatch",m,true,1e-8);
  List<GeometryPart> a=new ArrayList<>(pm.getLeafParts()); a.removeAll(before); if(a.size()!=1)throw new IllegalStateException("import "+file);
  GeometryPart p=a.get(0); p.setPresentationName(file.replace(".stl","")); return p;
 }
 void build()throws Exception{
  String[] bodies=cfg.getProperty("bodies").split(",");
  double C=d("chord_m",0.156), U=d("U_m_s",12.346666666666666);
  GeometryPart dom=imp("domena.stl"); List<GeometryPart> all=new ArrayList<>(List.of(dom)); List<GeometryPart> tools=new ArrayList<>();
  for(String b:cfg.getProperty("stl_files",cfg.getProperty("bodies")).split(",")){GeometryPart p=imp(b.trim()+".stl");all.add(p);tools.add(p);}
  // 1. Unite bryl (plytka przenika konce platow), potem Subtract: domena minus bryla
  if(tools.size()>1){   // Surface Wrapper laczy przenikajace sie bryly w jedna szczelna powierzchnie (natywna operacja, edytowalna)
   double Bw=d("base_size_m",0.8);
   AutoMeshOperation wr=s.get(MeshOperationManager.class).createSurfaceWrapperAutoMeshOperation(tools,"P3D Surface wrapper - platy i plytki");
   wr.getDefaultValues().get(BaseSize.class).setValue(Bw);
   wr.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*C/i("cells_per_chord",40)/Bw);
   wr.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*C/400/Bw);
   wr.execute();
   GeometryPart u=(GeometryPart)((star.surfacewrapper.SurfaceWrapperAutoMeshOperation)wr).getOutputParts().getObjects().iterator().next();
   u.setPresentationName("P3D bryla platow (wrapper)");
   all=new ArrayList<>(List.of(dom,u));
  }
  SubtractPartsOperation sub=(SubtractPartsOperation)s.get(MeshOperationManager.class).createSubtractPartsOperation(all);
  sub.setPresentationName("P3D Subtract - domena minus platy"); sub.setTargetPart((MeshPart)dom); sub.execute();
  GeometryPart fl=(GeometryPart)sub.getOutputParts().getObjects().iterator().next(); fl.setPresentationName("P3D fluid");
  Map<String,PartSurface> sf=new LinkedHashMap<>(); for(PartSurface ps:fl.getPartSurfaces())sf.put(ps.getPresentationName(),ps);
  log.put("part_surfaces",String.join(";",sf.keySet()));
  List<PartSurface> wall=new ArrayList<>(),outer=new ArrayList<>();
  for(var e:sf.entrySet()){String n=e.getKey().toLowerCase(Locale.ROOT);boolean w=false;for(String b:bodies)if(n.contains(b.trim().toLowerCase(Locale.ROOT)))w=true;(w?wall:outer).add(e.getValue());}
  if(wall.isEmpty())throw new IllegalStateException("brak scian platow: "+sf.keySet());
  // 2. Siatka: resurfacer + trimmer + prism, rozmiary wzgledem cieciwy C
  AutoMeshOperation am=s.get(MeshOperationManager.class).createAutoMeshOperation(
    List.of("star.resurfacer.ResurfacerAutoMesher","star.resurfacer.AutomaticSurfaceRepairAutoMesher","star.trimmer.TrimmerAutoMesher","star.prismmesher.PrismAutoMesher"),List.of(fl));
  am.setPresentationName("P3D Automated mesh (rozmiary wzgledem cieciwy, edytowalne)");
  double B=d("base_size_m",0.8); am.getDefaultValues().get(BaseSize.class).setValue(B);
  am.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100);
  am.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*C/200/B);
  am.getDefaultValues().get(NumPrismLayers.class).setNumLayers(3);
  am.getDefaultValues().get(PrismThickness.class).setAbsoluteSize(d("prism_total_m",6.3e-4),m);
  am.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.18);
  SurfaceCustomMeshControl fc=am.getCustomMeshControls().createSurfaceControl(); fc.setPresentationName("P3D platy: rozmiar c/"+i("cells_per_chord",60));
  fc.getGeometryObjects().setObjects(wall);
  fc.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
  fc.getCustomConditions().get(PartsMinimumSurfaceSizeOption.class).setSelected(PartsMinimumSurfaceSizeOption.Type.CUSTOM);
  fc.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*C/i("cells_per_chord",60)/B);
  fc.getCustomValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*C/200/B);
  SurfaceCustomMeshControl oc=am.getCustomMeshControls().createSurfaceControl(); oc.setPresentationName("P3D bez warstw przysciennych na granicach domeny");
  oc.getGeometryObjects().setObjects(outer);
  oc.getCustomConditions().get(PartsCustomizePrismMesh.class).getCustomPrismOptions().setSelected(PartsCustomPrismsOption.Type.DISABLE);
  double z0=d("zmin_m",-0.3),z1=d("zmax_m",1.3),xs=d("xmax_m",0.6);
  volume(am,"P3D otoczenie platow (c/8)",new double[]{-0.15,0,z0},new double[]{xs,d("ymax_m",4.3),z1},100*C/8/B);
  volume(am,"P3D slad i wir koncowy (c/3)",new double[]{-0.5,0,z0-0.4},new double[]{6,d("ymax_m",4.3)+0.6,z1+0.4},100*C/3/B);
  int kk=0; for(String fz:cfg.getProperty("foil_lev","0:0").split(";")){String[] q=fz.split(":");double fx=Double.parseDouble(q[0]),zz=Double.parseDouble(q[1]);
   volume(am,"P3D bliskie otoczenie platu "+(++kk)+" (c/24)",new double[]{fx-0.15*C,0,zz-0.25*C},new double[]{fx+1.15*C,4.03,zz+0.25*C},100*C/24/B);}
  if(cfg.containsKey("plate_x")){String[] q=cfg.getProperty("plate_x").split(":");double xa=Math.min(Double.parseDouble(q[0]),Double.parseDouble(q[1])),xb=Math.max(Double.parseDouble(q[0]),Double.parseDouble(q[1]));
   volume(am,"P3D bliskie otoczenie plytki (c/24)",new double[]{xa-0.15*C,3.96,-0.25*C},new double[]{xb+1.15*C,4.04,d("gap_m",1.0)+0.25*C},100*C/24/B);}
  // 3. Region, granice, fizyka (region musi istniec przed siatka objetosciowa)
  s.getRegionManager().newRegionsFromParts(List.of(fl),"OneRegion",null,"OneBoundaryPerPartSurface",null,RegionManager.CreateInterfaceMode.BOUNDARY);
  Region rg=s.getRegionManager().getRegions().iterator().next(); rg.setPresentationName("P3D woda");
  PhysicsContinuum pc=s.getContinuumManager().createContinuum(PhysicsContinuum.class); pc.setPresentationName("P3D woda RANS SST");
  pc.enable(ThreeDimensionalModel.class);pc.enable(SteadyModel.class);pc.enable(SingleComponentLiquidModel.class);pc.enable(SegregatedFlowModel.class);
  pc.enable(ConstantDensityModel.class);pc.enable(TurbulentModel.class);pc.enable(RansTurbulenceModel.class);pc.enable(KOmegaTurbulence.class);
  pc.enable(SstKwTurbModel.class);pc.enable(KwAllYplusWallTreatment.class);
  rg.setPhysicsContinuum(pc);
  pc.getInitialConditions().get(VelocityProfile.class).getMethod(ConstantVectorProfileMethod.class).getQuantity().setComponents(U,0,0);
  Map<String,List<Boundary>> byBody=new LinkedHashMap<>(); List<String> bn=new ArrayList<>();
  for(Boundary b:rg.getBoundaryManager().getBoundaries()){
   String n=b.getPresentationName().toLowerCase(Locale.ROOT); bn.add(b.getPresentationName());
   if(n.contains("inlet")){b.setBoundaryType(InletBoundary.class);b.getValues().get(VelocityMagnitudeProfile.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(U);}
   else if(n.contains("outlet"))b.setBoundaryType(PressureBoundary.class);
   else if(n.contains("symmetry")||n.contains("side")||n.contains("top")||n.contains("bottom"))b.setBoundaryType(SymmetryBoundary.class);
   else for(String bb:bodies)if(n.contains(bb.trim().toLowerCase(Locale.ROOT)))byBody.computeIfAbsent(bb.trim(),k->new ArrayList<>()).add(b);
  }
  log.put("boundaries",String.join(";",bn));
  long tm=System.nanoTime(); am.execute(); log.put("mesh_seconds",(System.nanoTime()-tm)/1e9);
  // 4. Raporty sil (natywne), monitory i wykres
  List<Monitor> ms=new ArrayList<>(); List<Boundary> allw=new ArrayList<>();
  for(var e:byBody.entrySet()){allw.addAll(e.getValue());ms.add(force("Fx_"+e.getKey(),e.getValue(),1,0,0));ms.add(force("Fz_"+e.getKey(),e.getValue(),0,0,1));ms.add(force("Fy_"+e.getKey(),e.getValue(),0,1,0));}
  ms.add(force("Fx_suma",allw,1,0,0)); ms.add(force("Fz_suma",allw,0,0,1));
  s.getPlotManager().createMonitorPlot(ms,"P3D sily [N] (polowa rozpietosci)");
  ((StepStoppingCriterion)s.getSolverStoppingCriterionManager().getSolverStoppingCriterion("Maximum Steps")).setMaximumNumberSteps(i("max_iter",3000));
  FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
  log.put("cells",fv.getCellCount()); log.put("bodies",String.join(",",byBody.keySet()));
  write("P3D_MESH.json",js());
  try{scenes(rg,allw,fv);}catch(Exception e){log.put("scene_warning",e.toString());}
  s.saveState(out.resolve("PETLA_SETUP.sim").toString()); write("P3D_MESH.json",js());
 }

 ReportMonitor force(String n,List<Boundary> b,double x,double y,double z){
  ForceReport r=s.getReportManager().createReport(ForceReport.class); r.setPresentationName(n);
  r.getDirection().setComponents(x,y,z); r.getParts().setObjects(b);
  ReportMonitor rm=r.createMonitor(); rm.setPresentationName(n+" Monitor"); return rm;
 }
 void volume(AutoMeshOperation a,String name,double[] lo,double[] hi,double pct){
  SimpleBlockPart p=s.get(MeshPartFactory.class).createNewBlockPart(s.getGeometryPartManager());
  p.setPresentationName(name);p.setCorners(new DoubleVector(lo),new DoubleVector(hi));p.rebuildSimpleShapePart();
  VolumeCustomMeshControl c=a.getCustomMeshControls().createVolumeControl(); c.setPresentationName(name); c.getGeometryObjects().setObjects(p);
  for(Object v:c.getCustomConditions().getChildren())if(v instanceof VolumeControlBase st)st.setVolumeControlBaseSizeOption(true);
  c.getCustomValues().get(VolumeControlSize.class).setRelativeSize(pct);
 }
 void scenes(Region rg,List<Boundary> walls,FvRepresentation fv)throws Exception{
  Scene g=s.getSceneManager().createScene("P3D geometria");g.setPresentationName("P3D geometria");g.initializeAndWait();
  PartDisplayer gd=g.getDisplayerManager().createPartDisplayer("Platy");gd.getInputParts().setObjects(walls);gd.setOutline(false);gd.setSurface(true);
  view(g,new double[]{0.3,2.2,0.5},new double[]{-5.5,-3.5,4.5},2.6);g.printAndWait(out.resolve("P3D_GEOMETRIA.png").toString(),1,1600,1000);
  String[][] cut={{"P3D siatka y = 2 m","0","2","0","0","1","0"},{"P3D siatka x = c/4","0.04","0","0","1","0","0"}};
  for(String[] c:cut){
   PlaneSection pl=s.getPartManager().createPlaneSection();pl.setPresentationName(c[0]+" (przekroj)");pl.getInputParts().setObjects(rg);
   pl.setOrigin(new DoubleVector(new double[]{Double.parseDouble(c[1]),Double.parseDouble(c[2]),Double.parseDouble(c[3])}));
   pl.setOrientation(new DoubleVector(new double[]{Double.parseDouble(c[4]),Double.parseDouble(c[5]),Double.parseDouble(c[6])}));
   Scene sc=s.getSceneManager().createScene(c[0]);sc.setPresentationName(c[0]);sc.initializeAndWait();
   PartDisplayer pd=sc.getDisplayerManager().createPartDisplayer("Siatka");pd.getInputParts().setObjects(pl);pd.setRepresentation(fv);pd.setMesh(true);pd.setOutline(true);
   if(c[5].equals("1")){view(sc,new double[]{0.25,2,0.5},new double[]{0.25,-10,0.5},0.9);sc.printAndWait(out.resolve("P3D_SIATKA_BOK.png").toString(),1,1600,1000);
    view(sc,new double[]{0.08,2,0},new double[]{0.08,-10,0},0.12);sc.printAndWait(out.resolve("P3D_SIATKA_BOK_ZOOM.png").toString(),1,1600,1000);}
   else{view(sc,new double[]{0.04,2.4,0.5},new double[]{-10,2.4,0.5},2.4);sc.printAndWait(out.resolve("P3D_SIATKA_PRZOD.png").toString(),1,1600,1000);}
  }
 }
 void view(Scene sc,double[] f,double[] p,double scale){
  sc.getCurrentView().setInput(new DoubleVector(f),new DoubleVector(p),new DoubleVector(new double[]{0,0,1}),scale,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
 }
 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 void run()throws Exception{
  List<String> fr=new ArrayList<>(); for(Report r:s.getReportManager().getObjects())if(r instanceof ForceReport)fr.add(r.getPresentationName());
  Collections.sort(fr); Path hp=out.resolve("p3d_history.csv"); boolean newf=!Files.exists(hp);
  int maxIt=i("max_iter",3000),minIt=i("min_iter",800),W=i("conv_window",300),every=i("save_every",500); double tol=d("conv_tol",0.001);
  List<double[]> h=new ArrayList<>(); int okc=0; long t0=System.nanoTime();
  try(BufferedWriter w=Files.newBufferedWriter(hp,StandardOpenOption.CREATE,StandardOpenOption.APPEND)){
   if(newf){w.write("iter,s_wall,"+String.join(",",fr)+"\n");}
   while(s.getSimulationIterator().getCurrentIteration()<maxIt){
    s.getSimulationIterator().step(10); int it=s.getSimulationIterator().getCurrentIteration();
    StringBuilder b=new StringBuilder(it+","+(System.nanoTime()-t0)/1e9); double fx=rv("Fx_suma"),fz=rv("Fz_suma");
    for(String n:fr)b.append(",").append(rv(n)); w.write(b+"\n"); w.flush(); h.add(new double[]{it,fx,fz});
    if(!Double.isFinite(fx+fz))throw new IllegalStateException("sily nieskonczone, iter "+it);
    if(it%every==0)s.saveState(out.resolve("PETLA_CKPT.sim").toString());
    int k=W/10; if(it>=minIt&&h.size()>=2*k&&it%100==0){
     double a1=0,a0=0,b1=0,b0=0; for(int j=0;j<k;j++){double[] q1=h.get(h.size()-1-j),q0=h.get(h.size()-1-k-j);a1+=q1[1];a0+=q0[1];b1+=q1[2];b0+=q0[2];}
     double rx=Math.abs(a1-a0)/Math.abs(a1),rz=Math.abs(b1-b0)/Math.abs(b1); log.put("iter",it);log.put("rel_Fx",rx);log.put("rel_Fz",rz);write("P3D_CONV.json",js());
     if(rx<tol&&rz<tol){if(++okc>=2){log.put("converged",true);break;}}else okc=0;}
   }
  }
  for(String n:fr)log.put(n,rv(n)); log.put("final_iter",s.getSimulationIterator().getCurrentIteration());
  write("P3D_WYNIK.json",js()); s.saveState(out.resolve("PETLA_KONIEC.sim").toString());
 }
}
