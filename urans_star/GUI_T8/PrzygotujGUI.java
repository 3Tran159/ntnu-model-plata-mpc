package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.vis.*;
import java.io.*;import java.nio.file.*;import java.util.*;import java.lang.reflect.*;

/** PrzygotujGUI - 26.11 (Julek 10:27: "przygotuj w GUI tej symulki na MPC URANS wykresy, sceny, wszystkie bajery pod samodzielne ogladanie").
 *  Na kopii END_t36.0000.sim z OVS_CEL_005g_T8_90 (fala czolowa T 8 s, H 1,5 m, jeden MPC, cel 0,05 g):
 *  - 10 scen natywnych (powierzchnia cala / przy placie, predkosc, wirowosc, cisnienie, woda nad platem, linie pradu, LIC, siatka overset),
 *  - tabela HISTORIA_T8_005g.csv (cala historia 0-36 s) i 6 wykresow XY z niej,
 *  - PNG kazdej sceny i wykresu w GUI_PNG\, zapis OVS_CEL_005g_T8_90_GUI.sim. Wszystko edytowalne w GUI. Log: GUI_LOG.txt */
public class PrzygotujGUI extends StarMacro {
 Simulation s; Path out; StringBuilder L=new StringBuilder();
 void log(String m){L.append(m).append("\n");try{Files.writeString(out.resolve("GUI_LOG.txt"),L.toString());}catch(Exception e){}}
 static Object call(Object o,String m,Object... a)throws Exception{
  for(Method x:o.getClass().getMethods()) if(x.getName().equals(m)&&x.getParameterCount()==a.length){ try{return x.invoke(o,a);}catch(IllegalArgumentException e){} }
  throw new NoSuchMethodException(o.getClass().getSimpleName()+"."+m+"/"+a.length);
 }
 DoubleVector dv(double... d){return new DoubleVector(d);}
 void view(Scene sc,double x,double y,double wd,int W,int H){ sc.getCurrentView().setInput(dv(x,y,0),dv(x,y,5),dv(0,1,0),wd*H/W/2,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false); }
 Scene nowa(String n){ for(Scene x:s.getSceneManager().getScenes()) if(x.getPresentationName().equals(n)) return x; Scene sc=s.getSceneManager().createScene(n); sc.setPresentationName(n); sc.initializeAndWait(); return sc; }
 void png(Scene sc,String n,int W,int H){ try{ sc.printAndWait(out.resolve("GUI_PNG").resolve(n+".png").toString(),1,W,H); log("png "+n); }catch(Throwable e){ log("PNG BLAD "+n+": "+e); } }

