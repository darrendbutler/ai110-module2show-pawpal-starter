from datetime import date, datetime, timedelta

from pawpal_system import Category, Owner, Pet, Priority, Recurrence, Task


def make_task(task_id: int = 1, pet_id: int = 1) -> Task:
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
    task = make_task()
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_add_task_increases_pet_task_count():
    pet = Pet(pet_id=1, name="Buddy", species="Dog", age=4)
    assert len(pet.tasks) == 0

    pet.add_task(make_task(task_id=1, pet_id=pet.pet_id))
    assert len(pet.tasks) == 1

    pet.add_task(make_task(task_id=2, pet_id=pet.pet_id))
    assert len(pet.tasks) == 2


def recurring_task(recurrence, start, task_id=1):
    return Task(task_id, 1, "Walk", Category.WALK, 30, Priority.HIGH, start, recurrence=recurrence)


def test_daily_task_creates_next_occurrence_one_day_later():
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
    start = datetime.now() + timedelta(hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.WEEKLY, start)
    pet.add_task(task)

    nxt = pet.complete_task(task)

    assert nxt.start_time == start + timedelta(weeks=1)


def test_non_recurring_task_creates_no_next_occurrence():
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.NONE, datetime.now() + timedelta(hours=1))
    pet.add_task(task)

    assert pet.complete_task(task) is None
    assert len(pet.tasks) == 1


def test_completing_twice_does_not_duplicate_occurrence():
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, datetime.now() + timedelta(hours=1))
    pet.add_task(task)

    pet.complete_task(task)
    assert pet.complete_task(task) is None
    assert len(pet.tasks) == 2


def test_overdue_daily_task_skips_past_occurrences():
    start = datetime.now() - timedelta(days=3, hours=1)
    pet = Pet(1, "Buddy", "Dog", 4)
    task = recurring_task(Recurrence.DAILY, start)
    pet.add_task(task)

    nxt = pet.complete_task(task)

    assert nxt.start_time > datetime.now()
    assert nxt.start_time - start == timedelta(days=4)  # stays on the original time of day


def conflict_setup():
    owner = Owner(1, "Darren", "d@example.com")
    buddy, mia = Pet(1, "Buddy", "Dog", 4), Pet(2, "Mia", "Cat", 2)
    owner.add_pet(buddy)
    owner.add_pet(mia)
    return owner, buddy, mia


def timed_task(task_id, pet, hour, minute=0, duration=30):
    return Task(
        task_id, pet.pet_id, f"Task {task_id}", Category.WALK, duration, Priority.LOW,
        datetime(2026, 10, 12, hour, minute),
    )


def test_conflict_warning_for_different_pets():
    owner, buddy, mia = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8))
    mia.add_task(timed_task(1, mia, 8, 15))

    warnings = owner.get_schedule(date(2026, 10, 12)).conflict_warnings(owner)

    assert len(warnings) == 1
    assert "Buddy vs Mia" in warnings[0]


def test_conflict_warning_for_same_pet():
    owner, buddy, _ = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8))
    buddy.add_task(timed_task(2, buddy, 8))  # identical start time

    warnings = owner.get_schedule(date(2026, 10, 12)).conflict_warnings(owner)

    assert len(warnings) == 1
    assert "both for Buddy" in warnings[0]


def test_back_to_back_tasks_do_not_conflict():
    owner, buddy, mia = conflict_setup()
    buddy.add_task(timed_task(1, buddy, 8, 0, duration=30))
    mia.add_task(timed_task(1, mia, 8, 30))

    assert owner.get_schedule(date(2026, 10, 12)).conflict_warnings(owner) == []
