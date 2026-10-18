from datetime import date, datetime, timedelta

import pytest
from marshmallow import ValidationError

from pawpal_system import HORIZON_DAYS, Category, Owner, Pet, Priority, Recurrence, Task


def make_task(task_id: int = 1, pet_id: int = 1) -> Task:
    """Build a sample 30-minute HIGH-priority walk task starting 2026-10-12 07:30."""
    return Task(
        task_id=task_id,
        pet_id=pet_id,
        description="Morning walk",
        category=Category.WALK,
        duration_minutes=30,
        priority=Priority.HIGH,
        start_time=datetime(2026, 10, 12, 7, 30),
    )


def test_mark_complete_changes_task_status():
    """mark_complete flips a task from pending to completed."""
    task = make_task()
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_add_task_increases_pet_task_count():
    """Adding tasks to a pet grows its task list one at a time."""
    pet = Pet(pet_id=1, name="Buddy", species="Dog", age=4)
    assert len(pet.tasks) == 0

    pet.add_task(make_task(task_id=1, pet_id=pet.pet_id))
    assert len(pet.tasks) == 1

    pet.add_task(make_task(task_id=2, pet_id=pet.pet_id))
    assert len(pet.tasks) == 2


def recurring_task(recurrence, start, task_id=1):
    """Build a walk task for pet 1 with the given recurrence and start time."""
    return Task(task_id, 1, "Walk", Category.WALK, 30, Priority.HIGH, start, recurrence=recurrence)


def test_daily_task_creates_next_occurrence_one_day_later():
    """Completing a daily task adds a new pending copy exactly one day later with a new id."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)

    nxt = pet.complete_task(task)

    assert task.completed
    assert nxt is not None and not nxt.completed
    assert nxt.start_time == start + timedelta(days=1)
    assert nxt.task_id != task.task_id
    assert nxt in pet.tasks


def test_weekly_task_creates_next_occurrence_one_week_later():
    """Completing a weekly task adds a new occurrence exactly one week later."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.WEEKLY, start)
    pet.add_task(task)

    nxt = pet.complete_task(task)

    assert nxt.start_time == start + timedelta(weeks=1)


def test_non_recurring_task_creates_no_next_occurrence():
    """Completing a non-recurring task returns None and adds no task."""
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.NONE, datetime.now() + timedelta(hours=1))
    pet.add_task(task)

    assert pet.complete_task(task) is None
    assert len(pet.tasks) == 1


def test_completing_twice_does_not_duplicate_occurrence():
    """Completing an already-completed recurring task returns None and creates no duplicate."""
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, datetime.now() + timedelta(hours=1))
    pet.add_task(task)

    pet.complete_task(task)
    count = len(pet.tasks)
    assert pet.complete_task(task) is None
    assert len(pet.tasks) == count


def test_overdue_daily_task_skips_past_occurrences():
    """An overdue daily task rolls forward in whole days to the next future time, keeping its time of day."""
    start = datetime.now() - timedelta(days=3, hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)

    nxt = pet.complete_task(task)

    assert nxt.start_time > datetime.now()
    assert nxt.start_time - start == timedelta(days=4)  # stays on the original time of day


def conflict_setup():
    """Return an owner with two pets: Buddy (id 1) and Mia (id 2)."""
    owner = Owner(1, "Darren", "d@example.com")
    buddy, mia = Pet(1, "Buddy", "Dog", 4), Pet(2, "Mia", "Cat", 2)
    owner.add_pet(buddy)
    owner.add_pet(mia)
    return owner, buddy, mia


def timed_task(task_id, pet, hour, minute=0, duration=30):
    """Build a task for `pet` on 2026-10-12 at hour:minute lasting `duration` minutes."""
    return Task(
        task_id, pet.pet_id, f"Task {task_id}", Category.WALK, duration, Priority.LOW,
        datetime(2026, 10, 12, hour, minute),
    )


def test_conflict_warning_for_different_pets():
    """Overlapping tasks for different pets produce one 'Buddy vs Mia' warning."""
    owner, buddy, mia = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8))
    mia.add_task(timed_task(1, mia, 8, 15))

    warnings = owner.get_schedule(date(2026, 10, 12)).conflict_warnings(owner)

    assert len(warnings) == 1
    assert "Buddy vs Mia" in warnings[0]


def test_conflict_warning_for_same_pet():
    """Two tasks for the same pet at the same start time produce one 'both for Buddy' warning."""
    owner, buddy, _ = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8))
    buddy.add_task(timed_task(2, buddy, 8))  # identical start time

    warnings = owner.get_schedule(date(2026, 10, 12)).conflict_warnings(owner)

    assert len(warnings) == 1
    assert "both for Buddy" in warnings[0]


def test_back_to_back_tasks_do_not_conflict():
    """A task starting exactly when another ends is not a conflict (half-open windows)."""
    owner, buddy, mia = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8, 0, duration=30))
    mia.add_task(timed_task(1, mia, 8, 30))

    assert owner.get_schedule(date(2026, 10, 12)).conflict_warnings(owner) == []


