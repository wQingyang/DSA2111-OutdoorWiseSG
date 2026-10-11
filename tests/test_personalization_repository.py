from datetime import datetime, timezone

import pytest

from outdoorwise.personalization.models import CompletedRunCreate, DifficultyFeedbackCreate
from outdoorwise.personalization.repository import PersonalizationRepository
from outdoorwise.personalization.service import PersonalizationService


def run_input(route="route-a"):
    return CompletedRunCreate(route_id=route, completed_at=datetime.now(timezone.utc),
                              actual_distance_km=5, actual_duration_min=30)


def test_persistence_isolation_and_pace(tmp_path):
    service = PersonalizationService(PersonalizationRepository(tmp_path))
    run = service.create_completed_run("alice", run_input())
    service.create_completed_run("bob", run_input("route-b"))
    assert service.list_completed_runs("alice") == [run]
    assert run.average_pace_min_per_km == 6
    assert (tmp_path / "runtime/personalization/completed_runs.json").exists()
    assert not (tmp_path / "runtime/completed_runs.json").exists()


def test_duplicate_favourite_and_deletion(tmp_path):
    service = PersonalizationService(PersonalizationRepository(tmp_path))
    first = service.add_favourite("alice", "route-a")
    second = service.add_favourite("alice", "route-a")
    assert first == second
    assert len(service.list_favourites("alice")) == 1
    assert service.remove_favourite("alice", "route-a")
    assert not service.remove_favourite("alice", "route-a")


def test_feedback_linkage_and_difficulty_validation(tmp_path):
    service = PersonalizationService(PersonalizationRepository(tmp_path))
    run = service.create_completed_run("alice", run_input())
    with pytest.raises(ValueError):
        DifficultyFeedbackCreate(difficulty=6)
    feedback = service.add_feedback("alice", "route-a", run.completed_run_id,
                                   DifficultyFeedbackCreate(difficulty=4, tags=["too_hilly"]))
    assert feedback.completed_run_id == run.completed_run_id
    with pytest.raises(LookupError):
        service.add_feedback("bob", "route-a", run.completed_run_id,
                             DifficultyFeedbackCreate(difficulty=3))
