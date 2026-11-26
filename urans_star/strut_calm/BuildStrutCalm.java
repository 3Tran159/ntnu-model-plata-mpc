package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.meshing.*;import star.cadmodeler.*;
import star.vof.*;import star.flow.*;import star.vis.*;import star.post.*;import star.prismmesher.*;import star.trimmer.*;import star.resurfacer.*;
import java.nio.file.*;import java.io.*;import java.util.*;

/**
 * BuildStrutCalm - natywny przypadek STAR: sam wspornik przebijajacy powierzchnie swobodna, woda spokojna, 24 kn.
 *
 *  Geometria (3D-CAD STAR, edytowalna w GUI):
 *    "STRUT domena"  - szkic prostokata na plaszczyznie ZX, wyciagniety w gore (y); sciany nazwane Inlet/Outlet/Bottom/Top/Sym/Side
 *    "STRUT NACA0012" - szkic: splajn NACA 00tt (tepa krawedz splywu) + odcinek TE, wyciagniety przez cala domene; sciana "Strut"
 *  Pol modelu: plaszczyzna symetrii z = 0 przez cieciwe (Sym). Dno y = 0 = plaszczyzna symetrii = miejsce plata (zlacze z platem).
 *  Glebokosc zanurzenia h = poziom wody nad dnem (control.properties h_m).
 *  Siatka: Automated Mesh (surface remesher + trimmer + 6 warstw przysciennych na wsporniku), rozmiary wzgledem Base Size,
 *          pas powierzchni swobodnej anizotropowy (dy drobne), skrzynka przy wsporniku, pas sladu.
 *  Fizyka: kontinuum VOF (woda/powietrze, SST k-omega, All y+) skopiowane ze sprawdzonego przypadku GodÃƒÂ¸; fala plaska
 *          "CB Initial Flat 1" z pradem U (uklad zwiazany ze wspornikiem), forcing na wlocie, tlumienie na wylocie i boku.
 *  Raporty STRUT_*: Fx cisnieniowa / tarcia / suma (pol modelu i caly wspornik), D na metr zanurzenia, zwilzona powierzchnia,
 *          powierzchnia zapowietrzona ponizej poziomu (wentylacja), najwyzszy punkt wody (bryzg / fala dziobowa).
 *  Tryb: mode=setup -> STRUT_SETUP_h<h>.sim + STRUT_SETUP.json
 */
