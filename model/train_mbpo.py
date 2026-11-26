"""MBPO (Janner et al. 2019) exactly as implemented in Meta's mbrl-lib 0.2.0 (mbrl.algorithms.mbpo.train), applied to the flap env.

PIPELINE TEST tonight: the "real" environment is the URANS-fitted surrogate of the Mini case (flap_env.FlapEnv) - this only
proves the code path (env wrapper, configs, logging, policy export). In production the real environment is an episode
in STAR-CCM+ (Godø case) and the surrogate is replaced by STAR data collection.
usage: python train_mbpo.py <seed> [num_steps=20000] [tag=MBPO_PIPE]
Configs: mbrl-lib's own algorithm/mbpo.yaml + dynamics_model/gaussian_mlp_ensemble.yaml; overrides adapted from
mbpo_halfcheetah.yaml (documented below, epoch = one 8-period episode of 729 ticks).
"""
import json, os, sys, time
from pathlib import Path
import numpy as np
import gymnasium as gym
import omegaconf, torch

sys.path.insert(0, str(Path(__file__).parent))
from flap_env import FlapEnv, EP_TICKS

torch.set_num_threads(int(os.environ.get("RL_THREADS", "1")))
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NUM = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
TAG = sys.argv[3] if len(sys.argv) > 3 else "MBPO_PIPE"
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\05_literature\mbrl_src\mbrl-lib-main\mbrl\examples\conf")
OUT = Path(__file__).parent / "runs" / ("%s_s%d" % (TAG, SEED)); OUT.mkdir(parents=True, exist_ok=True)


class GymFlap(gym.Env):
    def __init__(self, seed):
        self.e = FlapEnv(seed=seed)
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, (4,), np.float32)
        self.action_space = gym.spaces.Box(-1.0, 1.0, (1,), np.float32)

    def reset(self, seed=None, options=None):
        return self.e.reset().astype(np.float32), {}

    def step(self, a):
        o, r, done, info = self.e.step(a)
        return o.astype(np.float32), float(r), False, bool(done), info


def make_box(low, high, shape):
    return gym.spaces.Box(np.asarray(list(low), dtype=np.float32), np.asarray(list(high), dtype=np.float32), tuple(shape), np.float32)


def no_termination(act, next_obs):
    return torch.zeros(next_obs.shape[0], 1, dtype=torch.bool, device=next_obs.device)


def main():
    import mbrl.algorithms.mbpo as mbpo
    alg = omegaconf.OmegaConf.load(SRC / "algorithm" / "mbpo.yaml")
    dyn = omegaconf.OmegaConf.load(SRC / "dynamics_model" / "gaussian_mlp_ensemble.yaml")
    ov = omegaconf.OmegaConf.load(SRC / "overrides" / "mbpo_halfcheetah.yaml")
    ov.env = "flap_surrogate"; ov.num_steps = NUM; ov.epoch_length = EP_TICKS
    ov.freq_train_model = 250; ov.rollout_schedule = [1, 15, 1, 1]
    ov.sac_gamma = float(1 - 1 / (2.5 * 91)); ov.sac_hidden_size = 256
    alg.initial_exploration_steps = 2 * EP_TICKS
    dyn._recursive_ = False   # hydra >= 1.1 instantiates nested nodes by default; mbrl-lib (hydra 1.0.3) builds SiLU itself
    alg.agent.action_space._target_ = "train_mbpo.make_box"   # mbrl-lib main still points at the removed 'gym.env.Box'
    cfg = omegaconf.OmegaConf.create({"algorithm": alg, "dynamics_model": dyn, "overrides": ov, "seed": SEED, "device": "cpu",
                                      "log_frequency_agent": 1000, "save_video": False, "debug_mode": False})
    omegaconf.OmegaConf.resolve(cfg)
    (OUT / "config.yaml").write_text(omegaconf.OmegaConf.to_yaml(cfg))
    env, test_env = GymFlap(SEED), GymFlap(SEED + 1000)
    t0 = time.time()
    ret = mbpo.train(env, test_env, no_termination, cfg, silent=False, work_dir=str(OUT))
    (OUT / "RESULT.json").write_text(json.dumps({"best_eval_reward": float(ret), "wall_s": time.time() - t0, "num_steps": NUM}))
    print("MBPO pipeline OK, best eval reward", ret)


if __name__ == "__main__":
    main()
