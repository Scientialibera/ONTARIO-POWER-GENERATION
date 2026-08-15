from __future__ import annotations

import asyncio
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from xml.etree import ElementTree

import httpx


BASE = "https://reports-public.ieso.ca/public"
URLS = {
    "demand": f"{BASE}/Demand/PUB_Demand.csv",
    "demand_zonal": f"{BASE}/DemandZonal/PUB_DemandZonal.csv",
    "realtime_price": f"{BASE}/RealtimeOntarioZonalPrice/PUB_RealtimeOntarioZonalPrice.xml",
    "day_ahead_price": f"{BASE}/DAHourlyOntarioZonalPrice/PUB_DAHourlyOntarioZonalPrice.xml",
    "generation": f"{BASE}/GenOutputCapability/PUB_GenOutputCapability.xml",
}


@dataclass(frozen=True)
class HourlyDemand:
    date: str
    hour: int
    market_demand_mw: float
    ontario_demand_mw: float


def _clean_csv_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("\\"):
            continue
        yield line


def parse_demand_csv(text: str) -> list[HourlyDemand]:
    reader = csv.DictReader(_clean_csv_lines(text))
    if not reader.fieldnames:
        return []
    normalized = {name.strip().lower(): name for name in reader.fieldnames}
    required = ["date", "hour", "market demand", "ontario demand"]
    if not all(name in normalized for name in required):
        raise ValueError("Unexpected IESO Demand report schema")

    rows: list[HourlyDemand] = []
    for raw in reader:
        try:
            rows.append(
                HourlyDemand(
                    date=raw[normalized["date"]].strip(),
                    hour=int(float(raw[normalized["hour"]])),
                    market_demand_mw=float(raw[normalized["market demand"]]),
                    ontario_demand_mw=float(raw[normalized["ontario demand"]]),
                )
            )
        except (TypeError, ValueError, AttributeError):
            continue
    return rows


def parse_zonal_demand_csv(text: str) -> dict[str, float]:
    reader = csv.DictReader(_clean_csv_lines(text))
    if not reader.fieldnames:
        return {}
    names = [name.strip() for name in reader.fieldnames]
    rows = [row for row in reader if any((value or "").strip() for value in row.values())]
    if not rows:
        return {}
    last = rows[-1]

    excluded = {"date", "hour", "market demand", "ontario demand"}
    output: dict[str, float] = {}
    for name in names:
        if name.lower() in excluded:
            continue
        try:
            value = float(last.get(name, "") or "")
        except (TypeError, ValueError):
            continue
        if value >= 0:
            output[name] = value
    return output


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node: ElementTree.Element, names: set[str]) -> str | None:
    for child in node.iter():
        if _local_name(child.tag) in names and child.text and child.text.strip():
            return child.text.strip()
    return None


def parse_realtime_price_xml(text: str) -> dict:
    root = ElementTree.fromstring(text)
    delivery_hour = _text(root, {"DeliveryHour", "DELIVERYHOUR"})
    intervals = []
    for node in root.iter():
        if _local_name(node.tag) != "ZonalPrice":
            continue
        interval = _text(node, {"Interval"})
        price = _text(node, {"LmpCap", "ZonalPrice"})
        loss = _text(node, {"LossPriceCap", "LossPriceCapped"})
        congestion = _text(node, {"CongPriceCap", "CongestionPriceCapped"})
        try:
            intervals.append(
                {
                    "interval": int(float(interval)) if interval else None,
                    "price": float(price) if price else None,
                    "loss": float(loss) if loss else None,
                    "congestion": float(congestion) if congestion else None,
                }
            )
        except ValueError:
            continue
    priced = [row for row in intervals if row["price"] is not None]
    return {
        "delivery_hour": int(delivery_hour) if delivery_hour and delivery_hour.isdigit() else None,
        "price": priced[-1]["price"] if priced else None,
        "intervals": intervals,
    }


def parse_day_ahead_price_xml(text: str) -> dict:
    root = ElementTree.fromstring(text)
    rows = []
    for node in root.iter():
        if _local_name(node.tag) != "HourlyPriceComponents":
            continue
        hour = _text(node, {"PricingHour"})
        price = _text(node, {"ZonalPrice"})
        loss = _text(node, {"LossPriceCapped", "LossPriceCap"})
        congestion = _text(node, {"CongestionPriceCapped", "CongPriceCap"})
        try:
            rows.append(
                {
                    "hour": int(float(hour)) if hour else None,
                    "price": float(price) if price else None,
                    "loss": float(loss) if loss else None,
                    "congestion": float(congestion) if congestion else None,
                }
            )
        except ValueError:
            continue
    rows = [row for row in rows if row["hour"] is not None and row["price"] is not None]
    rows.sort(key=lambda row: row["hour"])
    return {"delivery_date": _text(root, {"DeliveryDate"}), "hours": rows}


def parse_generation_xml(text: str) -> dict[str, float]:
    root = ElementTree.fromstring(text)
    latest_by_generator: dict[str, tuple[int, str, float]] = {}

    for generator in root.iter():
        if _local_name(generator.tag) != "Generator":
            continue
        name = _text(generator, {"GeneratorName", "Name"}) or "Unknown"
        fuel = (_text(generator, {"FuelType"}) or "OTHER").upper()
        best = None

        for output in generator.iter():
            if _local_name(output.tag) not in {"Output", "HourlyData", "Data"}:
                continue
            hour_text = _text(output, {"Hour"})
            output_text = _text(output, {"EnergyMW", "OutputMW", "Energy"})
            if not hour_text or not output_text:
                continue
            try:
                candidate = (int(float(hour_text)), fuel, float(output_text))
            except ValueError:
                continue
            if best is None or candidate[0] >= best[0]:
                best = candidate

        if best is not None:
            latest_by_generator[name] = best

    totals: defaultdict[str, float] = defaultdict(float)
    for _, fuel, value in latest_by_generator.values():
        totals[fuel.title()] += value
    return dict(sorted(totals.items()))


class IESOClient:
    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout_seconds = timeout_seconds

    async def _get_text(self, key: str) -> str:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ontario-power-generation/0.1"},
        ) as client:
            response = await client.get(URLS[key])
            response.raise_for_status()
            return response.text

    async def live_snapshot(self) -> dict:
        keys = ["demand", "realtime_price", "day_ahead_price", "generation", "demand_zonal"]
        demand_text, realtime_text, day_ahead_text, generation_text, zonal_text = await asyncio.gather(
            *(self._get_text(key) for key in keys)
        )
        demand_rows = parse_demand_csv(demand_text)
        latest = demand_rows[-1] if demand_rows else None
        recent = demand_rows[-24:]

        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "source": "IESO public reports",
            "demand": {
                "latest_mw": latest.ontario_demand_mw if latest else None,
                "hourly": [
                    {"hour": row.hour, "date": row.date, "ontario_demand_mw": row.ontario_demand_mw}
                    for row in recent
                ],
            },
            "zonal_demand": parse_zonal_demand_csv(zonal_text),
            "realtime_price": parse_realtime_price_xml(realtime_text),
            "day_ahead_price": parse_day_ahead_price_xml(day_ahead_text),
            "generation_mix_mw": parse_generation_xml(generation_text),
        }
