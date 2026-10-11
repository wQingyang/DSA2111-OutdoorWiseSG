from datetime import datetime, timezone
from uuid import uuid4

from .models import (CompletedRun, CompletedRunCreate, DifficultyFeedback,
                     DifficultyFeedbackCreate, FavouriteRoute)
from .repository import PersonalizationRepository


class PersonalizationService:
    def __init__(self, repository: PersonalizationRepository):
        self.repository = repository

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def create_completed_run(self, user_id: str, data: CompletedRunCreate):
        return self.repository.save_completed_run(CompletedRun(
            completed_run_id=uuid4().hex, user_id=user_id, **data.model_dump()))

    def list_completed_runs(self, user_id):
        return self.repository.list_completed_runs(user_id)

    def get_completed_run(self, user_id, completed_run_id):
        return self.repository.get_completed_run(user_id, completed_run_id)

    def add_favourite(self, user_id, route_id):
        return self.repository.add_favourite(FavouriteRoute(
            user_id=user_id, route_id=route_id, created_at=self._now()))

    def remove_favourite(self, user_id, route_id):
        return self.repository.remove_favourite(user_id, route_id)

    def list_favourites(self, user_id):
        return self.repository.list_favourites(user_id)

    def add_feedback(self, user_id, route_id, completed_run_id, data: DifficultyFeedbackCreate):
        run = self.get_completed_run(user_id, completed_run_id)
        if run is None:
            raise LookupError("Completed run not found")
        if run.route_id != route_id:
            raise ValueError("Feedback route does not match completed run")
        return self.repository.save_feedback(DifficultyFeedback(
            feedback_id=uuid4().hex, user_id=user_id, route_id=route_id,
            completed_run_id=completed_run_id, created_at=self._now(), **data.model_dump()))

    def list_feedback(self, user_id):
        return self.repository.list_feedback(user_id)