 public void execute(){
  s=getActiveSimulation(); out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{Files.createDirectories(out.resolve("GUI_PNG"));}catch(Exception e){}
  s.getSimulationIterator().getAutoSave().setEnabled(false);
  log("czas rozwiazania "+s.getSolution().getPhysicalTime()+" s");
  Collection<Region> regs=s.getRegionManager().getRegions(); FieldFunctionManager fm=s.getFieldFunctionManager();
  PlaneSection scp=null; for(Object o:s.getPartManager().getObjects()) if(o instanceof PlaneSection pp&&pp.getPresentationName().equals("GODO_scene_plane")) scp=pp;
  if(scp==null){ scp=s.getPartManager().createPlaneSection(); scp.setPresentationName("GODO_scene_plane"); scp.getInputParts().setObjects(regs); scp.setOrigin(dv(0,0,0.01)); scp.setOrientation(dv(0,0,1)); }
  // ---- sceny skalarne: nazwa, pole, x, y, szerokosc widoku [m], W, H, zakres min, max
  String[][] spec={{"T8_01_powierzchnia_cala_domena","vof","23.4","1.09","112","1920","420","0","1"},
   {"T8_02_powierzchnia_wokol_plata","vof","8","1.0","40","1600","500","0","1"},
   {"T8_03_woda_nad_platem","vof","1.0","0.6","5","1600","800","0","1"},
   {"T8_04_predkosc_przy_placie","vel","0.35","0.05","3","1600","900","8","16"},
   {"T8_05_wirowosc_slad","vort","3.5","0.0","9","1600","500","-60","60"},
   {"T8_06_cisnienie_przy_placie","p","0.35","0.05","2","1600","900","",""},
   {"T8_07_predkosc_cala_domena","vel","23.4","0","112","1920","500","8","16"}};
  for(String[] q:spec){try{
   Scene sc=nowa(q[0]); ScalarDisplayer sd=null;
   for(Object d:sc.getDisplayerManager().getObjects()) if(d instanceof ScalarDisplayer x) sd=x;
   if(sd==null) sd=sc.getDisplayerManager().createScalarDisplayer("Skalar");
   sd.getInputParts().setObjects(scp);
   FieldFunction ff=q[1].equals("vof")?fm.getFunction("VolumeFractionwater"):q[1].equals("vel")?((PrimitiveFieldFunction)fm.getFunction("Velocity")).getMagnitudeFunction()
     :q[1].equals("vort")?((PrimitiveFieldFunction)fm.getFunction("VorticityVector")).getComponentFunction(2):fm.getFunction("Pressure");
   sd.getScalarDisplayQuantity().setFieldFunction(ff);
   if(!q[7].isEmpty()){ sd.getScalarDisplayQuantity().setAutoRange(AutoRangeMode.NONE); sd.getScalarDisplayQuantity().setRange(dv(Double.parseDouble(q[7]),Double.parseDouble(q[8]))); }
   int W=Integer.parseInt(q[5]),H=Integer.parseInt(q[6]); view(sc,Double.parseDouble(q[2]),Double.parseDouble(q[3]),Double.parseDouble(q[4]),W,H); png(sc,q[0],W,H); log("scena "+q[0]);
  }catch(Throwable e){ log("SCENA BLAD "+q[0]+": "+e); }}
  PrimitiveFieldFunction vel=(PrimitiveFieldFunction)fm.getFunction("Velocity");
  try{ Scene s8=nowa("T8_08_linie_pradu_przy_placie");
   if(s8.getDisplayerManager().getObjects().size()<2){
    LinePart lp=s.getPartManager().createLinePart(new NeoObjectVector(regs.toArray()),dv(-1.0,-0.6,0.01),dv(-1.0,0.6,0.01),48); lp.setPresentationName("T8_stream_seed");
    StreamPart sp=s.getPartManager().createStreamPart(new NeoObjectVector(regs.toArray()),lp,vel,1); sp.setPresentationName("T8_linie_pradu"); sp.setFieldFunction(vel);
    sp.setMode(SeedMode.LINE); sp.getLineSeed().setPoint1(dv(-1.0,-0.6,0.01)); sp.getLineSeed().setPoint2(dv(-1.0,0.6,0.01)); sp.getLineSeed().setResolution(48); sp.setSolver(StreamPartSolver.RK4);
    StreamDisplayer sd=s8.getDisplayerManager().createStreamDisplayer("Linie pradu"); sd.getInputParts().setObjects(sp); sd.getScalarDisplayQuantity().setFieldFunction(vel.getMagnitudeFunction());
    sd.getScalarDisplayQuantity().setAutoRange(AutoRangeMode.NONE); sd.getScalarDisplayQuantity().setRange(dv(8,16)); }
   view(s8,0.8,0,4.0,1600,900); png(s8,"T8_08_linie_pradu_przy_placie",1600,900); log("scena S8");
  }catch(Throwable e){ log("SCENA BLAD S8: "+e); }
  try{ Scene s9=nowa("T8_09_wektory_LIC");
   VectorDisplayer vd=null; for(Object d:s9.getDisplayerManager().getObjects()) if(d instanceof VectorDisplayer x) vd=x;
   if(vd==null){ vd=s9.getDisplayerManager().createVectorDisplayer("Wektory"); }
   vd.getInputParts().setObjects(scp); vd.getVectorDisplayQuantity().setFieldFunction(vel); vd.setDisplayMode(VectorDisplayMode.VECTOR_DISPLAY_MODE_LIC);
   view(s9,0.3,0,1.6,1600,900); png(s9,"T8_09_wektory_LIC",1600,900); log("scena S9");
  }catch(Throwable e){ log("SCENA BLAD S9: "+e); }
  try{ Scene s10=nowa("T8_10_siatka_overset");
   PartDisplayer pd=null; for(Object d:s10.getDisplayerManager().getObjects()) if(d instanceof PartDisplayer x) pd=x;
   if(pd==null) pd=s10.getDisplayerManager().createPartDisplayer("Siatka");
   pd.getInputParts().setObjects(scp); pd.setMesh(true); pd.setOutline(false);
   view(s10,0.3,0,2.5,1600,900); png(s10,"T8_10_siatka_overset",1600,900); log("scena S10");
  }catch(Throwable e){ log("SCENA BLAD S10: "+e); }
  // ---- tabela z historii i wykresy XY (przez refleksje - nazwy klas API rozne miedzy wersjami)
  Object tab=null;
  try{ for(Object o:s.getTableManager().getObjects()) if(((NamedObject)o).getPresentationName().equals("HISTORIA_T8_005g")) tab=o;
   if(tab==null){ tab=call(s.getTableManager(),"createFromFile",out.resolve("HISTORIA_T8_005g.csv").toString()); ((NamedObject)tab).setPresentationName("HISTORIA_T8_005g"); }
   log("tabela ok: "+tab.getClass().getSimpleName());
  }catch(Throwable e){ log("TABELA BLAD: "+e); }
  String[][] wyk={{"W1_wysokosc_plata_i_fala [m]","z_m","eta_nad_LE_m","eta_3m_przed_m"},{"W2_kat_plata_i_zadany [deg]","kat_deg","kat_zadany_deg"},
   {"W3_moc_oporu_plata [W na pasek 0,02 m]","moc_oporu_W"},{"W4_przyspieszenie_pionowe [m/s2]","zdd_m_s2"},{"W5_CL_i_sila_nosna_do_ciezaru","CL","sila_nosna_do_ciezaru"},
   {"W6_predkosc_pionowa_plata [m/s]","zd_m_s"},{"W7_Courant_na_powierzchni","CFL_powierzchni"}};
  if(tab!=null) for(String[] w:wyk){ try{
   Object pm=s.getPlotManager(); Object pl=null;
   for(Object o:s.getPlotManager().getObjects()) if(((NamedObject)o).getPresentationName().equals(w[0])) pl=o;
   if(pl==null){ pl=call(pm,"createPlot",Class.forName("star.common.XYPlot")); ((NamedObject)pl).setPresentationName(w[0]); }
   Object dsm=call(pl,"getDataSetManager");
   for(int k=1;k<w.length;k++){
    call(dsm,"addDataProviders",new NeoObjectVector(new Object[]{tab}));
    Object ds=null; for(Object o:(Collection<?>)call(dsm,"getDataSets")) ds=o;
    call(ds,"setXValuesName","czas_s"); call(ds,"setYValuesName",w[k]); try{ call(ds,"setPresentationName",w[k]); }catch(Throwable e){}
   }
   try{ Object ax=call(pl,"getXAxes"); Object xa=call(ax,"getAxisType","Bottom Axis"); Object tt=call(xa,"getTitle"); call(tt,"setText","czas [s]"); }catch(Throwable e){}
   try{ call(pl,"encode",out.resolve("GUI_PNG").resolve(w[0].replaceAll("[^A-Za-z0-9_]","_")+".png").toString(),"png",1600,700); }catch(Throwable e){ log("  png wykresu: "+e); }
   log("wykres "+w[0]);
  }catch(Throwable e){ log("WYKRES BLAD "+w[0]+": "+e); }}
  try{ s.saveState(out.resolve("OVS_CEL_005g_T8_90_GUI.sim").toString()); log("zapisano OVS_CEL_005g_T8_90_GUI.sim"); }catch(Throwable e){ log("ZAPIS BLAD "+e); }
 }
}
