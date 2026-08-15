# Architecture

## Product surfaces

1. Live Grid: server-side adapters normalize official IESO public reports.
2. Battery Optimizer: constrained linear optimization over day-ahead price and optional load.
3. Scenario Lab: explicit sensitivity transforms for data-centre, heat-wave and EV growth assumptions.
4. Forecast and Backtest: reproducible forward-validated demand model trained from official hourly history.

## Data integrity

Measured public data, optimization output, forecast output and scenario assumptions are kept separate in both API responses and UI labels. If live IESO retrieval fails, the API returns a bundled sample fallback with `data_status=sample_fallback`.

## Optimization model

The storage model enforces:

- charge and discharge power limits
- energy capacity
- minimum and maximum state of charge
- round-trip efficiency
- terminal state-of-charge equality
- explicit degradation cost

The arbitrage objective maximizes energy-market value. Peak-shaving adds a peak variable and minimizes maximum post-battery system load.

## Forecast model

The training script uses a chronological holdout and compares the gradient-boosting model against a seasonal-naive one-week lag baseline. No model score is hard-coded into the repository.
