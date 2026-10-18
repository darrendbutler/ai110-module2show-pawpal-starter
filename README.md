# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
Today's Schedule for Darren - Monday, October 12, 2026
============================================================
07:30 AM - 08:00 AM  Morning walk         (Buddy, walk, high priority)
08:00 AM - 08:10 AM  Breakfast            (Whiskers, feeding, high priority)
12:30 PM - 12:35 PM  Thyroid medication   (Whiskers, medication, high priority)
06:00 PM - 06:20 PM  Grooming brush-out   (Buddy, grooming, low priority)
```

## Implementation Summary

PawPal is a pet-care scheduler. The logic is in pawpal_system.py. It can be driven from main.py, the Streamlit app.py, or tests.

|                 Class                  |                                                                                                                                                                 Role                                                                                                                                                                  |
| :------------------------------------: | :-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
| Category, Priority, Recurrence (enums) |                                                          Category has seven task types. Priority is an IntEnum (LOW=1 to HIGH=3), so priorities compare and sort numerically. Recurrence is NONE, DAILY or WEEKLY, and its interval property returns the matching timedelta.                                                          |
|                  Task                  | One care activity, with a start_time, a duration_minutes, a priority, a category and a completed flag. It validates that the duration is positive and coerces category and priority to their enums. It has a derived end_time, mark_complete() and reschedule(). next_occurrence() returns a copy shifted by the recurrence interval. |
|                  Pet                   |                                       Owns a list of Tasks. add_task rejects a task whose pet_id doesn't match or whose task_id is a duplicate. It also has remove_task and get_pending_tasks. complete_task marks a task done and, if it recurs, appends the next occurrence with a fresh ID.                                        |
|                 Owner                  |                                                                                    Owns a list of Pets and a cache of schedules by date. It validates the email and rejects duplicate pet IDs. get_schedule(day) builds a new Schedule each time.                                                                                     |
|                Schedule                |                                                                      The plan for one day. generate(owner) collects every pending task, across all of the owner's pets, that starts on that day. It also has add_entry, detect_conflicts and get_ordered_tasks.                                                                       |

### How they work together

Ownership chain: Owner → Pet → Task. Each Task stores its pet_id and Pet.add_task checks it, so a task can't be attached to the wrong pet.

1. Schedules are derived, not stored as the source of truth. Owner.get_schedule(day) creates a Schedule and calls generate(self). That walks owner.pets → pet.get_pending_tasks() and filters to tasks starting that day. Because it rebuilds each time, the schedule can't go stale after a task is edited, completed or rescheduled. The schedules dict is only a cache of the last result.

2. Recurrence: Pet.complete_task(task) calls Task.next_occurrence, which uses dataclasses.replace to copy the task one day or week later. The copy gets a new ID (max existing ID + 1) and completed=False, and goes back onto the pet. The next day's schedule then picks it up on its own.

3. Ordering: get_ordered_tasks() sorts by start time. Ties go to higher priority, then to lower task_id.

4. Conflict detection: detect_conflicts() does a sweep over tasks sorted by start time. It keeps a list of tasks still running and pairs each new task with any whose end_time is later than the new task's start. Windows are half-open, so back-to-back tasks don't conflict. It runs in O(n log n + overlaps) instead of comparing every pair. It checks across all pets, because one owner can't do two things at once.

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

All of these live in `pawpal_system.py`. The scheduling methods are on `Schedule` (the plan for one day); recurrence is on `Task` and `Pet`.

| Feature                    | Method(s)                                    | Notes                                                                                                                                      |
| -------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Sorting (in place)         | `Schedule.sort_by_time()`                    | Reorders `entries` by `start_time` and returns them. Stable, so equal start times keep their existing order. O(n log n).                   |
| Sorting (display order)    | `Schedule.get_ordered_tasks()`               | Returns a new sorted list without changing `entries`. Ties go to higher priority, then lower `task_id`.                                    |
| Filtering                  | `Schedule.filter_tasks(owner, completed, pet_name)` | Filter by completion status, pet name, or both. A filter left as `None` is ignored. Pet names match case-insensitively; an unknown name returns an empty list. |
| Conflict detection         | `Schedule.detect_conflicts()`                | Sorts by start time, then sweeps once, keeping only the tasks still running. Returns every overlapping pair in O(n log n + overlaps). Windows are half-open, so back-to-back tasks don't conflict. Checks across all pets and covers identical start times. |
| Conflict warnings          | `Schedule.conflict_warnings(owner)`          | Turns each conflicting pair into a readable message, marked "both for Buddy" (same pet) or "Buddy vs Whiskers" (different pets). Returns a list instead of raising, so a conflict never crashes the app. `app.py` shows each one with `st.warning`. |
| Recurring tasks            | `Task.next_occurrence(new_id)`, `Pet.complete_task(task)` | `complete_task` marks the task done and, for a `DAILY` or `WEEKLY` task, appends the next occurrence, which `next_occurrence` builds as a copy shifted by the recurrence interval. If that time is already past (an overdue task), it advances in whole intervals until it is in the future, keeping the original time of day. Completing the same task twice returns `None` and creates no duplicate. |

### Example

```python
schedule = owner.get_schedule(today)

schedule.sort_by_time()                                    # earliest first
schedule.filter_tasks(owner, completed=False, pet_name="Buddy")  # Buddy's pending tasks
schedule.conflict_warnings(owner)                          # ["Warning: 'Vet visit' (03:00 PM-03:30 PM) overlaps 'Playtime' ... [Buddy vs Whiskers]"]
buddy.complete_task(task)                                  # also creates tomorrow's task if it recurs
```

`python main.py` runs each of these on sample data, including tasks added out of order and tasks at the same time.

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** _(optional)_: <!-- Insert a screenshot or link to a demo video here -->
