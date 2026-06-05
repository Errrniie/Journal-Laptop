from datetime import datetime
from typing import TYPE_CHECKING

from Models import DailyEntry, Task

if TYPE_CHECKING:
    from Storage import StorageInterface


class TaskService:
    """
    Service for managing task checklist operations for daily entries.
    Provides business logic for task CRUD operations on top of the storage layer.
    """
    
    def __init__(self, storage: "StorageInterface") -> None:
        """
        Initialize Task Service.
        
        Args:
            storage: StorageInterface instance for data persistence
        """
        self.storage = storage
    
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
    
    def _validate_priority(self, priority: int) -> bool:
        """
        Validate priority is in range 1-5.
        
        Args:
            priority: Priority level to validate
            
        Returns:
            True if priority is valid (1-5), False otherwise
        """
        return isinstance(priority, int) and 1 <= priority <= 5
    
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
        # Ensure tasks list is initialized
        if entry.tasks is None:
            entry.tasks = []
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
    
    def get_tasks(self, date: str) -> list[Task]:
        """
        Get all tasks for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            List of Task objects, empty list if none found or invalid date
        """
        if not self._validate_date(date):
            return []
        
        try:
            entry = self.storage.get_entry(date)
            if entry is None or entry.tasks is None:
                return []
            return entry.tasks.copy()  # Return a copy to prevent external modification
        except Exception:
            return []
    
    def add_task(self, date: str, name: str, priority: int = 1, due_date: str = None, notes: str = "") -> bool:
        """
        Add a new task to a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            name: Task name (required)
            priority: Priority level (1-5), defaults to 1
            due_date: Due date in "YYYY-MM-DD" format, optional
            notes: Optional notes for the task, defaults to empty string
            
        Returns:
            True on success, False on error or invalid input
        """
        if not self._validate_date(date):
            return False
        
        # Validate priority
        if not self._validate_priority(priority):
            return False  # Invalid priority
        
        # Validate name is not empty
        if not name or not name.strip():
            return False
        
        # Validate due_date format if provided
        if due_date is not None and not self._validate_date(due_date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Create new task
            new_task = Task(
                name=name.strip(),
                completed=False,
                Priority=priority,
                Due_Date=due_date if due_date else "",
                Notes=notes if notes else ""
            )
            
            entry.tasks.append(new_task)
            return self._save_entry(entry)
        except Exception:
            return False
    
    def update_task(self, date: str, task_index: int, **kwargs) -> bool:
        """
        Update task fields for a task at the given index.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            task_index: Index of the task to update (0-based)
            **kwargs: Fields to update (name, completed, priority, due_date, notes)
            
        Returns:
            True on success, False on error or invalid input
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Validate task_index bounds
            if task_index < 0 or task_index >= len(entry.tasks):
                return False
            
            task = entry.tasks[task_index]
            
            # Update fields from kwargs
            if "name" in kwargs:
                new_name = kwargs["name"]
                if new_name and new_name.strip():
                    task.name = new_name.strip()
                else:
                    return False  # Name cannot be empty
            
            if "completed" in kwargs:
                task.completed = bool(kwargs["completed"])
            
            if "priority" in kwargs:
                new_priority = kwargs["priority"]
                if self._validate_priority(new_priority):
                    task.Priority = new_priority
                else:
                    return False  # Invalid priority
            
            if "due_date" in kwargs:
                due_date = kwargs["due_date"]
                if due_date is None:
                    task.Due_Date = ""
                elif self._validate_date(due_date):
                    task.Due_Date = due_date
                else:
                    return False  # Invalid date format
            
            if "notes" in kwargs:
                task.Notes = kwargs["notes"] if kwargs["notes"] else ""
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def delete_task(self, date: str, task_index: int) -> bool:
        """
        Remove a task by index.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            task_index: Index of the task to delete (0-based)
            
        Returns:
            True on success, False on error or invalid input
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Validate task_index bounds
            if task_index < 0 or task_index >= len(entry.tasks):
                return False
            
            # Remove task at index
            entry.tasks.pop(task_index)
            return self._save_entry(entry)
        except Exception:
            return False
    
    def toggle_task(self, date: str, task_index: int) -> bool:
        """
        Toggle task completion status.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            task_index: Index of the task to toggle (0-based)
            
        Returns:
            True on success, False on error or invalid input
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Validate task_index bounds
            if task_index < 0 or task_index >= len(entry.tasks):
                return False
            
            # Toggle completion status
            entry.tasks[task_index].completed = not entry.tasks[task_index].completed
            return self._save_entry(entry)
        except Exception:
            return False
    
    def clear_completed_tasks(self, date: str) -> bool:
        """
        Remove all completed tasks for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or invalid date
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Filter out completed tasks
            entry.tasks = [task for task in entry.tasks if not task.completed]
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def save_tasks_with_sync_info(self, date: str, tasks: list[Task]) -> bool:
        """
        Save tasks preserving API tracking information.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            tasks: List of Task objects to save (may include API tracking fields)
            
        Returns:
            True on success, False on error or invalid date
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            entry.tasks = tasks
            return self._save_entry(entry)
        except Exception:
            return False