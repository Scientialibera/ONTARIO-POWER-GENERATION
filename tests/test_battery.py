from domain.battery import BatteryConfig, optimize_dispatch


def test_arbitrage_moves_energy_from_low_to_high_price():
    prices = [10, 10, 15, 20, 30, 80, 100, 60]
    config = BatteryConfig(
        power_mw=50,
        energy_mwh=100,
        round_trip_efficiency=0.90,
        initial_soc_pct=50,
        min_soc_pct=10,
        max_soc_pct=90,
        degradation_cost_per_mwh=1,
    )
    result = optimize_dispatch(prices, config)
    assert result.status == "optimal"
    assert result.net_value > 0
    assert any(row.charge_mw > 1 for row in result.rows[:4])
    assert any(row.discharge_mw > 1 for row in result.rows[4:])
    assert abs(result.rows[-1].soc_mwh - 50) < 1e-6


def test_peak_shaving_reduces_peak():
    prices = [40] * 8
    load = [100, 110, 120, 140, 200, 180, 130, 110]
    config = BatteryConfig(power_mw=50, energy_mwh=150, initial_soc_pct=70)
    result = optimize_dispatch(prices, config, strategy="peak_shaving", load_mw=load)
    assert result.peak_after_mw < result.peak_before_mw
