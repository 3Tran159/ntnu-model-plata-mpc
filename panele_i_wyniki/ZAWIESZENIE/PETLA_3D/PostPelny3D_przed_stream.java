package macro;
import star.common.*;import star.base.neo.*;import star.vis.*;import java.nio.file.*;import java.util.*;

/** PostPelny3D - komplet natywnych scen objasniajacych (zapisanych w symulacji, edytowalnych w GUI) dla jednego przypadku petli/platu.
 *  Parametry z post.properties w folderze przypadku: hs (pol rozpietosci), gap (odstep), c (cieciwa), yluk (y srodka luku), U, rho.
 *  Sceny "P3D 01..12" + PNG P3D_SC_XX_*.png. Zapis do PETLA_KONIEC.sim. Agent D, 16.11.2026. */
public class PostPelny3D extends StarMacro {
 Simulation s; Path out; Properties pr=new Properties(); Region rg; List<Boundary> walls=new ArrayList<>(); Units m;
 double d(String k,double def){return Double.parseDouble(pr.getProperty(k,""+def));}
 public void execute(){
  s=getActiveSimulation(); out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{pr.load(Files.newBufferedReader(out.resolve("post.properties")));}catch(Exception e){}
  double hs=d("hs",2),gap=d("gap",0),c=d("c",0.3),yl=d("yluk",hs),U=d("U",12.347),rho=d("rho",997.561);
  for(Scene x:new ArrayList<>(s.getSceneManager().getScenes()))if(x.getPresentationName().matches("P3D (0[2-9]|1[0-9]) .*"))s.getSceneManager().deleteScenes(new NeoObjectVector(new Object[]{x}));
  for(Part x:new ArrayList<>(s.getPartManager().getObjects()))if(x.getPresentationName().startsWith("P3D przekroj ")||x.getPresentationName().startsWith("P3D izopowierzchnia"))try{s.getPartManager().removeObjects(x);}catch(Throwable e){}
  rg=s.getRegionManager().getRegions().iterator().next();
  for(Boundary b:rg.getBoundaryManager().getBoundaries())if(b.getPresentationName().contains("bryla"))walls.add(b);
  FieldFunctionManager fm=s.getFieldFunctionManager();
  UserFieldFunction cp=fm.createFieldFunction(); cp.setPresentationName("P3D Cp"); cp.setFunctionName("P3D_Cp");
  cp.setDefinition("$Pressure/(0.5*"+rho+"*"+U+"*"+U+")");
  PrimitiveFieldFunction vel=(PrimitiveFieldFunction)fm.getFunction("Velocity");
  FieldFunction vmag=vel.getMagnitudeFunction(), vx=vel.getComponentFunction(0);
  FieldFunction vort=null,q=null,tau=null,yp=null;
  for(FieldFunction f:fm.getObjects()){String n=f.getFunctionName();
   if(f instanceof PrimitiveFieldFunction&&n.startsWith("Vorticity")&&(vort==null||n.equals("VorticityVector")))vort=f;
   if(n.toLowerCase().contains("qcriterion")||n.toLowerCase().equals("q_criterion"))q=f;
   if(n.equals("WallShearStress"))tau=f; if(n.equals("WallYplus"))yp=f;}
  FieldFunction wx=((PrimitiveFieldFunction)vort).getComponentFunction(0);
  double zc=gap/2, xc=0.25*c, L=Math.max(hs,1.0); final FieldFunction fwx=wx, fq=q, ftau=tau, fyp=yp, fvort=vort, fcp=cp, fvmag=vmag, fvx=vx; final PrimitiveFieldFunction fvel=vel;
  step("02",()->{Scene a=sc("P3D 02 Cp na platach - widok z gory");scal(a,"Cp",walls,fcp,-1.2,1.0);view(a,new double[]{xc,hs/2,zc},new double[]{xc,hs/2,zc+30},new double[]{-1,0,0},L*0.62);png(a,"02_CP_GORA");});
  step("03",()->{Scene b=sc("P3D 03 Cp na platach - widok z dolu");scal(b,"Cp",walls,fcp,-1.2,1.0);view(b,new double[]{xc,hs/2,zc},new double[]{xc,hs/2,zc-30},new double[]{-1,0,0},L*0.62);png(b,"03_CP_DOL");});
  step("04",()->{Scene b2=sc("P3D 04 Cp - widok izometryczny");scal(b2,"Cp",walls,fcp,-1.2,1.0);view(b2,new double[]{xc,hs/2,zc},new double[]{xc-6,hs/2-5,zc+4},new double[]{0,0,1},L*0.62);png(b2,"04_CP_ISO");});
  step("05",()->{Scene t=sc("P3D 05 Naprezenie styczne |tau_w| [Pa] - z gory (oderwanie = minima)");scal(t,"|tau_w|",walls,((PrimitiveFieldFunction)ftau).getMagnitudeFunction(),0,400);view(t,new double[]{xc,hs/2,zc},new double[]{xc,hs/2,zc+30},new double[]{-1,0,0},L*0.62);png(t,"05_TARCIE");});
  step("06",()->{Scene t=sc("P3D 06 y+ pierwszej komorki (funkcja scianowa 30-100)");scal(t,"y+",walls,fyp,0,120);view(t,new double[]{xc,hs/2,zc},new double[]{xc-6,hs/2-5,zc+4},new double[]{0,0,1},L*0.62);png(t,"06_YPLUS");});
  step("07",()->{IsoPart iso=s.getPartManager().createIsoPart();iso.getInputParts().setObjects(rg);
   if(fq!=null){iso.setFieldFunction(fq);iso.setMode(IsoMode.ISOVALUE_SINGLE);iso.getSingleIsoValue().setValue(Math.pow(U/c,2)*25);iso.setPresentationName("P3D izopowierzchnia Q = 25 (U/c)^2");}
   else{iso.setFieldFunction(((PrimitiveFieldFunction)fvort).getMagnitudeFunction());iso.setMode(IsoMode.ISOVALUE_SINGLE);iso.getSingleIsoValue().setValue(12*U/c);iso.setPresentationName("P3D izopowierzchnia |omega| = 12 U/c");}
   Scene w=sc("P3D 07 Wiry - izopowierzchnia kolorowana wirowoscia wzdluzna omega_x [1/s]");scal(w,"omega_x",List.of(iso),fwx,-60,60);outline(w);view(w,new double[]{1.5,hs/2,zc},new double[]{-5,hs/2-7,zc+5},new double[]{0,0,1},Math.max(L*0.75,2.5));png(w,"07_WIRY_ISO");});
  final List<Part> pls=new ArrayList<>();
  step("08",()->{for(double x:new double[]{xc+c,1.0,3.0})pls.add(plane("P3D przekroj x = "+String.format(Locale.ROOT,"%.2f",x)+" m",new double[]{x,0,0},new double[]{1,0,0}));
   Scene w2=sc("P3D 08 Wirowosc wzdluzna omega_x w przekrojach x = 1c za platem, 1 m, 3 m");scal(w2,"omega_x",pls,fwx,-40,40);outline(w2);view(w2,new double[]{1.5,hs/2,zc},new double[]{8,hs/2+6,zc+3},new double[]{0,0,1},Math.max(L*0.75,2.5));png(w2,"08_WIRY_PRZEKROJE");});
  final double yflat=Math.max(0.1,(yl-c)/2); final PlaneSection[] py=new PlaneSection[1];
  step("09",()->{py[0]=plane("P3D przekroj y = "+String.format(Locale.ROOT,"%.2f",yflat)+" m (plaskie platy)",new double[]{0,yflat,0},new double[]{0,1,0});
   Scene v=sc("P3D 09 Predkosc |U| i linie pradu (LIC) w przekroju przez plaskie platy");scal(v,"|U|",List.of(py[0]),fvmag,0.6*U,1.3*U);lic(v,py[0],fvel);view(v,new double[]{xc+0.2,yflat,zc},new double[]{xc+0.2,yflat+30,zc},new double[]{0,0,1},Math.max(gap,c)*1.1+0.3);png(v,"09_PREDKOSC_PRZEKROJ_Y");});
  step("10",()->{Scene v2=sc("P3D 10 Cp w przekroju przez plaskie platy");scal(v2,"Cp",List.of(py[0]),fcp,-1.2,1.0);view(v2,new double[]{xc+0.2,yflat,zc},new double[]{xc+0.2,yflat+30,zc},new double[]{0,0,1},Math.max(gap,c)*1.1+0.3);png(v2,"10_CP_PRZEKROJ_Y");});
  step("11",()->{PlaneSection pz=plane("P3D przekroj z = "+String.format(Locale.ROOT,"%.2f",zc)+" m (srodek luku)",new double[]{0,0,zc},new double[]{0,0,1});
   Scene k=sc("P3D 11 Cp i linie pradu w przekroju poziomym przez srodek luku");scal(k,"Cp",List.of(pz),fcp,-0.6,1.0);lic(k,pz,fvel);view(k,new double[]{xc+0.2,yl,zc},new double[]{xc+0.2,yl,zc+30},new double[]{-1,0,0},1.3*c+0.05);png(k,"11_LUK_PRZEKROJ_Z");});
  step("12",()->{Scene sl=sc("P3D 12 Slad: predkosc osiowa U_x w przekroju x = 1 m");scal(sl,"U_x",List.of(pls.get(1)),fvx,0.85*U,1.05*U);outline(sl);view(sl,new double[]{1.0,hs/2,zc},new double[]{-10,hs/2,zc},new double[]{0,0,1},L*0.62);png(sl,"12_SLAD");});
  s.saveState(out.resolve("PETLA_KONIEC.sim").toString());
 }
 void step(String n,Runnable r){try{r.run();s.println("POST krok "+n+" OK");}catch(Throwable e){s.println("POST BLAD krok "+n+": "+e);StackTraceElement[] st=e.getStackTrace();for(int i=0;i<Math.min(6,st.length);i++)s.println("   "+st[i]);}}
 Scene sc(String n){Scene x=s.getSceneManager().createScene(n);x.setPresentationName(n);x.initializeAndWait();return x;}
 void scal(Scene x,String n,Collection<?> parts,FieldFunction f,double lo,double hi){
  ScalarDisplayer d=x.getDisplayerManager().createScalarDisplayer(n);d.getInputParts().setObjects((Collection)parts);d.getScalarDisplayQuantity().setFieldFunction(f);
  try{d.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{lo,hi}));d.getScalarDisplayQuantity().setClip(ClipMode.NONE);}catch(Throwable e){}}
 void outline(Scene x){PartDisplayer o=x.getDisplayerManager().createPartDisplayer("Platy");o.getInputParts().setObjects(walls);o.setSurface(true);o.setOutline(false);try{o.setOpacity(0.5);}catch(Throwable e){}}
 void lic(Scene x,Part p,FieldFunction v){VectorDisplayer l=x.getDisplayerManager().createVectorDisplayer("Linie pradu (LIC)");l.getInputParts().setObjects(p);
  l.getVectorDisplayQuantity().setFieldFunction(v);l.setDisplayMode(VectorDisplayMode.VECTOR_DISPLAY_MODE_LIC);try{l.setOpacity(0.3);}catch(Throwable e){}}
 PlaneSection plane(String n,double[] o,double[] nv){PlaneSection p=s.getPartManager().createPlaneSection();p.setPresentationName(n);p.getInputParts().setObjects(rg);
  p.setOrigin(new DoubleVector(o));p.setOrientation(new DoubleVector(nv));return p;}
 void view(Scene x,double[] f,double[] p,double[] up,double scale){
  x.getCurrentView().setInput(new DoubleVector(f),new DoubleVector(p),new DoubleVector(up),scale,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);}
 void png(Scene x,String n){try{x.printAndWait(out.resolve("P3D_SC_"+n+".png").toString(),1,1600,1000);}catch(Throwable e){}}
}
