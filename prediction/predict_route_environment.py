"""Experimental historical-snapshot inference for one catalog route."""

import argparse
import csv
import json
import math
import tomllib
from datetime import timedelta
from pathlib import Path

import train_wbgt_multihorizon as heat
import train_pm25_multihorizon as air
import train_rainfall_classification as rain
import train_rainfall_neighbors as neighbors
from check_rainfall_sample_rules import build_relaxed_samples


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/datasets/snapshot_20261015"


def latest_record(records, origin, max_age):
    """Use only observations available at the forecast origin."""
    times = [
        time
        for time, record in records.items()
        if time <= origin
        and record["available_at"] <= origin
    ]

    if not times:
        return None

    time = max(times)

    if origin - time > timedelta(minutes=max_age):
        return None

    return time


def choose_station(
    stations,
    locations,
    source,
    point,
    origin,
    max_age,
    max_distance,
):
    """Choose the nearest usable station for this prototype."""
    candidates = []

    for row in locations:
        station = row["location_id"]

        if row["source"] != source or station not in stations:
            continue

        time = latest_record(
            stations[station],
            origin,
            max_age,
        )

        if time is None:
            continue

        distance = neighbors.distance_km(
            point,
            (float(row["lat"]), float(row["lon"])),
        )

        if distance <= max_distance:
            candidates.append((distance, station, time))

    return min(candidates) if candidates else None


def block(start, end, value, method, **metadata):
    """Describe one native forecast interval."""
    return {
        "valid_from": start.isoformat(),
        "valid_to": end.isoformat(),
        "value": value,
        "method": method,
        **metadata,
    }


def coverage(series, start, end):
    """Require usable forecast blocks across the entire run."""
    cursor = start

    for row in sorted(series, key=lambda item: item["valid_from"]):
        left = air.parse_timestamp(row["valid_from"])
        right = air.parse_timestamp(row["valid_to"])

        if row["value"] is None or right <= cursor:
            continue

        if left > cursor:
            break

        cursor = max(cursor, right)

    return cursor >= end


def rain_forecasts(stations, station, origin):
    """Refit the fixed neighbor experiment using pre-holdout labels."""
    forecasts = [
        block(
            origin + timedelta(minutes=horizon - 15),
            origin + timedelta(minutes=horizon),
            None,
            (
                "missing_input_or_training"
                if horizon <= 30
                else "unsupported_horizon"
            ),
        )
        for horizon in range(15, 181, 15)
    ]

    if station is None:
        return forecasts

    cutoff = min(
        origin,
        rain.parse_timestamp(rain.HOLDOUT_START),
    )

    training = {15: [], 30: []}
    origins = {origin}

    for name, records in stations.items():
        samples = build_relaxed_samples(records)

        for horizon in training:
            eligible = rain.training_before(
                samples[horizon],
                cutoff,
            )

            for sample in eligible:
                # Require complete targets available before the cutoff.
                complete_and_available = (
                    sample["target_complete"]
                    and all(
                        records[
                            sample["end"] - timedelta(minutes=5 * index)
                        ]["available_at"] < cutoff
                        for index in range(3)
                    )
                )

                if complete_and_available:
                    sample = dict(sample, station=name)
                    training[horizon].append(sample)
                    origins.add(sample["origin"])

    links = neighbors.load_neighbors(stations)
    snapshots = neighbors.build_snapshots(stations, origins)

    if station not in snapshots[origin]:
        return forecasts

    value, age = snapshots[origin][station]

    hour = origin.hour + origin.minute / 60
    angle = 2 * math.pi * hour / 24

    features = [
        value,
        age,
        math.sin(angle),
        math.cos(angle),
    ]

    query = {
        "x": features,
        "persistence": float(value > 0),
        "neighbor_x": (
            features
            + neighbors.neighbor_features(
                links[station],
                snapshots[origin],
            )
        ),
    }

    feature_cache = {}

    for horizon, samples in training.items():
        if not samples:
            continue

        for sample in samples:
            key = (sample["station"], sample["origin"])

            if key not in feature_cache:
                feature_cache[key] = neighbors.neighbor_features(
                    links[key[0]],
                    snapshots[key[1]],
                )

            sample["neighbor_x"] = (
                sample["x"] + feature_cache[key]
            )

        probabilities, statuses = neighbors.predict_methods(
            samples,
            [query],
        )

        forecasts[horizon // 15 - 1].update(
            value=float(
                probabilities["logistic_neighbors"][0]
            ),
            method=statuses["logistic_neighbors"],
            training_label_cutoff=cutoff.isoformat(),
            training_samples=len(samples),
        )

    return forecasts


