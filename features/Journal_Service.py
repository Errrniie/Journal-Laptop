from datetime import datetime
from typing import TYPE_CHECKING, Optional

from Models import DailyEntry, JournalPage

if TYPE_CHECKING:
    from Storage import StorageInterface
    from features.API_Client import APIClient
    from features.Journal_Sync_Service import JournalSyncService


class JournalService:
    """
    Service for managing journal text entries for daily entries.
    When api_client is set, journal pages and content sync with the Life API.
    """
    
    def __init__(
        self,
        storage: "StorageInterface",
        api_client: Optional["APIClient"] = None,
    ) -> None:
        """
        Initialize Journal Service.
        
        Args:
            storage: StorageInterface instance for data persistence
            api_client: Optional APIClient for journal sync with backend
        """
        self.storage = storage
        self.api_client = api_client
        self.sync_service: Optional["JournalSyncService"] = None
        if api_client is not None:
            from features.Journal_Sync_Service import JournalSyncService
            self.sync_service = JournalSyncService(self, api_client)

    @property
    def uses_api(self) -> bool:
        return bool(self.sync_service and self.sync_service.is_enabled)

    def sync_from_api(self, date: str) -> dict:
        """Load journal entry/pages from API into local storage."""
        if not self.sync_service:
            return {"success": True, "skipped": True, "errors": []}
        return self.sync_service.sync_journal_for_date(date)

    def get_available_page_types(self, date: str) -> list[dict]:
        if self.sync_service:
            return self.sync_service.get_available_page_types(date)
        return []

    def fetch_page_types(self) -> list[dict]:
        if self.sync_service:
            return self.sync_service.fetch_page_types()
        return []

    def create_page_type(self, display_name: str) -> tuple[bool, Optional[str]]:
        if self.sync_service:
            return self.sync_service.create_page_type(display_name)
        return False, "API not configured"
    
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
    
    def get_journal(self, date: str) -> str:
        """
        Get journal text for a date (backward compatibility method).
        Returns content of first page or "Main" page if exists, else empty string.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            Journal text string, empty string if not found or invalid date
        """
        if not self._validate_date(date):
            return ""
        
        try:
            entry = self.storage.get_entry(date)
            if entry is None:
                return ""
            
            # Migrate old journal if needed
            if not entry.journal_pages and entry.journal:
                entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                self._save_entry(entry)
            
            # Return content from pages if available
            if entry.journal_pages:
                # Try to find "Main" page first
                main_page = next((p for p in entry.journal_pages if p.name == "Main"), None)
                if main_page:
                    return main_page.content
                # Otherwise return first page content
                return entry.journal_pages[0].content if entry.journal_pages[0].content else ""
            
            # Fallback to old journal field
            return entry.journal if entry.journal else ""
        except Exception:
            return ""
    
    def set_journal(self, date: str, text: str) -> bool:
        """
        Set or update journal text for a date (backward compatibility method).
        Updates/creates "Main" page with the text.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            text: Journal text to set (can be empty string or None)
            
        Returns:
            True on success, False on error or invalid date
        """
        if not self._validate_date(date):
            return False
        
        # Handle None text by converting to empty string
        if text is None:
            text = ""

        if self.uses_api:
            pages = self.get_pages(date)
            main_page = next(
                (
                    p for p in pages
                    if (p.page_type and p.page_type.lower().replace(" ", "_") == "main")
                    or p.name == "Main"
                ),
                None,
            )
            if main_page is None:
                sync_result = self.sync_from_api(date)
                if not sync_result.get("success"):
                    return False
                main_page = self.get_page(date, "Main")
            if main_page is None:
                return False
            success, _error = self.sync_service.update_page_content(date, main_page, text)
            return success
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Migrate if needed
            if not entry.journal_pages:
                if entry.journal:
                    entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                else:
                    entry.journal_pages = []
            
            # Find or create "Main" page
            main_page = next((p for p in entry.journal_pages if p.name == "Main"), None)
            if main_page:
                main_page.content = text
            else:
                # Create "Main" page if it doesn't exist
                entry.journal_pages.append(JournalPage(name="Main", content=text))
            
            # Also update old journal field for backward compatibility
            entry.journal = text
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def clear_journal(self, date: str) -> bool:
        """
        Clear journal text for a date (backward compatibility method).
        Clears "Main" page content.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            True on success, False on error or invalid date
        """
        if not self._validate_date(date):
            return False
        
        if self.uses_api:
            pages = self.get_pages(date)
            main_page = next(
                (
                    p for p in pages
                    if (p.page_type and p.page_type.lower().replace(" ", "_") == "main")
                    or p.name == "Main"
                ),
                None,
            )
            if main_page is None:
                return True
            success, _error = self.sync_service.update_page_content(date, main_page, "")
            return success

        try:
            entry = self._get_or_create_entry(date)
            
            # Clear "Main" page if it exists
            main_page = next((p for p in entry.journal_pages if p.name == "Main"), None)
            if main_page:
                main_page.content = ""
            
            # Also clear old journal field
            entry.journal = ""
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def get_pages(self, date: str) -> list[JournalPage]:
        """
        Get all journal pages for a date.
        Ensures backward compatibility by migrating old journal format if needed.
        
        Migration strategy:
        1. If journal_pages exists and has content → Use pages
        2. If journal_pages is empty but journal has content → Create "Main" page with that content
        3. If both empty → Return empty list (empty "Main" page will be created by GUI when needed)
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            List of JournalPage objects, empty list if none found or invalid date
        """
        if not self._validate_date(date):
            return []
        
        try:
            entry = self.storage.get_entry(date)
            if entry is None:
                return []
            
            # Migration on load: Handle backward compatibility
            # Case 1: journal_pages exists and has content → Use pages (already handled by storage)
            # Case 2: journal_pages is empty but journal has content → Create "Main" page
            if not entry.journal_pages and entry.journal:
                entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                self._save_entry(entry)
            # Case 3: Both empty → Return empty list (empty "Main" page will be created by GUI when needed)
            
            return entry.journal_pages if entry.journal_pages else []
        except Exception:
            return []
    
    def get_page(self, date: str, page_name: str) -> Optional[JournalPage]:
        """
        Get specific page by display name or page type for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            page_name: Display name or page type of the page to retrieve
            
        Returns:
            JournalPage object if found, None otherwise
        """
        if not self._validate_date(date):
            return None
        
        if not page_name or not page_name.strip():
            return None
        
        try:
            pages = self.get_pages(date)
            page_name = page_name.strip()
            normalized = page_name.lower().replace(" ", "_")
            return next(
                (
                    p for p in pages
                    if p.name == page_name
                    or (p.page_type and p.page_type == normalized)
                ),
                None,
            )
        except Exception:
            return None
    
    def page_type_exists(self, date: str, page_type: str) -> bool:
        if not self._validate_date(date) or not page_type:
            return False
        if self.sync_service and self.sync_service.is_enabled:
            return self.sync_service.active_page_type_exists(date, page_type)
        normalized = page_type.lower().strip().replace(" ", "_")
        try:
            pages = self.get_pages(date)
            return any(
                p.page_type and p.page_type.lower().strip().replace(" ", "_") == normalized
                for p in pages
            )
        except Exception:
            return False

    def restore_page(self, date: str, page_name: str) -> tuple[bool, Optional[str]]:
        """Restore a soft-deleted journal page (API mode)."""
        if not self.sync_service or not self.sync_service.is_enabled:
            return False, "API not configured"
        page = self.get_page(date, page_name)
        if page is None:
            return False, "Page not found"
        return self.sync_service.restore_page(date, page)

    def create_page(
        self,
        date: str,
        page_name: str,
        content: str = "",
        tag: str | None = None,
        page_type: str | None = None,
    ) -> bool:
        """
        Create a new journal page.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            page_name: Display name / title for the new page (local mode)
            content: Initial content for the page (default empty string)
            tag: Optional preset tag/category for the page (local mode)
            page_type: API page type key (API mode; falls back to page_name/tag)
            
        Returns:
            True on success, False on error or if page already exists
        """
        if not self._validate_date(date):
            return False
        
        if not page_name or not page_name.strip():
            return False
        
        page_name = page_name.strip()
        api_page_type = page_type or tag or page_name

        if self.sync_service and self.sync_service.is_enabled:
            success, _error = self.sync_service.create_page(
                date,
                api_page_type,
                title=page_name if page_name.lower().replace(" ", "_") != api_page_type.lower().replace(" ", "_") else None,
                content=content,
            )
            return success

        try:
            entry = self._get_or_create_entry(date)
            
            # Migrate if needed
            if not entry.journal_pages:
                if entry.journal:
                    entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                else:
                    entry.journal_pages = []
            
            # Check if page already exists
            if any(p.name == page_name for p in entry.journal_pages):
                return False  # Page already exists
            
            # Create new page with optional tag
            new_page = JournalPage(name=page_name, content=content if content else "", tag=tag)
            entry.journal_pages.append(new_page)
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def update_page(self, date: str, page_name: str, content: str) -> bool:
        """
        Update page content.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            page_name: Name of the page to update
            content: New content for the page
            
        Returns:
            True on success, False on error or if page doesn't exist
        """
        if not self._validate_date(date):
            return False
        
        if not page_name or not page_name.strip():
            return False
        
        page_name = page_name.strip()
        
        # Handle None content
        if content is None:
            content = ""

        if self.uses_api:
            page = self.get_page(date, page_name)
            if page is None:
                return False
            success, _error = self.sync_service.update_page_content(date, page, content)
            return success
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Migrate if needed
            if not entry.journal_pages:
                if entry.journal:
                    entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                else:
                    entry.journal_pages = []
            
            normalized = page_name.lower().replace(" ", "_")
            page = next(
                (
                    p for p in entry.journal_pages
                    if p.name == page_name
                    or (p.page_type and p.page_type.lower().replace(" ", "_") == normalized)
                ),
                None,
            )
            if page is None:
                return False  # Page doesn't exist
            
            # Update content
            page.content = content
            
            # Also update old journal field if this is "Main" page (for backward compatibility)
            if page.page_type and page.page_type.lower().replace(" ", "_") == "main":
                entry.journal = content
            elif page_name == "Main":
                entry.journal = content
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def delete_page(self, date: str, page_name: str) -> bool:
        """
        Delete a page.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            page_name: Name of the page to delete
            
        Returns:
            True on success, False on error or if page doesn't exist
        """
        if not self._validate_date(date):
            return False
        
        if not page_name or not page_name.strip():
            return False
        
        page_name = page_name.strip()
        page = self.get_page(date, page_name)
        if page is None:
            return False

        if self.sync_service and self.sync_service.is_enabled:
            success, _error = self.sync_service.delete_page(date, page)
            return success

        try:
            entry = self._get_or_create_entry(date)
            
            # Migrate if needed
            if not entry.journal_pages:
                if entry.journal:
                    entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                else:
                    entry.journal_pages = []
            
            # Find and remove page
            page_to_remove = next(
                (p for p in entry.journal_pages if p.name == page.name),
                None,
            )
            if page_to_remove is None:
                return False  # Page doesn't exist
            
            entry.journal_pages.remove(page_to_remove)
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def rename_page(self, date: str, old_name: str, new_name: str) -> bool:
        """
        Rename a page (local-only; API page types are fixed).
        """
        if self.uses_api:
            return False
        if not self._validate_date(date):
            return False
        
        if not old_name or not old_name.strip() or not new_name or not new_name.strip():
            return False
        
        old_name = old_name.strip()
        new_name = new_name.strip()
        
        if old_name == new_name:
            return True  # No change needed
        
        try:
            entry = self._get_or_create_entry(date)
            
            # Migrate if needed
            if not entry.journal_pages:
                if entry.journal:
                    entry.journal_pages = [JournalPage(name="Main", content=entry.journal)]
                else:
                    entry.journal_pages = []
            
            # Find page to rename
            page = next((p for p in entry.journal_pages if p.name == old_name), None)
            if page is None:
                return False  # Page doesn't exist
            
            # Check if new name already exists
            if any(p.name == new_name for p in entry.journal_pages):
                return False  # New name already exists
            
            # Rename page
            page.name = new_name
            
            return self._save_entry(entry)
        except Exception:
            return False
    
    def page_exists(self, date: str, page_name: str) -> bool:
        """
        Check if a page exists for a date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            page_name: Name of the page to check
            
        Returns:
            True if page exists, False otherwise
        """
        if not self._validate_date(date):
            return False
        
        if not page_name or not page_name.strip():
            return False
        
        try:
            pages = self.get_pages(date)
            normalized = page_name.strip().lower().replace(" ", "_")
            return any(
                p.name == page_name.strip()
                or (p.page_type and p.page_type.lower().strip().replace(" ", "_") == normalized)
                for p in pages
            )
        except Exception:
            return False
