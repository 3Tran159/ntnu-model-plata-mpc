import pickle, time, susp_mpc as SM, mpc_irr as M, mpc_irr2 as M2
_, pred = pickle.loads(open("MPC_IRR2_MODEL.pkl","rb").read())
mdl = M.identify(M2.collect_spread(seeds=range(100,102)))
for args in [("pasywne_1.5Hz","MPC",0.0),("pasywne_0.7Hz","MPC",0.0),("polaktywne_v2","PID",0.0)]:
    print(args, SM.run(5,*args,mdl,pred,T=4.0), flush=True)
