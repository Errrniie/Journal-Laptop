"""
Task Sync Service for syncing tasks with the external API.
Handles fetching, mapping, and merging API tasks with local tasks.
"""

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from Models import Task
from features.API_Client import APIClient

if TYPE_CHECKING:
    from features.Task_Service import TaskService


class TaskSyncService:
    """
    Service for syncing tasks between local storage and external API.
    """
    
    def __init__(self, task_service: "TaskService", api_client: Optional[APIClient] = None) -> None:
        """
        Initialize Task Sync Service.
        
        Args:
            task_service: TaskService instance for local operations
            api_client: APIClient instance (creates new one if None, but API key must be set)
        """
        self.task_service = task_service
        self.api_client = api_client or APIClient(api_key=None)
        storage_path = getattr(task_service.storage, "file_path", None)
        self._pending_tasks_path = (
            Path(storage_path).with_name("pending_task_requests.json")
            if storage_path else None
        )

    def _pending_task_id(self, payload: dict) -> tuple[Optional[str], Optional[str]]:
        """Keep the same request ID when a POST succeeds but its reply is lost."""
        if self._pending_tasks_path is None:
            return None, "Task request storage is unavailable"
        path = self._pending_tasks_path
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        try:
            pending = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if not isinstance(pending, dict):
                raise ValueError("pending request file is not an object")
            if fingerprint in pending:
                return pending[fingerprint], None
            request_id = str(uuid4())
            pending[fingerprint] = request_id
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
            temp_path.replace(path)
            return request_id, None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return None, f"Could not persist task request: {exc}"

    def _forget_pending_task(self, payload: dict) -> None:
        if self._pending_tasks_path is None:
            return
        path = self._pending_tasks_path
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        try:
            pending = json.loads(path.read_text(encoding="utf-8"))
            pending.pop(fingerprint, None)
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
            temp_path.replace(path)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    
    def refetch_and_replace_tasks(self, date: str) -> dict:
        """
        Refetch all tasks from API and reconcile observed IDs with local tasks.
        
        Tasks are stored in entries based on their due date, not the current view date.
        
        Before refetching, pushes any local-only tasks (without activity_id) to the API.
        
        Args:
            date: Date string in "YYYY-MM-DD" format (for statistics only, not used for filtering)
            
        Returns:
            Dictionary with sync results:
            {
                "success": bool,
                "tasks_synced": int,
                "errors": list[str]
            }
        """
        result = {
            "success": False,
            "tasks_synced": 0,
            "tasks_added": 0,
            "tasks_updated": 0,
            "tasks_pushed": 0,
            "errors": [],
        }
        
        # Give every local-only task a durable request ID before sending it.
        # A timeout can otherwise create a duplicate on the next sync.
        if self.api_client.api_key:
            local_tasks_to_push = []
            try:
                entries = self.task_service.storage.get_entries_range("0001-01-01", "9999-12-31")
            except Exception as exc:
                result["errors"].append(f"Could not inspect local tasks: {exc}")
                return result
            for entry in entries:
                changed = False
                for task in entry.tasks or []:
                    if not task.activity_id and not task.client_request_id:
                        task.client_request_id = str(uuid4())
                        changed = True
                if changed and not self.task_service.replace_tasks_with_sync_info(entry.date, entry.tasks):
                    result["errors"].append(f"Could not save task request IDs for {entry.date}")
                    return result
                local_tasks_to_push.extend(
                    (entry.date, task)
                    for task in entry.tasks or [] if not task.activity_id
                )

            for task_date, task in local_tasks_to_push:
                task_response, error = self.api_client.create_task(
                    title=task.name,
                    description=task.Notes if task.Notes else "",
                    category="",
                    priority=task.Priority if task.Priority else 1,
                    due_date=task.Due_Date or None,
                    client_request_id=task.client_request_id,
                    completed=task.completed,
                )

                if error:
                    result["errors"].append(f"Failed to push local task '{task.name}': {error}")
                elif task_response:
                    task_id = task_response.get("id") or task_response.get("task_id")
                    if task_id:
                        task.activity_id = task_id
                        task.last_synced = datetime.utcnow().isoformat() + "Z"
                        tasks_for_date = self.task_service.get_tasks(task_date)
                        for t in tasks_for_date:
                            if t.client_request_id == task.client_request_id and not t.activity_id:
                                t.activity_id = task_id
                                t.last_synced = task.last_synced
                                break
                        if self.task_service.save_tasks_with_sync_info(task_date, tasks_for_date):
                            result["tasks_pushed"] += 1
                        else:
                            result["errors"].append(f"Could not save API ID for task '{task.name}'")
                            return result
                    else:
                        result["errors"].append(f"Pushed task '{task.name}' but response missing task ID")
                else:
                    result["errors"].append(f"Failed to push local task '{task.name}': No response from server")
        
        # Fetch all pages including tombstones. An omitted task is never proof
        # of deletion; only an explicit deleted_at value removes a cached task.
        api_tasks_raw, error = self.api_client.get_tasks(include_deleted=True)
        if error:
            result["errors"].append(f"Failed to get tasks from API: {error}")
            return result

        # Remember dates with API-backed tasks before replacing groups. This
        # lets a successful full fetch clear dates omitted after remote deletion.
        local_by_date = {}
        storage = getattr(self.task_service, "storage", None)
        if storage is not None and hasattr(storage, "get_entries_range"):
            try:
                for entry in storage.get_entries_range("0001-01-01", "9999-12-31"):
                    if entry.tasks:
                        local_by_date[entry.date] = entry.tasks
            except Exception as e:
                result["errors"].append(f"Failed to inspect local tasks: {e}")
                return result
        deleted_ids = {
            str(task["id"])
            for task in api_tasks_raw
            if task.get("deleted_at") is not None
        }
        active_rows = [task for task in api_tasks_raw if task.get("deleted_at") is None]
        active_ids = {str(task["id"]) for task in active_rows}
        touched_ids = active_ids | deleted_ids
        
        # Group tasks by their due date (or created_at if no due_at)
        # Tasks should be stored in entries based on when they're due, not when viewed
        tasks_by_date = {}
        
        for task_data in active_rows:
            try:
                mapped_task = self._map_api_task_to_local(task_data)
                if not mapped_task:
                    result["errors"].append(f"Could not map API task {task_data.get('id')}")
                    continue
                
                # Determine which date entry this task belongs to
                # A date-only deadline is stable across device time zones.
                task_date = task_data.get("due_date") or None
                due_at = task_data.get("due_at", "")
                created_at = task_data.get("created_at", "")
                
                # Try due_at first (this is what the user set)
                if not task_date and due_at:
                    try:
                        due_date_obj = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                        task_date = due_date_obj.strftime("%Y-%m-%d")
                    except (ValueError, AttributeError):
                        pass
                
                # Fallback to created_at if no due_at
                if not task_date and created_at:
                    try:
                        created_date_obj = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        task_date = created_date_obj.strftime("%Y-%m-%d")
                    except (ValueError, AttributeError):
                        pass
                
                # Fallback to today if no date info
                if not task_date:
                    from datetime import date as date_class
                    task_date = date_class.today().strftime("%Y-%m-%d")
                
                # Group task by its due date
                if task_date not in tasks_by_date:
                    tasks_by_date[task_date] = []
                tasks_by_date[task_date].append(mapped_task)
                
            except Exception as e:
                result["errors"].append(f"Error mapping API task: {str(e)}")
                continue
        
        # A malformed page must not partially replace the local task cache.
        if any(error.startswith(("Could not map API task", "Error mapping API task")) for error in result["errors"]):
            return result

        # Save tasks to their respective date entries
        # Each task is stored in the entry for its due date
        total_tasks = 0
        dates_to_replace = set(tasks_by_date)
        dates_to_replace.update(
            task_date
            for task_date, tasks in local_by_date.items()
            if any(task.activity_id and str(task.activity_id) in touched_ids for task in tasks)
        )
        all_saves_succeeded = True
        for task_date in dates_to_replace:
            # Preserve local-only tasks and API tasks that were not observed in
            # this snapshot. Remove only observed/changed IDs or tombstones.
            untouched = [
                task for task in local_by_date.get(task_date, [])
                if not task.activity_id or str(task.activity_id) not in touched_ids
            ]
            combined = list(tasks_by_date.get(task_date, [])) + untouched
            if self.task_service.replace_tasks_with_sync_info(task_date, combined):
                total_tasks += len(tasks_by_date.get(task_date, []))
            else:
                result["errors"].append(f"Failed to save tasks for date {task_date}")
                all_saves_succeeded = False
        
        if all_saves_succeeded and not result["errors"]:
            result["success"] = True
            result["tasks_synced"] = total_tasks
        
        return result
    
    def sync_tasks_for_date(self, date: str) -> dict:
        """
        Sync tasks for a specific date (legacy method - now just calls refetch_and_replace_tasks).
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            
        Returns:
            Dictionary with sync results (for backward compatibility)
        """
        return self.refetch_and_replace_tasks(date)
    
    def create_task_and_refetch(self, date: str, title: str, description: str = "", 
                                category: str = "", priority: int = 1,
                                due_at: Optional[str] = None,
                                due_date: Optional[str] = None) -> dict:
        """
        Create a task on the API and immediately refetch all tasks.
        Server is the single source of truth.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            title: Task title (required)
            description: Task description (optional)
            category: Task category (optional)
            priority: Priority level (optional, defaults to 1)
            due_at: Due date in ISO format (optional)
            
        Returns:
            Dictionary with results:
            {
                "success": bool,
                "errors": list[str]
            }
        """
        result = {
            "success": False,
            "errors": [],
        }

        request_payload = {
            "title": title,
            "description": description,
            "category": category,
            "priority": priority,
            "due_at": due_at,
            "due_date": due_date,
        }
        request_id, id_error = self._pending_task_id(request_payload)
        if id_error:
            result["errors"].append(id_error)
            return result
        
        # Create task on API
        task_response, error = self.api_client.create_task(
            title=title,
            description=description,
            category=category,
            priority=priority,
            due_at=due_at,
            due_date=due_date,
            client_request_id=request_id,
        )
        
        if error:
            result["errors"].append(f"Failed to create task: {error}")
            return result
        
        # Check if task was created successfully
        if not task_response:
            result["errors"].append("Task creation returned no response")
            return result
        
        # Immediately refetch all tasks from server (mandatory after mutation)
        refetch_result = self.refetch_and_replace_tasks(date)
        result["success"] = refetch_result["success"]
        result["errors"].extend(refetch_result["errors"])
        if result["success"]:
            self._forget_pending_task(request_payload)
        
        return result
    
    def delete_task_and_refetch(self, date: str, task_id: str,
                                expected_revision: Optional[int] = None) -> dict:
        """
        Delete a task from the API and immediately refetch all tasks.
        Server is the single source of truth.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            task_id: UUID of the task to delete
            
        Returns:
            Dictionary with results:
            {
                "success": bool,
                "errors": list[str]
            }
        """
        result = {
            "success": False,
            "errors": [],
        }
        
        # Delete task on API
        success, error = self.api_client.delete_task(task_id, expected_revision)
        
        if error:
            result["errors"].append(f"Failed to delete task: {error}")
            return result
        
        if not success:
            result["errors"].append("Delete request did not return 204 No Content")
            return result
        
        # Immediately refetch all tasks from server (mandatory after mutation)
        refetch_result = self.refetch_and_replace_tasks(date)
        result["success"] = refetch_result["success"]
        result["errors"].extend(refetch_result["errors"])
        
        return result
    
    def complete_task_and_refetch(self, date: str, task_id: str,
                                  expected_revision: Optional[int] = None) -> dict:
        """
        Mark task as complete via POST /tasks/{task_id}/complete and refetch all tasks.
        """
        result = {"success": False, "errors": []}
        success, error = self.api_client.complete_task(task_id, expected_revision)
        if error:
            result["errors"].append(error)
            return result
        refetch_result = self.refetch_and_replace_tasks(date)
        result["success"] = refetch_result["success"]
        result["errors"].extend(refetch_result["errors"])
        return result

    def reopen_task_and_refetch(self, date: str, task_id: str,
                                expected_revision: Optional[int] = None) -> dict:
        """Mark a completed task pending using the task API, then refresh."""
        result = {"success": False, "errors": []}
        success, error = self.api_client.reopen_task(task_id, expected_revision)
        if not success:
            result["errors"].append(error or "Failed to reopen task")
            return result
        refetch_result = self.refetch_and_replace_tasks(date)
        result["success"] = refetch_result["success"]
        result["errors"].extend(refetch_result["errors"])
        return result
    
    def restore_task_and_refetch(self, date: str, task_id: str) -> dict:
        """
        Restore a deleted task via POST /tasks/{task_id}/restore and refetch all tasks.
        """
        result = {"success": False, "errors": []}
        success, error = self.api_client.restore_task(task_id)
        if error:
            result["errors"].append(error)
            return result
        refetch_result = self.refetch_and_replace_tasks(date)
        result["success"] = refetch_result["success"]
        result["errors"].extend(refetch_result["errors"])
        return result
    
    def clear_completed_and_refetch(self, date: str) -> dict:
        """
        Delete each completed task via API then refetch. Server is source of truth.
        """
        result = {"success": False, "errors": [], "deleted": 0}
        tasks = self.task_service.get_tasks(date)
        completed = [t for t in tasks if t.completed and t.activity_id]
        for task in completed:
            ok, err = self.api_client.delete_task(task.activity_id, task.revision)
            if err:
                result["errors"].append(f"Delete '{task.name}': {err}")
            else:
                result["deleted"] += 1
        refetch_result = self.refetch_and_replace_tasks(date)
        result["success"] = refetch_result["success"]
        result["errors"].extend(refetch_result["errors"])
        return result
    
    def sync_all_recent_tasks(self, limit: int = 20) -> dict:
        """Compatibility entry point for a complete all-date task reconciliation."""
        from datetime import date as date_class
        today = date_class.today().strftime("%Y-%m-%d")
        return self.refetch_and_replace_tasks(today)
    
    def _map_api_task_to_local(self, task_data: dict) -> Optional[Task]:
        """
        Convert API task (from GET /tasks) to local Task model.
        
        Args:
            task_data: Task dictionary from API with fields: id, title, description, status, priority, due_at, created_at
            
        Returns:
            Task object or None if mapping fails
        """
        try:
            # Map required fields
            task_id = task_data.get("id")
            title = task_data.get("title", "")
            
            if not task_id or not title:
                return None
            
            # Map optional fields
            description = task_data.get("description", "")
            status = task_data.get("status", "").lower()
            priority = task_data.get("priority", 1)
            due_at = task_data.get("due_at", "")
            due_date = task_data.get("due_date") or ""
            created_at = task_data.get("created_at", "")
            
            # Ensure priority is in range 1-5
            if isinstance(priority, (int, float)):
                priority = max(1, min(5, int(priority)))
            else:
                priority = 1
            
            # Map status to completed boolean
            completed = status in ["completed", "done", "finished", "closed"]
            
            # Convert due_at from ISO format to "YYYY-MM-DD" format
            due_date_str = ""
            if due_date:
                due_date_str = str(due_date)
            elif due_at:
                try:
                    due_date_obj = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                    due_date_str = due_date_obj.strftime("%Y-%m-%d")
                except (ValueError, AttributeError):
                    pass
            
            # Use created_at or current time for last_synced
            last_synced = created_at if created_at else datetime.utcnow().isoformat() + "Z"
            
            return Task(
                name=title,
                completed=completed,
                Priority=priority,
                Due_Date=due_date_str,
                Notes=description,
                activity_id=task_id,  # Store task ID in activity_id field
                session_id=None,  # Not available from GET /tasks
                last_synced=last_synced,
                revision=task_data.get("revision"),
                client_request_id=(str(task_data["client_request_id"])
                                   if task_data.get("client_request_id") else None),
            )
        except Exception as e:
            # Return None if mapping fails - error will be logged by caller
            return None
    
    def _merge_tasks(self, api_tasks: list[Task], local_tasks: list[Task]) -> list[Task]:
        """
        Smart merge of API tasks with local tasks.
        
        Strategy:
        1. Match by activity_id if local task has it
        2. Fall back to name matching (case-insensitive)
        3. Update matched tasks with API data
        4. Add new tasks from API that don't match
        5. Keep local-only tasks (no API match)
        
        Args:
            api_tasks: List of tasks from API
            local_tasks: List of local tasks
            
        Returns:
            Merged list of tasks
        """
        merged = []
        matched_local_indices = set()
        
        # First pass: match by activity_id
        for api_task in api_tasks:
            matched = False
            for i, local_task in enumerate(local_tasks):
                if i in matched_local_indices:
                    continue
                
                if local_task.activity_id and local_task.activity_id == api_task.activity_id:
                    # Update local task with API data, but preserve local-only fields
                    local_task.name = api_task.name
                    local_task.completed = api_task.completed
                    local_task.Priority = api_task.Priority
                    local_task.Notes = api_task.Notes if api_task.Notes else local_task.Notes
                    local_task.session_id = api_task.session_id
                    local_task.last_synced = api_task.last_synced
                    merged.append(local_task)
                    matched_local_indices.add(i)
                    matched = True
                    break
            
            if not matched:
                # Try name matching
                api_name_lower = api_task.name.lower().strip()
                for i, local_task in enumerate(local_tasks):
                    if i in matched_local_indices:
                        continue
                    
                    if not local_task.activity_id and local_task.name.lower().strip() == api_name_lower:
                        # Update local task with API data
                        local_task.name = api_task.name
                        local_task.completed = api_task.completed
                        local_task.Priority = api_task.Priority
                        local_task.Notes = api_task.Notes if api_task.Notes else local_task.Notes
                        local_task.activity_id = api_task.activity_id
                        local_task.session_id = api_task.session_id
                        local_task.last_synced = api_task.last_synced
                        merged.append(local_task)
                        matched_local_indices.add(i)
                        matched = True
                        break
            
            if not matched:
                # New task from API
                merged.append(api_task)
        
        # Add unmatched local tasks (local-only)
        for i, local_task in enumerate(local_tasks):
            if i not in matched_local_indices:
                merged.append(local_task)
        
        return merged
    
    def _push_local_tasks_to_api(self, date: str, local_tasks: list[Task]) -> dict:
        """
        Push local tasks that don't have an activity_id to the API.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
            local_tasks: List of local tasks
            
        Returns:
            Dictionary with push results:
            {
                "tasks_pushed": int,
                "errors": list[str]
            }
        """
        result = {
            "tasks_pushed": 0,
            "errors": [],
        }
        
        if not self.api_client.api_key:
            result["errors"].append("API key not configured")
            return result
        
        # Find tasks without activity_id (local-only tasks)
        tasks_to_push = [task for task in local_tasks if not task.activity_id]
        
        if not tasks_to_push:
            return result
        
        # Push each task to API
        for task in tasks_to_push:
            try:
                # Convert Due_Date from "YYYY-MM-DD" to ISO format "YYYY-MM-DDTHH:MM:SS.fffZ"
                due_at = None
                if task.Due_Date:
                    try:
                        # Parse date and convert to ISO format with milliseconds
                        due_date_obj = datetime.strptime(task.Due_Date, "%Y-%m-%d")
                        # Set time to end of day (23:59:59.490) in UTC with milliseconds
                        due_at = due_date_obj.strftime("%Y-%m-%dT23:59:59.490Z")
                    except (ValueError, AttributeError):
                        # If date format is invalid, skip due_at
                        pass
                
                # Create task on API using new /tasks endpoint
                task_response, error = self.api_client.create_task(
                    title=task.name,  # Required field
                    description=task.Notes if task.Notes else "",  # Optional
                    category="",  # Optional - can be enhanced later
                    priority=task.Priority if task.Priority else 0,  # Priority (defaults to 0)
                    due_at=due_at  # Optional ISO format with milliseconds
                )
                
                if error:
                    # API request failed - include detailed error message
                    result["errors"].append(f"Failed to create task '{task.name}': {error}")
                elif task_response:
                    # Check for task ID in response (could be 'id' or 'task_id' depending on API)
                    task_id = task_response.get("id") or task_response.get("task_id")
                    if task_id:
                        # Update task with task_id
                        task.activity_id = task_id  # Using activity_id field to store task ID
                        task.last_synced = datetime.utcnow().isoformat() + "Z"
                        result["tasks_pushed"] += 1
                        # If task is completed, call complete endpoint
                        if task.completed:
                            _, complete_error = self.api_client.complete_task(task_id)
                            if complete_error:
                                result["errors"].append(f"Created task '{task.name}' but failed to complete: {complete_error}")
                    else:
                        # Task creation succeeded but response missing ID
                        error_msg = f"Task '{task.name}' created but response missing task ID. Response: {task_response}"
                        result["errors"].append(error_msg)
                else:
                    # Task creation returned None
                    result["errors"].append(f"Failed to create task '{task.name}': No response from server")
            except Exception as e:
                result["errors"].append(f"Error pushing task '{task.name}': {str(e)}")
        
        # Save updated tasks with activity_ids
        if result["tasks_pushed"] > 0:
            self.task_service.save_tasks_with_sync_info(date, local_tasks)
        
        return result
