from stable_baselines3.common.callbacks import BaseCallback
from env import SchedEnv
from utils import partition_map, makespan_lower_bound, compute_makespan
import csv
from pprint import pprint


        

class CustomCallback(BaseCallback):
    def __init__(self, M, N, type_tasks = "good_scaling", verbose=1):
        super(CustomCallback, self).__init__(verbose)
        self.M = M
        self.N = N
        self.type_tasks = type_tasks

    def calculate_ratio(self, N, M, model):
        env_test = SchedEnv({"N": N, "M": M})
        sum_ratios = 0
        num_episodes = 150
        for _ in range(num_episodes):
            env_test.reset()
            lower_bound = makespan_lower_bound(env_test.tasks)
            done = False
            while not done:
                action, _ = model.predict(env_test.get_numpy_obs_state(), action_masks=env_test.valid_action_mask())
                _, _, done, _, _ = env_test.step(action)

            makespan = compute_makespan(env_test.init_state, env_test.actions)
            ratio = makespan / lower_bound
            sum_ratios += ratio
            # obs_preprocessed = self.locals["obs_tensor"]
            # print(f"Step: {self.num_timesteps}, Preprocessed Observation: {obs_preprocessed}")
        
        with open(f'ratios_N{N}_M{M}_{self.type_tasks}.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([model.num_timesteps, sum_ratios / num_episodes])
        

    def _on_step(self):      
        self.calculate_ratio(self.N, self.M, self.model)
        return True