import pickle, time, susp_mpc as SM, mpc_irr as M, mpc_irr2 as M2
_, pred = pickle.loads(open("MPC_IRR2_MODEL.pkl","rb").read())
t=time.time(); mdl = M.identify(M2.collect_spread(seeds=range(100,103))); print("id", round(time.time()-t), mdl["r2L"], flush=True)
for args in [("polaktywne_v2","MPC",0.0),("pasywne_1.5Hz","PID",-0.4),("sztywne","MPC",-0.4)]:
    t=time.time(); print(args, SM.run(5,*args,mdl,pred,T=4.0), round(time.time()-t), "s", flush=True)
