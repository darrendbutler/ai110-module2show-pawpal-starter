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
        """Return the time between occurrences, or None if not recurring."""
        return {
            Recurrence.DAILY: timedelta(days=1),
            Recurrence.WEEKLY: timedelta(weeks=1),
        }.get(self)


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
        """Validate the duration and coerce category and priority to their enums."""
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
        """Return the next pending instance of a recurring task, or None.

        Args:
            new_id: task_id to give the new instance (must be unique for the pet).

        Returns:
            A copy of this task, not completed, starting one interval (a day or
            a week) later. If that time has already passed, the start is advanced
            in whole intervals until it is in the future, so an overdue task
            keeps its original time of day. None if the task does not recur.
        """
        step = self.recurrence.interval
        if step is None:
            return None
        next_start = self.start_time + step
        while next_start <= datetime.now():  # skip occurrences already in the past
            next_start += step
        return replace(
            self,
            task_id=new_id,
            start_time=next_start,
            completed=False,
        )


@dataclass
class Pet:
    pet_id: int
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject a negative age."""
        if self.age < 0:
            raise ValueError("age cannot be negative")

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        if task.pet_id != self.pet_id:
            raise ValueError(
                f"Task {task.task_id} belongs to pet {task.pet_id}, not {self.pet_id}"
            )
        if any(t.task_id == task.task_id for t in self.tasks):
            raise ValueError(
                f"Task {task.task_id} already exists for pet {self.pet_id}"
            )
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
        """Complete a task; if it recurs, add and return the next occurrence.

        Args:
            task: a task belonging to this pet.

        Returns:
            The newly created next occurrence, which is also appended to
            self.tasks. None for non-recurring tasks and for tasks already
            completed, so completing twice never creates duplicate occurrences.

        Raises:
            ValueError: if the task is not one of this pet's tasks.
        """
        if not any(t is task for t in self.tasks):
            raise ValueError(f"Task {task.task_id} not found for pet {self.pet_id}")
        if task.completed:
            return None
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
        """Reject an email address that lacks an '@'."""
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

    def _runs_on_day(self, task: Task) -> bool:
        """True if the task starts on self.day or is still running into it."""
        last_moment = task.end_time - timedelta(microseconds=1)
        return task.start_time.date() <= self.day <= last_moment.date()

    def generate(self, owner: Owner) -> None:
        """Rebuild entries from all of the owner's tasks that run on self.day.

        Includes completed tasks (so filter_tasks(completed=True) works) and tasks
        that started the previous day but run past midnight into self.day.
        """
        self.entries = [
            task
            for pet in owner.pets
            for task in pet.tasks
            if self._runs_on_day(task)
        ]

    def add_entry(self, task: Task) -> None:
        """Add a task that runs on this schedule's day."""
        if not self._runs_on_day(task):
            raise ValueError(
                f"Task {task.task_id} does not run on {self.day}"
            )
        if any(
            e.pet_id == task.pet_id and e.task_id == task.task_id
            for e in self.entries
        ):
            raise ValueError(f"Task {task.task_id} is already scheduled")
        self.entries.append(task)

    def filter_tasks(
        self, owner: Owner, completed: bool | None = None, pet_name: str | None = None
    ) -> list[Task]:
        """Return entries matching the given completion status and/or pet name.

        Args:
            owner: used to look up pet names, since Task only stores pet_id.
            completed: True for finished tasks, False for pending ones, None to
                ignore completion status.
            pet_name: matched case-insensitively against owner.pets, or None to
                ignore the pet.

        Returns:
            A new list in the existing entries order; entries is not modified.
            Empty if nothing matches, including when pet_name is unknown.
        """
        pet_ids = None
        if pet_name is not None:
            pet_ids = {p.pet_id for p in owner.pets if p.name.lower() == pet_name.lower()}
        return [
            t
            for t in self.entries
            if (completed is None or t.completed == completed)
            and (pet_ids is None or t.pet_id in pet_ids)
        ]

    def conflict_warnings(self, owner: Owner) -> list[str]:
        """Return a human-readable warning for each overlapping pair; never raises.

        Args:
            owner: used to turn pet ids into names for the message.

        Returns:
            One string per conflicting pair, with both tasks' times and either
            "both for <pet>" (same pet) or "<pet> vs <pet>" (different pets).
            Empty if the day is conflict-free. Reuses detect_conflicts; pet ids
            missing from owner.pets are shown as "pet <id>".
        """
        names = {p.pet_id: p.name for p in owner.pets}
        warnings = []
        for a, b in self.detect_conflicts():
            who_a = names.get(a.pet_id, f"pet {a.pet_id}")
            who_b = names.get(b.pet_id, f"pet {b.pet_id}")
            scope = f"both for {who_a}" if a.pet_id == b.pet_id else f"{who_a} vs {who_b}"
            warnings.append(
                f"Warning: '{a.description}' ({a.start_time:%I:%M %p}-{a.end_time:%I:%M %p}) "
                f"overlaps '{b.description}' ({b.start_time:%I:%M %p}-{b.end_time:%I:%M %p}) "
                f"[{scope}]"
            )
        return warnings

    def sort_by_time(self) -> list[Task]:
        """Sort entries in place by start_time and return them.

        Unlike get_ordered_tasks, this mutates self.entries and does not use
        priority. The sort is stable, so tasks with equal start times keep their
        existing relative order. Cost is O(n log n).
        """
        self.entries.sort(key=lambda t: t.start_time)
        return self.entries

    def detect_conflicts(self) -> list[tuple[Task, Task]]:
        """Return every pair of tasks whose [start_time, end_time) windows overlap.

        Sweeps tasks in start order, keeping only the tasks still running when
        the next one starts, so cost is O(n log n + overlaps) rather than
        comparing all pairs. Applies across pets: the owner can only do one
        thing at a time. Windows are half-open, so a task that starts exactly
        when another ends is not a conflict. Completed tasks are ignored.

        Returns:
            (earlier, later) pairs, where earlier starts no later than later.
            Does not modify entries.
        """
        conflicts: list[tuple[Task, Task]] = []
        active: list[Task] = []
        pending = (t for t in self.entries if not t.completed)
        for task in sorted(pending, key=lambda t: t.start_time):
            active = [a for a in active if a.end_time > task.start_time]
            conflicts.extend((a, task) for a in active)
            active.append(task)
        return conflicts

    def get_ordered_tasks(self) -> list[Task]:
        """Return entries by start time; ties go to higher priority, then lower task_id."""
        return sorted(
            self.entries, key=lambda t: (t.start_time, -t.priority, t.task_id)
        )
