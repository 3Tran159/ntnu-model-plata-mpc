import sys, json, numpy as np
sys.path.insert(0,'../model'); sys.dont_write_bytecode=True
import faltinsen_plant as FP
from urans import harm, load, TE, OME, U, G
from model import run, H, PlantZ0
A,_=load('../data/K0.csv'); t=A['time_s']; m=t>=t[-1]-3*TE; tt=t[m]
ur=dict(acc=harm(tt,np.gradient(A['v_m_s'][m],tt)), Fy=harm(tt,A['GODO_Fy_fluid'][m]), CL=harm(tt,A['AF_CL'][m]), theta=harm(tt,A['theta_deg'][m]), cmd=harm(tt,A['theta_cmd_deg'][m]),
        z=harm(tt,A['z_m'][m]), eta=harm(tt,A['GODO_eta_at_LE'][m]), etau=harm(tt,A['GODO_eta_upstream_quarter_lambda'][m]), P=harm(tt,A['P_drag_W'][m]))
M=json.load(open('MODEL_HARM.json'))['wyniki']
cplx=lambda h,i: h['amp'][i]*np.exp(1j*np.radians(h['ph'][i]))
print('=== harmoniczne 1-5: URANS / model A / model G')
for key,unit in (('acc','m/s2'),('Fy','N/pasek'),('CL','-'),('theta','deg')):
    for name,h in (('URANS',ur[key]),('model A',M['A pelny model B'][key]),('model G',M['G pelny + 2. harmoniczna komendy jak w URANS'][key])):
        print(f"{key:6s} {name:8s} "+' '.join(f'{a:.4f}' for a in h['amp'])+f" | fazy {h['ph'][0]:+.0f} {h['ph'][1]:+.0f} | rms {h['rms']:.4f} sr {h['mean']:.4f}")
# reszta wektorowa 2. harmonicznej
for key in ('acc','CL'):
    for nm in ('A pelny model B','G pelny + 2. harmoniczna komendy jak w URANS'):
        d=abs(cplx(ur[key],1)-cplx(M[nm][key],1)); d1=abs(cplx(ur[key],0)-cplx(M[nm][key],0)); print(f'reszta wektorowa URANS - {nm[:1]}: {key} 2. harm {d:.4f}, 1. harm {d1:.4f}')
# skladniki w modelu: roznice wektorowe wzgledem pelnego
full=M['A pelny model B']
for nm in M:
    if nm[0] in 'BCDEF': print(f"{nm:46s} z'' 2. harm {M[nm]['acc']['amp'][1]:.3f}; wklad wylaczonego skladnika (wektorowo) {abs(cplx(full['acc'],1)-cplx(M[nm]['acc'],1)):.3f}; 1. harm {M[nm]['acc']['amp'][0]:.3f}")
