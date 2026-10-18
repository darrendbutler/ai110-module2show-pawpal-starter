from datetime import date, datetime, timedelta

import pytest

from pawpal_system import Category, Owner, Pet, Priority, Recurrence, Task


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
    assert pet.complete_task(task) is None
    assert len(pet.tasks) == 2


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
    assert len(pet.get_pending_tasks()) == 1


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
    """Characterization: a daily task materializes one occurrence at a time."""
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
