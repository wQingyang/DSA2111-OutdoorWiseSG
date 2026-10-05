# API Configuration and Source Semantics

Endpoint URLs are configured in `config/environment.toml`. Independent collectors live in `outdoorwise/collectors/`. The verified public requests did not require an API key. An optional DATA_GOV_API_KEY is sent through the x-api-key header and is never written to CSV.

Use `OUTDOORWISE_ENV_CONFIG` to select another TOML configuration and `OUTDOORWISE_DATA_ROOT` to select another data directory.

The base URL is `https://api-open.data.gov.sg/v2/real-time/api/`. Append each endpoint below to that base URL. All eight endpoints were requested successfully and parsed into real CSV observations.

| Endpoint / collector | Actual response fields | Upstream to canonical unit | Aggregation window | Published cadence / polling interval |
|---|---|---|---|---|
| rainfall / rainfall.py | readings[].data[].value; TB1 Rainfall 5 Minute Total F | mm | 5-minute accumulation, PT5M | 5 minutes / 300s |
| wind-speed / wind_speed.py | value; Wind Speed AVG(S)10M M1M | knots to m/s, multiply by 1852/3600 | 10-minute mean, PT10M; upstream field indicates minute resolution | 5 minutes / 300s |
| wind-direction / wind_direction.py | value; Wind Dir AVG (S) 10M M1M | degrees to degree | 10-minute mean, PT10M | 5 minutes / 300s |
| air-temperature / temperature.py | value; DBT 1M F | deg C to degC | 1 minute, PT1M | 5 minutes / 300s |
| relative-humidity / humidity.py | value; RH 1M F | percentage to % | 1 minute, PT1M | 5 minutes / 300s |
| pm25 / pm25.py | items[].readings.pm25_one_hourly[region] | micrograms/m3 to ug/m3 | 1 hour, PT1H | 15 minutes / 900s |
| psi / psi.py | psi_twenty_four_hourly[region] | dimensionless to index | 24 hours, PT24H | 15 minutes / 900s |
| psi / psi.py | pm10_twenty_four_hourly[region] | micrograms/m3 to ug/m3 | 24 hours, PT24H | 15 minutes / 900s |
| weather?api=wbgt / wbgt.py | records[].item.readings[].wbgt | Celsius string to degC | 15-minute mean, PT15M | 15 minutes / 900s |
| weather?api=wbgt / wbgt.py | records[].item.readings[].heatStress | Low / Moderate / High to category_value | Official category corresponding to the PT15M WBGT observation | 15 minutes / 900s |

Publication cadence, aggregation window, and timestamp resolution are separate concepts. PM2.5 has a one-hour aggregation window, not a 15-minute window. PSI and PM10 are 24-hour measures and should not be described as instantaneous concentrations. PM10 uses the concentration field, **not pm10_sub_index**.

The station endpoints currently do not supply a reliable source_updated_at. This field remains empty; fetched_at must not substitute for a source update timestamp. Regional collectors use items[].timestamp and updatedTimestamp. WBGT uses records[].datetime and updatedTimestamp and accepts only observation records with isStationData=true. Both WBGT and heat stress come directly from the official source rather than being estimated from temperature and humidity.

## Official Dataset References

- Rainfall: https://data.gov.sg/datasets/d_6580738cdd7db79374ed3152159fbd69/view
- Wind speed: https://data.gov.sg/datasets/d_7677738484067741bf3b56ab5d69c7e9/view
- Wind direction: https://data.gov.sg/datasets/d_534cf203023b51f51f879145ccc56ff9/view
- Temperature: https://data.gov.sg/datasets/d_66b77726bbae1b33f218db60ff5861f0/view
- Humidity: https://data.gov.sg/datasets/d_2d3b0c4da128a9a59efca806441e1429/view
- PM2.5: https://data.gov.sg/datasets/d_e1058d6974c877257e32048ab128ad83/view
- PSI: https://data.gov.sg/datasets/d_fe37906a0182569d891506e815e819b7/view
- WBGT: https://data.gov.sg/datasets/d_87884af1f85d702d4f74c6af13b4853d/view

## Transport and Freshness Policy

The TOML configuration sets timeout_seconds=20, max_retries=2 (up to three requests), exponential backoff with Retry-After handling, a maximum retry delay of 30 seconds, and 1.5-second spacing between sources. HTTP 429, server errors, and network errors can be retried. Parsing failures and unexpected units are logged as failures without retries. Each source failure is isolated so other collectors can continue.

stale_after_seconds is an application policy, not an official health standard: 900 seconds for station metrics, 7200 seconds for regional metrics, and 2700 seconds for WBGT. Freshness uses observed_at; cache delivery uses fetch age and the latest failed collection. Missing observations remain missing. Actual zero values remain zero. Future observations do not enter a current query. Configured intervals do not start a scheduler automatically.

## Regional Matching

Air quality regions are explicit curated source assignments: Marina Bay=south and Woodlands=north. The service does not implement official region polygon containment. A regional labelLocation is not a route station, so station_distance_km remains empty for regional metrics. New routes require reviewed route_regions entries.
