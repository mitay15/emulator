from copy import deepcopy
from .determine_basal import DetermineBasalEngine


def run_scenario_change_isf(cycle_input, new_isf: float):
    ci = deepcopy(cycle_input)
    ci.profile["sens"] = new_isf
    engine = DetermineBasalEngine()
    return engine.compute_from_input(ci)


def run_scenario_change_target(cycle_input, new_target: float):
    ci = deepcopy(cycle_input)
    ci.profile["target_bg"] = new_target
    engine = DetermineBasalEngine()
    return engine.compute_from_input(ci)


def run_scenario_change_max_basal(cycle_input, max_basal: float):
    ci = deepcopy(cycle_input)
    engine = DetermineBasalEngine(max_basal=max_basal)
    return engine.compute_from_input(ci)
