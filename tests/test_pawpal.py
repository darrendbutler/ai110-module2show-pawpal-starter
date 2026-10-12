from datetime import datetime

from pawpal_system import Category, Pet, Priority, Task


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
