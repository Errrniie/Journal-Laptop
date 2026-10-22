from dataclasses import dataclass, field

@dataclass
class Set:
    reps: int                    # Reps for this set
    weight: float                # Weight (lbs/kg) for this set
    comment: str = ""            # Optional comment for this set (default empty string)
    unit: str = "lbs"
    extra_data: dict = field(default_factory=dict)
    comment_key: str = "comment"
    weight_key: str = "weight"
    record_time: str | None = None

@dataclass
class Exercise:
    name: str                    # Exercise name (e.g., "Bench Press")
    sets: list[Set] = field(default_factory=list)  # List of Set objects
    muscle_groups: list[str] = field(default_factory=list)  # List of muscle groups for this exercise
    metadata: dict = field(default_factory=dict)

@dataclass
class Workout:
    date: str                    # Date in "YYYY-MM-DD" format
    muscle_groups: list[str]     # List of muscle groups (e.g., ["Chest", "Triceps"])
    exercises: list[Exercise]    # List of Exercise objects
    duration_minutes: int = 0    # Optional: workout duration (default 0)
    notes: str = ""              # Optional: workout-level notes (default empty)
    workout_time: str | None = None  # Optional: time of workout in "HH:MM" 24-hour format (e.g. "09:30")
    session_id: str | None = None   # API session ID for delete/restore
    revision: int | None = None     # API version used to reject stale edits
    name: str = ""                  # Session title when supplied by the API
    edit_reason: str = ""           # Read-only when a legacy shape cannot round-trip
    metadata: dict = field(default_factory=dict)
    source: str = ""
    start_time: str | None = None

