from datetime import datetime
from typing import TYPE_CHECKING, Optional

from Models import DailyEntry, Workout, Exercise, Set

if TYPE_CHECKING:
    from Storage import StorageInterface
    from features.API_Client import APIClient


class WorkoutService:
    """
    Service for managing workout entries with exercises, muscle groups, and validation.
    When api_client is set, workout list is loaded from API and cached; otherwise uses storage.
    """
    
    def __init__(self, storage: "StorageInterface", api_client: Optional["APIClient"] = None) -> None:
        """
        Initialize Workout Service.
        
        Args:
            storage: StorageInterface instance for data persistence
            api_client: Optional APIClient for loading workouts from API (backend as source of truth)
        """
        self.storage = storage
        self.api_client = api_client
        self._workout_cache: Optional[dict[str, Workout]] = None  # date -> Workout
    
    def _validate_date(self, date: str) -> bool:
        """
        Validate date format is "YYYY-MM-DD".
        
        Args:
            date: Date string to validate
            
        Returns:
            True if date is valid, False otherwise
        """
        try:
            datetime.strptime(date, "%Y-%m-%d")
            return True
        except (ValueError, TypeError):
            return False
    
    def _get_or_create_entry(self, date: str) -> DailyEntry:
        """
        Load existing DailyEntry for a date or create a new one.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            DailyEntry object (existing or newly created)
        """
        entry = self.storage.get_entry(date)
        if entry is None:
            entry = DailyEntry(date=date)
        return entry
    
    def _save_entry(self, entry: DailyEntry) -> bool:
        """
        Save entry to storage with merge enabled.
        
        Args:
            entry: DailyEntry object to save
            
        Returns:
            True on success, False on error
        """
        try:
            self.storage.save_entry(entry, merge=True)
            return True
        except Exception:
            # Error handling - could add logging here later
            return False
    
    def _normalize_muscle_groups(self, muscle_groups: list[str]) -> list[str]:
        """
        Normalize muscle groups list: remove duplicates, trim whitespace, filter empty strings.
        
        Args:
            muscle_groups: List of muscle group names
            
        Returns:
            Normalized list of muscle groups (no duplicates, trimmed, no empty strings)
        """
        if not muscle_groups:
            return []
        
        # Normalize: trim, filter empty, remove duplicates (case-insensitive)
        normalized = []
        seen = set()
        
        for group in muscle_groups:
            if group:
                trimmed = group.strip()
                if trimmed:
                    # Case-insensitive duplicate check
                    lower = trimmed.lower()
                    if lower not in seen:
                        seen.add(lower)
                        normalized.append(trimmed)
        
        return normalized
    
    def validate_exercise(self, exercise: Exercise) -> tuple[bool, str]:
        """
        Validate exercise data.
        
        Args:
            exercise: Exercise object to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            is_valid is True if exercise is valid, False otherwise
            error_message is empty string if valid, otherwise contains error description
        """
        if not exercise:
            return False, "Exercise cannot be None"
        
        # Validate name
        if not exercise.name or not exercise.name.strip():
            return False, "Exercise name cannot be empty"
        
        # Validate muscle groups
        exercise_muscle_groups = getattr(exercise, 'muscle_groups', None)
        if exercise_muscle_groups is None:
            exercise_muscle_groups = []
        if not isinstance(exercise_muscle_groups, list):
            return False, "Exercise muscle_groups must be a list"
        if len(exercise_muscle_groups) == 0:
            return False, "Exercise must have at least one muscle group"
        
        # Validate sets list
        if not isinstance(exercise.sets, list):
            return False, "Exercise sets must be a list"
        
        if len(exercise.sets) == 0:
            return False, "Exercise must have at least one set"
        
        # Validate each set
        for i, set_obj in enumerate(exercise.sets):
            if not isinstance(set_obj, Set):
                return False, f"Set {i + 1} is not a valid Set object"
            
            # Validate reps
            if not isinstance(set_obj.reps, int) or set_obj.reps <= 0:
                return False, f"Set {i + 1}: Reps must be a positive integer"
            
            # Validate weight
            if not isinstance(set_obj.weight, (int, float)) or set_obj.weight < 0:
                return False, f"Set {i + 1}: Weight must be a non-negative number"
        
        return True, ""
    
    def validate_workout(self, workout: Workout) -> tuple[bool, str]:
        """
        Validate workout data.
        
        Args:
            workout: Workout object to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            is_valid is True if workout is valid, False otherwise
            error_message is empty string if valid, otherwise contains error description
        """
        if not workout:
            return False, "Workout cannot be None"
        
        # Validate date
        if not self._validate_date(workout.date):
            return False, "Workout date must be in YYYY-MM-DD format"
        
        # Validate exercises
        if not workout.exercises or len(workout.exercises) == 0:
            return False, "Workout must have at least one exercise"
        
        # Note: Muscle groups are now validated at the exercise level
        # Workout-level muscle_groups is optional (can be derived from exercises)
        
        # Validate each exercise
        for i, exercise in enumerate(workout.exercises):
            is_valid, error_msg = self.validate_exercise(exercise)
            if not is_valid:
                return False, f"Exercise {i + 1}: {error_msg}"
        
        return True, ""
    
    def calculate_volume(self, workout: Workout) -> float:
        """
        Calculate total volume for a workout.
        Volume = sum of (reps × weight) for all sets in all exercises.
        
        Args:
            workout: Workout object to calculate volume for
            
        Returns:
            Total volume as float, 0.0 if workout is None or has no exercises
        """
        if not workout or not workout.exercises:
            return 0.0
        
        total_volume = 0.0
        for exercise in workout.exercises:
            for set_obj in exercise.sets:
                total_volume += set_obj.reps * set_obj.weight
        
        return total_volume
    
    def load_workouts_from_api(self) -> tuple[bool, Optional[str]]:
        """
        Fetch GET /workouts/full and fill in-memory cache (date -> Workout).
        Returns (True, None) on success, (False, error_message) on failure.
        """
        if not self.api_client:
            return False, "API client not configured"
        raw, err = self.api_client.get_workouts_full()
        if err:
            return False, err
        self._workout_cache = {}
        for session in raw or []:
            if session.get("type") != "workout":
                continue
            session_id = session.get("session_id") or session.get("id")
            start_time = session.get("start_time") or ""
            date_str = ""
            workout_time = None
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d")
                    workout_time = dt.strftime("%H:%M")
                except (ValueError, AttributeError):
                    pass
            if not date_str:
                continue
            notes = session.get("notes") or ""
            name = session.get("name") or ""
            if name and not notes:
                notes = name
            exercises = []
            all_muscle_groups = set()
            for act in session.get("activities") or []:
                ex_name = act.get("name") or ""
                meta = act.get("metadata") or {}
                muscle_groups = meta.get("muscle_groups") if isinstance(meta.get("muscle_groups"), list) else []
                sets_list = []
                for rec in act.get("records") or []:
                    d = rec.get("data") or {}
                    sets_list.append(Set(
                        reps=int(d.get("reps", 0)),
                        weight=float(d.get("weight", 0)),
                        comment=str(d.get("comment", "")),
                    ))
                if ex_name or sets_list:
                    ex = Exercise(name=ex_name or "Exercise", sets=sets_list, muscle_groups=muscle_groups)
                    exercises.append(ex)
                    all_muscle_groups.update(muscle_groups)
            workout = Workout(
                date=date_str,
                muscle_groups=list(all_muscle_groups),
                exercises=exercises,
                duration_minutes=0,
                notes=notes,
                workout_time=workout_time,
                session_id=session_id,
            )
            self._workout_cache[date_str] = workout
            # Write through to storage so analytics and get_entries_range see API data
            try:
                entry = self._get_or_create_entry(date_str)
                entry.workout = workout
                self._save_entry(entry)
            except Exception:
                pass
        return True, None
    
    def invalidate_workout_cache(self) -> None:
        """Clear API workout cache so next get_workout refetches."""
        self._workout_cache = None
    
    def get_workout(self, date: str) -> Optional[Workout]:
        """
        Get workout for a date. When api_client is set, uses API cache (refetches if cache empty).
        """
        if not self._validate_date(date):
            return None
        try:
            if self.api_client:
                if self._workout_cache is None:
                    self.load_workouts_from_api()
                if self._workout_cache is not None:
                    return self._workout_cache.get(date)
            entry = self.storage.get_entry(date)
            if entry is None or entry.workout is None:
                return None
            return entry.workout
        except Exception:
            return None
    
    def create_workout(self, date: str, muscle_groups: list[str], exercises: list[Exercise], duration_minutes: int = 0, notes: str = "", workout_time: str | None = None) -> bool:
        """
        Create new workout for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            muscle_groups: List of muscle group names
            exercises: List of Exercise objects
            duration_minutes: Workout duration in minutes, defaults to 0
            notes: Optional workout notes, defaults to empty string
            workout_time: Optional workout time in "HH:MM" 24-hour format (e.g. "09:30"), defaults to None
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        # Normalize muscle groups
        normalized_groups = self._normalize_muscle_groups(muscle_groups)
        
        # Create workout object
        workout = Workout(
            date=date,
            muscle_groups=normalized_groups,
            exercises=exercises if exercises else [],
            duration_minutes=duration_minutes if duration_minutes >= 0 else 0,
            notes=notes if notes else "",
            workout_time=workout_time if workout_time else None
        )
        
        # Validate workout
        is_valid, error_msg = self.validate_workout(workout)
        if not is_valid:
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            entry.workout = workout
            # Clear rest_day and missed_day when creating a workout
            entry.rest_day = False
            entry.missed_day = False
            return self._save_entry(entry)
        except Exception:
            return False
    
    def create_workout_via_api(
        self,
        date: str,
        muscle_groups: list[str],
        exercises: list[Exercise],
        duration_minutes: int = 0,
        notes: str = "",
        workout_time: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Create workout via API: POST /sessions, then POST /activities per exercise,
        then POST /records per set. Refreshes workout cache on success.
        Returns (True, None) or (False, error_message).
        """
        if not self.api_client:
            return False, "API client not configured"
        if not self._validate_date(date):
            return False, "Invalid date"
        workout = Workout(
            date=date,
            muscle_groups=muscle_groups or [],
            exercises=exercises or [],
            duration_minutes=duration_minutes,
            notes=notes,
            workout_time=workout_time,
        )
        is_valid, err = self.validate_workout(workout)
        if not is_valid:
            return False, err or "Validation failed"
        # Build start_time ISO (date + time or noon)
        hour, minute = 12, 0
        if workout_time:
            parts = workout_time.split(":")
            if len(parts) >= 2:
                try:
                    hour, minute = int(parts[0]), int(parts[1])
                except ValueError:
                    pass
        start_time = f"{date}T{hour:02d}:{minute:02d}:00.000Z"
        name = (notes or "Workout")[:200]
        sess, err = self.api_client.create_session(
            type="workout", name=name, start_time=start_time, notes=notes
        )
        if err or not sess:
            return False, err or "Failed to create session"
        session_id = sess.get("session_id") or sess.get("id")
        if not session_id:
            return False, "Session response missing session_id"
        for exercise in exercises:
            act, act_err = self.api_client.create_activity(
                session_id=session_id,
                type="exercise",
                name=exercise.name,
                metadata={"muscle_groups": getattr(exercise, "muscle_groups", []) or []},
            )
            if act_err or not act:
                return False, act_err or "Failed to create activity"
            activity_id = act.get("activity_id") or act.get("id")
            if not activity_id:
                return False, "Activity response missing activity_id"
            for set_obj in exercise.sets:
                data = {"reps": set_obj.reps, "weight": set_obj.weight, "comment": getattr(set_obj, "comment", "") or ""}
                _, rec_err = self.api_client.create_record(activity_id=activity_id, data=data)
                if rec_err:
                    return False, rec_err or "Failed to create record"
        self.invalidate_workout_cache()
        self.load_workouts_from_api()
        return True, None
    
    def delete_session_and_refetch(self, session_id: str) -> tuple[bool, Optional[str]]:
        """DELETE /sessions/{id}, then refetch workouts. Returns (True, None) or (False, error)."""
        if not self.api_client:
            return False, "API client not configured"
        ok, err = self.api_client.delete_session(session_id)
        if not ok:
            return False, err
        self.invalidate_workout_cache()
        self.load_workouts_from_api()
        return True, None
    
    def restore_session_and_refetch(self, session_id: str) -> tuple[bool, Optional[str]]:
        """POST /sessions/{id}/restore, then refetch workouts. Returns (True, None) or (False, error)."""
        if not self.api_client:
            return False, "API client not configured"
        ok, err = self.api_client.restore_session(session_id)
        if not ok:
            return False, err
        self.invalidate_workout_cache()
        self.load_workouts_from_api()
        return True, None
    
    def update_workout(self, date: str, **kwargs) -> bool:
        """
        Update workout fields for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            **kwargs: Fields to update (muscle_groups, exercises, duration_minutes, notes)
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Get existing workout or create new one
            if entry.workout is None:
                # Create new workout if none exists
                entry.workout = Workout(
                    date=date,
                    muscle_groups=[],
                    exercises=[],
                    duration_minutes=0,
                    notes=""
                )
            
            workout = entry.workout
            
            # Update fields from kwargs
            if "muscle_groups" in kwargs:
                normalized = self._normalize_muscle_groups(kwargs["muscle_groups"])
                workout.muscle_groups = normalized
            
            if "exercises" in kwargs:
                workout.exercises = kwargs["exercises"] if kwargs["exercises"] else []
            
            if "duration_minutes" in kwargs:
                duration = kwargs["duration_minutes"]
                workout.duration_minutes = duration if duration >= 0 else 0
            
            if "notes" in kwargs:
                workout.notes = kwargs["notes"] if kwargs["notes"] else ""
            
            # Validate updated workout
            is_valid, error_msg = self.validate_workout(workout)
            if not is_valid:
                return False
            
            # Clear rest_day and missed_day when updating a workout
            entry.rest_day = False
            entry.missed_day = False
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def add_exercise(self, date: str, exercise: Exercise) -> bool:
        """
        Add exercise to existing workout.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            exercise: Exercise object to add
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        # Validate exercise
        is_valid, error_msg = self.validate_exercise(exercise)
        if not is_valid:
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Create workout if it doesn't exist
            if entry.workout is None:
                entry.workout = Workout(
                    date=date,
                    muscle_groups=[],
                    exercises=[],
                    duration_minutes=0,
                    notes=""
                )
            
            entry.workout.exercises.append(exercise)
            
            # Validate workout after adding exercise
            is_valid, error_msg = self.validate_workout(entry.workout)
            if not is_valid:
                # Rollback: remove the exercise we just added
                entry.workout.exercises.pop()
                return False
            
            # Clear rest_day and missed_day when modifying a workout
            entry.rest_day = False
            entry.missed_day = False
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def remove_exercise(self, date: str, exercise_index: int) -> bool:
        """
        Remove exercise by index from workout.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            exercise_index: Index of the exercise to remove (0-based)
            
        Returns:
            True on success, False on error or invalid input
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            if entry.workout is None or not entry.workout.exercises:
                return False
            
            # Validate exercise_index bounds
            if exercise_index < 0 or exercise_index >= len(entry.workout.exercises):
                return False
            
            # Remove exercise
            entry.workout.exercises.pop(exercise_index)
            
            # If no exercises remain, we might want to delete the workout
            # But per the plan, we'll keep it and let validation handle it
            # Actually, if there are no exercises, the workout becomes invalid
            # So we should either delete it or keep it but it won't pass validation
            # For now, we'll keep it and let the user decide
            
            # Clear rest_day and missed_day when modifying a workout
            entry.rest_day = False
            entry.missed_day = False
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def update_exercise(self, date: str, exercise_index: int, **kwargs) -> bool:
        """
        Update exercise fields for an exercise at the given index.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            exercise_index: Index of the exercise to update (0-based)
            **kwargs: Fields to update (name, sets)
                - name: Exercise name (str)
                - sets: List of Set objects (list[Set])
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            if entry.workout is None or not entry.workout.exercises:
                return False
            
            # Validate exercise_index bounds
            if exercise_index < 0 or exercise_index >= len(entry.workout.exercises):
                return False
            
            exercise = entry.workout.exercises[exercise_index]
            
            # Update fields from kwargs
            if "name" in kwargs:
                new_name = kwargs["name"]
                if new_name and new_name.strip():
                    exercise.name = new_name.strip()
                else:
                    return False  # Name cannot be empty
            
            if "sets" in kwargs:
                # Update sets list - should be a list of Set objects
                sets = kwargs["sets"]
                if isinstance(sets, list):
                    # Validate all sets are Set objects
                    for set_obj in sets:
                        if not isinstance(set_obj, Set):
                            return False  # Invalid set object
                    exercise.sets = sets
                else:
                    return False  # Sets must be a list
            
            # Validate updated exercise
            is_valid, error_msg = self.validate_exercise(exercise)
            if not is_valid:
                return False
            
            # Clear rest_day and missed_day when modifying a workout
            entry.rest_day = False
            entry.missed_day = False
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def delete_workout(self, date: str) -> bool:
        """
        Remove workout for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or invalid date
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            if entry.workout is None:
                return False  # No workout to delete
            
            entry.workout = None
            return self._save_entry(entry)
        except Exception:
            return False
    
    def get_muscle_groups(self, date: str) -> list[str]:
        """
        Get list of muscle groups for a workout.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            List of muscle group names, empty list if no workout or invalid date
        """
        if not self._validate_date(date):
            return []
        
        try:
            entry = self.storage.get_entry(date)
            if entry is None or entry.workout is None:
                return []
            return entry.workout.muscle_groups.copy()  # Return a copy
        except Exception:
            return []
    
    def set_rest_day(self, date: str) -> bool:
        """
        Set a date as a rest day.
        Clears any workout and missed_day flag for that date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            # Set rest_day, clear workout and missed_day
            entry.rest_day = True
            entry.missed_day = False
            entry.workout = None
            return self._save_entry(entry)
        except Exception:
            return False
    
    def set_missed_day(self, date: str) -> bool:
        """
        Set a date as a missed workout day.
        Clears any workout and rest_day flag for that date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            # Set missed_day, clear workout and rest_day
            entry.missed_day = True
            entry.rest_day = False
            entry.workout = None
            return self._save_entry(entry)
        except Exception:
            return False
    
    def clear_rest_missed(self, date: str) -> bool:
        """
        Clear rest_day and missed_day flags for a date.
        Does not affect workout data.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or validation failure
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            # Clear both flags
            entry.rest_day = False
            entry.missed_day = False
            return self._save_entry(entry)
        except Exception:
            return False
    
    def get_day_type(self, date: str) -> Optional[str]:
        """
        Get the type of day for a given date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            "workout" if there's a workout, "rest" if rest_day is True,
            "missed" if missed_day is True, or None if none of the above
        """
        if not self._validate_date(date):
            return None
        
        try:
            entry = self.storage.get_entry(date)
            if entry is None:
                return None
            
            if entry.workout is not None:
                return "workout"
            elif entry.rest_day:
                return "rest"
            elif entry.missed_day:
                return "missed"
            else:
                return None
        except Exception:
            return None
