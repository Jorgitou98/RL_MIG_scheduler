from ray.rllib.models.torch.torch_modelv2 import TorchModelV2
from ray.rllib.models.torch.fcnet import FullyConnectedNetwork as TorchFC
from ray.rllib.utils.framework import try_import_torch
from ray.rllib.utils.torch_utils import FLOAT_MAX, FLOAT_MIN
from gymnasium.spaces import Box
import numpy as np

torch, nn = try_import_torch()


class TorchParametricActionsModel(TorchModelV2, torch.nn.Module):
    """PyTorch version of above ParametricActionsModel."""

    def __init__(
        self,
        obs_space,
        action_space,
        num_outputs,
        model_config,
        name,
        **kw
    ):
        torch.nn.Module.__init__(self)
        TorchModelV2.__init__(
            self, obs_space, action_space, num_outputs, model_config, name, **kw
        )
        obs_len = obs_space.shape[0]-action_space.n
        orig_obs_space = Box(-1.0, 1.0, (obs_len,), np.float32)

        self.action_embed_model = TorchFC(
            orig_obs_space,
            action_space,
            action_space.n,
            model_config,
            name + "_action_embed",
        )

    def forward(self, input_dict, state, seq_lens):
        shape_x, shape_y = (input_dict["obs_flat"][:, :69]).shape
        
        # Quitar! Esto es solo para comprobar que estoy cogiendo bien la action_mask
        for i in range(shape_x):
            for j in range(shape_y):
                assert(input_dict["obs_flat"][i][j] == input_dict["obs"]["action_mask"][i][j])

        action_mask = real_obs = input_dict["obs_flat"][:, :69]
        real_obs = input_dict["obs_flat"][:, -68:]

        # Compute the predicted action embedding
        action_logits, _ = self.action_embed_model({"obs": real_obs})
        # turns probit action mask into logit action mask
        inf_mask = torch.clamp(torch.log(action_mask), -1e10, FLOAT_MAX)

        masked_logits = action_logits + inf_mask

        return masked_logits, state

    def value_function(self):
        return self.action_embed_model.value_function()

