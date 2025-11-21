import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import json
from functools import reduce


class FuzzyControllerBase:
    def __init__(self, config):
        with open(config, "r") as f:
            self.config = json.load(f)
        self.name = self.config["name"]
        self.base_value = self.config.get("initial_value", 50.0)
        self.delay_const = self.config.get("delay_const", 1)
        self.delay_history = [[], []]
        self.inputs = {}
        self.defaults = {}
        self.output = None
        self.simulation = None
        self.createSystem(
            self.config["inputs"], self.config["output"], self.config["rules"]
        )

    def createSystem(self, inputs, output, rules):
        for var_name, var_data in inputs.items():
            antecedent = ctrl.Antecedent(np.arange(*var_data["range"]), var_name)
            for label, (func_name, params) in var_data["sets"].items():
                mf = getattr(fuzz, func_name)(np.arange(*var_data["range"]), params)
                antecedent[label] = mf
            self.inputs[var_name] = antecedent
            if "default" in var_data:
                self.defaults[var_name] = var_data["default"]

        self.output = ctrl.Consequent(np.arange(*output["range"]), self.name)
        for label, (func_name, params) in output["sets"].items():
            mf = getattr(fuzz, func_name)(np.arange(*output["range"]), params)
            self.output[label] = mf

        def build_fuzzy_condition(conds):
            return lambda inputs: reduce(
                lambda a, cond: a & inputs[cond[0]][cond[1]],
                conds[1:],
                inputs[conds[0][0]][conds[0][1]],
            )

        rules = [
            {"if": build_fuzzy_condition(rule["if"]), "then": rule["then"]}
            for rule in rules
        ]

        fuzzy_rules = [
            ctrl.Rule(rule["if"](self.inputs), self.output[rule["then"]])
            for rule in rules
        ]

        system = ctrl.ControlSystem(fuzzy_rules)
        self.simulation = ctrl.ControlSystemSimulation(system)

    def applyDelay(self, current_value):
        delayed_value = (self.base_value * self.delay_const + current_value) / (
            self.delay_const + 1
        )
        self.base_value = delayed_value
        self.delay_history[0].append(current_value)
        self.delay_history[1].append(delayed_value)
        return delayed_value

    def compute(self, input_values, return_label=False):
        for var in self.inputs:
            if var in input_values:
                self.simulation.input[var] = input_values[var]
            elif var in self.defaults:
                self.simulation.input[var] = self.defaults[var]

        self.simulation.compute()
        output = self.simulation.output[self.name]

        if self.config.get("use_delay", False):
            output = self.applyDelay(output)

        if return_label:
            return output, self.mapOutput(output)
        return output

    def mapOutput(self, value):
        if "mapping" not in self.config:
            return value
        for low, high, label in self.config["mapping"]:
            if low <= value <= high:
                return label
        return None

    def visualize(self):
        for var in self.inputs.values():
            var.view()
        self.output.view()
