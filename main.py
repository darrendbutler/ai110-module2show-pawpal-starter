import datetime

from pawpal_system import (
    Category,
    Owner,
    Pet,
    Priority,
    Recurrence,
    Task,
)


def at(day: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time(hour, minute))


def main() -> None:
    today = datetime.date.today()

    owner = Owner(owner_id=1, name="Darren", email="darren@example.com")
    buddy = Pet(pet_id=1, name="Buddy", species="Dog", age=4)
    whiskers = Pet(pet_id=2, name="Whiskers", species="Cat", age=7)
    owner.add_pet(buddy)
    owner.add_pet(whiskers)

    buddy.add_task(
        Task(
            1,
            buddy.pet_id,
            "Morning walk",
            Category.WALK,
            30,
            Priority.HIGH,
            at(today, 7, 30),
            recurrence=Recurrence.DAILY,
        )
    )
    buddy.add_task(
        Task(
            2,
            buddy.pet_id,
            "Grooming brush-out",
            Category.GROOMING,
            20,
            Priority.LOW,
            at(today, 18, 0),
        )
    )
    whiskers.add_task(
        Task(
            1,
            whiskers.pet_id,
            "Breakfast",
            Category.FEEDING,
            10,
            Priority.HIGH,
            at(today, 8, 0),
            recurrence=Recurrence.DAILY,
        )
    )
    whiskers.add_task(
        Task(
            2,
            whiskers.pet_id,
            "Thyroid medication",
            Category.MEDICATION,
            5,
            Priority.HIGH,
            at(today, 12, 30),
        )
    )

    schedule = owner.get_schedule(today)

    print(f"Today's Schedule for {owner.name} - {today:%A, %B %d, %Y}")
    print("=" * 60)
    pets_by_id = {p.pet_id: p for p in owner.pets}
    for task in schedule.get_ordered_tasks():
        pet = pets_by_id[task.pet_id]
        print(
            f"{task.start_time:%I:%M %p} - {task.end_time:%I:%M %p}  "
            f"{task.description:<20} ({pet.name}, {task.category.value}, "
            f"{task.priority.name.lower()} priority)"
        )

    conflicts = schedule.detect_conflicts()
    if conflicts:
        print("\nConflicts:")
        for a, b in conflicts:
            print(f"  '{a.description}' overlaps '{b.description}'")


if __name__ == "__main__":
    main()
