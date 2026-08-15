from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ScenarioInput:
    data_centre_mw: float = 0.0
    heat_wave_delta_c: float = 0.0
    ev_growth_pct: float = 0.0
    data_centre_load_factor: float = 0.90


def apply_load_scenario(baseline_mw: list[float], scenario: ScenarioInput) -> list[float]:
    if not baseline_mw:
        return []

    baseline = np.asarray(baseline_mw, dtype=float)
    hours = np.arange(len(baseline))

    afternoon = np.exp(-0.5 * ((hours - 17.0) / 4.0) ** 2)
    heat_multiplier = 1.0 + 0.006 * max(scenario.heat_wave_delta_c, 0.0) * afternoon

    ev_shape = 0.35 + 0.65 * np.exp(-0.5 * ((hours - 20.0) / 3.0) ** 2)
    ev_addition = baseline * (scenario.ev_growth_pct / 100.0) * 0.12 * ev_shape

    data_centre = np.full_like(
        baseline,
        max(scenario.data_centre_mw, 0.0)
        * min(max(scenario.data_centre_load_factor, 0.0), 1.0),
    )
    return list(baseline * heat_multiplier + ev_addition + data_centre)
