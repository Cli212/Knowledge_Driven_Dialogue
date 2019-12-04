#!/usr/bin/env python
# -*- coding: UTF-8 -*-


import os
import torch
import torch.nn as nn


class BaseModel(nn.Module):

    def __init__(self):
        super(BaseModel, self).__init__()

    def forward(self, *input):

        raise NotImplementedError

    def __repr__(self):
        main_string = super(BaseModel, self).__repr__()
        num_parameters = sum([p.nelement() for p in self.parameters()])
        main_string += "\nNumber of parameters: {}\n".format(num_parameters)
        return main_string

    def save(self, filename):

        torch.save(self.state_dict(), filename)
        print("Saved model state to '{}'!".format(filename))

    def load(self, filename):

        if os.path.isfile(filename):
            state_dict = torch.load(
                filename, map_location=lambda storage, loc: storage)
            self.load_state_dict(state_dict, strict=False)
            print("Loaded model state from '{}'".format(filename))
        else:
            print("Invalid model state file: '{}'".format(filename))
