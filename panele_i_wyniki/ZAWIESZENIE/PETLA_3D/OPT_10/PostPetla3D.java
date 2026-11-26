package macro;
import star.common.*;import star.base.neo.*;import star.vis.*;import java.nio.file.*;import java.util.*;

/** PostPetla3D - natywne sceny wynikow (zapisane w symulacji): cisnienie na platach i wirowosc wzdluzna w przekroju x = 1 m
 *  za platami (wir koncowy vs petla). Uruchamiane na PETLA_KONIEC.sim. Agent D, 15.11.2026. */
public class PostPetla3D extends StarMacro {
 Simulation s; Path out;
 public void execute(){
  s=getActiveSimulation(); out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  Region rg=s.getRegionManager().getRegions().iterator().next(); List<Boundary> walls=new ArrayList<>();
  for(Boundary b:rg.getBoundaryManager().getBoundaries())if(b.getPresentationName().contains("bryla"))walls.add(b);
  FieldFunction p=s.getFieldFunctionManager().getFunction("Pressure");
  FieldFunction vv=null; for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f instanceof PrimitiveFieldFunction&&f.getFunctionName().startsWith("Vorticity")&&(vv==null||f.getFunctionName().equals("VorticityVector")))vv=f;
  FieldFunction vx=((PrimitiveFieldFunction)vv).getComponentFunction(0);
  Scene a=s.getSceneManager().createScene("P3D wynik cisnienie");a.setPresentationName("P3D wynik: cisnienie na platach");a.initializeAndWait();
  ScalarDisplayer sd=a.getDisplayerManager().createScalarDisplayer("Cisnienie");sd.getInputParts().setObjects(walls);sd.getScalarDisplayQuantity().setFieldFunction(p);
  try{sd.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{-60000,40000}));}catch(Throwable e){}
  view(a,new double[]{0.3,2.0,0.5},new double[]{-5.5,-3.5,4.5},2.4);a.printAndWait(out.resolve("P3D_WYNIK_CISNIENIE.png").toString(),1,1600,1000);
  PlaneSection pl=s.getPartManager().createPlaneSection();pl.setPresentationName("P3D przekroj x = 1 m");pl.getInputParts().setObjects(rg);
  pl.setOrigin(new DoubleVector(new double[]{1.0,0,0}));pl.setOrientation(new DoubleVector(new double[]{1,0,0}));
  Scene b=s.getSceneManager().createScene("P3D wynik wirowosc");b.setPresentationName("P3D wynik: wirowosc wzdluzna x = 1 m");b.initializeAndWait();
  ScalarDisplayer vd=b.getDisplayerManager().createScalarDisplayer("Wirowosc x");vd.getInputParts().setObjects(pl);vd.getScalarDisplayQuantity().setFieldFunction(vx);
  try{vd.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{-40,40}));}catch(Throwable e){}
  PartDisplayer od=b.getDisplayerManager().createPartDisplayer("Platy");od.getInputParts().setObjects(walls);od.setOutline(true);od.setSurface(false);
  view(b,new double[]{1.0,2.4,0.5},new double[]{-10,2.4,0.5},2.4);b.printAndWait(out.resolve("P3D_WYNIK_WIRY.png").toString(),1,1600,1000);
  s.saveState(out.resolve("PETLA_KONIEC.sim").toString());
 }
 void view(Scene sc,double[] f,double[] p,double scale){
  sc.getCurrentView().setInput(new DoubleVector(f),new DoubleVector(p),new DoubleVector(new double[]{0,0,1}),scale,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
 }
}
