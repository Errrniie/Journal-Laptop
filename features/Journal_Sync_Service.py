"""
Sync journal entries and pages with the Life API.
API is the source of truth for page structure and content when configured.
"""

from typing import TYPE_CHECKING, Optional

from Models import DailyEntry, JournalPage

if TYPE_CHECKING:
    from features.API_Client import APIClient
    from features.Journal_Service import JournalService


def normalize_type_key(value: str) -> str:
    return value.lower().strip().replace(" ", "_")


class JournalSyncService:
    """Coordinates journal load/create/delete with the Life API."""

    def __init__(
        self,
        journal_service: "JournalService",
        api_client: Optional["APIClient"] = None,
    ) -> None:
        self.journal_service = journal_service
        self.api_client = api_client or getattr(journal_service, "api_client", None)
        self._page_type_cache: list[dict] = []
        self._journal_entry_ids: dict[str, str] = {}

    @property
    def is_enabled(self) -> bool:
        return bool(self.api_client and self.api_client.api_key)

    def fetch_page_types(self, force_refresh: bool = False) -> list[dict]:
        """Return active journal page types from GET /journal/page-types."""
        if not self.is_enabled:
            return []
        if self._page_type_cache and not force_refresh:
            return self._page_type_cache
        types, error = self.api_client.get_journal_page_types()
        if error:
            return self._page_type_cache
        self._page_type_cache = types
        return types

    def get_page_type_display_name(self, type_key: str) -> str:
        normalized = normalize_type_key(type_key)
        for page_type in self.fetch_page_types():
            if page_type.get("type_key") == normalized:
                return page_type.get("display_name") or normalized.replace("_", " ").title()
        return normalized.replace("_", " ").title()

    def get_active_pages_for_date(self, date: str) -> list[JournalPage]:
        """Active pages for a date (API when enabled, otherwise local storage)."""
        if not self.is_enabled:
            return self.journal_service.get_pages(date)
        entry_data, error = self.api_client.get_journal_by_date(date)
        if error or not entry_data:
            return self.journal_service.get_pages(date)
        entry_id = str(entry_data.get("id", ""))
        return self._map_api_pages(entry_data.get("pages") or [], entry_id)

    def active_page_type_exists(self, date: str, page_type: str) -> bool:
        """True when an active (non-deleted) page of this type exists for the date."""
        if not page_type:
            return False
        normalized = normalize_type_key(page_type)
        return any(
            p.page_type and normalize_type_key(p.page_type) == normalized
            for p in self.get_active_pages_for_date(date)
        )

    def get_available_page_types(self, date: str) -> list[dict]:
        """Page types from the API that are not yet on the entry for this date."""
        if not self.is_enabled:
            return []
        existing_types = {
            normalize_type_key(p.page_type)
            for p in self.get_active_pages_for_date(date)
            if p.page_type
        }
        available = []
        for page_type in self.fetch_page_types():
            type_key = page_type.get("type_key")
            if type_key and normalize_type_key(type_key) not in existing_types:
                available.append(page_type)
        return available

    def sync_journal_for_date(self, date: str) -> dict:
        """
        Load journal entry + pages from API and replace local journal pages for the date.
        Creates the entry and a main page when missing.
        """
        result = {"success": False, "errors": [], "skipped": False}
        if not self.is_enabled:
            result["success"] = True
            result["skipped"] = True
            return result

        entry_data, error = self.api_client.get_journal_by_date(date)
        if error:
            result["errors"].append(error)
            return result

        if entry_data is None:
            entry_id, create_error = self.api_client.create_journal_entry(date)
            if create_error == "entry_exists":
                entry_data, error = self.api_client.get_journal_by_date(date)
                if error:
                    result["errors"].append(error)
                    return result
            elif create_error:
                result["errors"].append(create_error)
                return result
            else:
                self._journal_entry_ids[date] = entry_id
                page_id, page_error = self.api_client.create_journal_page(
                    journal_entry_id=entry_id,
                    page_type="main",
                    title="Main",
                )
                if page_error and page_error != "page_type_exists":
                    result["errors"].append(page_error)
                    return result
                entry_data, error = self.api_client.get_journal_by_date(date)
                if error:
                    result["errors"].append(error)
                    return result

        if not entry_data:
            result["errors"].append("Journal entry not found after create")
            return result

        entry_id = str(entry_data.get("id", ""))
        if entry_id:
            self._journal_entry_ids[date] = entry_id

        pages = self._map_api_pages(entry_data.get("pages") or [], entry_id)
        if not pages:
            page_id, page_error = self.api_client.create_journal_page(
                journal_entry_id=entry_id,
                page_type="main",
                title="Main",
            )
            if page_error and page_error != "page_type_exists":
                result["errors"].append(page_error or "Failed to create main page")
                return result
            entry_data, error = self.api_client.get_journal_by_date(date)
            if error:
                result["errors"].append(error)
                return result
            pages = self._map_api_pages(entry_data.get("pages") or [], entry_id)

        self._replace_local_pages(date, pages, "")
        result["success"] = True
        return result

    def create_page(
        self,
        date: str,
        page_type: str,
        title: Optional[str] = None,
        content: str = "",
    ) -> tuple[bool, Optional[str]]:
        """Create a page via POST /journal/pages (and entry if needed)."""
        if not self.is_enabled:
            return False, "API not configured"

        sync_result = self.sync_journal_for_date(date)
        if not sync_result.get("success") and not sync_result.get("skipped"):
            return False, "; ".join(sync_result.get("errors") or ["Sync failed"])

        normalized_type = normalize_type_key(page_type)
        if self.active_page_type_exists(date, normalized_type):
            return False, "Page type already exists for this date"

        entry_id = self._journal_entry_ids.get(date)
        if not entry_id:
            entry_data, error = self.api_client.get_journal_by_date(date)
            if error:
                return False, error
            if not entry_data:
                return False, "Journal entry not found"
            entry_id = str(entry_data["id"])
            self._journal_entry_ids[date] = entry_id

        page_order = 0
        for page_type_row in self.fetch_page_types():
            if page_type_row.get("type_key") == normalized_type:
                page_order = page_type_row.get("page_order", 0)
                break

        page_id, error = self.api_client.create_journal_page(
            journal_entry_id=entry_id,
            page_type=normalized_type,
            title=title,
            content=content,
            page_order=page_order,
        )
        if error:
            return False, error

        sync_result = self.sync_journal_for_date(date)
        if not sync_result.get("success"):
            return False, "; ".join(sync_result.get("errors") or ["Failed to refresh journal"])
        return True, None

    def create_page_type(self, display_name: str) -> tuple[bool, Optional[str]]:
        """Create a new page type via POST /journal/page-types."""
        if not self.is_enabled:
            return False, "API not configured"
        display_name = display_name.strip()
        if not display_name:
            return False, "Display name is required"
        type_key = normalize_type_key(display_name)
        _, error = self.api_client.create_journal_page_type(
            type_key=type_key,
            display_name=display_name,
        )
        if error:
            return False, error
        self.fetch_page_types(force_refresh=True)
        return True, None

    def delete_page(self, date: str, page: JournalPage) -> tuple[bool, Optional[str]]:
        """Soft-delete a page via DELETE /journal/pages/{id}."""
        if not self.is_enabled:
            return False, "API not configured"
        if not page.page_id:
            return False, "Page has no API id"
        if page.page_type and normalize_type_key(page.page_type) == "main":
            return False, "The main page cannot be deleted"
        success, error = self.api_client.delete_journal_page(page.page_id)
        if not success:
            return False, error
        sync_result = self.sync_journal_for_date(date)
        if not sync_result.get("success"):
            return False, "; ".join(sync_result.get("errors") or ["Failed to refresh journal"])
        return True, None

    def update_page_content(
        self,
        date: str,
        page: JournalPage,
        content: str,
    ) -> tuple[bool, Optional[str]]:
        """Persist page content via PATCH /journal/pages/{id}."""
        if not self.is_enabled:
            return False, "API not configured"

        if content is None:
            content = ""

        page_id = page.page_id
        if not page_id:
            sync_result = self.sync_journal_for_date(date)
            if not sync_result.get("success"):
                return False, "; ".join(sync_result.get("errors") or ["Sync failed"])
            refreshed = self._find_cached_page(date, page)
            if refreshed is None or not refreshed.page_id:
                return False, "Page has no API id"
            page = refreshed
            page_id = page.page_id

        api_page, error = self.api_client.update_journal_page(page_id, content=content)
        if error:
            return False, error

        saved_content = (api_page or {}).get("content", content)
        self._apply_page_to_cache(date, page_id, saved_content, api_page)
        return True, None

    def restore_page(self, date: str, page: JournalPage) -> tuple[bool, Optional[str]]:
        """Restore a soft-deleted page via POST /journal/pages/{id}/restore."""
        if not self.is_enabled:
            return False, "API not configured"
        if not page.page_id:
            return False, "Page has no API id"
        success, error = self.api_client.restore_journal_page(page.page_id)
        if not success:
            if error == "page_type_inactive":
                display = self.get_page_type_display_name(page.page_type or "")
                return (
                    False,
                    f"Cannot restore page: the '{display}' page type is no longer active.",
                )
            return False, error
        sync_result = self.sync_journal_for_date(date)
        if not sync_result.get("success"):
            return False, "; ".join(sync_result.get("errors") or ["Failed to refresh journal"])
        return True, None

    def _find_cached_page(self, date: str, page: JournalPage) -> Optional[JournalPage]:
        pages = self.journal_service.get_pages(date)
        if page.page_id:
            match = next((p for p in pages if p.page_id == page.page_id), None)
            if match is not None:
                return match
        if page.page_type:
            normalized = normalize_type_key(page.page_type)
            return next(
                (p for p in pages if p.page_type and normalize_type_key(p.page_type) == normalized),
                None,
            )
        return next((p for p in pages if p.name == page.name), None)

    def _apply_page_to_cache(
        self,
        date: str,
        page_id: str,
        content: str,
        api_page: Optional[dict] = None,
    ) -> None:
        """Refresh local cache after a successful API write."""
        entry = self.journal_service.storage.get_entry(date)
        if entry is None:
            entry = DailyEntry(date=date)

        updated = False
        for cached_page in entry.journal_pages or []:
            if cached_page.page_id == page_id:
                cached_page.content = content
                if api_page:
                    title = (api_page.get("title") or "").strip()
                    if title:
                        cached_page.name = title
                    cached_page.created_at = str(api_page.get("created_at") or cached_page.created_at)
                updated = True
                if cached_page.page_type and normalize_type_key(cached_page.page_type) == "main":
                    entry.journal = content
                break

        if not updated and api_page:
            page_type = api_page.get("page_type") or ""
            title = (api_page.get("title") or "").strip()
            display_name = title or self.get_page_type_display_name(page_type)
            entry.journal_pages = entry.journal_pages or []
            entry.journal_pages.append(
                JournalPage(
                    name=display_name,
                    content=content,
                    created_at=str(api_page.get("created_at") or ""),
                    tag=page_type,
                    page_id=page_id,
                    page_type=page_type,
                    journal_entry_id=str(api_page.get("journal_entry_id") or ""),
                )
            )
            if page_type and normalize_type_key(page_type) == "main":
                entry.journal = content

        self.journal_service.storage.save_entry(entry, merge=False)

    def _map_api_pages(self, api_pages: list[dict], journal_entry_id: str) -> list[JournalPage]:
        pages: list[JournalPage] = []
        for api_page in api_pages:
            page_type = api_page.get("page_type") or ""
            title = (api_page.get("title") or "").strip()
            display_name = title or self.get_page_type_display_name(page_type)
            pages.append(
                JournalPage(
                    name=display_name,
                    content=api_page.get("content") or "",
                    created_at=str(api_page.get("created_at") or ""),
                    tag=page_type,
                    page_id=str(api_page.get("id")) if api_page.get("id") else None,
                    page_type=page_type,
                    journal_entry_id=journal_entry_id,
                )
            )
        return pages

    def _replace_local_pages(self, date: str, pages: list[JournalPage], legacy_journal: str) -> None:
        entry = self.journal_service.storage.get_entry(date)
        if entry is None:
            entry = DailyEntry(date=date)

        entry.journal_pages = pages
        if pages:
            main_page = next(
                (p for p in pages if p.page_type and normalize_type_key(p.page_type) == "main"),
                pages[0],
            )
            entry.journal = main_page.content or legacy_journal
        else:
            entry.journal = legacy_journal
        self.journal_service.storage.save_entry(entry, merge=False)
