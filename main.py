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

    # Tasks are deliberately added out of chronological order.
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

    schedule = owner.get_schedule(today)
    pets_by_id = {p.pet_id: p for p in owner.pets}

    def show(title: str, tasks: list[Task]) -> None:
        print(f"\n{title}")
        print("-" * 60)
        if not tasks:
            print("  (none)")
        for task in tasks:
            pet = pets_by_id[task.pet_id]
            status = "done" if task.completed else "pending"
            print(
                f"  {task.start_time:%I:%M %p} - {task.end_time:%I:%M %p}  "
                f"{task.description:<20} ({pet.name}, {status})"
            )

    print(f"Today's Schedule for {owner.name} - {today:%A, %B %d, %Y}")
    print("=" * 60)

    show("Entries as generated (insertion order)", schedule.entries)
    show("sort_by_time()", schedule.sort_by_time())

    # Mark one task done so the completion filter has something to find.
    schedule.entries[0].mark_complete()

    show("filter_tasks(completed=False)", schedule.filter_tasks(owner, completed=False))
    show("filter_tasks(completed=True)", schedule.filter_tasks(owner, completed=True))
    show("filter_tasks(pet_name='whiskers')", schedule.filter_tasks(owner, pet_name="whiskers"))
    show(
        "filter_tasks(completed=False, pet_name='Buddy')",
        schedule.filter_tasks(owner, completed=False, pet_name="Buddy"),
    )
    show("filter_tasks(pet_name='Nobody')", schedule.filter_tasks(owner, pet_name="Nobody"))

    conflicts = schedule.detect_conflicts()
    if conflicts:
        print("\nConflicts:")
        for a, b in conflicts:
            print(f"  '{a.description}' overlaps '{b.description}'")


if __name__ == "__main__":
    main()
