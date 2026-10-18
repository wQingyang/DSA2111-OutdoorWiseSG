"""Experimental four-component risk with rain/wind persistence baselines."""

import csv
import json
import math
import tomllib

import predict_route_environment as environment


# Preserve the existing API import contract.
air = environment.air


def normalize(value, points):
    """Use the team's clamped piecewise-linear risk curves."""
    if value <= points[0][0]:
        return float(points[0][1])

    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (value - x0) * (y1 - y0) / (x1 - x0)

    return float(points[-1][1])


def missing(reason):
    return {
        "score": None,
        "status": "unavailable",
        "coverage_fraction": 0.0,
        "methods": [],
        "reason": reason,
    }


def component(metric, start, end, points, unit):
    """Score blocks before weighting them by overlap with the run."""
    result = missing("Missing or incomplete forecast.")

    if not metric or metric.get("unit") != unit:
        return result

    cursor = start
    covered = 0.0
    weighted = 0.0
    methods = set()
    total = (end - start).total_seconds()

    blocks = sorted(
        metric["blocks"],
        key=lambda row: row["valid_from"],
    )

    for row in blocks:
        left = max(
            start,
            air.parse_timestamp(row["valid_from"]),
        )
        right = min(
            end,
            air.parse_timestamp(row["valid_to"]),
        )

        if (
            right <= left
            or row["value"] is None
            or not math.isfinite(row["value"])
        ):
            continue

        if left < cursor:
            raise ValueError("Overlapping forecast blocks.")

        seconds = (right - left).total_seconds()

        weighted += normalize(row["value"], points) * seconds
        covered += seconds
        cursor = right
        methods.add(row["method"])

    result.update(
        coverage_fraction=round(covered / total, 4),
        methods=sorted(methods),
    )

    if abs(covered - total) < 0.001:
        result.update(
            score=round(weighted / total, 2),
            status="experimental",
            reason=None,
        )

    return result


def load_baseline_inputs():
    """Read canonical rain/wind values and availability timestamps."""
    specs = {
        "rainfall": ("nea_rainfall", "mm", "PT5M"),
        "wind_speed": ("nea_wind_speed", "m/s", "PT10M"),
    }

    output = {
        name: {}
        for name in specs
    }

    path = (
        environment.SNAPSHOT
        / "weather_observations.csv"
    )

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row["metric"]

            if name not in specs or row["source_kind"] != "live":
                continue

            source, unit, window = specs[name]

            if row["source"] != source:
                continue

            if (
                row["unit"],
                row["aggregation_window"],
            ) != (unit, window):
                raise ValueError(
                    f"Unexpected unit or window for {name}."
                )

            fetched = (
                row.get("first_fetched_at")
                or row.get("fetched_at")
            )

            if not row["value"] or not fetched:
                continue

            value = float(row["value"])

            if not math.isfinite(value) or value < 0:
                continue

            observed = air.parse_timestamp(
                row["observed_at"]
            )

            times = [
                observed,
                air.parse_timestamp(fetched),
            ]

            if row.get("source_updated_at"):
                times.append(
                    air.parse_timestamp(row["source_updated_at"])
                )

            records = output[name].setdefault(
                row["location_id"],
                {},
            )

            if observed in records:
                raise ValueError(
                    "Duplicate station observation timestamp."
                )

            records[observed] = {
                "value": value,
                "available_at": max(times),
            }

    return output


def context(route_id):
    """Read the route start point and station metadata."""
    catalog = environment.ROOT / "data/catalog"

    with (catalog / "routes.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        route = next(
            row
            for row in csv.DictReader(handle)
            if row["route_id"] == route_id
        )

    path = (
        catalog / route["geometry_file"]
    ).resolve()

    if path.parent != catalog.resolve():
        raise ValueError("Invalid geometry path.")

    feature = json.loads(
        path.read_text(encoding="utf-8")
    )

    lon, lat = feature["geometry"]["coordinates"][0][:2]

    with (environment.SNAPSHOT / "locations.csv").open(
        newline="",
        encoding="utf-8",
    ) as handle:
        locations = [
            row
            for row in csv.DictReader(handle)
            if row["source_kind"] == "live"
        ]

    return (lat, lon), locations


def check_source(
    result,
    observed,
    as_of,
    source,
    config,
    distance=None,
):
    """Check input freshness and configured spatial limits."""
    if observed is None:
        return missing(
            "Observation timestamp unavailable."
        )

    age = (as_of - observed).total_seconds()

    if (
        age < 0
        or age > config["sources"][source]["stale_after_seconds"]
    ):
        return missing(
            "Input observation is unavailable or stale at issue time."
        )

    if distance is not None:
        limit = config["matching"]["station_max_distance_km"]

        if (
            not math.isfinite(distance)
            or distance < 0
            or distance > limit
        ):
            return missing(
                "Station is outside the configured matching limit."
            )

        reliable = min(
            config["risk"]["max_reliable_station_distance_km"],
            limit,
        )

        if (
            distance > reliable
            and not config["risk"]["allow_approximate_station_estimates"]
        ):
            return missing(
                "Distant-station approximation is disabled."
            )

        result["spatial_quality"] = (
            "approximate"
            if distance > reliable
            else "start_point"
        )
    else:
        result["spatial_quality"] = "regional"

    result.update(
        input_observed_at=observed.isoformat(),
        input_age_minutes=round(age / 60, 2),
    )

    return result


