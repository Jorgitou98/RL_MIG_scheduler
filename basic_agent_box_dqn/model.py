from ray.rllib.algorithms.dqn.dqn_torch_model import DQNTorchModel
from ray.rllib.models.torch.fcnet import FullyConnectedNetwork as TorchFC
from ray.rllib.utils.framework import try_import_torch
from ray.rllib.utils.torch_utils import FLOAT_MAX, FLOAT_MIN
from gymnasium.spaces import Box, Discrete
import numpy as np

torch, nn = try_import_torch()


class DQNActionMaskModel(DQNTorchModel):
    """PyTorch version of above ParametricActionsModel."""

    def __init__(
        self,
        obs_space: Box,
        action_space: Discrete,
        num_outputs,
        model_config,
        name,
        **kw,
    ):
        DQNTorchModel.__init__(
            self, obs_space, action_space, num_outputs, model_config, name, **kw
        )
        obs_len = obs_space.shape[0]-action_space.n
        orig_obs_space = Box(0, 19, (obs_len,), np.float32)
        #model_config["vf_share_layers"] = True
        self.action_embed_model = TorchFC(
            orig_obs_space,
            action_space,
            action_space.n,
            model_config,
            name + "_action_embed",
        )
        print()

    def forward(self, input_dict, state, seq_lens):
        # shape_x, shape_y = (input_dict["obs_flat"][:, :125]).shape
        
        # # Quitar! Esto es solo para comprobar que estoy cogiendo bien la action_mas
        # for i in range(shape_x):
        #     for j in range(shape_y):
        #         assert(input_dict["obs_flat"][i][j] == input_dict["obs"]["action_mask"][i][j])

        action_mask = real_obs = input_dict["obs_flat"][:, :125]
        real_obs = input_dict["obs_flat"][:, 125:]

        # Compute the predicted action embedding
        action_logits, _ = self.action_embed_model({"obs": real_obs})
        #print(action_logits)
        # turns probit action mask into logit action mask
        inf_mask = torch.clamp(torch.log(action_mask), min=FLOAT_MIN)

        masked_logits = action_logits + inf_mask

        return masked_logits, state

    def value_function(self):
        return self.action_embed_model.value_function()

