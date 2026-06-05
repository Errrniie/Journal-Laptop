from abc import ABC, abstractmethod
from typing import Optional

from Models import DailyEntry


class StorageInterface(ABC):
    """
    Abstract base class defining the storage contract for the Journal application.
    All storage implementations must follow this interface.
    """
    
    @abstractmethod
    def get_entry(self, date: str) -> Optional[DailyEntry]:
        """
        Retrieve a single entry by date string.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            DailyEntry object if found, None otherwise
        """
        pass
    
    @abstractmethod
    def save_entry(self, entry: DailyEntry, merge: bool = True) -> None:
        """
        Save or update an entry.
        
        Args:
            entry: DailyEntry object to save
            merge: If True and entry exists, merge new data into existing
                   (don't overwrite non-empty fields). If False, replace entry.
        """
        pass
    
    @abstractmethod
    def get_entries_range(self, start_date: str, end_date: str) -> list[DailyEntry]:
        """
        Get all entries within a date range (inclusive).
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            
        Returns:
            List of DailyEntry objects sorted by date
        """
        pass
    
    @abstractmethod
    def delete_entry(self, date: str) -> bool:
        """
        Delete an entry by date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True if entry was deleted, False if not found
        """
        pass