# komenda URANS: skad 2. harmoniczna - z pochodnej eta_LE
omW=2*np.pi/5.0; kw=omW**2/9.81
e1,e2=ur['eta']['amp'][0],ur['eta']['amp'][1]
w1=omW/OME*e1*OME*np.exp(-kw*1.09); w2=omW/OME*e2*2*OME*np.exp(-kw*1.09)
print(f"eta_LE amp1 {e1:.4f} amp2 {e2:.4f} (upstream {ur['etau']['amp'][0]:.4f} {ur['etau']['amp'][1]:.4f}); Stokes 2. rzad k a^2/2 = {kw*e1**2/2:.4f} m")
print(f"szacunek w z makra: 1. harm {w1:.4f} m/s -> {np.degrees(w1/U):.3f} deg x0.85 = {0.85*np.degrees(w1/U):.3f}; 2. harm {w2:.4f} m/s -> {np.degrees(w2/U):.3f} deg x0.85 = {0.85*np.degrees(w2/U):.3f} deg; URANS theta_cmd amp1 {ur['cmd']['amp'][0]:.3f} amp2 {ur['cmd']['amp'][1]:.3f}")
# rekonstrukcja komendy z historii: cmd_ff = -0.85*deg(wF/U), wF = (omW/omE) d eta/dt (tick 10 ms) * exp(-kw (1.09 - z))
eta=A['GODO_eta_at_LE']; z=A['z_m']; idx=np.arange(0,len(t),10)
ws=np.zeros(len(t)); 
for a,b in zip(idx[:-1],idx[1:]): ws[b:b+10]=(omW/OME)*(eta[b]-eta[a])/0.01*np.exp(-kw*np.maximum(0,1.09-z[b]))
ff=-0.85*np.degrees(ws/U); hf=harm(tt,ff[m]); print('rekonstrukcja kasowania z eta_LE: amp1,2',[round(x,3) for x in hf['amp'][:2]],'fazy',[round(x) for x in hf['ph'][:2]],'| theta_cmd URANS fazy',[round(x) for x in ur['cmd']['ph'][:2]])
# nieliniowosc CL(alfa) w URANS: regresja CL na quasi-stacjonarny kat naplywu
beta=np.radians(ur['eta']['ph'][0]); a=e1
psi=-OME*tt+beta; Aw=a*omW*np.exp(-kw*(1.09-A['z_m'][m])); wv=Aw*np.sin(psi); uv=Aw*np.cos(psi)
alpha=np.radians(A['theta_deg'][m])-(A['v_m_s'][m]-wv)/U
X=np.stack([np.ones_like(alpha),alpha,alpha**2,uv/U],1); c,_,_,_=np.linalg.lstsq(X,A['AF_CL'][m],rcond=None); r=A['AF_CL'][m]-X@c
ha=harm(tt,alpha); print(f"regresja CL = c0 + c1 a + c2 a^2 + c3 u/U: c1 {c[1]:.2f} /rad, c2 {c[2]:.1f} /rad2, c3 {c[3]:.3f}; reszta rms {r.std():.4f}; alfa amp1 {np.degrees(ha['amp'][0]):.3f} deg amp2 {np.degrees(ha['amp'][1]):.3f} deg; wklad c2 do 2. harm CL: {abs(c[2])*ha['amp'][0]**2/2:.5f}")
X2=np.stack([np.ones_like(alpha),alpha,uv/U],1); c2,_,_,_=np.linalg.lstsq(X2,A['AF_CL'][m],rcond=None); print('bez c2: c1',round(c2[1],2),'reszta rms',round((A['AF_CL'][m]-X2@c2).std(),4))
json.dump(dict(urans=ur,model=M,okno_s=[float(tt[0]),float(tt[-1])]),open('BZ4_HARMONICZNE.json','w'),indent=1)
# wykres
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig,ax=plt.subplots(1,2,figsize=(12,4.6)); x=np.arange(5); w=0.27
ser=[('URANS (OVS_K0_85_90)',ur,'#d94801'),('model B',dict(acc=M['A pelny model B']['acc'],theta=M['A pelny model B']['theta']),'#2171b5'),
     ('model B + 2. harmoniczna kąta jak w URANS',dict(acc=M['G pelny + 2. harmoniczna komendy jak w URANS']['acc'],theta=M['G pelny + 2. harmoniczna komendy jak w URANS']['theta']),'#222222')]
for j,(nm,h,col) in enumerate(ser):
    for a_,key in ((ax[0],'acc'),(ax[1],'theta')):
        b=a_.bar(x+(j-1)*w,h[key]['amp'],w,label=nm,color=col)
        for xi,v in zip(x+(j-1)*w,h[key]['amp']): a_.text(xi,v,f'{v:.2f}',ha='center',va='bottom',fontsize=7)
for a_,yl,tl in ((ax[0],'amplituda przyspieszenia pionowego [m/s²]','Przyspieszenie pionowe'),(ax[1],'amplituda kąta płata [°]','Kąt płata')):
    a_.set_xticks(x); a_.set_xticklabels([f'{n}. harmoniczna\n{n*0.516:.2f} Hz' for n in range(1,6)],fontsize=8); a_.set_ylabel(yl); a_.set_title(tl,fontsize=10); a_.grid(axis='y',alpha=0.3)
ax[0].legend(fontsize=8)
fig.suptitle('K0 85 %, fala regularna H 1,5 m, T 5 s, obciążenie 90 %; ostatnie 3 okresy spotkania (5,81–11,62 s)',fontsize=10); fig.tight_layout(); fig.savefig('BZ4_harmoniczne.png',dpi=160)
