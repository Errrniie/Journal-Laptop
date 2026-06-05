from dataclasses import dataclass, field
from .Task import Task
from .Workout import Workout
from .Journal_Page import JournalPage

@dataclass
class DailyEntry:
    date: str                           # Date in "YYYY-MM-DD" format
    journal: str = ""                   # Optional: journal entry text (default empty) - kept for backward compatibility
    journal_pages: list[JournalPage] = field(default_factory=list)  # Optional: list of JournalPage objects (default empty)
    tasks: list[Task] = None            # Optional: list of Task objects (default None)
    sleep_hours: float = None           # Optional: hours of sleep (default None)
    workout: Workout = None             # Optional: Workout object (default None)
    rest_day: bool = False              # Optional: True if this is a rest day (default False)
    missed_day: bool = False            # Optional: True if this is a missed workout day (default False)
    
    def __post_init__(self):
        # Ensure tasks is initialized as empty list if None
        if self.tasks is None:
            self.tasks = []
        
        # Ensure journal_pages is initialized as empty list if None
        if self.journal_pages is None:
            self.journal_pages = []
        
        # Validation: At most one of {workout, rest_day, missed_day} should be True
        # If workout exists, rest_day and missed_day should be False
        if self.workout is not None:
            self.rest_day = False
            self.missed_day = False
        # If rest_day is True, missed_day should be False
        elif self.rest_day and self.missed_day:
            self.missed_day = False

