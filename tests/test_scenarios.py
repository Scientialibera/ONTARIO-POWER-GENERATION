from domain.scenarios import ScenarioInput, apply_load_scenario


def test_load_scenario_increases_peak():
    baseline = [100.0] * 24
    result = apply_load_scenario(
        baseline,
        ScenarioInput(data_centre_mw=50, heat_wave_delta_c=5, ev_growth_pct=20),
    )
    assert max(result) > max(baseline)
    assert len(result) == 24
