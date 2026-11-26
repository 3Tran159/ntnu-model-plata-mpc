p = 'BuildPetla3D.java'; t = open(p, encoding='utf-8').read()
R = [('new double[]{fx+1.15*C,4.03,zz+0.25*C}', 'new double[]{fx+1.15*C,d("half_span_m",4.0)+0.03,zz+0.25*C}'),
     ('new double[]{xa-0.15*C,3.96,-0.25*C},new double[]{xb+1.15*C,4.04,',
      'new double[]{xa-0.15*C,d("plate_ylo",d("half_span_m",4.0)-0.04),-0.25*C},new double[]{xb+1.15*C,d("plate_yhi",d("half_span_m",4.0)+0.04),')]
for a, b in R:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(t); print('ok')
