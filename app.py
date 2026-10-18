import streamlit as st

from datetime import date, datetime

from pawpal_system import Category, Owner, Pet, Priority, Task

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

if "owner" not in st.session_state:
    st.session_state.owner = Owner(owner_id=1, name="Jordan", email="jordan@example.com")
owner: Owner = st.session_state.owner

st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)

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
        pet = st.selectbox("Pet", owner.pets, format_func=lambda p: p.name)
        description = st.text_input("Task description", value="Morning walk")
        c1, c2, c3 = st.columns(3)
        category = c1.selectbox("Category", list(Category), format_func=lambda c: c.value)
        duration = c2.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority = c3.selectbox(
            "Priority", list(Priority), index=2, format_func=lambda p: p.name.title()
        )
        c4, c5 = st.columns(2)
        day = c4.date_input("Date", value=date.today())
        start = c5.time_input("Start time", value=datetime.now().replace(minute=0).time())
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
                    )
                )
                st.success(f"Added task for {pet.name}.")
            except ValueError as e:
                st.error(str(e))

    all_tasks = [(p, t) for p in owner.pets for t in p.tasks]
    if all_tasks:
        st.table(
            [
                {
                    "pet": p.name,
                    "task": t.description,
                    "category": t.category.value,
                    "start": t.start_time.strftime("%Y-%m-%d %H:%M"),
                    "minutes": t.duration_minutes,
                    "priority": t.priority.name.title(),
                    "done": t.completed,
                }
                for p, t in all_tasks
            ]
        )
    else:
        st.info("No tasks yet. Add one above.")
else:
    st.info("Add a pet before scheduling tasks.")

st.divider()

st.subheader("Build Schedule")
day = st.date_input("Schedule for", value=date.today(), key="schedule_day")

if st.button("Generate schedule"):
    schedule = owner.get_schedule(day)
    ordered = schedule.get_ordered_tasks()
    if not ordered:
        st.info(f"No pending tasks on {day}.")
    else:
        pet_names = {p.pet_id: p.name for p in owner.pets}
        st.table(
            [
                {
                    "time": f"{t.start_time:%H:%M}-{t.end_time:%H:%M}",
                    "pet": pet_names[t.pet_id],
                    "task": t.description,
                    "priority": t.priority.name.title(),
                }
                for t in ordered
            ]
        )
        for a, b in schedule.detect_conflicts():
            st.warning(
                f"Conflict: '{a.description}' ({pet_names[a.pet_id]}) overlaps "
                f"'{b.description}' ({pet_names[b.pet_id]})"
            )
