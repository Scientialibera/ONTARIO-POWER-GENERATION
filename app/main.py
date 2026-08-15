from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from domain.battery import BatteryConfig, optimize_dispatch
from domain.scenarios import ScenarioInput, apply_load_scenario
from services.ieso import IESOClient


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SAMPLE = ROOT / "data" / "sample" / "market_snapshot.json"

app = FastAPI(
    title="Ontario Power Generation",
    version="0.1.0",
    description="Ontario electricity market intelligence, forecasting and storage optimization.",
)


class BatteryRequest(BaseModel):
    prices: list[float] | None = None
    load_mw: list[float] | None = None
    strategy: str = "arbitrage"
    power_mw: float = Field(100.0, gt=0)
    energy_mwh: float = Field(400.0, gt=0)
    round_trip_efficiency: float = Field(0.88, gt=0, le=1)
    initial_soc_pct: float = Field(50.0, ge=0, le=100)
    min_soc_pct: float = Field(10.0, ge=0, le=100)
    max_soc_pct: float = Field(95.0, ge=0, le=100)
    degradation_cost_per_mwh: float = Field(3.0, ge=0)


class ScenarioRequest(BaseModel):
    baseline_mw: list[float]
    data_centre_mw: float = Field(0.0, ge=0)
    heat_wave_delta_c: float = Field(0.0, ge=0)
    ev_growth_pct: float = Field(0.0, ge=0)
    data_centre_load_factor: float = Field(0.9, ge=0, le=1)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environment": os.getenv("APP_ENV", "development")}


@app.get("/api/live")
async def live() -> dict:
    try:
        payload = await IESOClient(float(os.getenv("IESO_TIMEOUT_SECONDS", "12"))).live_snapshot()
        payload["data_status"] = "live"
        return payload
    except Exception as exc:
        fallback = json.loads(SAMPLE.read_text(encoding="utf-8"))
        fallback["data_status"] = "sample_fallback"
        fallback["warning"] = f"Live IESO reports unavailable: {type(exc).__name__}"
        return fallback


@app.post("/api/battery/optimize")
async def battery_optimize(request: BatteryRequest) -> dict:
    prices = request.prices
    load = request.load_mw
    if prices is None:
        market = await live()
        prices = [
            float(row["price"])
            for row in market.get("day_ahead_price", {}).get("hours", [])
            if row.get("price") is not None
        ]
        if load is None:
            load = [
                float(row["ontario_demand_mw"])
                for row in market.get("demand", {}).get("hourly", [])
                if row.get("ontario_demand_mw") is not None
            ]
    if not prices:
        raise ValueError("No market price series is available")
    if load and len(load) != len(prices):
        load = load[-len(prices):] if len(load) >= len(prices) else None

    config = BatteryConfig(
        power_mw=request.power_mw,
        energy_mwh=request.energy_mwh,
        round_trip_efficiency=request.round_trip_efficiency,
        initial_soc_pct=request.initial_soc_pct,
        min_soc_pct=request.min_soc_pct,
        max_soc_pct=request.max_soc_pct,
        degradation_cost_per_mwh=request.degradation_cost_per_mwh,
    )
    strategy = "peak_shaving" if request.strategy == "peak_shaving" else "arbitrage"
    return optimize_dispatch(prices, config, strategy=strategy, load_mw=load).to_dict()


@app.post("/api/scenario/load")
def load_scenario(request: ScenarioRequest) -> dict:
    scenario = ScenarioInput(
        data_centre_mw=request.data_centre_mw,
        heat_wave_delta_c=request.heat_wave_delta_c,
        ev_growth_pct=request.ev_growth_pct,
        data_centre_load_factor=request.data_centre_load_factor,
    )
    projected = apply_load_scenario(request.baseline_mw, scenario)
    return {
        "baseline_mw": request.baseline_mw,
        "scenario_mw": projected,
        "peak_before_mw": max(request.baseline_mw) if request.baseline_mw else None,
        "peak_after_mw": max(projected) if projected else None,
        "assumption_type": "scenario_transform_not_forecast",
    }


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str):
    requested = FRONTEND / full_path
    if full_path and requested.exists() and requested.is_file():
        return FileResponse(requested)
    return FileResponse(FRONTEND / "index.html")
