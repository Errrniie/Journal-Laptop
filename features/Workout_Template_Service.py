import json
from pathlib import Path
from typing import Optional

# #region agent log
import json as json_module
LOG_PATH = "/home/LxSparda/Desktop/Journal/.cursor/debug.log"
def _log(service, method, message, data=None, hypothesis_id=None):
    try:
        with open(LOG_PATH, 'a') as f:
            log_entry = {
                "sessionId": "template-test",
                "runId": "run1",
                "hypothesisId": hypothesis_id or "A",
                "location": f"Workout_Template_Service.py:{service}.{method}",
                "message": message,
                "data": data or {},
                "timestamp": __import__('time').time() * 1000
            }
            f.write(json_module.dumps(log_entry) + "\n")
    except: pass
# #endregion


class WorkoutTemplateService:
    """
    Service for managing workout templates.
    Handles CRUD operations for workout templates stored in JSON format.
    Templates are workouts without a date field, allowing users to save
    and reuse workout structures.
    """
    
    def __init__(self, file_path: str = "data/workout_templates.json") -> None:
        """
        Initialize Workout Template Service.
        
        Args:
            file_path: Path to JSON file for template storage. Defaults to "data/workout_templates.json"
        """
        self.file_path = Path(file_path)
        # Create parent directories if they don't exist
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure file exists
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Create empty JSON file if it doesn't exist."""
        if not self.file_path.exists():
            with open(self.file_path, 'w') as f:
                json.dump({}, f)
    
    def _load_templates(self) -> dict:
        """
        Load templates from JSON file.
        Handles missing file / invalid JSON by treating as empty dict ({}).
        
        Returns:
            Dictionary with template names as keys and template data as values
        """
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # File doesn't exist, return empty dict (treat as {})
            return {}
        except json.JSONDecodeError:
            # Handle corrupted JSON - treat as {} for recovery
            return {}
    
    def _save_templates(self, templates: dict) -> bool:
        """
        Save templates to JSON file.
        Uses atomic write (temporary file then rename) for safety.
        
        Args:
            templates: Dictionary of templates to save
            
        Returns:
            True on success, False on error
        """
        temp_path = self.file_path.with_suffix('.tmp')
        try:
            # Write to temporary file first, then rename (atomic operation)
            with open(temp_path, 'w') as f:
                json.dump(templates, f, indent=2)
            temp_path.replace(self.file_path)
            return True
        except Exception:
            # Error handling - clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass  # Ignore cleanup errors
            return False
    
    def list_templates(self) -> list[str]:
        """
        Return list of template names.
        
        Returns:
            List of template names (keys) in storage, sorted alphabetically
        """
        # #region agent log
        _log("WorkoutTemplateService", "list_templates", "ENTRY", {}, "A")
        # #endregion
        templates = self._load_templates()
        result = sorted(templates.keys())
        # #region agent log
        _log("WorkoutTemplateService", "list_templates", "EXIT", {"count": len(result), "names": result}, "A")
        # #endregion
        return result
    
    def get_template(self, name: str) -> Optional[dict]:
        """
        Load one template by name.
        
        Args:
            name: Template name to retrieve
            
        Returns:
            Template data dictionary if found, None otherwise
        """
        # #region agent log
        _log("WorkoutTemplateService", "get_template", "ENTRY", {"name": name}, "A")
        # #endregion
        if not name or not name.strip():
            # #region agent log
            _log("WorkoutTemplateService", "get_template", "EXIT", {"result": None, "reason": "empty_name"}, "A")
            # #endregion
            return None
        
        templates = self._load_templates()
        result = templates.get(name.strip())
        # #region agent log
        _log("WorkoutTemplateService", "get_template", "EXIT", {"result": "found" if result else "not_found", "has_date_field": "date" in result if result else False, "keys": list(result.keys()) if result else []}, "B")
        # #endregion
        return result
    
    def save_template(self, name: str, data: dict) -> bool:
        """
        Save or overwrite a template.
        
        Args:
            name: Template name
            data: Template data dictionary (muscle_groups, exercises, duration_minutes, notes)
                  Should not include 'date' field
            
        Returns:
            True on success, False on error
        """
        # #region agent log
        _log("WorkoutTemplateService", "save_template", "ENTRY", {"name": name, "data_keys": list(data.keys()), "has_date": "date" in data}, "B")
        # #endregion
        if not name or not name.strip():
            # #region agent log
            _log("WorkoutTemplateService", "save_template", "EXIT", {"result": False, "reason": "empty_name"}, "B")
            # #endregion
            return False
        
        name = name.strip()
        templates = self._load_templates()
        existed_before = name in templates
        
        # Remove 'date' field if present (templates don't have dates)
        template_data = {k: v for k, v in data.items() if k != 'date'}
        
        # #region agent log
        _log("WorkoutTemplateService", "save_template", "BEFORE_SAVE", {"existed_before": existed_before, "final_keys": list(template_data.keys()), "exercise_count": len(template_data.get("exercises", []))}, "B")
        # #endregion
        
        # Save template
        templates[name] = template_data
        
        result = self._save_templates(templates)
        # #region agent log
        _log("WorkoutTemplateService", "save_template", "EXIT", {"result": result}, "B")
        # #endregion
        return result
    
    def delete_template(self, name: str) -> bool:
        """
        Remove a template by name.
        
        Args:
            name: Template name to delete
            
        Returns:
            True if template was deleted, False if not found or error
        """
        # #region agent log
        _log("WorkoutTemplateService", "delete_template", "ENTRY", {"name": name}, "A")
        # #endregion
        if not name or not name.strip():
            # #region agent log
            _log("WorkoutTemplateService", "delete_template", "EXIT", {"result": False, "reason": "empty_name"}, "A")
            # #endregion
            return False
        
        name = name.strip()
        templates = self._load_templates()
        
        if name not in templates:
            # #region agent log
            _log("WorkoutTemplateService", "delete_template", "EXIT", {"result": False, "reason": "not_found"}, "A")
            # #endregion
            return False
        
        del templates[name]
        result = self._save_templates(templates)
        # #region agent log
        _log("WorkoutTemplateService", "delete_template", "EXIT", {"result": result}, "A")
        # #endregion
        return result
    
    def template_exists(self, name: str) -> bool:
        """
        Check if a template name already exists.
        
        Args:
            name: Template name to check
            
        Returns:
            True if template exists, False otherwise
        """
        # #region agent log
        _log("WorkoutTemplateService", "template_exists", "ENTRY", {"name": name}, "A")
        # #endregion
        if not name or not name.strip():
            # #region agent log
            _log("WorkoutTemplateService", "template_exists", "EXIT", {"result": False}, "A")
            # #endregion
            return False
        
        templates = self._load_templates()
        result = name.strip() in templates
        # #region agent log
        _log("WorkoutTemplateService", "template_exists", "EXIT", {"result": result}, "A")
        # #endregion
        return result
