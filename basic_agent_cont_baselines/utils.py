from collections import Counter
# Mapa de número de partición a sus instancias
partition_map = {
    1: {"slices": ["7"] * 7, "sizes": [7], "instances" : [0,0,0,0,0,0,0]}, 
    2: {"slices": ["4"] * 4 + ["3"] * 3, "sizes": [4, 3], "instances" : [0,0,0,0,1,1,1]}, 
    3: {"slices": ["4"] * 4 + ["2"] * 2 + ["1"], "sizes": [4, 2, 1], "instances" : [0,0,0,0,1,1,2]}, 
    4: {"slices": ["4"] * 4 + ["1"] * 3, "sizes": [4, 1, 1, 1], "instances" : [0,0,0,0,1,2,3]}, 
    5: {"slices": ["3"] * 4 + ["3"] * 3, "sizes": [3, 3], "instances" : [0,0,0,0,1,1,1]}, 
    6: {"slices": ["3"] * 4 + ["2"] * 2 + ["1"], "sizes": [3, 2, 1], "instances" : [0,0,0,0,1,1,2]}, 
    7: {"slices": ["3"] * 4 + ["1"] * 3, "sizes": [3, 1, 1, 1], "instances" : [0,0,0,0,1,2,3]}, 
    8: {"slices": ["2"] * 4 + ["3"] * 3, "sizes": [2, 2, 3], "instances" : [0,0,1,1,2,2,2]}, 
    9: {"slices": ["2"] * 6 + ["1"], "sizes": [2, 2, 2, 1], "instances" : [0,0,1,1,2,2,3]}, 
    10: {"slices": ["2"] * 4 + ["1"] * 3, "sizes": [2, 2, 1, 1, 1], "instances" : [0,0,1,1,2,3,4]}, 
    11: {"slices": ["2"] * 2 + ["1"] * 2 + ["3"] * 3, "sizes": [2, 1, 1, 3], "instances" : [0,0,1,2,3,3,3]}, 
    12: {"slices": ["2"] * 2 + ["1"] * 2 + ["2"] * 2 + ["1"], "sizes": [2, 1, 1, 2, 1], "instances" : [0,0,1,2,3,3,4]}, 
    13: {"slices": ["2"] * 2 + ["1"] * 5, "sizes": [2, 1, 1, 1, 1, 1], "instances" : [0,0,1,2,3,4,5]}, 
    14: {"slices": ["1"] * 2 + ["2"] * 2 + ["3"] * 3, "sizes": [1, 1, 2, 3], "instances" : [0,1,2,2,3,3,3]}, 
    15: {"slices": ["1"] * 2 + ["2"] * 4 + ["1"], "sizes": [1, 1, 2, 2, 1], "instances" : [0,1,2,2,3,3,4]}, 
    16: {"slices": ["1"] * 2 + ["2"] * 2 + ["1"] * 3, "sizes": [1, 1, 2, 1, 1, 1], "instances" : [0,1,2,2,3,4,5]}, 
    17: {"slices": ["1"] * 4 + ["3"] * 3, "sizes": [1, 1, 1, 1, 3], "instances" : [0,1,2,3,4,4,4]}, 
    18: {"slices": ["1"] * 4 + ["2"] * 2 + ["1"], "sizes": [1, 1, 1, 1, 2, 1], "instances" : [0,1,2,3,4,4,5]}, 
    19: {"slices": ["1"] * 7, "sizes": [1, 1, 1, 1, 1, 1, 1], "instances" : [0,1,2,3,4,5,6]}, 
}


# Mapa de tamaño de instancia a posición de array en que se codifica
instance_size_map = {1: 0, 2: 1, 3: 2, 4: 3, 7: 4}

def basic_print_obs(obs):
    state = obs["observations"]
    action_mask = obs["action_mask"]
    print("-----------")
    print("State:")
    print("\tPartition:", partition_map[state["partition"]]["sizes"])
    print("\tSlices:", state["slices_t"])
    for task in state["ready_tasks"]:
        if task[-1] != 0:
            print("\tTask type:", task[:5], "number", task[5])
    print("Action mask:")
    print("\tEsperar:", action_mask[0])
    print("\tReconfiguración:", action_mask[1:20])
    for i, task in enumerate(state["ready_tasks"]):
        print("\tPut task in instance:", action_mask[20 + i * 7: 20 + (i+1) * 7])
    print("-----------")

def _action_to_str(action):
    action = int(action)
    if action == 0:
        return "Wait"
    elif action < 20:
        return f"Reconfigure to {partition_map[action]['sizes']}"
    else:
        task = (action - 20) // 7
        instance = (action - 20) % 7
        return f"Put task {task} in instance {instance}"
    
def time_discretization(ready_tasks, M):
    max_time = max(max(task) for task in ready_tasks)
    time_step = max_time / M
    return [[max(1, round(time / time_step)) for time in task] for task in ready_tasks]