def baseline(
    name,
    stations,
    locations,
    point,
    as_of,
    config,
):
    """Hold the latest usable observation unchanged during the run."""
    source = (
        "nea_rainfall"
        if name == "rainfall"
        else "nea_wind_speed"
    )

    match = environment.choose_station(
        stations,
        locations,
        source,
        point,
        as_of,
        config["sources"][source]["stale_after_seconds"] / 60,
        config["matching"]["station_max_distance_km"],
    )

    if match is None:
        return missing(
            f"No fresh usable {name} observation near the route start."
        )

    distance, station, observed = match
    record = stations[station][observed]
    value = record["value"]

    if (
        name == "wind_speed"
        and not config["risk"]["wind_scoring_enabled"]
    ):
        score = 0.0
    else:
        curve = (
            "rainfall"
            if name == "rainfall"
            else "wind"
        )

        score = normalize(
            value,
            config["risk"][curve]["points"],
        )

    result = {
        "score": round(score, 2),
        "status": "experimental_baseline",
        "coverage_fraction": 1.0,
        "methods": ["persistence_baseline"],
        "reason": None,
        "input_value": value,
        "unit": "mm" if name == "rainfall" else "m/s",
        "input_aggregation_window": (
            "PT5M"
            if name == "rainfall"
            else "PT10M"
        ),
        "station_id": station,
        "station_distance_km": round(distance, 3),
        "input_available_at": (
            record["available_at"].isoformat()
        ),
        "assumption": (
            "Hold the latest usable observation unchanged "
            "throughout the run."
        ),
    }

    if name == "wind_speed":
        result["wind_scoring_enabled"] = (
            config["risk"]["wind_scoring_enabled"]
        )

    return check_source(
        result,
        observed,
        as_of,
        source,
        config,
        distance,
    )


def predict(route_id, as_of, start_delay_min, duration_min):
    data = environment.predict(
        route_id,
        as_of,
        start_delay_min,
        duration_min,
    )

    with (environment.ROOT / "config/environment.toml").open(
        "rb"
    ) as handle:
        config = tomllib.load(handle)

    risk = config["risk"]
    start = air.parse_timestamp(data["run_start"])
    end = air.parse_timestamp(data["run_end"])

    heat = component(
        data["metrics"].get("wbgt"),
        start,
        end,
        risk["wbgt"]["points"],
        "degC",
    )

    heat_source = data["sources"].get("wbgt")

    if heat_source:
        heat = check_source(
            heat,
            air.parse_timestamp(heat_source["observed_at"]),
            as_of,
            "nea_wbgt",
            config,
            heat_source["distance_km"],
        )
    else:
        heat = missing("No usable WBGT source.")

    pollution = component(
        data["metrics"].get("pm25"),
        start,
        end,
        risk["pm25"]["points"],
        "ug/m3",
    )

    region = data["sources"].get("pm25")
    records = air.load_regions().get(region, {})

    origin = air.parse_timestamp(
        data["metrics"]["pm25"]["model_origin"]
    )

    latest = environment.latest_record(
        records,
        origin,
        90,
    )

    pollution = check_source(
        pollution,
        latest,
        as_of,
        "nea_pm25",
        config,
    )

    point, locations = context(route_id)
    inputs = load_baseline_inputs()

    components = {
        "rainfall": baseline(
            "rainfall",
            inputs["rainfall"],
            locations,
            point,
            as_of,
            config,
        ),
        "heat": heat,
        "air_quality": pollution,
        "wind": baseline(
            "wind_speed",
            inputs["wind_speed"],
            locations,
            point,
            as_of,
            config,
        ),
    }

    weights = risk["weights"]

    if (
        set(weights) != set(components)
        or any(
            not math.isfinite(weight) or weight < 0
            for weight in weights.values()
        )
        or abs(sum(weights.values()) - 1) > 1e-8
    ):
        raise ValueError(
            "Risk weights must cover all four components and sum to one."
        )

    complete = all(
        item["score"] is not None
        for item in components.values()
    )

    # Do not bypass future configured blocking policies.
    policy_pending = any(
        rule.get("enabled", True)
        for rule in risk.get("blocking_rules", [])
    )

    if complete and not policy_pending:
        score = round(
            sum(
                weights[name] * item["score"]
                for name, item in components.items()
            ),
            2,
        )
    else:
        score = None

    data["forecast_risk"] = {
        "risk_score": score,
        "status": (
            "experimental_complete"
            if score is not None
            else "incomplete"
        ),
        "assessment_mode": (
            "historical_forecast_with_persistence_baselines"
        ),
        "affects_ranking": False,
        "eligible_for_production_ranking": False,
        "weights": weights,
        "components": components,
        "policy_evaluation_pending": policy_pending,
        "notes": [
            "Four original risk curves and weights are reused; "
            "no missing-item renormalization.",

            "Rain risk uses held five-minute rainfall AMOUNT, "
            "not the displayed rain probability.",

            "Rain/wind persistence assumptions are experimental; "
            "forecast skill is not established.",

            "A zero rain component is not evidence "
            "that future weather will remain dry.",

            "Neutral wind scoring still requires a usable wind input; "
            "it does not imply no wind danger.",

            "Coverage=1 means the baseline assumption spans the run, "
            "not verified forecast accuracy.",

            "Station inputs represent the route start; "
            "air quality is regional.",

            "Not a substitute for the full observation-policy assessment; "
            "no route eligibility or ranking is changed.",
        ],
    }

    return data