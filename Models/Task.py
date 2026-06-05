from dataclasses import dataclass
from typing import Optional

@dataclass
class Task:
    name: str              # Task name (e.g., "Exercise", "Read")
    completed: bool        # Completion status (True/False)
    Priority: int          # Priority level (1-5)
    Due_Date: str          # Due date in "YYYY-MM-DD" format
    Notes: str = ""        # Optional notes (default empty string)
    activity_id: Optional[str] = None  # API activity UUID for tracking
    session_id: Optional[str] = None   # API session UUID
    last_synced: Optional[str] = None  # ISO timestamp of last sync

    def __post_init__(self):
        # Ensure Priority is set to 1 if not provided
        if self.Priority is None:
            self.Priority = 1
        if self.Due_Date is None:
            self.Due_Date = None



