import streamlit as st

from datetime import date, datetime
from pathlib import Path

from marshmallow import ValidationError

from pawpal_system import (
    DATA_FILE,
    Category,
    Owner,
    Pet,
    Priority,
    Recurrence,
    Task,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

def load_owner() -> Owner:
    """Load the saved owner, or start fresh if there is no usable data file."""
    try:
        return Owner.load_from_json()
    except FileNotFoundError:
        pass
    except (ValidationError, ValueError) as e:
        # Keep the unreadable file instead of overwriting it on the next save.
        Path(DATA_FILE).replace(f"{DATA_FILE}.bak")
        st.session_state.flash = f"Could not read {DATA_FILE} ({e}); saved it as {DATA_FILE}.bak."
    return Owner(owner_id=1, name="Jordan", email="jordan@example.com")


def save_owner() -> None:
    """Persist the owner after a change; call after every mutation."""
    try:
        owner.save_to_json()
    except OSError as e:
        st.error(f"Could not save to {DATA_FILE}: {e}")


if "owner" not in st.session_state:
    st.session_state.owner = load_owner()
owner: Owner = st.session_state.owner

st.subheader("Owner")
new_name = st.text_input("Owner name", value=owner.name)
if new_name != owner.name:
    owner.name = new_name
    save_owner()

st.subheader("Pets")
with st.form("add_pet", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    pet_name = c1.text_input("Pet name", value="Mochi")
    species = c2.selectbox("Species", ["dog", "cat", "other"])
    age = c3.number_input("Age", min_value=0, max_value=40, value=3)
    if st.form_submit_button("Add pet"):
        try:
            owner.add_pet(
                Pet(
                    pet_id=max((p.pet_id for p in owner.pets), default=0) + 1,
                    name=pet_name,
                    species=species,
                    age=int(age),
                )
            )
            save_owner()
            st.success(f"Added {pet_name}.")
        except ValueError as e:
            st.error(str(e))

if owner.pets:
    st.table([{"name": p.name, "species": p.species, "age": p.age} for p in owner.pets])
else:
    st.info("No pets yet. Add one above.")

st.markdown("### Tasks")
if owner.pets:
    with st.form("add_task", clear_on_submit=False):
        # Newer Streamlit returns a *copy* of the selected option, so select by
        # id and look up the real Pet, or add_task would mutate a throwaway copy.
        pet_names = {p.pet_id: p.name for p in owner.pets}
        selected_pet_id = st.selectbox(
            "Pet", list(pet_names), format_func=lambda pid: pet_names[pid]
        )
        pet = next(p for p in owner.pets if p.pet_id == selected_pet_id)
        description = st.text_input("Task description", value="Morning walk")
        c1, c2, c3 = st.columns(3)
        category = c1.selectbox("Category", list(Category), format_func=lambda c: c.value)
        duration = c2.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority = c3.selectbox(
            "Priority", list(Priority), index=2, format_func=lambda p: p.name.title()
        )
        c4, c5, c6 = st.columns(3)
        day = c4.date_input("Date", value=date.today())
        start = c5.time_input("Start time", value=datetime.now().replace(minute=0).time())
        recurrence = c6.selectbox(
            "Repeats", list(Recurrence), format_func=lambda r: r.value.title()
        )
        if st.form_submit_button("Add task"):
            try:
                pet.add_task(
                    Task(
                        task_id=max((t.task_id for t in pet.tasks), default=0) + 1,
                        pet_id=pet.pet_id,
                        description=description,
                        category=category,
                        duration_minutes=int(duration),
                        priority=priority,
                        start_time=datetime.combine(day, start),
                        recurrence=recurrence,
                    )
                )
                save_owner()
                st.success(f"Added task for {pet.name}.")
                # Warn right away if the new task collides with something on its day.
                for warning in owner.get_schedule(day).conflict_warnings(owner):
                    st.warning(warning)
            except ValueError as e:
                st.error(str(e))
else:
    st.info("Add a pet before scheduling tasks.")

st.divider()

st.subheader("Schedule")
if not owner.pets:
    st.info("Add a pet and some tasks to see a schedule.")
else:
    day = st.date_input("Schedule for", value=date.today(), key="schedule_day")
    # Rebuilt on every rerun, so it always reflects the latest tasks.
    schedule = owner.get_schedule(day)

    f1, f2, f3 = st.columns(3)
    sort_mode = f1.radio(
        "Sort by", ["Start time, then priority", "Start time only"]
    )
    pet_filter = f2.selectbox("Pet", ["All pets"] + [p.name for p in owner.pets])
    status_filter = f3.selectbox("Status", ["All", "Pending", "Done"])

    # Conflicts are checked against the whole day, regardless of the filters.
    conflicts = schedule.conflict_warnings(owner)
    if conflicts:
        st.error(f"{len(conflicts)} scheduling conflict(s) on {day}:")
        for warning in conflicts:
            st.warning(warning)
    else:
        st.success(f"No conflicts on {day}.")

    if sort_mode == "Start time only":
        schedule.sort_by_time()
    else:
        schedule.entries = schedule.get_ordered_tasks()
    visible = schedule.filter_tasks(
        owner,
        completed={"All": None, "Pending": False, "Done": True}[status_filter],
        pet_name=None if pet_filter == "All pets" else pet_filter,
    )

    if not visible:
        st.info(f"No matching tasks on {day}.")
    else:
        pets_by_id = {p.pet_id: p for p in owner.pets}
        st.table(
            [
                {
                    "time": f"{t.start_time:%H:%M}-{t.end_time:%H:%M}",
                    "pet": pets_by_id[t.pet_id].name,
                    "task": t.description,
                    "category": t.category.value,
                    "priority": t.priority.name.title(),
                    "repeats": t.recurrence.value.title(),
                    "status": "Done" if t.completed else "Pending",
                }
                for t in visible
            ]
        )

        pending = [t for t in visible if not t.completed]
        if pending:
            st.markdown("**Mark a task complete**")
            for t in pending:
                pet = pets_by_id[t.pet_id]
                label = f"{t.start_time:%H:%M} {pet.name}: {t.description}"
                if st.button(f"✓ {label}", key=f"done_{t.pet_id}_{t.task_id}"):
                    nxt = pet.complete_task(t)
                    save_owner()
                    if nxt is not None:
                        st.session_state.flash = (
                            f"Completed '{t.description}'. Next one scheduled for "
                            f"{nxt.start_time:%Y-%m-%d %H:%M}."
                        )
                    else:
                        st.session_state.flash = f"Completed '{t.description}'."
                    st.rerun()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"))
