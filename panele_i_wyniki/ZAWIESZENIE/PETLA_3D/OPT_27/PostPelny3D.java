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
  double zc=gap/2, xc=0.25*c, L=Math.max(hs,1.0);
  // 02-04 Cp na powierzchni
  Scene a=sc("P3D 02 Cp na platach - widok z gory (grzbiet dolnego, spod gornego od wewnatrz niewidoczny)");
  scal(a,"Cp",walls,cp,-1.2,1.0); view(a,new double[]{xc,hs/2,zc},new double[]{xc,hs/2,zc+30},new double[]{-1,0,0},L*0.62); png(a,"02_CP_GORA");
  Scene b=sc("P3D 03 Cp na platach - widok z dolu");
  scal(b,"Cp",walls,cp,-1.2,1.0); view(b,new double[]{xc,hs/2,zc},new double[]{xc,hs/2,zc-30},new double[]{-1,0,0},L*0.62); png(b,"03_CP_DOL");
  Scene b2=sc("P3D 04 Cp - widok izometryczny");
  scal(b2,"Cp",walls,cp,-1.2,1.0); view(b2,new double[]{xc,hs/2,zc},new double[]{xc-6,hs/2-5,zc+4},new double[]{0,0,1},L*0.62); png(b2,"04_CP_ISO");
  // 05 tarcie scienne, 06 y+
  if(tau!=null){Scene t=sc("P3D 05 Naprezenie styczne |tau_w| [Pa] - z gory (linie oderwania = minima)");
   scal(t,"|tau_w|",walls,((PrimitiveFieldFunction)tau).getMagnitudeFunction(),0,400); view(t,new double[]{xc,hs/2,zc},new double[]{xc,hs/2,zc+30},new double[]{-1,0,0},L*0.62); png(t,"05_TARCIE");}
  if(yp!=null){Scene t=sc("P3D 06 y+ pierwszej komorki (funkcja scianowa: 30-100)");
   scal(t,"y+",walls,yp,0,120); view(t,new double[]{xc,hs/2,zc},new double[]{xc-6,hs/2-5,zc+4},new double[]{0,0,1},L*0.62); png(t,"06_YPLUS");}
  // 07 wiry: izopowierzchnia Q (lub |omega|) kolorowana wirowoscia wzdluzna
  IsoPart iso=s.getPartManager().createIsoPart(); iso.getInputParts().setObjects(rg);
  if(q!=null){iso.setFieldFunction(q);iso.setMode(IsoMode.ISOVALUE_SINGLE);iso.getSingleIsoValue().setValue(Math.pow(U/c,2)*2);iso.setPresentationName("P3D izopowierzchnia Q = 2 (U/c)^2");}
  else{iso.setFieldFunction(((PrimitiveFieldFunction)vort).getMagnitudeFunction());iso.setMode(IsoMode.ISOVALUE_SINGLE);iso.getSingleIsoValue().setValue(3*U/c);iso.setPresentationName("P3D izopowierzchnia |omega| = 3 U/c");}
  Scene w=sc("P3D 07 Wiry - izopowierzchnia kolorowana wirowoscia wzdluzna omega_x [1/s]");
  scal(w,"omega_x",List.of(iso),wx,-60,60); outline(w); view(w,new double[]{1.5,hs/2,zc},new double[]{-5,hs/2-7,zc+5},new double[]{0,0,1},Math.max(L*0.75,2.5)); png(w,"07_WIRY_ISO");
  // 08 wirowosc wzdluzna w przekrojach za platem
  List<Part> pls=new ArrayList<>(); for(double x:new double[]{xc+c,1.0,3.0}){pls.add(plane("P3D przekroj x = "+String.format(Locale.ROOT,"%.2f",x)+" m",new double[]{x,0,0},new double[]{1,0,0}));}
  Scene w2=sc("P3D 08 Wirowosc wzdluzna omega_x w przekrojach x = 1c za platem, 1 m, 3 m");
  scal(w2,"omega_x",pls,wx,-40,40); outline(w2); view(w2,new double[]{1.5,hs/2,zc},new double[]{8,hs/2+6,zc+3},new double[]{0,0,1},Math.max(L*0.75,2.5)); png(w2,"08_WIRY_PRZEKROJE");
  // 09 przekroj przez plaskie platy (y = polowa plaskiej czesci): predkosc + LIC
  double yflat=Math.max(0.1,(yl-c)/2);
  PlaneSection py=plane("P3D przekroj y = "+String.format(Locale.ROOT,"%.2f",yflat)+" m (plaskie platy)",new double[]{0,yflat,0},new double[]{0,1,0});
  Scene v=sc("P3D 09 Predkosc |U| i linie pradu (LIC) w przekroju przez plaskie platy");
  scal(v,"|U|",List.of(py),vmag,0.6*U,1.3*U); lic(v,py,vel); view(v,new double[]{xc+0.2,yflat,zc},new double[]{xc+0.2,yflat+30,zc},new double[]{0,0,1},Math.max(gap,c)*1.1+0.3); png(v,"09_PREDKOSC_PRZEKROJ_Y");
  Scene v2=sc("P3D 10 Cp w przekroju przez plaskie platy (podcisnienie na grzbiecie, wplyw platow na siebie)");
  scal(v2,"Cp",List.of(py),cp,-1.2,1.0); view(v2,new double[]{xc+0.2,yflat,zc},new double[]{xc+0.2,yflat+30,zc},new double[]{0,0,1},Math.max(gap,c)*1.1+0.3); png(v2,"10_CP_PRZEKROJ_Y");
  // 11 przekroj poziomy przez srodek luku: profil luku i jego opor
  PlaneSection pz=plane("P3D przekroj z = "+String.format(Locale.ROOT,"%.2f",zc)+" m (srodek luku)",new double[]{0,0,zc},new double[]{0,0,1});
  Scene k=sc("P3D 11 Cp i linie pradu w przekroju poziomym przez srodek luku");
  scal(k,"Cp",List.of(pz),cp,-0.6,1.0); lic(k,pz,vel); view(k,new double[]{xc+0.2,yl,zc},new double[]{xc+0.2,yl,zc+30},new double[]{-1,0,0},Math.max(4*c,0.8)); png(k,"11_LUK_PRZEKROJ_Z");
  // 12 slad: deficyt predkosci osiowej 1 m za platem
  Scene sl=sc("P3D 12 Slad: predkosc osiowa U_x w przekroju x = 1 m");
  scal(sl,"U_x",List.of(pls.get(1)),vx,0.85*U,1.05*U); outline(sl); view(sl,new double[]{1.0,hs/2,zc},new double[]{-10,hs/2,zc},new double[]{0,0,1},L*0.62); png(sl,"12_SLAD");
  s.saveState(out.resolve("PETLA_KONIEC.sim").toString());
 }
 Scene sc(String n){Scene x=s.getSceneManager().createScene(n);x.setPresentationName(n);x.initializeAndWait();return x;}
 void scal(Scene x,String n,Collection<?> parts,FieldFunction f,double lo,double hi){
  ScalarDisplayer d=x.getDisplayerManager().createScalarDisplayer(n);d.getInputParts().setObjects((Collection)parts);d.getScalarDisplayQuantity().setFieldFunction(f);
  try{d.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{lo,hi}));d.getScalarDisplayQuantity().setClip(ClipMode.NONE);}catch(Throwable e){}}
 void outline(Scene x){PartDisplayer o=x.getDisplayerManager().createPartDisplayer("Platy");o.getInputParts().setObjects(walls);o.setSurface(true);o.setOutline(false);try{o.setOpacity(0.5);}catch(Throwable e){}}
 void lic(Scene x,Part p,FieldFunction v){VectorDisplayer l=x.getDisplayerManager().createVectorDisplayer("Linie pradu (LIC)");l.getInputParts().setObjects(p);
  l.getVectorDisplayQuantity().setFieldFunction(v);l.setDisplayMode(VectorDisplayMode.VECTOR_DISPLAY_MODE_LIC);try{l.setOpacity(0.55);}catch(Throwable e){}}
 PlaneSection plane(String n,double[] o,double[] nv){PlaneSection p=s.getPartManager().createPlaneSection();p.setPresentationName(n);p.getInputParts().setObjects(rg);
  p.setOrigin(new DoubleVector(o));p.setOrientation(new DoubleVector(nv));return p;}
 void view(Scene x,double[] f,double[] p,double[] up,double scale){
  x.getCurrentView().setInput(new DoubleVector(f),new DoubleVector(p),new DoubleVector(up),scale,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);}
 void png(Scene x,String n){try{x.printAndWait(out.resolve("P3D_SC_"+n+".png").toString(),1,1600,1000);}catch(Throwable e){}}
}
