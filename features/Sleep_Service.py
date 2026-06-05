import csv
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from Models import DailyEntry

if TYPE_CHECKING:
    from Storage import StorageInterface


class SleepService:
    """
    Service for managing sleep hours tracking and import from Samsung Health CSV.
    Provides business logic for sleep operations on top of the storage layer.
    """
    
    def __init__(self, storage: "StorageInterface") -> None:
        """
        Initialize Sleep Service.
        
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
    
    def _validate_sleep_hours(self, hours: float) -> bool:
        """
        Validate sleep hours is in reasonable range (0-24).
        
        Args:
            hours: Sleep hours to validate
            
        Returns:
            True if hours is valid, False otherwise
        """
        try:
            hours_float = float(hours)
            return 0 <= hours_float <= 24
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
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse date string in various formats and return "YYYY-MM-DD" format.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Date string in "YYYY-MM-DD" format, or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        date_str = date_str.strip()
        if not date_str:
            return None
        
        # Try different date formats
        date_formats = [
            "%Y-%m-%d",      # YYYY-MM-DD
            "%m/%d/%Y",      # MM/DD/YYYY
            "%d/%m/%Y",      # DD/MM/YYYY
            "%Y/%m/%d",      # YYYY/MM/DD
            "%d-%m-%Y",      # DD-MM-YYYY
            "%m-%d-%Y",      # MM-DD-YYYY
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return None
    
    def _parse_sleep_duration(self, duration_str: str) -> Optional[float]:
        """
        Parse sleep duration from various formats and return hours as float.
        
        Handles:
        - Decimal hours: "7.5" -> 7.5
        - Minutes: "450" -> 7.5 (450 / 60)
        - Time format: "07:30" -> 7.5 (7 hours 30 minutes)
        
        Args:
            duration_str: Sleep duration string in various formats
            
        Returns:
            Sleep hours as float, or None if parsing fails
        """
        if not duration_str or not isinstance(duration_str, str):
            return None
        
        duration_str = duration_str.strip()
        if not duration_str:
            return None
        
        # Try decimal hours format (e.g., "7.5", "8.25")
        try:
            hours = float(duration_str)
            if 0 <= hours <= 24:
                return hours
        except ValueError:
            pass
        
        # Try time format (e.g., "07:30", "7:30", "23:45")
        time_pattern = r'^(\d{1,2}):(\d{2})$'
        match = re.match(time_pattern, duration_str)
        if match:
            try:
                hours_part = int(match.group(1))
                minutes_part = int(match.group(2))
                if 0 <= hours_part < 24 and 0 <= minutes_part < 60:
                    total_hours = hours_part + (minutes_part / 60.0)
                    return total_hours
            except (ValueError, IndexError):
                pass
        
        # Try minutes format (assume large numbers are minutes)
        try:
            minutes = float(duration_str)
            if minutes > 60:  # Likely minutes if > 60
                hours = minutes / 60.0
                if hours <= 24:  # Reasonable range
                    return hours
        except ValueError:
            pass
        
        return None
    
    def _detect_csv_columns(self, headers: list[str]) -> tuple[Optional[int], Optional[int]]:
        """
        Auto-detect date and sleep columns from CSV headers.
        
        Args:
            headers: List of CSV header strings
            
        Returns:
            Tuple of (date_column_index, sleep_column_index), or (None, None) if not found
        """
        date_index = None
        sleep_index = None
        
        # Normalize headers for comparison
        normalized_headers = [h.strip().lower() for h in headers]
        
        # Find date column
        date_keywords = ["date"]
        for i, header in enumerate(normalized_headers):
            if any(keyword in header for keyword in date_keywords):
                date_index = i
                break
        
        # Find sleep column
        sleep_keywords = ["sleep", "duration"]
        for i, header in enumerate(normalized_headers):
            if any(keyword in header for keyword in sleep_keywords):
                sleep_index = i
                break
        
        return date_index, sleep_index
    
    def get_sleep_hours(self, date: str) -> Optional[float]:
        """
        Get sleep hours for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            Sleep hours as float if found, None otherwise
        """
        if not self._validate_date(date):
            return None
        
        try:
            entry = self.storage.get_entry(date)
            if entry is None or entry.sleep_hours is None:
                return None
            return entry.sleep_hours
        except Exception:
            return None
    
    def set_sleep_hours(self, date: str, hours: float) -> bool:
        """
        Set or update sleep hours for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            hours: Sleep hours to set (0-24)
            
        Returns:
            True on success, False on error or invalid input
        """
        if not self._validate_date(date):
            return False
        
        if not self._validate_sleep_hours(hours):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            entry.sleep_hours = float(hours)
            return self._save_entry(entry)
        except Exception:
            return False
    
    def clear_sleep_hours(self, date: str) -> bool:
        """
        Clear sleep hours for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or invalid date
        """
        if not self._validate_date(date):
            return False
        
        try:
            entry = self._get_or_create_entry(date)
            entry.sleep_hours = None
            return self._save_entry(entry)
        except Exception:
            return False
    
    def get_sleep_range(self, start_date: str, end_date: str) -> list[tuple[str, float]]:
        """
        Get sleep hours for date range.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            
        Returns:
            List of (date, hours) tuples, sorted by date
        """
        if not self._validate_date(start_date) or not self._validate_date(end_date):
            return []
        
        try:
            entries = self.storage.get_entries_range(start_date, end_date)
            result = []
            
            for entry in entries:
                if entry.sleep_hours is not None:
                    result.append((entry.date, entry.sleep_hours))
            
            # Sort by date (should already be sorted, but ensure it)
            result.sort(key=lambda x: x[0])
            return result
        except Exception:
            return []
    
    def import_from_csv(self, file_path: str, skip_existing: bool = True) -> dict:
        """
        Import sleep data from Samsung Health CSV file.
        
        Args:
            file_path: Path to CSV file
            skip_existing: If True, skip rows where entry already has sleep_hours
            
        Returns:
            Dictionary with keys: rows_processed, rows_imported, rows_skipped, errors
        """
        result = {
            "rows_processed": 0,
            "rows_imported": 0,
            "rows_skipped": 0,
            "errors": []
        }
        
        # Validate file exists and is readable
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            result["errors"].append(f"File not found: {file_path}")
            return result
        
        if not file_path_obj.is_file():
            result["errors"].append(f"Path is not a file: {file_path}")
            return result
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Try to detect CSV dialect
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
                
                reader = csv.reader(f, dialect)
                
                # Read header row
                try:
                    headers = next(reader)
                except StopIteration:
                    result["errors"].append("CSV file is empty or has no header row")
                    return result
                
                # Detect date and sleep columns
                date_col, sleep_col = self._detect_csv_columns(headers)
                
                if date_col is None:
                    result["errors"].append("Could not detect date column in CSV header")
                    return result
                
                if sleep_col is None:
                    result["errors"].append("Could not detect sleep/duration column in CSV header")
                    return result
                
                # Process each row
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    result["rows_processed"] += 1
                    
                    # Skip empty rows
                    if not row or all(not cell.strip() for cell in row):
                        continue
                    
                    # Get date and sleep values
                    if date_col >= len(row) or sleep_col >= len(row):
                        result["errors"].append(f"Row {row_num}: Not enough columns")
                        continue
                    
                    date_str = row[date_col].strip()
                    sleep_str = row[sleep_col].strip()
                    
                    # Skip if date or sleep is empty
                    if not date_str or not sleep_str:
                        result["errors"].append(f"Row {row_num}: Empty date or sleep value")
                        continue
                    
                    # Parse date
                    parsed_date = self._parse_date(date_str)
                    if parsed_date is None:
                        result["errors"].append(f"Row {row_num}: Could not parse date '{date_str}'")
                        continue
                    
                    # Parse sleep duration
                    parsed_hours = self._parse_sleep_duration(sleep_str)
                    if parsed_hours is None:
                        result["errors"].append(f"Row {row_num}: Could not parse sleep duration '{sleep_str}'")
                        continue
                    
                    # Validate sleep hours
                    if not self._validate_sleep_hours(parsed_hours):
                        result["errors"].append(f"Row {row_num}: Sleep hours {parsed_hours} out of range (0-24)")
                        continue
                    
                    # Check if entry exists and has sleep_hours
                    if skip_existing:
                        existing_entry = self.storage.get_entry(parsed_date)
                        if existing_entry and existing_entry.sleep_hours is not None:
                            result["rows_skipped"] += 1
                            continue
                    
                    # Create/update entry
                    try:
                        entry = self._get_or_create_entry(parsed_date)
                        entry.sleep_hours = parsed_hours
                        if self._save_entry(entry):
                            result["rows_imported"] += 1
                        else:
                            result["errors"].append(f"Row {row_num}: Failed to save entry for date {parsed_date}")
                    except Exception as e:
                        result["errors"].append(f"Row {row_num}: Exception while saving: {str(e)}")
        
        except UnicodeDecodeError:
            result["errors"].append(f"File encoding error: Could not read file as UTF-8")
        except csv.Error as e:
            result["errors"].append(f"CSV parsing error: {str(e)}")
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
        
        return result
