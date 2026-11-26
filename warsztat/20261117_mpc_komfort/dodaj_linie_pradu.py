# 17.11 (prosba Julka 14:54): sceny S7 linie pradu wokol plata (StreamPart z linii zasiewu 1 m przed platem, kolor |V|, woda w tle)
# i S8 wektory predkosci przy placie - natywne obiekty STAR (LinePart, StreamPart, StreamDisplayer, VectorDisplayer), edytowalne w GUI.
from pathlib import Path
f = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\makro_mpcf\GodoOversetRun.java")
s = f.read_text(encoding="utf-8")
anchor = "\n void snapScenes(double t){"
assert s.count(anchor) == 1 and "GODO_S7_linie_pradu" not in s
blk = r'''
 void buildFlowScenes(java.util.Collection<Region> regs,star.vis.PlaneSection scp){
  FieldFunctionManager fm=s.getFieldFunctionManager(); PrimitiveFieldFunction vel=(PrimitiveFieldFunction)fm.getFunction("Velocity");
  try{ String n7="GODO_S7_linie_pradu_przy_placie"; star.vis.Scene s7=null; for(star.vis.Scene x:s.getSceneManager().getScenes()) if(x.getPresentationName().equals(n7)) s7=x;
   if(s7==null){ s7=s.getSceneManager().createScene(n7); s7.setPresentationName(n7); s7.initializeAndWait();
    star.vis.LinePart lp=s.getPartManager().createLinePart(new NeoObjectVector(regs.toArray()),new DoubleVector(new double[]{-1.0,-0.6,0.01}),new DoubleVector(new double[]{-1.0,0.6,0.01}),48); lp.setPresentationName("GODO_stream_seed");
    star.vis.StreamPart sp=s.getPartManager().createStreamPart(new NeoObjectVector(regs.toArray()),new NeoObjectVector(new Object[]{lp})); sp.setPresentationName("GODO_streamlines"); sp.setFieldFunction(vel);
    star.vis.ScalarDisplayer bg=s7.getDisplayerManager().createScalarDisplayer("Woda"); bg.getInputParts().setObjects(scp); bg.getScalarDisplayQuantity().setFieldFunction(fm.getFunction("VolumeFractionwater")); bg.setOpacity(0.35);
    star.vis.StreamDisplayer sd=s7.getDisplayerManager().createStreamDisplayer("Linie pradu"); sd.getInputParts().setObjects(sp); sd.getScalarDisplayQuantity().setFieldFunction(vel.getMagnitudeFunction());
    sd.getScalarDisplayQuantity().setAutoRange(star.vis.AutoRangeMode.NONE); sd.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{8,16})); }
   s7.getCurrentView().setInput(new DoubleVector(new double[]{0.8,0,0}),new DoubleVector(new double[]{0.8,0,5}),new DoubleVector(new double[]{0,1,0}),4.0*900/1600/2,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
   SC.add(new Object[]{s7,n7,1600,900});
  }catch(Throwable e){ try{put("SCENE_WARN_S7.txt",e.toString());}catch(Exception z){} }
  try{ String n8="GODO_S8_wektory_predkosci"; star.vis.Scene s8=null; for(star.vis.Scene x:s.getSceneManager().getScenes()) if(x.getPresentationName().equals(n8)) s8=x;
   if(s8==null){ s8=s.getSceneManager().createScene(n8); s8.setPresentationName(n8); s8.initializeAndWait();
    star.vis.VectorDisplayer vd=s8.getDisplayerManager().createVectorDisplayer("Wektory"); vd.getInputParts().setObjects(scp); vd.getVectorDisplayQuantity().setFieldFunction(vel); }
   s8.getCurrentView().setInput(new DoubleVector(new double[]{0.3,0,0}),new DoubleVector(new double[]{0.3,0,5}),new DoubleVector(new double[]{0,1,0}),1.6*900/1600/2,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
   SC.add(new Object[]{s8,n8,1600,900});
  }catch(Throwable e){ try{put("SCENE_WARN_S8.txt",e.toString());}catch(Exception z){} }
 }'''
s = s.replace(anchor, blk + anchor)
# wywolanie na koncu buildScenes: po petli spec (ostatnia linia catch SCENE_WARN_ + "}}")
a = '  }catch(Throwable e){ try{put("SCENE_WARN_"+q[0]+".txt",e.toString());}catch(Exception z){} }}\n'
assert s.count(a) == 1
s = s.replace(a, a + "  buildFlowScenes(regs,scp);\n")
f.write_text(s, encoding="utf-8"); print("ok")
