from dataclasses import dataclass
from typing import Optional


@dataclass
class JournalPage:
    name: str              # Display label (page title or page-type display name)
    content: str = ""      # Rich text content (HTML format)
    created_at: str = ""   # Optional: timestamp when page was created
    tag: Optional[str] = None  # Legacy preset tag (local-only)
    page_id: Optional[str] = None  # API journal_pages.id
    page_type: Optional[str] = None  # API page_type / type_key
    journal_entry_id: Optional[str] = None  # API parent journal_entries.id