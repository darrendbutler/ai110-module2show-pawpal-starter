from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from enum import Enum, IntEnum


class Category(Enum):
    FEEDING = "feeding"
    WALK = "walk"
    MEDICATION = "medication"
    GROOMING = "grooming"
    VET = "vet"
    PLAY = "play"
    OTHER = "other"


class Priority(IntEnum):
    """Higher value means more urgent."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Recurrence(Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"

    @property
    def interval(self) -> timedelta | None:
        return {Recurrence.DAILY: timedelta(days=1), Recurrence.WEEKLY: timedelta(weeks=1)}.get(self)


@dataclass
class Task:
    task_id: int  # unique within its pet
    pet_id: int  # the Pet this task belongs to
    description: str
    category: Category
    duration_minutes: int
    priority: Priority
    start_time: datetime  # when the task starts; it runs for duration_minutes
    completed: bool = False
    recurrence: Recurrence = Recurrence.NONE

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        self.category = Category(self.category)
        self.priority = Priority(self.priority)

    @property
    def end_time(self) -> datetime:
        """When the task finishes: start_time + duration_minutes."""
        return self.start_time + timedelta(minutes=self.duration_minutes)

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.completed = True

    def reschedule(self, new_time: datetime) -> None:
        """Move the task to a new start time."""
        self.start_time = new_time

    def next_occurrence(self, new_id: int) -> Task | None:
        """Return the next pending instance of a recurring task, or None."""
        step = self.recurrence.interval
        if step is None:
            return None
        return replace(self, task_id=new_id, start_time=self.start_time + step, completed=False)


@dataclass
class Pet:
    pet_id: int
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.age < 0:
            raise ValueError("age cannot be negative")

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        if task.pet_id != self.pet_id:
            raise ValueError(f"Task {task.task_id} belongs to pet {task.pet_id}, not {self.pet_id}")
        if any(t.task_id == task.task_id for t in self.tasks):
            raise ValueError(f"Task {task.task_id} already exists for pet {self.pet_id}")
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        """Remove a care task from this pet, matched by task_id."""
        for i, t in enumerate(self.tasks):
            if t.task_id == task.task_id:
                del self.tasks[i]
                return
        raise ValueError(f"Task {task.task_id} not found for pet {self.pet_id}")

    def get_pending_tasks(self) -> list[Task]:
        """Return tasks that are not yet completed."""
        return [t for t in self.tasks if not t.completed]

    def complete_task(self, task: Task) -> Task | None:
        """Complete a task; if it recurs, add and return the next occurrence."""
        task.mark_complete()
        new_id = max(t.task_id for t in self.tasks) + 1
        nxt = task.next_occurrence(new_id)
        if nxt is not None:
            self.tasks.append(nxt)
        return nxt


@dataclass
class Owner:
    owner_id: int
    name: str
    email: str
    pets: list[Pet] = field(default_factory=list)
    schedules: dict[date, Schedule] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if "@" not in self.email:
            raise ValueError("email must contain '@'")

    def add_pet(self, pet: Pet) -> None:
        """Register a pet with this owner."""
        if any(p.pet_id == pet.pet_id for p in self.pets):
            raise ValueError(f"Pet {pet.pet_id} already registered")
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner, matched by pet_id."""
        for i, p in enumerate(self.pets):
            if p.pet_id == pet.pet_id:
                del self.pets[i]
                return
        raise ValueError(f"Pet {pet.pet_id} not found")

    def get_schedule(self, day: date) -> Schedule:
        """Rebuild the schedule for a day from current tasks, so it is never stale."""
        schedule = Schedule(day)
        schedule.generate(self)
        self.schedules[day] = schedule
        return schedule


@dataclass
class Schedule:
    day: date
    entries: list[Task] = field(default_factory=list)

    def generate(self, owner: Owner) -> None:
        """Rebuild entries from the owner's pending tasks that start on self.day."""
        self.entries = [
            task
            for pet in owner.pets
            for task in pet.get_pending_tasks()
            if task.start_time.date() == self.day
        ]

    def add_entry(self, task: Task) -> None:
        """Add a task that starts on this schedule's day."""
        if task.start_time.date() != self.day:
            raise ValueError(f"Task {task.task_id} does not start on {self.day}")
        if any(e.pet_id == task.pet_id and e.task_id == task.task_id for e in self.entries):
            raise ValueError(f"Task {task.task_id} is already scheduled")
        self.entries.append(task)

    def detect_conflicts(self) -> list[tuple[Task, Task]]:
        """Return every pair of tasks whose [start_time, end_time) windows overlap.

        Sweeps tasks in start order, so cost is O(n log n + overlaps) rather
        than comparing all pairs. Applies across pets: the owner can only do
        one thing at a time.
        """
        conflicts: list[tuple[Task, Task]] = []
        active: list[Task] = []
        for task in sorted(self.entries, key=lambda t: t.start_time):
            active = [a for a in active if a.end_time > task.start_time]
            conflicts.extend((a, task) for a in active)
            active.append(task)
        return conflicts

    def get_ordered_tasks(self) -> list[Task]:
        """Return entries by start time; ties go to higher priority, then lower task_id."""
        return sorted(self.entries, key=lambda t: (t.start_time, -t.priority, t.task_id))
