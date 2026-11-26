package macro;
import star.common.*;import star.base.neo.*;import star.vis.*;
import java.nio.file.*;import java.util.*;

/** ShowFreeSurface - natywne sceny STAR z zapisanego stanu wspornika (kopia checkpointu, niczego nie zapisuje):
 *  1) izopowierzchnia wody (alpha 0,5) kolorowana wysokoscia nad poziomem spokojnym, widok z gory-z boku
 *  2) to samo z gory
 *  3) plaszczyzna symetrii (przekroj przez cieciwe wspornika): udzial wody, zblizenie na fale dziobowa
 *  PNG do MINI_CASE_DIR. Sceny zostaja w pliku tylko jesli ktos go zapisze w GUI. */
public class ShowFreeSurface extends StarMacro {
 public void execute(){
  Simulation s=getActiveSimulation();
  Path out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  double yfs=Double.parseDouble(System.getenv().getOrDefault("STRUT_YFS","1.09"));
  StringBuilder log=new StringBuilder();
  try{
   Region region=s.getRegionManager().getRegions().iterator().next();
   Boundary strut=null,sym=null;
   for(Boundary b:region.getBoundaryManager().getBoundaries()){String n=b.getPresentationName();if(n.endsWith("Strut"))strut=b;if(n.endsWith("Sym"))sym=b;}
   FieldFunction alpha=s.getFieldFunctionManager().getFunction("VolumeFractionwater");
   UserFieldFunction eta=s.getFieldFunctionManager().createFieldFunction();eta.setPresentationName("STRUT_wysokosc_nad_poziomem");eta.setFunctionName("STRUT_eta_viz");
   eta.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);eta.setDefinition("$${Position}[1] - "+yfs);
   IsoPart iso=s.getPartManager().createIsoPart(new Vector<NamedObject>(List.of(region)),alpha);
   iso.setPresentationName("powierzchnia swobodna (alpha 0.5)");iso.getSingleIsoValue().setValue(0.5);
   FvRepresentation fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
   log.append("t=").append(s.getSolution().getPhysicalTime()).append("\n");
   // 1 + 2: izopowierzchnia
   Scene sc=s.getSceneManager().createScene("STRUT powierzchnia swobodna");sc.initializeAndWait();
   ScalarDisplayer sd=sc.getDisplayerManager().createScalarDisplayer("wysokosc wody nad poziomem [m]");
   sd.getInputParts().setObjects(iso);sd.getScalarDisplayQuantity().setFieldFunction(eta);
   try{sd.getScalarDisplayQuantity().setRangeMin(-0.15);sd.getScalarDisplayQuantity().setRangeMax(0.45);}catch(Throwable e){log.append("range ").append(e).append("\n");}
   PartDisplayer pd=sc.getDisplayerManager().createPartDisplayer("wspornik");pd.getInputParts().setObjects(strut);pd.setRepresentation(fv);
   CoordinateSystem lab=s.getCoordinateSystemManager().getLabCoordinateSystem();
   sc.getCurrentView().setInput(new DoubleVector(new double[]{1.2,yfs,0.6}),new DoubleVector(new double[]{-3.5,yfs+4.0,5.5}),new DoubleVector(new double[]{0,1,0}),1.6,1,lab,false);
   sc.printAndWait(out.resolve("FS_1_widok_skos.png").toString(),1,1800,1000);
   sc.getCurrentView().setInput(new DoubleVector(new double[]{1.6,yfs,1.0}),new DoubleVector(new double[]{1.6,yfs+8,1.0}),new DoubleVector(new double[]{-1,0,0}),2.2,1,lab,false);
   sc.printAndWait(out.resolve("FS_2_widok_z_gory.png").toString(),1,1800,1000);
   sc.getCurrentView().setInput(new DoubleVector(new double[]{0.3,yfs+0.1,0.15}),new DoubleVector(new double[]{-1.2,yfs+1.0,1.6}),new DoubleVector(new double[]{0,1,0}),0.45,1,lab,false);
   sc.printAndWait(out.resolve("FS_3_zblizenie_dziob.png").toString(),1,1800,1000);
   // 4: plaszczyzna symetrii, udzial wody
   Scene s2=s.getSceneManager().createScene("STRUT przekroj przez cieciwe");s2.initializeAndWait();
   ScalarDisplayer a2=s2.getDisplayerManager().createScalarDisplayer("udzial wody");a2.getInputParts().setObjects(sym);a2.getScalarDisplayQuantity().setFieldFunction(alpha);
   try{a2.getScalarDisplayQuantity().setRangeMin(0);a2.getScalarDisplayQuantity().setRangeMax(1);}catch(Throwable e){}
   s2.getCurrentView().setInput(new DoubleVector(new double[]{0.6,yfs+0.1,0}),new DoubleVector(new double[]{0.6,yfs+0.1,6}),new DoubleVector(new double[]{0,1,0}),0.55,1,lab,false);
   s2.printAndWait(out.resolve("FS_4_przekroj_cieciwa.png").toString(),1,1800,1000);
  }catch(Throwable e){log.append("ERROR ").append(e).append("\n");}
  try{Files.writeString(out.resolve("SHOW_FS.txt"),log.toString());}catch(Exception e){}
 }
}