# --- Requested core behaviors -------------------------------------------------


def test_sorting_returns_tasks_in_chronological_order():
    """Tasks added out of order across pets come back sorted by start time from both sort methods."""
    owner, buddy, mia = conflict_setup()
    # Added deliberately out of order, across two pets.
    buddy.add_task(timed_task(1, buddy, 15))
    mia.add_task(timed_task(1, mia, 7, 30))
    buddy.add_task(timed_task(2, buddy, 9))
    mia.add_task(timed_task(2, mia, 12, 45))
    schedule = owner.get_schedule(date(2026, 10, 12))

    times = [t.start_time for t in schedule.sort_by_time()]

    assert times == sorted(times)
    assert [t.start_time.hour for t in schedule.entries] == [7, 9, 12, 15]
    assert [t.start_time for t in schedule.get_ordered_tasks()] == times


def test_marking_daily_task_complete_creates_task_for_following_day():
    """Completing a daily task creates a pending task on the next calendar day at the same time of day."""
    pet = Pet(1, "Buddy", "Dog", 4)
    start = datetime.now().replace(microsecond=0) + timedelta(hours=1)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)

    nxt = pet.complete_task(task)

    assert nxt is not None
    assert nxt.start_time.date() == (start + timedelta(days=1)).date()
    assert nxt.start_time.time() == start.time()
    assert nxt.completed is False
    assert nxt in pet.get_pending_tasks()


def test_scheduler_flags_duplicate_times_across_pets():
    """Two tasks for different pets with an identical start time are flagged as one conflict."""
    owner, buddy, mia = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8))
    mia.add_task(timed_task(1, mia, 8))  # exact same start time

    schedule = owner.get_schedule(date(2026, 10, 12))
    warnings = schedule.conflict_warnings(owner)

    assert len(schedule.detect_conflicts()) == 1
    assert len(warnings) == 1
    assert "Buddy vs Mia" in warnings[0]


def test_three_tasks_at_same_time_flag_every_pair():
    """Three tasks at the same time produce a conflict for each of the three pairs."""
    owner, buddy, mia = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8))
    buddy.add_task(timed_task(2, buddy, 8))
    mia.add_task(timed_task(1, mia, 8))

    schedule = owner.get_schedule(date(2026, 10, 12))

    assert len(schedule.detect_conflicts()) == 3


# --- Edge cases: items 1-4 from the review ------------------------------------


def test_filter_completed_returns_completed_tasks_from_generated_schedule():
    """A generated schedule keeps completed tasks so filter_tasks can split them from pending ones."""
    owner, buddy, _ = conflict_setup()
    done, pending = timed_task(1, buddy, 8), timed_task(2, buddy, 10)
    buddy.add_task(done)
    buddy.add_task(pending)
    done.mark_complete()

    schedule = owner.get_schedule(date(2026, 10, 12))

    assert schedule.filter_tasks(owner, completed=True) == [done]
    assert schedule.filter_tasks(owner, completed=False) == [pending]


def test_task_crossing_midnight_conflicts_with_early_task_next_day():
    """A task running past midnight shows up on the next day's schedule and conflicts with an early task there."""
    owner, buddy, mia = conflict_setup()
    late = Task(1, buddy.pet_id, "Late meds", Category.MEDICATION, 60, Priority.HIGH,
                datetime(2026, 10, 12, 23, 45))  # runs until 00:45 on the 13th
    early = Task(1, mia.pet_id, "Midnight play", Category.PLAY, 30, Priority.LOW,
                 datetime(2026, 10, 13, 0, 15))
    buddy.add_task(late)
    mia.add_task(early)

    warnings = owner.get_schedule(date(2026, 10, 13)).conflict_warnings(owner)

    assert len(warnings) == 1


def test_only_next_occurrence_is_scheduled_not_future_days():
    """Occurrences beyond the HORIZON_DAYS rolling window are not materialized."""
    pet = Pet(1, "Buddy", "Dog", 4)
    owner = Owner(1, "Darren", "d@example.com")
    owner.add_pet(pet)
    start = datetime.now() + timedelta(hours=1)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)
    pet.complete_task(task)

    two_weeks_out = (start + timedelta(days=14)).date()

    assert owner.get_schedule(two_weeks_out).entries == []
    assert len(owner.get_schedule((start + timedelta(days=1)).date()).entries) == 1


def test_complete_task_not_in_pet_raises_and_changes_nothing():
    """Completing a task the pet does not own raises ValueError and leaves everything unchanged."""
    buddy = Pet(1, "Buddy", "Dog", 4)
    buddy.add_task(timed_task(1, buddy, 8))
    stranger = recurring_task(Recurrence.DAILY, datetime.now() + timedelta(hours=1), task_id=99)

    with pytest.raises(ValueError):
        buddy.complete_task(stranger)

    assert stranger.completed is False
    assert len(buddy.tasks) == 1


