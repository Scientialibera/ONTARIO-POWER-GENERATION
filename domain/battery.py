from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True)
class BatteryConfig:
    power_mw: float = 100.0
    energy_mwh: float = 400.0
    round_trip_efficiency: float = 0.88
    initial_soc_pct: float = 50.0
    min_soc_pct: float = 10.0
    max_soc_pct: float = 95.0
    degradation_cost_per_mwh: float = 3.0
    require_terminal_soc: bool = True


@dataclass(frozen=True)
class DispatchRow:
    hour: int
    price_per_mwh: float
    charge_mw: float
    discharge_mw: float
    soc_mwh: float
    net_grid_mw: float | None
    gross_margin: float


@dataclass(frozen=True)
class DispatchResult:
    status: str
    strategy: str
    net_value: float
    gross_discharge_revenue: float
    charge_cost: float
    degradation_cost: float
    throughput_mwh: float
    equivalent_cycles: float
    peak_before_mw: float | None
    peak_after_mw: float | None
    peak_reduction_mw: float | None
    rows: list[DispatchRow]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["rows"] = [asdict(row) for row in self.rows]
        return payload


def optimize_dispatch(
    prices: list[float],
    config: BatteryConfig,
    *,
    strategy: Literal["arbitrage", "peak_shaving"] = "arbitrage",
    load_mw: list[float] | None = None,
) -> DispatchResult:
    if not prices:
        raise ValueError("At least one hourly price is required")
    if strategy == "peak_shaving" and (load_mw is None or len(load_mw) != len(prices)):
        raise ValueError("Peak shaving requires a load series matching the price series")
    if config.power_mw <= 0 or config.energy_mwh <= 0:
        raise ValueError("Battery power and energy must be positive")
    if not 0 < config.round_trip_efficiency <= 1:
        raise ValueError("Round-trip efficiency must be in (0, 1]")
    if config.min_soc_pct > config.initial_soc_pct or config.initial_soc_pct > config.max_soc_pct:
        raise ValueError("Initial SOC must sit between minimum and maximum SOC")

    n = len(prices)
    eta = config.round_trip_efficiency ** 0.5
    initial_soc = config.energy_mwh * config.initial_soc_pct / 100.0
    min_soc = config.energy_mwh * config.min_soc_pct / 100.0
    max_soc = config.energy_mwh * config.max_soc_pct / 100.0

    peak_idx = 3 * n if strategy == "peak_shaving" else None
    count = 3 * n + (1 if peak_idx is not None else 0)
    objective = np.zeros(count, dtype=float)
    price = np.asarray(prices, dtype=float)

    if strategy == "arbitrage":
        objective[:n] = price + config.degradation_cost_per_mwh
        objective[n:2*n] = -price + config.degradation_cost_per_mwh
    else:
        objective[:n] = 0.02
        objective[n:2*n] = 0.02
        objective[peak_idx] = 1.0

    a_eq = np.zeros((n, count), dtype=float)
    b_eq = np.zeros(n, dtype=float)
    for h in range(n):
        a_eq[h, h] = -eta
        a_eq[h, n+h] = 1.0 / eta
        a_eq[h, 2*n+h] = 1.0
        if h == 0:
            b_eq[h] = initial_soc
        else:
            a_eq[h, 2*n+h-1] = -1.0

    if config.require_terminal_soc:
        terminal = np.zeros(count, dtype=float)
        terminal[2*n+n-1] = 1.0
        a_eq = np.vstack([a_eq, terminal])
        b_eq = np.concatenate([b_eq, np.array([initial_soc])])

    a_ub = []
    b_ub = []
    if strategy == "peak_shaving":
        load = np.asarray(load_mw, dtype=float)
        for h in range(n):
            row = np.zeros(count, dtype=float)
            row[h] = 1.0
            row[n+h] = -1.0
            row[peak_idx] = -1.0
            a_ub.append(row)
            b_ub.append(-load[h])

    bounds = (
        [(0.0, config.power_mw)] * n
        + [(0.0, config.power_mw)] * n
        + [(min_soc, max_soc)] * n
    )
    if peak_idx is not None:
        bounds.append((0.0, None))

    result = linprog(
        objective,
        A_ub=np.asarray(a_ub) if a_ub else None,
        b_ub=np.asarray(b_ub) if b_ub else None,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"Battery optimization failed: {result.message}")

    charge = result.x[:n]
    discharge = result.x[n:2*n]
    soc = result.x[2*n:3*n]
    throughput = float(np.sum(charge + discharge))
    gross_revenue = float(np.dot(price, discharge))
    charge_cost = float(np.dot(price, charge))
    degradation_cost = float(config.degradation_cost_per_mwh * throughput)
    net_value = gross_revenue - charge_cost - degradation_cost

    peak_before = peak_after = peak_reduction = None
    net_grid_values: list[float | None] = [None] * n
    if load_mw is not None:
        load_array = np.asarray(load_mw, dtype=float)
        net_grid = load_array + charge - discharge
        net_grid_values = [float(v) for v in net_grid]
        peak_before = float(load_array.max())
        peak_after = float(net_grid.max())
        peak_reduction = peak_before - peak_after

    rows = [
        DispatchRow(
            hour=h + 1,
            price_per_mwh=float(price[h]),
            charge_mw=float(charge[h]),
            discharge_mw=float(discharge[h]),
            soc_mwh=float(soc[h]),
            net_grid_mw=net_grid_values[h],
            gross_margin=float(price[h] * (discharge[h] - charge[h])),
        )
        for h in range(n)
    ]
    return DispatchResult(
        status="optimal",
        strategy=strategy,
        net_value=net_value,
        gross_discharge_revenue=gross_revenue,
        charge_cost=charge_cost,
        degradation_cost=degradation_cost,
        throughput_mwh=throughput,
        equivalent_cycles=throughput / (2 * config.energy_mwh),
        peak_before_mw=peak_before,
        peak_after_mw=peak_after,
        peak_reduction_mw=peak_reduction,
        rows=rows,
    )
