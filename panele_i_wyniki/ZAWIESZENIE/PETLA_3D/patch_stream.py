"""Sceny 13-15: plaszczyzna przekroju kolorowana Cp + linie pradu (z predkosci, ograniczone do plaszczyzny), kolor linii |U|."""
p = 'PostPelny3D.java'; t = open(p, encoding='utf-8').read()
add = '''  step("13",()->{Scene x=sc("P3D 13 Przekroj y przez plaskie platy: tlo Cp + linie pradu (kolor |U|)");scal(x,"Cp",List.of(py[0]),fcp,-1.2,1.0);
   stream(x,"P3D linie pradu y",py[0],new double[]{-0.9,yflat,-0.6},new double[]{-0.9,yflat,gap+0.6},60,fvel,fvmag,0.7*U,1.3*U);
   view(x,new double[]{xc+0.2,yflat,zc},new double[]{xc+0.2,yflat+30,zc},new double[]{0,0,1},Math.max(gap,c)*1.1+0.3);png(x,"13_LINIE_PRADU_Y");});
  step("14",()->{PlaneSection pz2=plane("P3D przekroj z srodek luku (linie pradu)",new double[]{0,0,zc},new double[]{0,0,1});
   Scene x=sc("P3D 14 Przekroj poziomy przez srodek luku: tlo Cp + linie pradu (kolor |U|)");scal(x,"Cp",List.of(pz2),fcp,-0.6,1.0);
   stream(x,"P3D linie pradu z",pz2,new double[]{-0.9,Math.max(0.05,yl-1.0),zc},new double[]{-0.9,yl+0.6,zc},50,fvel,fvmag,0.7*U,1.3*U);
   view(x,new double[]{xc+0.2,yl,zc},new double[]{xc+0.2,yl,zc+30},new double[]{-1,0,0},1.3*c+0.25);png(x,"14_LINIE_PRADU_LUK");});
  step("15",()->{PlaneSection px=plane("P3D przekroj x = 1c za platem (przeplyw poprzeczny)",new double[]{xc+c,0,0},new double[]{1,0,0});
   Scene x=sc("P3D 15 Przeplyw poprzeczny za petla x = 1c: tlo Cp + linie pradu w plaszczyznie (wiry)");scal(x,"Cp",List.of(px),fcp,-0.3,0.3);
   stream(x,"P3D linie pradu x",px,new double[]{xc+c,0.02,-0.5},new double[]{xc+c,hs+0.5,gap+0.5},80,fvel,fvmag,0.9*U,1.05*U);
   view(x,new double[]{xc+c,hs/2,zc},new double[]{-10,hs/2,zc},new double[]{0,0,1},L*0.62);png(x,"15_PRZEPLYW_POPRZECZNY");});
  s.saveState(out.resolve("PETLA_KONIEC.sim").toString());'''
a = '  s.saveState(out.resolve("PETLA_KONIEC.sim").toString());'
assert t.count(a) == 1; t = t.replace(a, add)
m = ''' void step(String n,Runnable r){'''
h = ''' void stream(Scene x,String n,Part plane,double[] p1,double[] p2,int res,FieldFunction vel,FieldFunction col,double lo,double hi){
  ConstrainedStreamPart sp=s.getPartManager().createConstrainedStreamPart();sp.setPresentationName(n);sp.getInputParts().setObjects(plane);sp.setFieldFunction(vel);
  sp.setMode(SeedMode.LINE);LineSeed ls=sp.getLineSeed();ls.setPoint1(new DoubleVector(p1));ls.setPoint2(new DoubleVector(p2));ls.setResolution(res);
  StreamDisplayer d=x.getDisplayerManager().createStreamDisplayer("Linie pradu");d.getInputParts().setObjects(sp);d.setMode(StreamDisplayerMode.LINES);
  d.getScalarDisplayQuantity().setFieldFunction(col);try{d.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{lo,hi}));}catch(Throwable e){}}
'''
assert t.count(m) == 1; t = t.replace(m, h + m)
c1 = 'x.getPresentationName().startsWith("P3D izopowierzchnia"))'
assert t.count(c1) == 1; t = t.replace(c1, 'x.getPresentationName().startsWith("P3D izopowierzchnia")||x.getPresentationName().startsWith("P3D linie pradu"))')
open(p, 'w', encoding='utf-8', newline='').write(t); print('ok')
