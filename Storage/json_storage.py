import json
import os
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Optional

from Models import DailyEntry, Task, Workout, Exercise, Set, JournalPage
from .interface import StorageInterface


class JSONStorage(StorageInterface):
    """
    JSON file-based storage implementation for DailyEntry objects.
    Stores entries in a single JSON file with date as keys.
    """
    
    def __init__(self, file_path: str = "data/lifelog.json") -> None:
        """
        Initialize JSON storage.
        
        Args:
            file_path: Path to JSON file for storage. Defaults to "data/lifelog.json"
        """
        self.file_path = Path(file_path)
        # Create parent directories if they don't exist
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        # Load existing data on initialization
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Create empty JSON file if it doesn't exist."""
        if not self.file_path.exists():
            with open(self.file_path, 'w') as f:
                json.dump({}, f)
    
    def _load_data(self) -> dict:
        """
        Load data from JSON file.
        
        Returns:
            Dictionary with date strings as keys and entry data as values
            
        Raises:
            json.JSONDecodeError: If JSON file is corrupted
            IOError: If file cannot be read
        """
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # File doesn't exist, return empty dict
            return {}
        except json.JSONDecodeError as e:
            # Log corruption details; avoid crashing the GUI on startup.
            print(
                f"Warning: corrupted JSON at {self.file_path}: {e.msg} "
                f"(line {e.lineno}, column {e.colno})"
            )
            return {}
    
    def _save_data(self, data: dict) -> None:
        """
        Save data to JSON file.
        
        Args:
            data: Dictionary to save
            
        Raises:
            IOError: If file cannot be written
        """
        # Write to temporary file first, then rename (atomic operation)
        temp_path = self.file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.file_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise IOError(f"Failed to save data to {self.file_path}: {e}")
    
    def _entry_to_dict(self, entry: DailyEntry) -> dict:
        """
        Convert DailyEntry dataclass to dictionary for JSON serialization.
        Handles nested dataclasses (Task, Workout, Exercise).
        
        Args:
            entry: DailyEntry object to convert
            
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return asdict(entry)
    
    def _dict_to_entry(self, data: dict) -> DailyEntry:
        """
        Convert dictionary to DailyEntry dataclass.
        Handles nested dataclasses (Task, Workout, Exercise, JournalPage).
        
        Backward Compatibility Migration:
        - If journal_pages exists and has content → Use pages
        - If journal_pages is empty but journal has content → Create "Main" page with that content
        - If both empty → Initialize empty list (empty "Main" page will be created by service/GUI when needed)
        - Old journal field is preserved in storage for backward compatibility
        
        Args:
            data: Dictionary containing entry data
            
        Returns:
            DailyEntry object reconstructed from dictionary
        """
        # Handle nested Task objects
        if 'tasks' in data and data['tasks'] is not None:
            tasks = []
            for task_data in data['tasks']:
                if isinstance(task_data, dict):
                    tasks.append(Task(**task_data))
                else:
                    tasks.append(task_data)
            data['tasks'] = tasks
        
        # Handle nested JournalPage objects and migration
        if 'journal_pages' in data and data['journal_pages'] is not None:
            journal_pages = []
            for page_data in data['journal_pages']:
                if isinstance(page_data, dict):
                    journal_pages.append(JournalPage(**page_data))
                else:
                    journal_pages.append(page_data)
            data['journal_pages'] = journal_pages
            
            # Migration: If journal_pages is empty but old journal field has content, migrate it
            if len(journal_pages) == 0 and 'journal' in data and data['journal']:
                # Migrate old journal string to new page format
                data['journal_pages'] = [
                    JournalPage(name="Main", content=data['journal'])
                ]
                # Keep old journal field for backward compatibility (don't clear it)
        elif 'journal_pages' not in data:
            # Migration: If journal_pages doesn't exist, check for old journal field
            if 'journal' in data and data['journal']:
                # Migrate old journal string to new page format
                data['journal_pages'] = [
                    JournalPage(name="Main", content=data['journal'])
                ]
                # Keep old journal field for backward compatibility (don't clear it)
            else:
                # No journal data, initialize empty list
                # Note: Empty "Main" page will be created by service layer when needed
                data['journal_pages'] = []
        
        # Handle nested Workout object
        if 'workout' in data and data['workout'] is not None:
            workout_data = data['workout']
            if isinstance(workout_data, dict):
                # Handle nested Exercise objects in workout
                if 'exercises' in workout_data and workout_data['exercises'] is not None:
                    exercises = []
                    for exercise_data in workout_data['exercises']:
                        if isinstance(exercise_data, dict):
                            # Handle nested Set objects in Exercise
                            if 'sets' in exercise_data and exercise_data['sets'] is not None:
                                sets_list = []
                                # Check if sets is a list (new format) or integer (old format)
                                if isinstance(exercise_data['sets'], list):
                                    # New format: list of Set objects
                                    for set_data in exercise_data['sets']:
                                        if isinstance(set_data, dict):
                                            sets_list.append(Set(**set_data))
                                        else:
                                            sets_list.append(set_data)
                                elif isinstance(exercise_data['sets'], int):
                                    # Old format: integer (number of sets) - can't convert without reps/weight data
                                    # Set to empty list or skip - old data doesn't have per-set info
                                    sets_list = []  # Empty list for old format exercises
                                exercise_data['sets'] = sets_list
                            
                            # Handle muscle_groups (may be missing in old data)
                            if 'muscle_groups' not in exercise_data:
                                exercise_data['muscle_groups'] = []  # Default to empty list for old data
                            
                            # Create and append Exercise object
                            exercises.append(Exercise(**exercise_data))
                        else:
                            exercises.append(exercise_data)
                    workout_data['exercises'] = exercises
                
                data['workout'] = Workout(**workout_data)
        
        # Handle rest_day and missed_day (default to False if missing for backward compatibility)
        if 'rest_day' not in data:
            data['rest_day'] = False
        if 'missed_day' not in data:
            data['missed_day'] = False
        
        # Create DailyEntry from dictionary
        # Only include fields that exist in DailyEntry dataclass
        entry_fields = {f.name for f in fields(DailyEntry)}
        filtered_data = {k: v for k, v in data.items() if k in entry_fields}
        
        return DailyEntry(**filtered_data)
    
    def _merge_entries(self, existing: DailyEntry, new: DailyEntry) -> DailyEntry:
        """
        Merge new entry data into existing entry.
        Preserves non-empty fields from existing entry, updates empty/None fields from new entry.
        Always updates date field if it differs.
        
        Strategy:
        - If new entry provides a value (not None/empty), use it
        - If new entry field is None/empty and existing has value, preserve existing
        - Exception: Always use date from new entry
        
        Args:
            existing: Existing DailyEntry object
            new: New DailyEntry object to merge
            
        Returns:
            Merged DailyEntry object
        """
        merged_data = {}
        
        # Always use the date from new entry
        merged_data['date'] = new.date
        
        # Journal: use new if it has non-whitespace content, otherwise keep existing
        # Note: Old journal field is kept for backward compatibility with older data formats
        merged_data['journal'] = new.journal if new.journal.strip() else existing.journal
        
        # Journal pages: use new if it has items, otherwise keep existing
        if new.journal_pages and len(new.journal_pages) > 0:
            merged_data['journal_pages'] = new.journal_pages
        else:
            merged_data['journal_pages'] = existing.journal_pages if existing.journal_pages is not None else []
        
        # Tasks: use new if it has items, otherwise keep existing
        if new.tasks and len(new.tasks) > 0:
            merged_data['tasks'] = new.tasks
        else:
            merged_data['tasks'] = existing.tasks if existing.tasks is not None else []
        
        # Sleep hours: use new if not None, otherwise keep existing
        merged_data['sleep_hours'] = new.sleep_hours if new.sleep_hours is not None else existing.sleep_hours
        
        # Workout: use new if not None, otherwise keep existing
        merged_data['workout'] = new.workout if new.workout is not None else existing.workout
        
        # Rest day and missed day: use new if True, otherwise keep existing
        # Note: These are mutually exclusive with workout (handled in DailyEntry.__post_init__)
        merged_data['rest_day'] = new.rest_day
        merged_data['missed_day'] = new.missed_day
        
        return DailyEntry(**merged_data)
    
    def get_entry(self, date: str) -> Optional[DailyEntry]:
        """
        Retrieve a single entry by date string.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            DailyEntry object if found, None otherwise
        """
        data = self._load_data()
        if date not in data:
            return None
        
        entry_data = data[date]
        return self._dict_to_entry(entry_data)
    
    def save_entry(self, entry: DailyEntry, merge: bool = True) -> None:
        """
        Save or update an entry.
        
        Args:
            entry: DailyEntry object to save
            merge: If True and entry exists, merge new data into existing
                   (don't overwrite non-empty fields). If False, replace entry.
        """
        data = self._load_data()
        date = entry.date
        
        if merge and date in data:
            # Merge with existing entry
            existing_entry = self._dict_to_entry(data[date])
            merged_entry = self._merge_entries(existing_entry, entry)
            data[date] = self._entry_to_dict(merged_entry)
        else:
            # Replace or insert new entry
            data[date] = self._entry_to_dict(entry)
        
        self._save_data(data)
    
    def get_entries_range(self, start_date: str, end_date: str) -> list[DailyEntry]:
        """
        Get all entries within a date range (inclusive).
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            
        Returns:
            List of DailyEntry objects sorted by date
        """
        data = self._load_data()
        entries = []
        
        for date_str, entry_data in data.items():
            # Check if date is within range (inclusive)
            if start_date <= date_str <= end_date:
                entry = self._dict_to_entry(entry_data)
                entries.append(entry)
        
        # Sort by date
        entries.sort(key=lambda e: e.date)
        return entries
    
    def delete_entry(self, date: str) -> bool:
        """
        Delete an entry by date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True if entry was deleted, False if not found
        """
        data = self._load_data()
        
        if date not in data:
            return False
        
        del data[date]
        self._save_data(data)
        return True
