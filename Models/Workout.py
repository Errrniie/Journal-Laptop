from dataclasses import dataclass, field

@dataclass
class Set:
    reps: int                    # Reps for this set
    weight: float                # Weight (lbs/kg) for this set
    comment: str = ""            # Optional comment for this set (default empty string)

@dataclass
class Exercise:
    name: str                    # Exercise name (e.g., "Bench Press")
    sets: list[Set] = field(default_factory=list)  # List of Set objects
    muscle_groups: list[str] = field(default_factory=list)  # List of muscle groups for this exercise

@dataclass
class Workout:
    date: str                    # Date in "YYYY-MM-DD" format
    muscle_groups: list[str]     # List of muscle groups (e.g., ["Chest", "Triceps"])
    exercises: list[Exercise]    # List of Exercise objects
    duration_minutes: int = 0    # Optional: workout duration (default 0)
    notes: str = ""              # Optional: workout-level notes (default empty)
    workout_time: str | None = None  # Optional: time of workout in "HH:MM" 24-hour format (e.g. "09:30")
    session_id: str | None = None   # API session ID for delete/restore