def predict(route_id, as_of, start_delay_min, duration_min):
    """Return experimental forecasts for one requested running window."""
    if start_delay_min < 0 or duration_min <= 0:
        raise ValueError(
            "Delay must be nonnegative; duration must be positive."
        )

    if start_delay_min + duration_min > 180:
        raise ValueError(
            "Delay plus duration must not exceed 180 minutes."
        )

    with (ROOT / "config/environment.toml").open("rb") as handle:
        config = tomllib.load(handle)

    with (ROOT / "data/catalog/routes.csv").open(
        newline=""
    ) as handle:
        routes = {
            row["route_id"]: row
            for row in csv.DictReader(handle)
        }

    if route_id not in routes:
        raise ValueError(
            f"Unknown route. Choose from: {', '.join(routes)}"
        )

    route = routes[route_id]
    catalog = (ROOT / "data/catalog").resolve()
    geometry_path = (
        catalog / route["geometry_file"]
    ).resolve()

    if geometry_path.parent != catalog:
        raise ValueError("Invalid route geometry path.")

    feature = json.loads(geometry_path.read_text())
    lon, lat = feature["geometry"]["coordinates"][0][:2]

    with (SNAPSHOT / "locations.csv").open(
        newline=""
    ) as handle:
        locations = [
            row
            for row in csv.DictReader(handle)
            if row["source_kind"] == "live"
        ]

    heat_stations = heat.load_stations()
    rain_stations = rain.load_stations()
    regions = air.load_regions()

    # Match the forecast-origin grids used during training.
    quarter = as_of.replace(
        minute=as_of.minute // 15 * 15,
        second=0,
        microsecond=0,
    )

    hour = as_of.replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    distance_limit = config["matching"]["station_max_distance_km"]

    heat_match = choose_station(
        heat_stations,
        locations,
        "nea_wbgt",
        (lat, lon),
        quarter,
        30,
        distance_limit,
    )

    rain_match = choose_station(
        rain_stations,
        locations,
        "nea_rainfall",
        (lat, lon),
        quarter,
        15,
        distance_limit,
    )

    # Use persistence for WBGT.
    heat_series = []

    for horizon in range(15, 181, 15):
        end = quarter + timedelta(minutes=horizon)

        value = (
            heat_stations[heat_match[1]][heat_match[2]]["value"]
            if heat_match
            else None
        )

        heat_series.append(
            block(
                end - timedelta(minutes=15),
                end,
                value,
                "persistence" if heat_match else "missing_input",
            )
        )

    # Use the frozen PM2.5 coefficients saved by the training script.
    region = config["matching"]["route_regions"].get(route_id)
    records = regions.get(region, {})
    latest = latest_record(records, hour, 90)

    history_times = (
        [
            latest - timedelta(hours=index)
            for index in range(3)
        ]
        if latest is not None
        else []
    )

    complete_history = len(history_times) == 3 and all(
        time in records
        and records[time]["available_at"] <= hour
        for time in history_times
    )

    model_path = (
        ROOT
        / "prediction/results/pm25_multihorizon"
        / "backtest_models.json"
    )

    models = json.loads(model_path.read_text())
    air_series = []

    for horizon in [60, 120, 180]:
        model = next(
            (
                item
                for item in models
                if item["region"] == region
                and item["horizon_min"] == horizon
            ),
            None,
        )

        value = None
        method = "missing_input_or_model"

        usable_model = (
            complete_history
            and model is not None
            and air.parse_timestamp(
                model["training_cutoff"]
            ) <= hour
        )

        if usable_model:
            if model["selected_using_validation"] == "linear":
                coefficients = model[
                    "linear_intercept_and_coefficients"
                ]

                value = max(
                    0.0,
                    coefficients[0]
                    + sum(
                        coefficient * records[time]["value"]
                        for coefficient, time in zip(
                            coefficients[1:],
                            history_times,
                        )
                    ),
                )

                method = "frozen_experimental_linear"

            else:
                value = records[latest]["value"]
                method = "persistence"

        # Fall back only when a recent observation is available.
        if (
            value is None
            and latest is not None
            and timedelta(0) <= as_of - latest <= timedelta(minutes=90)
        ):
            value = records[latest]["value"]
            method = "persistence_fallback"

        # Fall back only when a recent observation is available.
        if (
            value is None
            and latest is not None
            and timedelta(0) <= as_of - latest <= timedelta(minutes=90)
        ):
            value = records[latest]["value"]
            method = "persistence_fallback"

        end = hour + timedelta(minutes=horizon)

        air_series.append(
            block(
                end - timedelta(hours=1),
                end,
                value,
                method,
                training_cutoff=(
                    model["training_cutoff"]
                    if model
                    else None
                ),
            )
        )

    rain_series = rain_forecasts(
        rain_stations,
        rain_match[1] if rain_match else None,
        quarter,
    )

    start = as_of + timedelta(minutes=start_delay_min)
    end = start + timedelta(minutes=duration_min)

    metrics = {}

    for name, series, unit, origin in [
        ("wbgt", heat_series, "degC", quarter),
        ("pm25", air_series, "ug/m3", hour),
        ("rain_probability", rain_series, "probability", quarter),
    ]:
        selected = [
            row
            for row in series
            if air.parse_timestamp(row["valid_to"]) > start
            and air.parse_timestamp(row["valid_from"]) < end
        ]

        metrics[name] = {
            "unit": unit,
            "model_origin": origin.isoformat(),
            "covers_entire_run": coverage(selected, start, end),
            "blocks": selected,
        }

    def source(match):
        if match is None:
            return None

        return {
            "station_id": match[1],
            "distance_km": round(match[0], 3),
            "observed_at": match[2].isoformat(),
        }

    return {
        "mode": "historical_snapshot_replay",
        "experimental": True,
        "as_of": as_of.isoformat(),
        "route_id": route_id,
        "run_start": start.isoformat(),
        "run_end": end.isoformat(),
        "sources": {
            "wbgt": source(heat_match),
            "rainfall": source(rain_match),
            "pm25": region,
        },
        "metrics": metrics,
        "risk_score": None,
        "notes": [
            "No new accuracy evaluation is performed by this script.",
            "Station matching uses the route start and prototype input-age limits.",
            "Snapshot metadata and revision history are not reconstructed.",
            "Rain values describe whole 15-minute events; do not prorate probabilities.",
            "PM2.5 values are hourly means, not minute-level predictions.",
            "Risk conversion and time ranking are not implemented.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--route", default="marina_bay")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--start-delay-min", type=int, default=0)
    parser.add_argument("--duration-min", type=int, default=30)

    args = parser.parse_args()

    result = predict(
        args.route,
        air.parse_timestamp(args.as_of),
        args.start_delay_min,
        args.duration_min,
    )

    output = ROOT / "prediction/results/route_forecasts"
    output.mkdir(parents=True, exist_ok=True)

    path = output / (
        f"{args.route}_"
        f"{args.start_delay_min}_"
        f"{args.duration_min}.json"
    )

    path.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )

    for name, metric in result["metrics"].items():
        print(
            f"{name}: full-run coverage = "
            f"{metric['covers_entire_run']}"
        )

        for row in metric["blocks"]:
            print(
                f"  {row['valid_from']} -> "
                f"{row['valid_to']}: {row['value']}"
            )

    print(f"Results saved to: {path}")


if __name__ == "__main__":
    main()