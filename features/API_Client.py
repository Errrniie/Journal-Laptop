"""
API Client for communicating with the external Life API.
Centralized api_request; handles tasks and workouts.
"""

import requests
from typing import Any, Optional, Tuple


class APIError(Exception):
    """Raised when API returns status >= 400."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"HTTP {status_code}: {message}")


class APIClient:
    """
    Client for making requests to the Life API.
    """

    BASE_URL = "https://life-api.bravedesert-0d7c33d5.northcentralus.azurecontainerapps.io"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self) -> None:
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key
        elif "x-api-key" in self.session.headers:
            del self.session.headers["x-api-key"]

    def set_api_key(self, api_key: Optional[str]) -> None:
        self.api_key = api_key
        self._update_headers()

    def api_request(self, method: str, endpoint: str, body: Optional[dict] = None) -> Optional[dict]:
        """
        Centralized API call. Raises APIError on status >= 400.
        Returns JSON body, or None for 204 No Content.
        """
        url = f"{self.BASE_URL}{endpoint}"
        kwargs = {}
        if body is not None:
            kwargs["json"] = body
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise APIError(0, f"Connection error: {e}") from e
        except requests.exceptions.Timeout as e:
            raise APIError(0, f"Request timeout: {e}") from e
        except requests.exceptions.RequestException as e:
            raise APIError(0, str(e)) from e

        if response.status_code >= 400:
            try:
                err_body = response.json()
            except Exception:
                err_body = response.text
            raise APIError(
                response.status_code,
                response.reason or "Error",
                err_body,
            )

        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as e:
            raise APIError(response.status_code, f"Invalid JSON: {e}", response.text) from e

    # --- Tasks ---

    def get_tasks(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        include_deleted: Optional[bool] = None,
    ) -> Tuple[list[dict], Optional[str]]:
        """GET /tasks. Returns (list of task dicts, error_message or None)."""
        try:
            params = []
            if status is not None:
                params.append(f"status={status}")
            if category is not None:
                params.append(f"category={category}")
            if include_deleted is not None:
                params.append(f"include_deleted={str(include_deleted).lower()}")
            endpoint = "/tasks"
            if params:
                endpoint += "?" + "&".join(params)
            data = self.api_request("GET", endpoint)
            if data is None:
                return [], None
            if isinstance(data, list):
                return data, None
            return [], f"Unexpected response format: expected list, got {type(data)}"
        except APIError as e:
            return [], str(e)

    def create_task(
        self,
        title: str,
        description: str = "",
        category: str = "",
        priority: int = 0,
        due_at: Optional[str] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """POST /tasks. Returns (created task dict or None, error or None)."""
        try:
            payload = {"title": title}
            if description:
                payload["description"] = description
            if category:
                payload["category"] = category
            payload["priority"] = priority
            if due_at:
                payload["due_at"] = due_at
            data = self.api_request("POST", "/tasks", payload)
            return (data, None)
        except APIError as e:
            return (None, str(e))

    def complete_task(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """POST /tasks/{task_id}/complete. Returns (success, error or None)."""
        try:
            self.api_request("POST", f"/tasks/{task_id}/complete")
            return (True, None)
        except APIError as e:
            return (False, str(e))

    def delete_task(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """DELETE /tasks/{task_id}. Returns (success, error or None)."""
        try:
            self.api_request("DELETE", f"/tasks/{task_id}")
            return (True, None)
        except APIError as e:
            return (False, str(e))

    def restore_task(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """POST /tasks/{task_id}/restore. Returns (success, error or None)."""
        try:
            self.api_request("POST", f"/tasks/{task_id}/restore")
            return (True, None)
        except APIError as e:
            return (False, str(e))

    def update_task(self, task_id: str, payload: dict) -> Tuple[Optional[dict], Optional[str]]:
        """Placeholder: PATCH/PUT /tasks/{task_id} when API supports it. Returns (updated task or None, error or None)."""
        try:
            data = self.api_request("PATCH", f"/tasks/{task_id}", payload)
            return (data, None)
        except APIError as e:
            return (None, str(e))

    def get_sessions(self, limit: int = 20) -> Tuple[list[dict], Optional[str]]:
        """GET /sessions?limit=... For backward compatibility."""
        try:
            data = self.api_request("GET", f"/sessions?limit={limit}")
            if not isinstance(data, list):
                return [], f"Unexpected format: {type(data)}"
            return [s for s in data if s.get("type") == "tasks"], None
        except APIError as e:
            return [], str(e)

    def create_record(self, activity_id: str, data: dict) -> Tuple[Optional[dict], Optional[str]]:
        """POST /records (for workout sets). Returns (created record or None, error or None)."""
        try:
            payload = {"activity_id": activity_id, "data": data}
            result = self.api_request("POST", "/records", payload)
            return (result, None)
        except APIError as e:
            return (None, str(e))

    # --- Workouts: sessions, activities, records ---

    def get_workouts_full(self) -> Tuple[list[dict], Optional[str]]:
        """GET /workouts/full. Returns (list of full workout sessions, error or None)."""
        try:
            data = self.api_request("GET", "/workouts/full")
            if data is None:
                return [], None
            if isinstance(data, list):
                return data, None
            return [], f"Unexpected response format: expected list, got {type(data)}"
        except APIError as e:
            return [], str(e)

    def create_session(
        self,
        type: str = "workout",
        name: str = "",
        start_time: Optional[str] = None,
        notes: str = "",
    ) -> Tuple[Optional[dict], Optional[str]]:
        """POST /sessions. Returns (session dict with session_id or id, error or None)."""
        try:
            payload = {"type": type, "name": name or "Workout"}
            if start_time:
                payload["start_time"] = start_time
            if notes:
                payload["notes"] = notes
            data = self.api_request("POST", "/sessions", payload)
            return (data, None)
        except APIError as e:
            return (None, str(e))

    def create_activity(
        self,
        session_id: str,
        type: str,
        name: str,
        metadata: Optional[dict] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """POST /activities. Returns (activity dict with activity_id or id, error or None)."""
        try:
            payload = {
                "session_id": session_id,
                "type": type,
                "name": name,
            }
            if metadata:
                payload["metadata"] = metadata
            data = self.api_request("POST", "/activities", payload)
            return (data, None)
        except APIError as e:
            return (None, str(e))

    def delete_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """DELETE /sessions/{session_id}. Returns (success, error or None)."""
        try:
            self.api_request("DELETE", f"/sessions/{session_id}")
            return (True, None)
        except APIError as e:
            return (False, str(e))

    def restore_session(self, session_id: str) -> Tuple[bool, Optional[str]]:
        """POST /sessions/{session_id}/restore. Returns (success, error or None)."""
        try:
            self.api_request("POST", f"/sessions/{session_id}/restore")
            return (True, None)
        except APIError as e:
            return (False, str(e))

    # --- Journal ---

    def get_journal_page_types(
        self, include_deleted: bool = False
    ) -> Tuple[list[dict], Optional[str]]:
        """GET /journal/page-types. Returns (list of type dicts, error or None)."""
        try:
            endpoint = "/journal/page-types"
            if include_deleted:
                endpoint += "?include_deleted=true"
            data = self.api_request("GET", endpoint)
            if data is None:
                return [], None
            if isinstance(data, list):
                return data, None
            return [], f"Unexpected response format: expected list, got {type(data)}"
        except APIError as e:
            return [], str(e)

    def create_journal_page_type(
        self,
        type_key: str,
        display_name: str,
        page_order: int = 0,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """POST /journal/page-types."""
        try:
            payload = {
                "type_key": type_key,
                "display_name": display_name,
                "page_order": page_order,
            }
            data = self.api_request("POST", "/journal/page-types", payload)
            return (data, None)
        except APIError as e:
            return (None, str(e))

    def get_journal_by_date(self, entry_date: str) -> Tuple[Optional[dict], Optional[str]]:
        """GET /journal/by-date/{entry_date}. Returns (entry dict or None, error or None)."""
        try:
            data = self.api_request("GET", f"/journal/by-date/{entry_date}")
            return (data, None)
        except APIError as e:
            if e.status_code == 404:
                return (None, None)
            return (None, str(e))

    def create_journal_entry(
        self,
        entry_date: str,
        mood: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """POST /journal/entries. Returns (journal_entry_id, error or None)."""
        try:
            payload: dict = {"entry_date": entry_date}
            if mood is not None:
                payload["mood"] = mood
            if metadata is not None:
                payload["metadata"] = metadata
            data = self.api_request("POST", "/journal/entries", payload)
            if not data:
                return (None, "Empty response from journal entry create")
            entry_id = data.get("journal_entry_id")
            if not entry_id:
                return (None, f"Missing journal_entry_id in response: {data}")
            return (str(entry_id), None)
        except APIError as e:
            if e.status_code == 409:
                return (None, "entry_exists")
            return (None, str(e))

    def create_journal_page(
        self,
        journal_entry_id: str,
        page_type: str,
        title: Optional[str] = None,
        content: str = "",
        page_order: int = 0,
        metadata: Optional[dict] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """POST /journal/pages. Returns (journal_page_id, error or None)."""
        try:
            payload: dict = {
                "journal_entry_id": journal_entry_id,
                "page_type": page_type,
                "content": content or "",
                "page_order": page_order,
            }
            if title is not None:
                payload["title"] = title
            if metadata is not None:
                payload["metadata"] = metadata
            data = self.api_request("POST", "/journal/pages", payload)
            if not data:
                return (None, "Empty response from journal page create")
            page_id = data.get("journal_page_id")
            if not page_id:
                return (None, f"Missing journal_page_id in response: {data}")
            return (str(page_id), None)
        except APIError as e:
            if e.status_code == 409:
                return (None, "page_type_exists")
            return (None, str(e))

    def delete_journal_page(self, journal_page_id: str) -> Tuple[bool, Optional[str]]:
        """DELETE /journal/pages/{journal_page_id}."""
        try:
            self.api_request("DELETE", f"/journal/pages/{journal_page_id}")
            return (True, None)
        except APIError as e:
            return (False, str(e))

    def restore_journal_page(self, journal_page_id: str) -> Tuple[bool, Optional[str]]:
        """POST /journal/pages/{journal_page_id}/restore. Returns (success, error or None)."""
        try:
            self.api_request("POST", f"/journal/pages/{journal_page_id}/restore")
            return (True, None)
        except APIError as e:
            if e.status_code == 409:
                return (False, "page_type_inactive")
            return (False, str(e))

    def update_journal_page(
        self,
        journal_page_id: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        page_order: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """PATCH /journal/pages/{journal_page_id}. Returns (page dict, error or None)."""
        try:
            payload: dict = {}
            if content is not None:
                payload["content"] = content
            if title is not None:
                payload["title"] = title
            if page_order is not None:
                payload["page_order"] = page_order
            if metadata is not None:
                payload["metadata"] = metadata
            if not payload:
                return (None, "No fields provided for update")
            data = self.api_request("PATCH", f"/journal/pages/{journal_page_id}", payload)
            return (data, None)
        except APIError as e:
            return (None, str(e))
