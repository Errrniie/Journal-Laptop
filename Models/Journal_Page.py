from dataclasses import dataclass
from typing import Optional

@dataclass
class JournalPage:
    name: str              # Page name (e.g., "A", "B", "Work", "Personal")
    content: str = ""      # Rich text content (HTML format)
    created_at: str = ""   # Optional: timestamp when page was created
    tag: Optional[str] = None  # Optional: preset tag/category (e.g., "School", "Work", "Lifting")