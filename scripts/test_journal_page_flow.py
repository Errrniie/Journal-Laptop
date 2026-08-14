#!/usr/bin/env python3
"""
Integration test: delete → sync → add same type → edit → restart simulation.

Uses the Life API when api_key is set in data/settings.json.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.API_Client import APIClient
from features.Journal_Service import JournalService
from Storage.json_storage import JSONStorage

TEST_DATE = "2099-01-15"
TEST_TYPE = "school"
TEST_CONTENT = "<p>flow-test-content-12345</p>"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def main() -> None:
    settings_path = PROJECT_ROOT / "data" / "settings.json"
    settings = json.loads(settings_path.read_text())
    api_key = settings.get("api_key")
    if not api_key:
        fail("No api_key in data/settings.json")

    api_client = APIClient(api_key=api_key)
    with tempfile.TemporaryDirectory() as tmp:
        storage = JSONStorage(str(Path(tmp) / "lifelog.json"))
        service = JournalService(storage, api_client)

        sync = service.sync_from_api(TEST_DATE)
        if not sync.get("success"):
            fail(f"Initial sync failed: {sync.get('errors')}")

        available = service.get_available_page_types(TEST_DATE)
        type_keys = {t.get("type_key") for t in available}
        if TEST_TYPE not in type_keys:
            fail(f"{TEST_TYPE} not available to add: {type_keys}")

        created = service.create_page(TEST_DATE, "School", page_type=TEST_TYPE)
        if not created:
            fail("Failed to create test page")

        page = next(
            (p for p in service.get_pages(TEST_DATE) if p.page_type == TEST_TYPE),
            None,
        )
        if not page or not page.page_id:
            fail("Created page missing page_id")
        old_page_id = page.page_id
        ok(f"Created page id={old_page_id}")

        deleted = service.delete_page(TEST_DATE, page.name)
        if not deleted:
            fail("Failed to delete page")

        sync = service.sync_from_api(TEST_DATE)
        if not sync.get("success"):
            fail(f"Sync after delete failed: {sync.get('errors')}")

        if service.page_type_exists(TEST_DATE, TEST_TYPE):
            fail("Page type still marked active after delete+sync")

        available = service.get_available_page_types(TEST_DATE)
        if TEST_TYPE not in {t.get("type_key") for t in available}:
            fail(f"{TEST_TYPE} not available after delete")

        ok("Delete + sync freed page type")

        recreated = service.create_page(TEST_DATE, "School", page_type=TEST_TYPE)
        if not recreated:
            fail("Failed to re-create page")

        page = next(
            (p for p in service.get_pages(TEST_DATE) if p.page_type == TEST_TYPE),
            None,
        )
        if not page or not page.page_id:
            fail("Re-created page missing page_id")
        if page.page_id == old_page_id:
            fail(f"Re-created page reused old id {old_page_id}")
        new_page_id = page.page_id
        ok(f"Re-created page has new id={new_page_id}")

        edited = service.update_page(TEST_DATE, page.name, TEST_CONTENT)
        if not edited:
            fail("Failed to edit page content")

        stored = service.get_page(TEST_DATE, page.name)
        if not stored or stored.content != TEST_CONTENT:
            fail("Edited content not persisted locally")

        ok("Edit saved locally")

        entry_data, error = api_client.get_journal_by_date(TEST_DATE)
        if error or not entry_data:
            fail(f"API read after edit failed: {error}")
        api_page = next(
            (p for p in entry_data.get("pages") or [] if p.get("page_type") == TEST_TYPE),
            None,
        )
        if not api_page or api_page.get("content") != TEST_CONTENT:
            fail("Edited content not found in API database")

        ok("Edit persisted to API database")

        storage2 = JSONStorage(str(Path(tmp) / "lifelog.json"))
        service2 = JournalService(storage2, api_client)
        restart_sync = service2.sync_from_api(TEST_DATE)
        if not restart_sync.get("success"):
            fail(f"Restart sync failed: {restart_sync.get('errors')}")

        restarted = service2.get_page(TEST_DATE, page.name)
        if not restarted:
            fail("Page missing after restart sync")
        if restarted.page_id != new_page_id:
            fail(
                f"Restart changed page_id: expected {new_page_id}, got {restarted.page_id}"
            )
        if restarted.content != TEST_CONTENT:
            fail("Content lost after restart sync")

        ok("Restart loaded content from API")

        cleanup_page = service2.get_page(TEST_DATE, page.name)
        if cleanup_page:
            service2.delete_page(TEST_DATE, cleanup_page.name)

        print("\nAll journal page flow checks passed.")


if __name__ == "__main__":
    main()
