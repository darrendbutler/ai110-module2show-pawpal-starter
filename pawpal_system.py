from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Task:
    task_id: int
    description: str
    category: str
    duration_minutes: int
    priority: int
    due_time: datetime
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        raise NotImplementedError

    def reschedule(self, new_time: datetime) -> None:
        """Move the task to a new due time."""
        raise NotImplementedError


@dataclass
class Pet:
    pet_id: int
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        raise NotImplementedError

    def remove_task(self, task: Task) -> None:
        """Remove a care task from this pet."""
        raise NotImplementedError

    def get_pending_tasks(self) -> list[Task]:
        """Return tasks that are not yet completed."""
        raise NotImplementedError


@dataclass
class Owner:
    owner_id: int
    name: str
    email: str
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet with this owner."""
        raise NotImplementedError

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner."""
        raise NotImplementedError

    def get_schedule(self) -> Schedule:
        """Build and return the owner's schedule."""
        raise NotImplementedError


@dataclass
class Schedule:
    day: date
    entries: list[Task] = field(default_factory=list)

    def generate(self, owner: Owner) -> None:
        """Populate entries from the pending tasks of the owner's pets."""
        raise NotImplementedError

    def add_entry(self, task: Task) -> None:
        """Add a task to the schedule."""
        raise NotImplementedError

    def detect_conflicts(self) -> list[Task]:
        """Return tasks whose time windows overlap."""
        raise NotImplementedError

    def get_ordered_tasks(self) -> list[Task]:
        """Return entries ordered by time and priority."""
        raise NotImplementedError
