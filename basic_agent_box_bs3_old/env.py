from collections import OrderedDict
import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, Discrete, MultiDiscrete, MultiBinary
from utils import *
from render import Window
import os
from task_times import generate_tasks


class SchedEnv(gym.Env):
    def __init__(self, env_config, type_tasks = "good_scaling"):
        self.N = env_config["N"]
        self.M = env_config["M"]
        self.type_tasks = type_tasks
        self.reconfig_time = 0.7
        self.observation_space = Box(low=0, high=1, shape=(1 + 6 * self.N + 7,)) # La última indica si el último momento fue una reconfiguración
        self.action_space = Discrete(1 + 16 + 7 * self.N) # 1 accion esperar, 13 acciones de configuración (3 eliminadas, y 3 fusionadas en el step), y 7*N acciones de asignar tarea
        #self.part_distribution = {}

    def _get_action_mask(self):
        current_partition = self.obs["partition"]
        slices_t = self.obs["slices_t"]
        ready_tasks = self.obs["ready_tasks"]

        # La acción de esperar sólo es válida si hay tareas en la GPU
        wait = 1 if any(slice_t != 0 for slice_t in slices_t) else 0

        # Reconfiguraciones válidas
        # Si no hay tareas ready o se acaba de reconfigurar, no tiene sentido reconfigurar la GPU
        if ready_tasks[0][-1] == 0:
            reconfig_mask = [0] * 16
        else:
            reconfig_mask = [1] * 16
            # Prohibido reconfigurar a la partición actual
            reconfig_mask[current_partition - 1] = 0
            # Prohibido reconfigurar a particiones en que haya que cambiar slices en uso
            for future_partition in range(1, 17):
                for curr_slice in range(7):
                    if partition_map[current_partition]["slices"][curr_slice] != partition_map[future_partition]["slices"][curr_slice] and slices_t[curr_slice] > 0:
                        reconfig_mask[future_partition - 1] = 0

        # Acciones válidas sobre tareas ready
        select_ready_task = [1] * 7 * self.N
        # Prohibido coger una tarea para ejecutar en la GPU más allá de los tipos disponibles
        for i, task in enumerate(ready_tasks):
            n_availables = task[-1]
            # Si en ready hay una no disponible todas las de detrás no están disponibles por el orden canónico
            if n_availables == 0:
                for j in range(i*7, 7 * self.N):
                    select_ready_task[j] = 0
                break
        
        # Prohibido asignar la tarea ready a una instancia con indice superior a la cantidad de instancias de la partición actual
        first_forbidden_instance = len(partition_map[current_partition]["sizes"])
        for task in range(self.N):
            for instance in range(first_forbidden_instance, 7):
                select_ready_task[task * 7 + instance] = 0

        # Prohibido asignar una tarea a una instancia con tarea en ejecución (o reconfiguración)
        first_instance_slice = 0
        for instance_index in range(first_forbidden_instance):
            if slices_t[first_instance_slice] > 0:
                for task in range(self.N):
                    select_ready_task[task * 7 + instance_index] = 0
            current_size = partition_map[current_partition]["sizes"][instance_index]
            if current_size == 3 and instance_index == 0:
                current_size = 4
            first_instance_slice += current_size

        return [wait] + reconfig_mask + select_ready_task
        


    def get_numpy_obs_state(self):
        #print(np.array(self.obs["ready_tasks"]).flatten())
        obs = [self.obs["partition"] - 1]
        for task in self.obs["ready_tasks"]:
            obs += task
        obs += self.obs["slices_t"]
        
        return (np.array(obs, dtype=np.float32)/max(self.M + 1, self.N, 19))

    def valid_action_mask(self):
        return np.array(self._get_action_mask())
    


    def reset(self, seed = None, options = None):
        init_partition = 2 # Por ahora, consideramos que se empieza en la partición 1 (una sola instancia de tamaño 7 siempre)
        init_slice_t = [0,0,0,0,0,0,0] # Consideramos que todos los slices están libres al principio      
        self.num_task_slices = [0,0,0,0,0,0,0] # Lleva el número de tipo de tarea que hay ejeuctando en cada slice
        
        ready_tasks = get_ready_tasks(self.type_tasks, self.N)
        ready_tasks, self.reconfig_time_scaled = time_discretization(ready_tasks, self.M, self.reconfig_time)
        ready_tasks_canonical, self.dic_cont_times = canonical_sort_tasks(self.M, ready_tasks) # Las siguientes N tareas pendientes, se ordenan canónicamente y colocando como 6ª componente la cantidad de veces que se repite
        

        # Para tener un índice con el número de tipo de tarea, que luego me permita ser consistente en la representación gráfica
        self.num_type_task = list(range(len(ready_tasks_canonical)))
        # Usamos el 0 para rellenar posiciones vacías en la representación de tareas ready
        init_ready_tasks = ready_tasks_canonical + [[0] * 6] * (self.N - len(ready_tasks_canonical)) # Rellenamos con arrays de 6 ceros hasta N
        self.obs = {
            "partition": init_partition,
            "ready_tasks": init_ready_tasks,
            "slices_t": init_slice_t,
            "last_reconfig": 0
        }
        self.obs["action_mask"] = self._get_action_mask()

        self._check_obs_consistency()

        self.last_action = None # Aún no se ha hecho ninguna acción

        self.acum_reward = 0
        
        self.init_state = {"partition": init_partition, "slices_t": [0,0,0,0,0,0,0]}
        self.actions = []
        
        return self.get_numpy_obs_state(), {}
    

    def render(self):
        basic_print_obs(self.obs)
        #graphic_obs(self)


    def _is_terminated(self):
        # Si todas las tareas están terminadas, y todo lo que hay en la GPU ha acabado, el episodio termina
        for slice_t in self.obs["slices_t"]:
            if slice_t > 0:
                return False

        for ready_task in self.obs["ready_tasks"]:
            if ready_task[-1] > 0:
                return False
        
        return True
    
    def _check_obs_consistency(self):
        times = {}
        for i, instance_num in enumerate(partition_map[self.obs["partition"]]["instances"]):
            if instance_num not in times:
                times[instance_num] = self.obs["slices_t"][i]
            else:
                if times[instance_num] != self.obs["slices_t"][i]:
                    print(self.obs["partition"], self.obs["slices_t"])
                assert times[instance_num] == self.obs["slices_t"][i] # Todos los slices de una misma instancia tienen que tener el mismo tiempo
    

    def step(self, action):
        current_partition = self.obs["partition"]
        slices_t = self.obs["slices_t"]
        ready_tasks = self.obs["ready_tasks"]
        # Esperar
        if action == 0:
            # Transitamos al primer slice que se libere
            min_slice_time = min(slice_time for slice_time in slices_t if slice_time > 0)
            
            self.obs["slices_t"] = [slice_time - min_slice_time if slice_time > 0 else 0 for slice_time in slices_t]
            # Recompensamos con -tiempo transcurrido, para minimizar el makespan
            reward = -min_slice_time
            self.actions.append(("wait", None))
        # Reconfigurar
        elif action <= 16:
            # reconfig_str = action_to_str(action)
            # if reconfig_str not in self.part_distribution:
            #     self.part_distribution[reconfig_str] = 1
            # else:
            #     self.part_distribution[reconfig_str] += 1
            # pprint(self.part_distribution)
            # Fusión de acciones de reconfiguración
            if action == 11 or action == 12 or action == 13: 
                slice_0, slice_1 = self.obs["slices_t"][0], self.obs["slices_t"][1]
                self.obs["slices_t"][0], self.obs["slices_t"][1] = self.obs["slices_t"][2], self.obs["slices_t"][3]
                self.obs["slices_t"][2], self.obs["slices_t"][3] = slice_0, slice_1
                action -= 3
                self.actions.append(("exchange", None))
            self.obs["partition"] = int(action)
            reward = -self.reconfig_time_scaled # Recompensa en propoción al tiempo de reconfiguración
            self.actions.append(("reconfig", int(action)))
        # Asignar tarea
        else:
            task = (action - 17) // 7
            instance = (action - 17) % 7
            # Aumentamos el tiempo que tarda la tarea para el tamaño de la instancia en todos los slices de la instancia
            instance_size = partition_map[current_partition]["sizes"][instance]

            # Ponemos la tarea como seleccionada en la lista de acciones hechas
            cont_time_selected = self.dic_cont_times[type_num_task(self.M, self.obs["ready_tasks"][task][:5])][0][instance_size_map[instance_size]]
            self.actions.append(("assign", (cont_time_selected, instance)))
            self.dic_cont_times[type_num_task(self.M, self.obs["ready_tasks"][task][:5])].pop(0)

            task_time = ready_tasks[task][instance_size_map[instance_size]]
            # Quitamos la tarea de las ready_tasks
            self.obs["ready_tasks"][task][-1] -= 1

            for i, instance_slice in enumerate(partition_map[current_partition]["instances"]):
                if instance_slice == instance:
                    self.obs["slices_t"][i] = task_time
                    self.num_task_slices[i] = self.num_type_task[task]

            # Si es la última de cierto tipo, quitamos el tipo de ready task
            if ready_tasks[task][-1] == 0:
                ready_tasks.pop(task)
                # Añadimos un tipo de tarea vacío al final para mantener la dimensionalidad
                ready_tasks.append([0] * 6)
                # Movemos ese número de tipo de tarea al final
                self.num_type_task.append(self.num_type_task[task])
                self.num_type_task.pop(task)
            reward = 0

        

        self._check_obs_consistency()

        # Actualizamos la máscara de acciones para el nuevo estado
        self.obs["action_mask"] = self._get_action_mask()

        # Comprobamos si el episodio ha terminado
        terminated = self._is_terminated()
        
        truncated, info = False, {}

        self.last_action = action # La última acción realizada es la que se acaba de hacer

        self.acum_reward += reward

        return self.get_numpy_obs_state(), reward, terminated, truncated, info

    def close(*args, **kwargs):
        pass

    # def deepcopy(self):
    #     sched = SchedEnv({"N": self.N, "M": self.M})
    #     sched.obs = copy.deepcopy(self.obs)
    #     sched.acum_reward = self.acum_reward
    #     sched.last_action = self.last_action
    #     sched.num_task_slices = self.num_task_slices
    #     sched.num_type_task = self.num_type_task
    #     return sched



if __name__ == "__main__":
    env_example = SchedEnv({"N": 15, "M": 35}, type_tasks="good_scaling")
    print(env_example.observation_space.sample())
    initial_obs, _ = env_example.reset()
    print("initial obs:", initial_obs)
    window = Window(env_example)

# terminated = False
# while not terminated:
    
#     input("Press enter to next step...")
#     action = np.random.choice(np.flatnonzero(env_example.obs["action_mask"]))
#     _, _, terminated, _, _= env_example.step(action)