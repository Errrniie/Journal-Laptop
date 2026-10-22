from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

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
        self._workout_library: Optional[list[Workout]] = None  # every API session, including same-day sessions
        self.last_created_session_id: str | None = None
        self._load_lock = RLock()
        self._pending_workouts_path = (
            Path(storage.file_path).with_name("pending_workout_requests.json")
            if getattr(storage, "file_path", None) else None
        )

    def _pending_workout_id(self, payload: dict) -> tuple[Optional[str], Optional[str]]:
        """Persist a request ID before posting so retries cannot duplicate a workout."""
        if self._pending_workouts_path is None:
            return None, "Workout request storage is unavailable"
        path = self._pending_workouts_path
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        try:
            pending = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if not isinstance(pending, dict):
                raise ValueError("pending request file is not an object")
            request_id = pending.get(fingerprint)
            if request_id:
                return request_id, None
            request_id = str(uuid4())
            pending[fingerprint] = request_id
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
            temp_path.replace(path)
            return request_id, None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return None, f"Could not persist workout request: {exc}"

    def _forget_pending_workout(self, payload: dict) -> None:
        if self._pending_workouts_path is None:
            return
        path = self._pending_workouts_path
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        try:
            pending = json.loads(path.read_text(encoding="utf-8"))
            pending.pop(fingerprint, None)
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
            temp_path.replace(path)
        except (OSError, ValueError, json.JSONDecodeError):
            # A retained key is safe: the server will return the existing workout.
            pass
    
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
                unit = str(getattr(set_obj, "unit", "lbs") or "lbs").casefold()
                weight_lbs = set_obj.weight * (2.2046226218 if unit in ("kg", "kgs") else 1)
                total_volume += set_obj.reps * weight_lbs
        
        return total_volume
    
    def load_workouts_from_api(self) -> tuple[bool, Optional[str]]:
        with self._load_lock:
            return self._load_workouts_from_api_locked()

    def _load_workouts_from_api_locked(self) -> tuple[bool, Optional[str]]:
        """
        Fetch GET /workouts/full into the complete session library and dated cache.
        Returns (True, None) on success, (False, error_message) on failure.
        """
        if not self.api_client or not self.api_client.api_key:
            return False, "API client not configured"
        raw, err = self.api_client.get_workouts_full()
        if err:
            return False, err
        next_cache: dict[str, Workout] = {}
        next_library: list[Workout] = []
        active_session_ids: set[str] = set()
        cache_errors: list[str] = []
        for session in raw or []:
            if not isinstance(session, dict):
                return False, "Workout API returned a malformed session"
            if session.get("type") != "workout":
                continue
            session_id = session.get("session_id") or session.get("id")
            if not session_id:
                return False, "Workout API returned a session without an ID"
            active_session_ids.add(str(session_id))
            start_time = session.get("start_time") or ""
            date_str = ""
            workout_time = None
            session_meta = session.get("metadata") or {}
            if not isinstance(session_meta, dict):
                return False, "Workout API returned malformed session metadata"
            if start_time:
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d")
                    workout_time = dt.strftime("%H:%M")
                    if isinstance(session_meta, dict):
                        offset = session_meta.get("utc_offset_minutes")
                        if isinstance(offset, int):
                            workout_time = (
                                dt.astimezone(timezone.utc) + timedelta(minutes=offset)
                            ).strftime("%H:%M")
                        local_date = session_meta.get("local_date")
                        if isinstance(local_date, str) and self._validate_date(local_date):
                            date_str = local_date
                except (ValueError, AttributeError, TypeError):
                    return False, f"Workout API returned invalid start time for {session_id}"
            if not date_str:
                return False, f"Workout API returned no date for {session_id}"
            notes = session.get("notes") or ""
            name = session.get("name") or ""
            exercises = []
            all_muscle_groups = set()
            edit_reason = ""
            for act in session.get("activities") or []:
                if not isinstance(act, dict):
                    return False, f"Workout API returned a malformed exercise for {session_id}"
                ex_name = act.get("name") or ""
                if act.get("type") != "exercise":
                    edit_reason = "This workout contains a non-exercise activity."
                meta = act.get("metadata") or {}
                if not isinstance(meta, dict):
                    return False, "Workout API returned malformed exercise metadata"
                muscle_groups = meta.get("muscle_groups") if isinstance(meta.get("muscle_groups"), list) else []
                if any(not isinstance(group, str) for group in muscle_groups):
                    return False, f"Workout API returned invalid muscle groups for {session_id}"
                sets_list = []
                for rec in act.get("records") or []:
                    try:
                        if not isinstance(rec, dict):
                            raise ValueError("record is not an object")
                        d = rec.get("data") or {}
                        if not isinstance(d, dict):
                            raise ValueError("record data is not an object")
                        if "sets" in d or "reps" not in d or not ({"weight", "weight_kg"} & d.keys()):
                            edit_reason = "This workout uses a legacy set format that the editor cannot safely replace."
                        reps = int(d.get("reps", 0))
                        weight_key = "weight" if "weight" in d else "weight_kg" if "weight_kg" in d else "weight"
                        weight = float(d.get(weight_key, 0))
                        if reps < 0 or not math.isfinite(weight):
                            raise ValueError("reps must be nonnegative and weight must be finite")
                        comment_key = "comment" if "comment" in d else "notes" if "notes" in d else "comment"
                        unit = str(d.get("unit") or ("kg" if weight_key == "weight_kg" else "lbs"))
                        sets_list.append(Set(
                            reps=reps,
                            weight=weight,
                            comment=str(d.get(comment_key) or ""),
                            unit=unit,
                            extra_data={key: value for key, value in d.items()
                                        if key not in {"reps", weight_key, comment_key, "unit"}},
                            comment_key=comment_key,
                            weight_key=weight_key,
                            record_time=rec.get("record_time"),
                        ))
                    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
                        return False, f"Workout API returned a malformed set for {session_id}: {exc}"
                if ex_name or sets_list:
                    ex = Exercise(
                        name=ex_name or "Exercise", sets=sets_list,
                        muscle_groups=muscle_groups, metadata=meta,
                    )
                    exercises.append(ex)
                    all_muscle_groups.update(muscle_groups)
            duration_minutes = session_meta.get("duration_minutes", 0)
            if not isinstance(duration_minutes, int) or duration_minutes < 0:
                return False, f"Workout API returned invalid duration for {date_str}"
            workout = Workout(
                date=date_str,
                muscle_groups=list(all_muscle_groups),
                exercises=exercises,
                duration_minutes=duration_minutes,
                notes=notes,
                workout_time=workout_time,
                session_id=session_id,
                revision=session.get("revision"),
                name=name,
                edit_reason=edit_reason,
                metadata=session_meta,
                source=session.get("source") or "",
                start_time=start_time,
            )
            next_library.append(workout)
            next_cache.setdefault(date_str, workout)

        # A locally recorded workout has no server ID. Do not replace it with
        # a phone workout on the same day before the two can be reconciled.
        try:
            for date_str in next_cache:
                existing = self.storage.get_entry(date_str)
                if existing and existing.workout and not existing.workout.session_id:
                    return False, f"Local and remote workouts both exist on {date_str}"
        except Exception as exc:
            return False, f"Could not inspect local workouts: {exc}"

        # Only write local analytics after the whole API response is usable.
        for date_str, workout in next_cache.items():
            try:
                entry = self._get_or_create_entry(date_str)
                entry.workout = workout
                if not self._save_entry(entry):
                    cache_errors.append(f"Could not cache workout for {date_str}")
            except Exception as exc:
                cache_errors.append(f"Could not cache workout for {date_str}: {exc}")

        # A successful complete API read can explicitly reconcile old remote
        # sessions from the local analytics cache. Local-only workouts stay put.
        try:
            for entry in self.storage.get_entries_range("0001-01-01", "9999-12-31"):
                cached = entry.workout
                if cached and cached.session_id and str(cached.session_id) not in active_session_ids:
                    entry.workout = next_cache.get(entry.date)
                    self.storage.save_entry(entry, merge=False)
        except Exception as exc:
            cache_errors.append(f"Could not reconcile local workout cache: {exc}")
        if cache_errors:
            return False, "; ".join(cache_errors[:3])
        self._workout_cache = next_cache
        self._workout_library = next_library
        return True, None
    
    def invalidate_workout_cache(self) -> None:
        """Clear API workout cache so next get_workout refetches."""
        with self._load_lock:
            self._workout_cache = None
            self._workout_library = None
    
    def get_workout(self, date: str, session_id: str | None = None) -> Optional[Workout]:
        """
        Get workout for a date. When api_client is set, uses API cache (refetches if cache empty).
        """
        if not self._validate_date(date):
            return None
        try:
            if self.api_client and self.api_client.api_key:
                if self._workout_cache is None:
                    self.load_workouts_from_api()
                if session_id is not None:
                    return next((workout for workout in self._workout_library or []
                                 if workout.date == date and str(workout.session_id) == str(session_id)), None)
                if self._workout_cache is not None:
                    remote = self._workout_cache.get(date)
                    if remote is not None:
                        return remote
            entry = self.storage.get_entry(date)
            if entry is None or entry.workout is None:
                return None
            if (self.api_client and self.api_client.api_key and entry.workout.session_id
                    and self._workout_cache is not None):
                # A previously cached remote workout is absent from the latest
                # active response; do not revive it through the local fallback.
                return None
            return entry.workout
        except Exception:
            return None
    
    def create_workout(self, date: str, muscle_groups: list[str], exercises: list[Exercise], duration_minutes: int = 0, notes: str = "", workout_time: str | None = None, name: str = "") -> bool:
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
            workout_time=workout_time if workout_time else None,
            name=name,
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
        name: str = "",
    ) -> tuple[bool, Optional[str]]:
        """Create a complete workout atomically with a durable retry ID."""
        if not self.api_client or not self.api_client.api_key:
            return False, "API client not configured"
        if not self._validate_date(date):
            return False, "Invalid date"
        try:
            existing = self.storage.get_entry(date)
        except Exception as exc:
            return False, f"Could not inspect local workout: {exc}"
        if existing and existing.workout and not existing.workout.session_id:
            return False, "A local-only workout already exists on this date"
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
        try:
            local_start = datetime.strptime(
                f"{date} {workout_time or '12:00'}", "%Y-%m-%d %H:%M"
            ).astimezone()
        except ValueError:
            return False, "Invalid workout date or time"
        name = (name or notes or "Workout")[:200]
        payload = {
            "start_time": local_start.isoformat(),
            "name": name,
            "notes": notes,
            "duration_minutes": duration_minutes,
            "source": "desktop",
            "exercises": [
                {
                    "name": exercise.name,
                    "muscle_groups": getattr(exercise, "muscle_groups", []) or [],
                    "sets": [
                        {"reps": set_obj.reps, "weight": set_obj.weight,
                         "comment": getattr(set_obj, "comment", "") or ""}
                        for set_obj in exercise.sets
                    ],
                }
                for exercise in exercises
            ],
        }
        request_id, id_error = self._pending_workout_id(payload)
        if id_error:
            return False, id_error
        response, create_error = self.api_client.create_workout(
            {**payload, "client_request_id": request_id}
        )
        if create_error or not response or not response.get("session_id"):
            return False, create_error or "Workout create response had no session ID"
        self.invalidate_workout_cache()
        loaded, load_error = self.load_workouts_from_api()
        if not loaded:
            return False, load_error or "Workout was saved, but refresh failed; retry to verify it"
        saved = next((workout for workout in self._workout_library or []
                      if str(workout.session_id) == str(response["session_id"])), None)
        if not saved or str(saved.session_id) != str(response["session_id"]):
            return False, "Workout was saved, but the server response did not include it on refresh"
        self._forget_pending_workout(payload)
        self.last_created_session_id = str(response["session_id"])
        return True, None

    def update_workout_via_api(
        self, date: str, session_id: str, expected_revision: int,
        muscle_groups: list[str], exercises: list[Exercise],
        duration_minutes: int = 0, notes: str = "",
        workout_time: Optional[str] = None, name: str = "",
    ) -> tuple[bool, Optional[str]]:
        """Save edits to a server workout without replacing a newer phone edit."""
        if not self.api_client or not self.api_client.api_key:
            return False, "API client not configured"
        workout = Workout(
            date=date, muscle_groups=muscle_groups, exercises=exercises,
            duration_minutes=duration_minutes, notes=notes,
            workout_time=workout_time,
        )
        valid, error = self.validate_workout(workout)
        if not valid:
            return False, error
        try:
            original = self.get_workout(date, session_id)
            if original and original.start_time and workout_time == original.workout_time:
                local_start = datetime.fromisoformat(original.start_time.replace("Z", "+00:00"))
                offset = (original.metadata or {}).get("utc_offset_minutes")
                if isinstance(offset, int):
                    local_start = local_start.astimezone(timezone(timedelta(minutes=offset)))
            else:
                local_start = datetime.strptime(
                    f"{date} {workout_time or '12:00'}", "%Y-%m-%d %H:%M"
                )
                offset = (original.metadata or {}).get("utc_offset_minutes") if original else None
                if isinstance(offset, int):
                    local_start = local_start.replace(tzinfo=timezone(timedelta(minutes=offset)))
                else:
                    local_start = local_start.astimezone()
        except (ValueError, TypeError):
            return False, "Invalid workout date or time"
        payload = {
            "expected_revision": expected_revision,
            "start_time": local_start.isoformat(),
            "local_date": date,
            "name": (name or notes or "Workout")[:200],
            "notes": notes,
            "duration_minutes": duration_minutes,
            "exercises": [
                {
                    "name": exercise.name,
                    "muscle_groups": exercise.muscle_groups,
                    "metadata": exercise.metadata or {},
                    "sets": [
                        {"reps": set_obj.reps, "weight": set_obj.weight,
                         "comment": set_obj.comment, "unit": set_obj.unit,
                         "extra_data": set_obj.extra_data or {},
                         "comment_key": set_obj.comment_key,
                         "weight_key": set_obj.weight_key,
                         "record_time": set_obj.record_time}
                        for set_obj in exercise.sets
                    ],
                }
                for exercise in exercises
            ],
        }
        response, update_error = self.api_client.update_workout(session_id, payload)
        if update_error:
            return False, update_error
        if (not response or str(response.get("session_id")) != str(session_id)
                or response.get("revision") != expected_revision + 1):
            return False, "Server response did not confirm the workout update"
        loaded, load_error = self.load_workouts_from_api()
        if not loaded:
            return False, f"Workout saved, but refresh failed: {load_error or 'unknown error'}"
        return True, None
    
    def delete_session_and_refetch(self, session_id: str) -> tuple[bool, Optional[str]]:
        """DELETE /sessions/{id}, then refetch workouts. Returns (True, None) or (False, error)."""
        if not self.api_client or not self.api_client.api_key:
            return False, "API client not configured"
        ok, err = self.api_client.delete_session(session_id)
        if not ok:
            return False, err
        self.invalidate_workout_cache()
        self.load_workouts_from_api()
        return True, None
    
    def restore_session_and_refetch(self, session_id: str) -> tuple[bool, Optional[str]]:
        """POST /sessions/{id}/restore, then refetch workouts. Returns (True, None) or (False, error)."""
        if not self.api_client or not self.api_client.api_key:
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

            if "workout_time" in kwargs:
                workout.workout_time = kwargs["workout_time"] or None

            if "name" in kwargs:
                workout.name = kwargs["name"] or ""
            
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
            
            remote_missing = (
                self.api_client and self.api_client.api_key
                and self._workout_cache is not None
                and entry.workout is not None and entry.workout.session_id
                and date not in self._workout_cache
            )
            if entry.workout is not None and not remote_missing:
                return "workout"
            elif entry.rest_day:
                return "rest"
            elif entry.missed_day:
                return "missed"
            else:
                return None
        except Exception:
            return None
