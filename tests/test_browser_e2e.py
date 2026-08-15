"""Browser-level checks for the main analyst workflows.

The live-feed call is fulfilled from the bundled snapshot so the tests are
deterministic; battery and scenario requests still exercise the running API.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000")
MARKET_FIXTURE = json.loads((ROOT / "data" / "sample" / "market_snapshot.json").read_text())
MARKET_FIXTURE["data_status"] = "sample_fallback"


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser) -> Page:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    yield page
    page.close()


@pytest.fixture
def dashboard(page: Page) -> Page:
    page.route(
        "**/api/live",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(MARKET_FIXTURE),
        ),
    )
    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.locator("#kpi-demand")).to_have_text("17,840")
    expect(page.locator("#dispatch-body tr")).to_have_count(24)
    return page


def set_range(page: Page, selector: str, value: str) -> None:
    page.locator(selector).evaluate(
        """(element, value) => {
            element.value = value;
            element.dispatchEvent(new Event('input', {bubbles: true}));
        }""",
        value,
    )


def test_live_grid_renders_market_summary_and_chart(dashboard: Page) -> None:
    expect(dashboard.locator("#source-label")).to_have_text("IESO unavailable: sample fallback")
    expect(dashboard.locator("#kpi-rt-price")).to_have_text("52.4")
    expect(dashboard.locator("#mix-bars .mix-row")).to_have_count(6)
    expect(dashboard.locator("#market-chart")).to_be_visible()


def test_generation_source_labels_are_rendered_as_text(page: Page) -> None:
    market = deepcopy(MARKET_FIXTURE)
    market["generation_mix_mw"] = {"<img src=x onerror=alert(1)>": 100}
    page.route(
        "**/api/live",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(market),
        ),
    )
    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.locator("#mix-bars img")).to_have_count(0)
    expect(page.locator("#mix-bars .mix-label")).to_have_text("<img src=x onerror=alert(1)>")


def test_battery_optimizer_runs_peak_shaving_with_updated_controls(dashboard: Page) -> None:
    dashboard.get_by_role("button", name="Battery Optimizer").click()
    dashboard.locator("#battery-strategy").select_option("peak_shaving")
    set_range(dashboard, "#power", "200")
    set_range(dashboard, "#energy", "800")
    expect(dashboard.locator("#power-out")).to_have_text("200 MW")
    expect(dashboard.locator("#energy-out")).to_have_text("800 MWh")

    dashboard.get_by_role("button", name="Run Optimization").click()

    expect(dashboard.locator("#result-peak")).not_to_have_text("--")
    expect(dashboard.locator("#result-net")).to_contain_text("$")
    expect(dashboard.locator("#dispatch-body tr")).to_have_count(24)
    expect(dashboard.locator("#battery-chart")).to_be_visible()


def test_scenario_lab_applies_all_load_assumptions(dashboard: Page) -> None:
    dashboard.get_by_role("button", name="Scenario Lab").click()
    set_range(dashboard, "#dc", "1000")
    set_range(dashboard, "#heat", "8")
    set_range(dashboard, "#ev", "30")
    expect(dashboard.locator("#dc-out")).to_have_text("1000 MW")
    expect(dashboard.locator("#heat-out")).to_have_text("+8 C")

    dashboard.get_by_role("button", name="Run Scenario").click()

    expect(dashboard.locator("#scenario-before")).to_contain_text("MW")
    expect(dashboard.locator("#scenario-after")).to_contain_text("MW")
    expect(dashboard.locator("#scenario-delta")).not_to_have_text("--")
    expect(dashboard.locator("#scenario-chart")).to_be_visible()


def test_forecast_tab_explains_model_boundary(dashboard: Page) -> None:
    dashboard.get_by_role("button", name="Forecast and Backtest").click()
    expect(dashboard.get_by_role("heading", name="Forward-Validated Demand Forecast")).to_be_visible()
    expect(dashboard.get_by_text("Published score", exact=True)).to_be_visible()
    expect(dashboard.get_by_text("Only after local training", exact=True)).to_be_visible()


def test_dashboard_is_usable_at_mobile_width(browser) -> None:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.route(
        "**/api/live",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(MARKET_FIXTURE),
        ),
    )
    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.locator("#kpi-demand")).to_have_text("17,840")
    page.get_by_role("button", name="Scenario Lab").click()
    expect(page.locator("#run-scenario")).to_be_visible()
    page.close()
