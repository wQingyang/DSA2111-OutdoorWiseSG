from math import isfinite
from statistics import mean, median

from .models import CompletedRun, DifficultyFeedback, UserRunningProfile


def _valid(value):
    return isinstance(value, (int, float)) and isfinite(value) and value > 0


def _percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def derive_running_profile(user_id: str, runs: list[CompletedRun], feedback: list[DifficultyFeedback], favourites) -> UserRunningProfile:
    distances = [r.actual_distance_km for r in runs if _valid(r.actual_distance_km)]
    paces = [r.average_pace_min_per_km for r in runs if _valid(r.average_pace_min_per_km)]
    ordered_runs = sorted((r for r in runs if _valid(r.actual_distance_km)), key=lambda r: r.completed_at)
    recent = ordered_runs[-5:]
    if len(distances) >= 4:
        lower, upper = _percentile(distances, .25), _percentile(distances, .75)
    elif distances:
        lower, upper = min(distances), max(distances)
    else:
        lower = upper = None

    by_run = {r.completed_run_id: r for r in ordered_runs}
    linked = sorted(((by_run[f.completed_run_id], f) for f in feedback if f.completed_run_id in by_run),
                    key=lambda item: item[0].completed_at)
    difficulties = [f.difficulty for _, f in linked]
    comfortable = [r.actual_distance_km for r, f in linked if f.difficulty in {2, 3}]
    if len(difficulties) < 3:
        trend = "insufficient_data"
    else:
        midpoint = len(difficulties) // 2
        change = mean(difficulties[midpoint:]) - mean(difficulties[:midpoint])
        trend = "increasing" if change > .25 else "decreasing" if change < -.25 else "stable"

    return UserRunningProfile(
        user_id=user_id,
        completed_run_count=len(runs), feedback_count=len(feedback), favourite_count=len(favourites),
        total_distance_km=round(sum(distances), 3) if distances else None,
        mean_distance_km=round(mean(distances), 3) if distances else None,
        median_distance_km=round(median(distances), 3) if distances else None,
        recent_mean_distance_km=round(mean([r.actual_distance_km for r in recent]), 3) if recent else None,
        typical_distance_min_km=round(lower, 3) if lower is not None else None,
        typical_distance_max_km=round(upper, 3) if upper is not None else None,
        comfortable_distance_km=round(median(comfortable), 3) if comfortable else None,
        mean_pace_min_per_km=round(mean(paces), 3) if paces else None,
        median_pace_min_per_km=round(median(paces), 3) if paces else None,
        mean_perceived_difficulty=round(mean(difficulties), 3) if difficulties else None,
        median_perceived_difficulty=round(median(difficulties), 3) if difficulties else None,
        recent_difficulty_trend=trend,
        usable_run_count=len(distances),
        profile_confidence="none" if not distances else "low" if len(distances) <= 2 else "medium" if len(distances) <= 5 else "high",
    )
