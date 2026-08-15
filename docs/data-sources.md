# Public data sources

The application is designed around official IESO public reports.

- Hourly Ontario Demand: https://reports-public.ieso.ca/public/Demand/
- Hourly Zonal Demand: https://reports-public.ieso.ca/public/DemandZonal/
- Real-Time Ontario Zonal Price: https://reports-public.ieso.ca/public/RealtimeOntarioZonalPrice/
- Day-Ahead Hourly Ontario Zonal Price: https://reports-public.ieso.ca/public/DAHourlyOntarioZonalPrice/
- Generator Output and Capability: https://reports-public.ieso.ca/public/GenOutputCapability/
- Hourly Consumption by FSA: https://reports-public.ieso.ca/public/HourlyConsumptionByFSA/
- IESO Data Directory: https://www.ieso.ca/power-data/data-directory
- 2026 Annual Planning Outlook: https://www.ieso.ca/Sector-Participants/Planning-and-Forecasting/Annual-Planning-Outlook

The FSA dataset is intentionally not bundled because individual monthly archives are large. The repository instead documents the official source and keeps downloaded history under gitignored `data/raw/`.