def test_add_recurring_task_assigns_series_id():
    """A recurring task starts its own series; a non-recurring one gets none."""
    pet = Pet(1, "Buddy", "Dog", 4)
    daily = recurring_task(Recurrence.DAILY, datetime.now() + timedelta(hours=1), task_id=5)
    once = recurring_task(Recurrence.NONE, datetime.now() + timedelta(hours=1), task_id=6)
    pet.add_task(daily)
    pet.add_task(once)

    assert daily.series_id == 5
    assert once.series_id is None


def test_ensure_occurrences_fills_window_to_horizon():
    """A daily series gets one instance per day through the horizon, all pending."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    pet.add_task(recurring_task(Recurrence.DAILY, start))
    horizon = (start + timedelta(days=5)).date()

    created = pet.ensure_occurrences(horizon)

    assert [t.start_time for t in created] == [start + timedelta(days=d) for d in range(1, 6)]
    assert all(not t.completed and t.series_id == 1 for t in created)
    assert len({t.task_id for t in pet.tasks}) == len(pet.tasks)


def test_ensure_occurrences_is_idempotent():
    """Calling ensure_occurrences twice with the same horizon creates nothing the second time."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    pet.add_task(recurring_task(Recurrence.WEEKLY, start))
    horizon = (start + timedelta(days=21)).date()

    pet.ensure_occurrences(horizon)
    count = len(pet.tasks)

    assert pet.ensure_occurrences(horizon) == []
    assert len(pet.tasks) == count == 4


def test_ensure_occurrences_ignores_non_recurring_tasks():
    """Non-recurring tasks never spawn instances."""
    pet = Pet(1, "Buddy", "Dog", 4)
    pet.add_task(recurring_task(Recurrence.NONE, datetime.now() + timedelta(hours=1)))

    assert pet.ensure_occurrences(date.today() + timedelta(days=30)) == []
    assert len(pet.tasks) == 1


def test_ensure_occurrences_skips_past_times():
    """An overdue series only gets instances in the future, not a backlog."""
    start = datetime.now() - timedelta(days=3)
    pet = Pet(1, "Buddy", "Dog", 4)
    pet.add_task(recurring_task(Recurrence.DAILY, start))

    created = pet.ensure_occurrences(date.today() + timedelta(days=2))

    assert created and all(t.start_time > datetime.now() for t in created)


def test_complete_task_reuses_already_materialized_next_occurrence():
    """Completing a task whose next instance already exists returns it without duplicating."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)
    pet.ensure_occurrences((start + timedelta(days=3)).date())
    before = len(pet.tasks)

    nxt = pet.complete_task(task)

    assert nxt.start_time == start + timedelta(days=1)
    assert [t.start_time for t in pet.tasks].count(nxt.start_time) == 1
    assert len(pet.tasks) >= before


def test_complete_task_tops_up_rolling_window():
    """Completing a recurring task leaves instances through today + HORIZON_DAYS."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)

    pet.complete_task(task)

    horizon = date.today() + timedelta(days=HORIZON_DAYS)
    assert max(t.start_time.date() for t in pet.tasks) == horizon


def test_get_schedule_shows_upcoming_occurrences_without_completion():
    """A never-completed daily task still appears on upcoming days in the schedule."""
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    owner = Owner(1, "Darren", "d@example.com")
    owner.add_pet(pet)
    pet.add_task(recurring_task(Recurrence.DAILY, start))

    day = (start + timedelta(days=3)).date()

    assert len(owner.get_schedule(day).entries) == 1


def test_save_and_load_round_trip(tmp_path):
    """An owner with pets and tasks is identical after save_to_json and load_from_json."""
    owner = Owner(1, "Darren", "d@example.com")
    pet = Pet(1, "Mochi", "dog", 3)
    owner.add_pet(pet)
    pet.add_task(make_task())
    done = make_task(task_id=2)
    done.recurrence = Recurrence.DAILY
    done.mark_complete()
    pet.add_task(done)

    path = tmp_path / "data.json"
    owner.save_to_json(path)

    assert Owner.load_from_json(path) == owner


@pytest.mark.parametrize(
    "contents",
    [
        '{"owner_id": 1}',  # required fields missing
        '{"owner_id": 1, "name": "D", "email": "no-at-sign", "pets": []}',
        '{"owner_id": 1, "name": "D", "email": "d@x.com", "pets": [{"pet_id": 1,'
        ' "name": "M", "species": "dog", "age": 3, "tasks": [{"task_id": 1,'
        ' "pet_id": 1, "description": "w", "category": "bogus",'
        ' "duration_minutes": 30, "priority": 3,'
        ' "start_time": "2030-01-01T08:00:00"}]}]}',  # unknown category
    ],
)
def test_load_from_json_rejects_invalid_data(tmp_path, contents):
    """Invalid saved data raises instead of producing a half-built owner."""
    path = tmp_path / "data.json"
    path.write_text(contents)

    with pytest.raises((ValidationError, ValueError)):
        Owner.load_from_json(path)


def test_load_from_json_missing_file_raises(tmp_path):
    """Loading before anything was saved raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Owner.load_from_json(tmp_path / "data.json")
