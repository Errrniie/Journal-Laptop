"""
Settings store for persisting application settings.
Uses JSON file for storage (settings.json in data/ directory).
"""
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QDate


class SettingsStore:
    """
    Manages application settings persistence.
    """
    
    def __init__(self, settings_path: Optional[Path] = None) -> None:
        """
        Initialize Settings Store.
        
        Args:
            settings_path: Path to settings.json file. If None, uses data/settings.json
        """
        if settings_path is None:
            # Default to data/settings.json relative to project root
            project_root = Path(__file__).parent.parent
            settings_path = project_root / "data" / "settings.json"
        
        self.settings_path = Path(settings_path)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Default values
        today = date.today()
        self._defaults = {
            "analytics_start_date": (today - timedelta(days=29)).strftime("%Y-%m-%d"),
            "analytics_end_date": today.strftime("%Y-%m-%d"),
            "group_box_color": "#F0F0F0",
            "sync_auto_enabled": False,
            "sync_interval_seconds": 60,
            "sync_last_run": None,
            "api_key": "",  # API key - user must enter manually
            "journal_presets": [],  # List of journal preset tags (e.g., ["School", "Work", "Lifting"])
        }
        
        # Load settings
        self._settings = self._load_settings()
    
    def _load_settings(self) -> dict:
        """
        Load settings from JSON file.
        
        Returns:
            Dictionary of settings, with defaults for missing keys
        """
        if not self.settings_path.exists():
            return self._defaults.copy()
        
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Merge with defaults to ensure all keys exist
                settings = self._defaults.copy()
                settings.update(loaded)
                return settings
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or can't be read, return defaults
            return self._defaults.copy()
    
    def _save_settings(self) -> bool:
        """
        Save settings to JSON file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Write atomically using temporary file
            temp_path = self.settings_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
            
            # Replace original file
            temp_path.replace(self.settings_path)
            return True
        except IOError:
            return False
    
    def get_analytics_start_date(self) -> QDate:
        """
        Get analytics start date.
        
        Returns:
            QDate object
        """
        date_str = self._settings.get("analytics_start_date", self._defaults["analytics_start_date"])
        return QDate.fromString(date_str, "yyyy-MM-dd")
    
    def get_analytics_end_date(self) -> QDate:
        """
        Get analytics end date.
        
        Returns:
            QDate object
        """
        date_str = self._settings.get("analytics_end_date", self._defaults["analytics_end_date"])
        return QDate.fromString(date_str, "yyyy-MM-dd")
    
    def get_analytics_start_date_string(self) -> str:
        """
        Get analytics start date as string.
        
        Returns:
            Date string in "YYYY-MM-DD" format
        """
        return self._settings.get("analytics_start_date", self._defaults["analytics_start_date"])
    
    def get_analytics_end_date_string(self) -> str:
        """
        Get analytics end date as string.
        
        Returns:
            Date string in "YYYY-MM-DD" format
        """
        return self._settings.get("analytics_end_date", self._defaults["analytics_end_date"])
    
    def set_analytics_start_date(self, qdate: QDate) -> bool:
        """
        Set analytics start date.
        
        Args:
            qdate: QDate object
            
        Returns:
            True if successful, False otherwise
        """
        date_str = qdate.toString("yyyy-MM-dd")
        self._settings["analytics_start_date"] = date_str
        return self._save_settings()
    
    def set_analytics_end_date(self, qdate: QDate) -> bool:
        """
        Set analytics end date.
        
        Args:
            qdate: QDate object
            
        Returns:
            True if successful, False otherwise
        """
        date_str = qdate.toString("yyyy-MM-dd")
        self._settings["analytics_end_date"] = date_str
        return self._save_settings()
    
    def get_group_box_color(self) -> str:
        """
        Get group box color.
        
        Returns:
            Color string (hex format, e.g. "#F0F0F0")
        """
        return self._settings.get("group_box_color", self._defaults["group_box_color"])
    
    def set_group_box_color(self, color: str) -> bool:
        """
        Set group box color.
        
        Args:
            color: Color string (hex format, e.g. "#F0F0F0")
            
        Returns:
            True if successful, False otherwise
        """
        self._settings["group_box_color"] = color
        return self._save_settings()
    
    def get_sync_auto_enabled(self) -> bool:
        """
        Get auto-sync enabled setting.
        
        Returns:
            True if auto-sync is enabled, False otherwise
        """
        return self._settings.get("sync_auto_enabled", self._defaults["sync_auto_enabled"])
    
    def set_sync_auto_enabled(self, enabled: bool) -> bool:
        """
        Set auto-sync enabled setting.
        
        Args:
            enabled: True to enable auto-sync, False to disable
            
        Returns:
            True if successful, False otherwise
        """
        self._settings["sync_auto_enabled"] = enabled
        return self._save_settings()
    
    def get_sync_interval_seconds(self) -> int:
        """
        Get sync interval in seconds.
        
        Returns:
            Sync interval in seconds
        """
        return self._settings.get("sync_interval_seconds", self._defaults["sync_interval_seconds"])
    
    def set_sync_interval_seconds(self, interval: int) -> bool:
        """
        Set sync interval in seconds.
        
        Args:
            interval: Sync interval in seconds (30-60 recommended)
            
        Returns:
            True if successful, False otherwise
        """
        self._settings["sync_interval_seconds"] = max(30, min(300, interval))  # Clamp between 30-300 seconds
        return self._save_settings()
    
    def get_sync_last_run(self) -> Optional[str]:
        """
        Get last sync timestamp.
        
        Returns:
            ISO timestamp string of last sync, or None if never synced
        """
        return self._settings.get("sync_last_run", self._defaults["sync_last_run"])
    
    def set_sync_last_run(self, timestamp: Optional[str]) -> bool:
        """
        Set last sync timestamp.
        
        Args:
            timestamp: ISO timestamp string, or None to clear
            
        Returns:
            True if successful, False otherwise
        """
        self._settings["sync_last_run"] = timestamp
        return self._save_settings()
    
    def get_api_key(self) -> str:
        """
        Get API key.
        
        Returns:
            API key string, empty string if not set
        """
        return self._settings.get("api_key", self._defaults["api_key"])
    
    def set_api_key(self, api_key: str) -> bool:
        """
        Set API key.
        
        Args:
            api_key: API key string
            
        Returns:
            True if successful, False otherwise
        """
        self._settings["api_key"] = api_key
        return self._save_settings()
    
    def get_journal_presets(self) -> list[str]:
        """
        Get journal preset tags.
        
        Returns:
            List of preset tag names
        """
        return self._settings.get("journal_presets", self._defaults["journal_presets"])
    
    def set_journal_presets(self, presets: list[str]) -> bool:
        """
        Set journal preset tags.
        
        Args:
            presets: List of preset tag names (duplicates will be removed)
            
        Returns:
            True if successful, False otherwise
        """
        # Remove duplicates and empty strings, preserve order
        unique_presets = []
        seen = set()
        for preset in presets:
            preset_clean = preset.strip()
            if preset_clean and preset_clean.lower() not in seen:
                unique_presets.append(preset_clean)
                seen.add(preset_clean.lower())
        self._settings["journal_presets"] = unique_presets
        return self._save_settings()
    
    def add_journal_preset(self, preset: str) -> bool:
        """
        Add a journal preset tag if it doesn't already exist.
        
        Args:
            preset: Preset tag name to add
            
        Returns:
            True if successful, False otherwise
        """
        preset_clean = preset.strip()
        if not preset_clean:
            return False
        
        presets = self.get_journal_presets()
        if preset_clean.lower() not in [p.lower() for p in presets]:
            presets.append(preset_clean)
            return self.set_journal_presets(presets)
        return True  # Already exists, no error
    
    def save(self) -> bool:
        """
        Save all settings to file.
        
        Returns:
            True if successful, False otherwise
        """
        return self._save_settings()