public class BuildStrutCalm extends StarMacro {
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
 void write(String n,Object v){try{Path p=out.resolve(n),t=out.resolve(n+".tmp");Files.writeString(t,json(v));Files.move(t,p,StandardCopyOption.REPLACE_EXISTING);}catch(Exception e){}}
 FieldFunction ff(String n){FieldFunction f=s.getFieldFunctionManager().getFunction(n);if(f==null)throw new IllegalStateException("Missing field "+n);return f;}
 FieldFunction ffByName(String pres){for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f.getPresentationName().equals(pres))return f;return null;}

 // geometria (z control.properties)
 double C,TC,H,B,XIN,XOUT,W,AIR,U;

 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  String stage="init";
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   m=s.getUnitsManager().getObject("m");
   C=d("chord_m",0.4);TC=d("tc",0.12);H=d("h_m",1.09);B=d("base_size_m",0.08);
   XIN=d("x_in_m",-2.4);XOUT=d("x_out_m",6.0);W=d("z_side_m",3.0);AIR=d("air_m",1.0);U=d("U_m_s",12.346666666666666);
   Region region=s.getRegionManager().getRegion(cfg.getProperty("region","MINI_water_air"));
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   for(SolutionHistory hh:s.get(SolutionHistoryManager.class).getObjects()){hh.setAutoRecord(false);hh.setAutoRescan(false);}
   s.getSolution().clearSolution(Solution.Clear.Fields,Solution.Clear.History);

   stage="cleanup";
   Object first=region.getPartGroup().getObjects().iterator().next(); GeometryPart oldDomain=first instanceof GeometryPart?(GeometryPart)first:null;
   cleanup();

   stage="cad";
   SimulationPartManager pm=s.get(SimulationPartManager.class);
   Set<GeometryPart> before=new HashSet<>(pm.getLeafParts());
   CadModel dm=domainModel(false);
   Map<String,Object> chk=bounds(dm);
   log.put("cad_domain_bounds",chk);
   // kontrola orientacji szkicu ZX: oczekiwane x w [XIN, XOUT], z w [0, W]
   double xr=(double)chk.get("x1")-(double)chk.get("x0"), zr=(double)chk.get("z1")-(double)chk.get("z0");
   boolean swap=Math.abs(xr-W)<1e-6&&Math.abs(zr-(XOUT-XIN))<1e-6;
   if(swap){drop(s.get(SolidModelManager.class),dm);dm=domainModel(true);chk=bounds(dm);log.put("cad_domain_bounds_swapped",chk);}
   log.put("sketch_uv_swapped",swap);
   double y0=(double)chk.get("y0");                  // dno (zalezy od kierunku wyciagniecia)
   double yfs=y0+H;                                  // poziom wody spokojnej
   log.put("y_bottom_m",y0);log.put("y_free_surface_m",yfs);
   nameDomainFaces(dm,chk);
   CadModel sm=strutModel(swap,y0);
   s.get(SolidModelManager.class).endEditCadModel(dm);s.get(SolidModelManager.class).endEditCadModel(sm);
   makeParts(dm);makeParts(sm);
   List<GeometryPart> added=new ArrayList<>(pm.getLeafParts());added.removeAll(before);
   GeometryPart dom=null,str=null;
   for(GeometryPart g:added){String n=g.getPresentationName();if(n.contains("domena"))dom=g;else if(n.contains("NACA"))str=g;}
   if(dom==null||str==null){List<String> nn=new ArrayList<>();for(GeometryPart g:added)nn.add(g.getPresentationName());throw new IllegalStateException("CAD parts not found: "+nn);}
   tess((CadPart)dom,1e-4);tess((CadPart)str,1e-5);
   List<String> sn=new ArrayList<>();for(PartSurface p:dom.getPartSurfaces())sn.add(p.getPresentationName());for(PartSurface p:str.getPartSurfaces())sn.add(p.getPresentationName());
   log.put("cad_part_surfaces",sn);write("STRUT_SETUP.json",log);

   stage="subtract";
   SubtractPartsOperation sub=(SubtractPartsOperation)s.get(MeshOperationManager.class).createSubtractPartsOperation(List.of(dom,str));
   sub.setPresentationName("STRUT odejmowanie (domena - wspornik)");
   sub.setTargetPart((MeshPart)dom);sub.execute();
   MeshOperationPart fluid=(MeshOperationPart)s.getGeometryPartManager().getPart(sub.getPresentationName());
   Map<String,PartSurface> sf=new LinkedHashMap<>();
   for(PartSurface p:fluid.getPartSurfaces()){String n=p.getPresentationName();for(String k:new String[]{"Inlet","Outlet","Bottom","Top","Sym","Side","Strut"})if(n.endsWith(k)||n.endsWith(k+" ")||n.contains("."+k))sf.put(k,p);}
   List<String> fn=new ArrayList<>();for(PartSurface p:fluid.getPartSurfaces())fn.add(p.getPresentationName());log.put("fluid_surfaces",fn);
   if(sf.size()!=7)throw new IllegalStateException("Fluid surfaces not identified: "+fn);

   stage="region";
   region.getPartGroup().setObjects(fluid);
   Map<String,Boundary> bnd=new LinkedHashMap<>();for(Boundary b:region.getBoundaryManager().getBoundaries())bnd.put(b.getPresentationName().toLowerCase(Locale.ROOT),b);
   log.put("source_boundaries",new ArrayList<>(bnd.keySet()));
   String[][] map={{"main","Strut"},{"inlet","Inlet"},{"outlet","Outlet"},{"bottom","Bottom"},{"top","Top"},{"span_front","Sym"},{"span_back","Side"}};
   for(String[] mp:map){Boundary b=bnd.get(mp[0]);if(b==null)throw new IllegalStateException("No boundary "+mp[0]);b.getPartSurfaceGroup().setObjects(sf.get(mp[1]));}
   for(String[] mp:map)bnd.get(mp[0]).setPresentationName("STRUT "+mp[1]);
   Boundary flap=bnd.get("flap");if(flap!=null){log.put("flap_removed",drop(region.getBoundaryManager(),flap));}
   SymmetryBoundary sym=s.get(ConditionTypeManager.class).get(SymmetryBoundary.class);
   for(String k:new String[]{"bottom","span_front","span_back"})bnd.get(k).setBoundaryType(sym);
   if(oldDomain!=null)drop(pm,oldDomain);
   for(Object o:new ArrayList<>(pm.getLeafParts())){GeometryPart g=(GeometryPart)o;if(g!=dom&&g!=str&&g!=fluid)drop(pm,g);}

   stage="mesh";
   AutoMeshOperation am=(AutoMeshOperation)s.get(MeshOperationManager.class).createAutoMeshOperation(
     new StringVector(new String[]{"star.resurfacer.ResurfacerAutoMesher","star.trimmer.TrimmerAutoMesher","star.prismmesher.PrismAutoMesher"}),List.of(fluid));
   am.setPresentationName("STRUT siatka (wszystkie rozmiary wzgledem Base Size)");
   am.getDefaultValues().get(BaseSize.class).setValue(B);
   am.getDefaultValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100);
   am.getDefaultValues().get(PartsMinimumSurfaceSize.class).setRelativeSize(100*d("min_surface_m",0.001)/B);
   am.getDefaultValues().get(NumPrismLayers.class).setNumLayers(i("prism_layers",6));
   am.getDefaultValues().get(PrismThickness.class).setAbsoluteSize(d("prism_total_m",0.003),m);
   am.getDefaultValues().get(PrismLayerStretching.class).setStretching(d("prism_stretch",1.3));
   SurfaceCustomMeshControl wall=am.getCustomMeshControls().createSurfaceControl();wall.setPresentationName("STRUT wspornik - powierzchnia");
   wall.getGeometryObjects().setObjects(sf.get("Strut"));
   wall.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
   wall.getCustomValues().get(PartsTargetSurfaceSize.class).setRelativeSize(100*d("strut_surface_m",0.01)/B);
   SurfaceCustomMeshControl far=am.getCustomMeshControls().createSurfaceControl();far.setPresentationName("STRUT bez warstw przysciennych na granicach domeny");
   List<PartSurface> outer=new ArrayList<>(sf.values());outer.remove(sf.get("Strut"));far.getGeometryObjects().setObjects(outer);
   far.getCustomConditions().get(PartsCustomizePrismMesh.class).getCustomPrismOptions().setSelected(PartsCustomPrismsOption.Type.DISABLE);
   double ds=d("near_m",0.0125), dyb=d("band_dy_m",0.01);
   volume(am,"STRUT skrzynka przy wsporniku",new double[]{-0.3,y0,0},new double[]{C+0.6,yfs+0.6,0.25},ds,null);
   volume(am,"STRUT pas powierzchni (dx dz 0.04, dy 0.01)",new double[]{XIN-0.1,yfs-0.15,-0.1},new double[]{XOUT+0.1,yfs+0.25,W+0.1},d("band_dxz_m",0.04),new double[]{Double.NaN,dyb,Double.NaN});
   volume(am,"STRUT pas sladu (dx dz 0.02, dy 0.01)",new double[]{-0.3,yfs-0.15,-0.1},new double[]{XOUT+0.1,yfs+0.35,d("wake_z_m",1.2)},d("wake_dxz_m",0.02),new double[]{Double.NaN,dyb,Double.NaN});
   long tm=System.nanoTime();am.execute();double meshSec=(System.nanoTime()-tm)/1e9;
   FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   long cells=fv.getCellCount();
   double minQ=metric("CellQuality",region,true),minV=metric("Volume",region,true),minF=metric("FaceValidity",region,true);
   log.put("cells",cells);log.put("mesh_seconds",meshSec);log.put("min_cell_quality",minQ);log.put("min_volume_m3",minV);log.put("min_face_validity",minF);
   write("STRUT_SETUP.json",log);
   if(!(cells>1000&&minV>0&&minF>0.5))throw new IllegalStateException("Mesh quality gate failed "+log);

   stage="physics";
   PhysicsContinuum pc=region.getPhysicsContinuum();
   VofWaveModel vm=pc.getModelManager().getModel(VofWaveModel.class);
   FlatVofWave flat=null;List<String> waveNames=new ArrayList<>();
   for(Object wo:vm.getVofWaveManager().getObjects()){NamedObject w=(NamedObject)wo;waveNames.add(w.getPresentationName());
    if(wo instanceof FlatVofWave f&&w.getPresentationName().equals(cfg.getProperty("flat_wave","CB Initial Flat 1")))flat=f;}
   if(flat==null)throw new IllegalStateException("flat wave not found in "+waveNames);
   for(Object wo:vm.getVofWaveManager().getObjects()){
    try{Object pol=wo.getClass().getMethod("getPointOnLevel").invoke(wo);pol.getClass().getMethod("setComponents",double.class,double.class,double.class).invoke(pol,0.0,yfs,0.0);}catch(Throwable e){}
    try{Object cu=wo.getClass().getMethod("getCurrent").invoke(wo);cu.getClass().getMethod("setComponents",double.class,double.class,double.class).invoke(cu,U,0.0,0.0);}catch(Throwable e){}
    try{Object wi=wo.getClass().getMethod("getWind").invoke(wo);wi.getClass().getMethod("setComponents",double.class,double.class,double.class).invoke(wi,U,0.0,0.0);}catch(Throwable e){}
   }
   String fl=flat.getPresentationName();
   region.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(flat);
   // wszystkie profile (brzegi + warunki poczatkowe) wskazujace pole "X of <inna fala>" -> "X of <fala plaska>"
   List<String> rew=new ArrayList<>();
   for(Boundary b:region.getBoundaryManager().getBoundaries())for(Object v:b.getValues().getObjects())rewire(v,waveNames,fl,b.getPresentationName(),rew);
   for(Object v:pc.getInitialConditions().getObjects())rewire(v,waveNames,fl,"init",rew);
   log.put("rewired",rew);
   for(Boundary b:region.getBoundaryManager().getBoundaries()){
    String n=b.getPresentationName();
    try{
     if(n.endsWith("Inlet")){b.getConditions().get(VofWaveForcingBoundaryOption.class).setSelected(VofWaveForcingBoundaryOption.Type.YES);
      b.getValues().get(VofWaveForcingLength.class).setMethod(ConstantScalarProfileMethod.class);
      b.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(d("forcing_length_m",1.0));}
     if(n.endsWith("Outlet")||n.endsWith("Side")){b.getConditions().get(VofWaveDampingBoundaryOption.class).setSelected(VofWaveDampingBoundaryOption.Type.YES);
      b.getValues().get(VofWaveDampingLength.class).setMethod(ConstantScalarProfileMethod.class);
      b.getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(d(n.endsWith("Side")?"side_damping_m":"damping_length_m",n.endsWith("Side")?1.0:2.0));}
    }catch(Throwable e){log.put("forcing_"+n,e.toString());}
   }
   ImplicitUnsteadySolver us=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
   us.getTimeStep().setValue(d("dt_s",6e-4));
   InnerIterationStoppingCriterion inner=(InnerIterationStoppingCriterion)s.getSolverStoppingCriterionManager().getSolverStoppingCriterion("Maximum Inner Iterations");
   inner.setMaximumNumberInnerIterations(i("inner",6));
   try{PhysicalTimeStoppingCriterion pt=(PhysicalTimeStoppingCriterion)s.getSolverStoppingCriterionManager().getSolverStoppingCriterion("Maximum Physical Time");pt.getMaximumTime().setValue(d("t_end_s",2.0));}catch(Throwable e){log.put("tmax",e.toString());}

   stage="reports";
   reports(region,bnd.get("main"),yfs);
   write("STRUT_SETUP.json",log);
   try{scenes(region,bnd,fv,yfs);}catch(Throwable e){log.put("scene_warning",e.toString());}
   String fnm="STRUT_SETUP_h"+H+".sim";
   s.saveState(out.resolve(fnm).toString());
   log.put("saved",fnm);log.put("stage","done");write("STRUT_SETUP.json",log);
  }catch(Throwable e){
   log.put("stage",stage);log.put("error",e.toString());
   StringWriter sw=new StringWriter();e.printStackTrace(new PrintWriter(sw));log.put("trace",sw.toString().substring(0,Math.min(4000,sw.toString().length())));
   write("STRUT_SETUP.json",log);
   throw new RuntimeException(e);
  }
 }

 // ---------- 3D-CAD ----------
 SketchPlane plane(CadModel cm,String name){
  for(Object o:cm.getFeatureManager().getSketchPlanes())if(((NamedObject)o).getPresentationName().equals(name))return (SketchPlane)o;
  throw new IllegalStateException("No sketch plane "+name);
 }
 DoubleVector uv(boolean swap,double x,double z){return swap?new DoubleVector(new double[]{x,z}):new DoubleVector(new double[]{z,x});}
 CadModel domainModel(boolean swap){
  CadModel cm=s.get(SolidModelManager.class).createSolidModel();cm.setPresentationName("STRUT domena 3D-CAD");
  Sketch sk=cm.getFeatureManager().createSketch(plane(cm,"ZX"));sk.setPresentationName("domena - przekroj poziomy");
  cm.getFeatureManager().startSketchEdit(sk);
  LineSketchPrimitive l1=sk.createLine(uv(swap,XIN,0),uv(swap,XOUT,0));
  LineSketchPrimitive l2=sk.createLine(l1.getEndPoint(),uv(swap,XOUT,W));
  LineSketchPrimitive l3=sk.createLine(l2.getEndPoint(),uv(swap,XIN,W));
  sk.createLine(l3.getEndPoint(),l1.getStartPoint());
  cm.getFeatureManager().stopSketchEdit(sk,true);
  ExtrusionMerge ex=cm.getFeatureManager().createExtrusionMerge(sk);ex.setPresentationName("domena - wyciagniecie H+powietrze");
  ex.getDistance().setValue(H+AIR);
  cm.getFeatureManager().execute(ex);
  for(Object b:cm.getBodyManager().getBodies())((star.cadmodeler.Body)b).setPresentationName("STRUT domena");
  return cm;
 }
 CadModel strutModel(boolean swap,double y0){
  CadModel cm=s.get(SolidModelManager.class).createSolidModel();cm.setPresentationName("STRUT NACA00"+Math.round(100*TC)+" c"+C+" 3D-CAD");
  Sketch sk=cm.getFeatureManager().createSketch(plane(cm,"ZX"));sk.setPresentationName("NACA - przekroj");
  cm.getFeatureManager().startSketchEdit(sk);
  int n=i("naca_points_per_side",60);List<Double> p=new ArrayList<>();
  for(int k=0;k<=2*n;k++){                      // TE gora -> LE -> TE dol
   double beta=Math.PI*k/n; double xc=0.5*(1+Math.cos(beta));  // k=0: x=1, k=n: x=0, k=2n: x=1
   double yt=5*TC*(0.2969*Math.sqrt(xc)-0.1260*xc-0.3516*xc*xc+0.2843*xc*xc*xc-0.1015*xc*xc*xc*xc);
   double z=(k<=n?1:-1)*yt*C, x=xc*C;
   DoubleVector q=uv(swap,x,z);p.add(q.get(0));p.add(q.get(1));
  }
  double[] arr=new double[p.size()];for(int k=0;k<arr.length;k++)arr[k]=p.get(k);
  SplineSketchPrimitive sp=sk.createSpline(false,null,false,null,new DoubleVector(arr));
  sk.createLine(sp.getEndPoint(),sp.getStartPoint());       // tepa krawedz splywu (0.25 % c)
  cm.getFeatureManager().stopSketchEdit(sk,true);
  ExtrusionMerge ex=cm.getFeatureManager().createExtrusionMerge(sk);ex.setPresentationName("wspornik - wyciagniecie przez domene");
  ex.getDistance().setValue(H+AIR+0.2);
  cm.getFeatureManager().execute(ex);
  // przesun w dol o 0.1 m, zeby przebil dno i gore (jesli wyciagniecie idzie w -y, przesuniecie w gore)
  Map<String,Object> b=bounds(cm);double sy0=(double)b.get("y0"),sy1=(double)b.get("y1");
  log.put("cad_strut_bounds",b);
  for(Object o:cm.getBodyManager().getBodies()){star.cadmodeler.Body bd=(star.cadmodeler.Body)o;bd.setPresentationName("STRUT wspornik");
   cm.setFaceNameAttributes(new ArrayList<>(bd.getFaceManager().getFaces()),"Strut");}
  double shift=(y0-0.1)-sy0;
  if(Math.abs(shift)>1e-9){
   try{MoveBodyFeature mv=cm.getFeatureManager().createMoveBodyFeature(new ArrayList<>(cm.getBodyManager().getBodies()));
    mv.setPresentationName("wspornik - przesuniecie o 0.1 m pod dno");
    mv.getTranslationVector().setComponents(0,shift,0);
    List<String> tried=new ArrayList<>();boolean ok=false;
    for(int opt=0;opt<4&&!ok;opt++){
     try{mv.setDirectionOption(opt);mv.getTranslationVector().setComponents(0,shift,0);try{mv.getDistance().setValue(Math.abs(shift));}catch(Throwable e){}
      boolean ex2=cm.getFeatureManager().execute(mv);Map<String,Object> b2=bounds(cm);
      ok=Math.abs((double)b2.get("y0")-(y0-0.1))<1e-4;tried.add("opt"+opt+" exec="+ex2+" y0="+b2.get("y0"));}
     catch(Throwable e){tried.add("opt"+opt+" "+e.toString().split("\n")[0]);}
    }
    log.put("strut_shift_m",shift);log.put("strut_move_tries",tried);log.put("strut_moved",ok);}
   catch(Throwable e){log.put("strut_shift_warning","translate not applied: "+e+" (strut y "+sy0+".."+sy1+")");}
  }
  return cm;
 }
 Map<String,Object> bounds(CadModel cm){
  double[] lo={1e9,1e9,1e9},hi={-1e9,-1e9,-1e9};
  for(Object o:cm.getBodyManager().getBodies())for(Object fo:((star.cadmodeler.Body)o).getFaceManager().getFaces()){
   Vector3 nn=new Vector3(0,0,0),cc=new Vector3(0,0,0);((star.cadmodeler.Face)fo).getFaceNormalAndCentroid(cc,nn);
   double[] c=cc.toArray();for(int k=0;k<3;k++){lo[k]=Math.min(lo[k],c[k]);hi[k]=Math.max(hi[k],c[k]);}
  }
  Map<String,Object> r=new LinkedHashMap<>();r.put("x0",lo[0]);r.put("x1",hi[0]);r.put("y0",lo[1]);r.put("y1",hi[1]);r.put("z0",lo[2]);r.put("z1",hi[2]);return r;
 }
 void nameDomainFaces(CadModel cm,Map<String,Object> bb){
  List<String> done=new ArrayList<>();
  for(Object o:cm.getBodyManager().getBodies())for(Object fo:((star.cadmodeler.Body)o).getFaceManager().getFaces()){
   star.cadmodeler.Face f=(star.cadmodeler.Face)fo;Vector3 nv=new Vector3(0,0,0),cv=new Vector3(0,0,0);f.getFaceNormalAndCentroid(cv,nv);
   double[] nn=nv.toArray(),cc=cv.toArray();
   String nm;
   if(Math.abs(nn[0])>0.9)nm=Math.abs(cc[0]-(double)bb.get("x0"))<1e-6?"Inlet":"Outlet";
   else if(Math.abs(nn[1])>0.9)nm=Math.abs(cc[1]-(double)bb.get("y0"))<1e-6?"Bottom":"Top";
   else nm=Math.abs(cc[2]-(double)bb.get("z0"))<1e-6?"Sym":"Side";
   cm.setFaceNameAttributes(List.of(f),nm);done.add(nm);
  }
  log.put("domain_face_names",done);
 }
 void makeParts(CadModel cm){
  try{cm.createParts(new ArrayList<>(cm.getBodyManager().getBodies()),new ArrayList<>(),true,false,1,false,false,3,"SharpEdges",30.0,2,true,1.0E-5,false);}
  catch(Throwable e){log.put("createParts_fallback_"+cm.getPresentationName(),e.toString());cm.createParts();}
  for(GeometryPart g:s.get(SimulationPartManager.class).getLeafParts())
   if(g instanceof SolidModelPart sp&&sp.getCadModel()==cm)g.setPresentationName(cm.getPresentationName().contains("domena")?"STRUT domena":"STRUT NACA wspornik");
 }
 void tess(CadPart cad,double tol){
  try{cad.getTessellationDensityOption().setSelected(TessellationDensityOption.Type.USER_DEFINED);
   TessellationParameters tp=cad.getTessellationDensityOption().getDetailedParameters();
   tp.setIsCurveChordTolerancePercentage(false);tp.setIsSurfacePlaneTolerancePercentage(false);
   tp.setCurveChordTolerance(tol);tp.setSurfacePlaneTolerance(tol);tp.setCurveChordAngle(1.0);tp.setSurfacePlaneAngle(1.0);
   cad.getTessellationDensityOption().setDetailedParameters(tp);cad.tessellate();}catch(Throwable e){log.put("tess_"+cad.getPresentationName(),e.toString());}
 }

 // ---------- fizyka / raporty ----------
 void rewire(Object prof,List<String> waves,String flat,String where,List<String> rew){
  try{
   Object m=prof.getClass().getMethod("getMethod").invoke(prof);
   java.lang.reflect.Method gp=null;try{gp=m.getClass().getMethod("getProfile",int.class);}catch(Throwable e){}
   if(gp!=null){for(int k=0;k<4;k++){try{rewire(gp.invoke(m,k),waves,flat,where+"["+k+"]",rew);}catch(Throwable e){break;}}return;}
   FieldFunction f=(FieldFunction)m.getClass().getMethod("getFieldFunction").invoke(m);
   String n=f.getPresentationName();
   for(String w:waves)if(!w.equals(flat)&&n.endsWith(" of "+w)){
    FieldFunction g=ffByName(n.substring(0,n.length()-w.length())+flat);
    if(g!=null){m.getClass().getMethod("setFieldFunction",FieldFunction.class).invoke(m,g);rew.add(where+": "+n+" -> "+g.getPresentationName());}
    else rew.add(where+": "+n+" (brak odpowiednika dla "+flat+")");
   }
  }catch(Throwable e){}
 }
 void mon(Report r){ReportMonitor rm=r.createMonitor();rm.setPresentationName(r.getPresentationName()+" Monitor");
  try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){} mons.add(rm);}
 List<Monitor> mons=new ArrayList<>();
 void reports(Region region,Boundary strut,double yfs){
  String[][] fo={{"STRUT_Fx_pressure_half","PRESSURE"},{"STRUT_Fx_shear_half","SHEAR"},{"STRUT_Fx_half","PRESSURE_AND_SHEAR"}};
  for(String[] f:fo){ForceReport r=s.getReportManager().createReport(ForceReport.class);r.setPresentationName(f[0]);r.getParts().setObjects(strut);
   r.getDirection().setComponents(1,0,0);
   try{r.getForceOption().setSelected(ForceReportForceOption.Type.valueOf(f[1]));}catch(Throwable e){log.put("forceopt_"+f[0],e.toString());}
   mon(r);}
  ExpressionReport full=s.getReportManager().createReport(ExpressionReport.class);full.setPresentationName("STRUT_D_full_N");full.setDefinition("2*${STRUT_Fx_halfReport}");mon(full);
  ExpressionReport per=s.getReportManager().createReport(ExpressionReport.class);per.setPresentationName("STRUT_D_per_m_submergence_N_m");per.setDefinition("2*${STRUT_Fx_halfReport}/"+H);mon(per);
  String air=cfg.getProperty("air_field","VolumeFractionair"), wat=cfg.getProperty("water_field","VolumeFractionwater");
  UserFieldFunction ven=s.getFieldFunctionManager().createFieldFunction();ven.setPresentationName("STRUT_air_below_level");ven.setFunctionName("STRUT_air_below_level");
  ven.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);ven.setDefinition("($${Position}[1] < "+(yfs-0.05)+") ? $"+air+" : 0");
  SurfaceIntegralReport va=s.getReportManager().createReport(SurfaceIntegralReport.class);va.setPresentationName("STRUT_ventilated_area_half_m2");va.setFieldFunction(ven);va.getParts().setObjects(strut);mon(va);
  SurfaceIntegralReport wa=s.getReportManager().createReport(SurfaceIntegralReport.class);wa.setPresentationName("STRUT_wetted_area_half_m2");wa.setFieldFunction(ff(wat));wa.getParts().setObjects(strut);mon(wa);
  UserFieldFunction top=s.getFieldFunctionManager().createFieldFunction();top.setPresentationName("STRUT_water_height");top.setFunctionName("STRUT_water_height");
  top.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);top.setDefinition("($"+wat+" > 0.5) ? $${Position}[1] - "+yfs+" : -9");
  MaxReport sp=s.getReportManager().createReport(MaxReport.class);sp.setPresentationName("STRUT_max_water_above_level_m");sp.setFieldFunction(top);sp.getParts().setObjects(region);mon(sp);
  UserFieldFunction ic=s.getFieldFunctionManager().createFieldFunction();ic.setPresentationName("STRUT_interface_Courant");ic.setFunctionName("STRUT_interface_Courant");
  ic.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);ic.setDefinition("($"+wat+">0.01 && $"+wat+"<0.99) ? $CourantNumber : 0");
  MaxReport cf=s.getReportManager().createReport(MaxReport.class);cf.setPresentationName("STRUT_interfaceCFL");cf.setFieldFunction(ic);cf.getParts().setObjects(region);mon(cf);
  MinReport yp0=s.getReportManager().createReport(MinReport.class);yp0.setPresentationName("STRUT_yplus_min");yp0.setFieldFunction(ff("WallYplus"));yp0.getParts().setObjects(strut);mon(yp0);
  AreaAverageReport yp=s.getReportManager().createReport(AreaAverageReport.class);yp.setPresentationName("STRUT_yplus_mean");yp.setFieldFunction(ff("WallYplus"));yp.getParts().setObjects(strut);mon(yp);
  try{s.getPlotManager().createMonitorPlot(mons.subList(0,5),"STRUT opor wspornika [N]");
      s.getPlotManager().createMonitorPlot(mons.subList(5,mons.size()),"STRUT wentylacja, bryzg, CFL, y+");}catch(Throwable e){log.put("plot_warning",e.toString());}
  List<String> rn=new ArrayList<>();for(Monitor mm:mons)rn.add(mm.getPresentationName());log.put("reports",rn);
 }
 void scenes(Region region,Map<String,Boundary> bnd,FvRepresentation fv,double yfs)throws Exception{
  Scene sc=s.getSceneManager().createScene("STRUT siatka - plaszczyzna symetrii");sc.initializeAndWait();
  PartDisplayer pd=sc.getDisplayerManager().createPartDisplayer("Sym + wspornik");
  pd.getInputParts().setObjects(bnd.get("span_front"),bnd.get("main"));pd.setRepresentation(fv);pd.setMesh(true);
  sc.getCurrentView().setInput(new DoubleVector(new double[]{0.5,yfs,0}),new DoubleVector(new double[]{0.5,yfs,8}),new DoubleVector(new double[]{0,1,0}),1.2,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
  sc.printAndWait(out.resolve("STRUT_MESH_SYM.png").toString(),1,1600,900);
 }

 // ---------- siatka / narzedzia ----------
 void setRel(Object o,double pct){
  for(String mth:new String[]{"setRelativeSize","setPercentage","setValue"})
   try{o.getClass().getMethod(mth,double.class).invoke(o,pct);return;}catch(Throwable e){}
  throw new IllegalStateException("cannot set relative size on "+o.getClass());
 }
 void volume(AutoMeshOperation am,String name,double[] lo,double[] hi,double iso,double[] aniso){
  SimpleBlockPart p=s.get(MeshPartFactory.class).createNewBlockPart(s.getGeometryPartManager());
  p.setPresentationName(name);p.setCorners(new DoubleVector(lo),new DoubleVector(hi));p.rebuildSimpleShapePart();
  VolumeCustomMeshControl c=am.getCustomMeshControls().createVolumeControl();c.setPresentationName(name);c.getGeometryObjects().setObjects(p);
  VolumeControlTrimmerSizeOption t=c.getCustomConditions().get(VolumeControlTrimmerSizeOption.class);
  t.setVolumeControlBaseSizeOption(true);
  c.getCustomValues().get(VolumeControlSize.class).setRelativeSize(100*iso/B);
  if(aniso!=null){
   try{t.setTrimmerAnisotropicSizeOption(true);
    TrimmerAnisotropicSize ta=c.getCustomValues().get(TrimmerAnisotropicSize.class);
    try{ta.getRelativeOrAbsoluteOption().setSelected(RelativeOrAbsoluteOption.Type.RELATIVE);}catch(Throwable e){}
    if(!Double.isNaN(aniso[0])){ta.setXSize(true);setRel(ta.getRelativeXSize(),100*aniso[0]/B);}
    if(!Double.isNaN(aniso[1])){ta.setYSize(true);setRel(ta.getRelativeYSize(),100*aniso[1]/B);}
    if(!Double.isNaN(aniso[2])){ta.setZSize(true);setRel(ta.getRelativeZSize(),100*aniso[2]/B);}
    log.put("aniso_"+name,"ok");
   }catch(Throwable e){log.put("aniso_"+name,"FALLBACK isotropic: "+e);}
  }
 }
 double metric(String name,NamedObject part,boolean minimum){
  AnalysisReport q2=minimum?s.getReportManager().createReport(MinReport.class):s.getReportManager().createReport(MaxReport.class);
  FieldFunction f=ff(name);
  if(q2 instanceof MinReport low)low.setFieldFunction(f);else ((MaxReport)q2).setFieldFunction(f);
  q2.getParts().setObjects(part);q2.setSmooth(false);q2.setPresentationName("STRUT mesh "+(minimum?"min ":"max ")+name);
  return q2.getReportMonitorValue();
 }
 boolean drop(Object mgr,Object obj){
  for(String mth:new String[]{"removeObjects","remove","deleteChildren","deleteObjects","removeParts"}){
   for(java.lang.reflect.Method mm:mgr.getClass().getMethods()){
    if(!mm.getName().equals(mth)||mm.getParameterCount()!=1)continue;
    try{Class<?> pt=mm.getParameterTypes()[0];
     if(pt.isArray()){Object arr=java.lang.reflect.Array.newInstance(pt.getComponentType(),1);java.lang.reflect.Array.set(arr,0,obj);mm.invoke(mgr,arr);}
     else if(Collection.class.isAssignableFrom(pt))mm.invoke(mgr,List.of(obj));
     else if(pt.isInstance(obj))mm.invoke(mgr,obj);else continue;
     return true;}catch(Throwable e){}
   }
  }
  return false;
 }
 String nm(Object o){try{return ((NamedObject)o).getPresentationName();}catch(Throwable e){return "";}}
 int sweep(Object mgr,java.util.function.Predicate<Object> del,int passes){
  int total=0;
  for(int p=0;p<passes;p++){int n=0;List<Object> objs;
   try{objs=new ArrayList<>((Collection<?>)mgr.getClass().getMethod("getObjects").invoke(mgr));}catch(Throwable e){return total;}
   for(Object o:objs){try{if(del.test(o)&&drop(mgr,o))n++;}catch(Throwable e){}}
   total+=n;if(n==0)break;}
  return total;
 }
 void cleanup(){
  Map<String,Integer> c=new LinkedHashMap<>();
  c.put("scenes",sweep(s.getSceneManager(),o->true,1));
  c.put("plots",sweep(s.getPlotManager(),o->true,1));
  c.put("tables",sweep(s.getTableManager(),o->true,1));
  c.put("monitors",sweep(s.getMonitorManager(),o->!(o instanceof ResidualMonitor),1));
  c.put("reports",sweep(s.getReportManager(),o->true,6));
  c.put("derived_parts",sweep(s.getPartManager(),o->true,4));
  c.put("mesh_operations",sweep(s.get(MeshOperationManager.class),o->true,2));
  c.put("user_field_functions",sweep(s.getFieldFunctionManager(),o->o instanceof UserFieldFunction&&!nm(o).startsWith("CB_"),3));
  c.put("reports_left",s.getReportManager().getObjects().size());
  log.put("cleanup",c);
 }
}
