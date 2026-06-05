from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QDate, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from GUI.Main_Window import qdate_to_string, string_to_qdate
from GUI.components.Star_Rating_Widget import StarRatingWidget
from GUI.components.Task_Notes_Dialog import TaskNotesDialog

if TYPE_CHECKING:
    from Models import Task
    from config.settings_store import SettingsStore
    from features.Task_Service import TaskService
    from features.Task_Sync_Service import TaskSyncService


class TaskItemWidget(QWidget):
    """
    Custom widget for displaying a single task item.
    """
    
    def __init__(self, task: "Task", task_index: int, parent=None) -> None:
        """
        Initialize Task Item Widget.
        
        Args:
            task: Task object to display
            task_index: Index of task in the list
            parent: Parent widget
        """
        super().__init__(parent)
        self.task = task
        self.task_index = task_index
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Checkbox for completion status
        self.completed_checkbox = QCheckBox()
        self.completed_checkbox.setChecked(self.task.completed)
        layout.addWidget(self.completed_checkbox)
        
        # Task name label
        self.name_label = QLabel(self.task.name)
        self.name_label.setWordWrap(True)
        if self.task.completed:
            self.name_label.setStyleSheet("text-decoration: line-through; color: gray;")
        layout.addWidget(self.name_label, stretch=2)
        
        # Priority indicator
        priority_colors = {
            1: "#4CAF50",  # Green
            2: "#8BC34A",  # Light Green
            3: "#FFC107",  # Amber
            4: "#FF9800",  # Orange
            5: "#F44336",  # Red
        }
        priority_stars = "★" * self.task.Priority
        priority_label = QLabel(priority_stars)
        priority_label.setStyleSheet(f"color: {priority_colors.get(self.task.Priority, '#000000')}; font-weight: bold;")
        priority_label.setMinimumWidth(60)
        layout.addWidget(priority_label)
        
        # Due date label
        due_date_label = QLabel(self.task.Due_Date if self.task.Due_Date else "No due date")
        due_date_label.setMinimumWidth(100)
        
        # Highlight overdue dates in red
        if self.task.Due_Date:
            try:
                due_date = datetime.strptime(self.task.Due_Date, "%Y-%m-%d").date()
                today = date.today()
                if due_date < today and not self.task.completed:
                    due_date_label.setStyleSheet("color: red; font-weight: bold;")
                elif due_date == today:
                    due_date_label.setStyleSheet("color: orange; font-weight: bold;")
            except ValueError:
                pass
        
        layout.addWidget(due_date_label)
        
        # Notes indicator button (always visible – click to view/edit notes)
        self.notes_button = QPushButton()
        self.notes_button.setMaximumSize(24, 24)
        self.notes_button.setToolTip("View/Edit notes")
        self.notes_button.setText("📝")
        self.notes_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                background-color: #F0F0F0;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #E0E0E0;
            }
        """)
        layout.addWidget(self.notes_button)
        
        # Delete button
        self.delete_button = QPushButton("Delete")
        self.delete_button.setMaximumWidth(70)
        layout.addWidget(self.delete_button)


class TasksWidget(QWidget):
    """
    Interactive task checklist widget with add/edit/delete functionality.
    """
    
    # Signal emitted when task data is saved (added, updated, or deleted)
    data_saved = pyqtSignal()
    
    def __init__(self, task_service: "TaskService", sync_service: Optional["TaskSyncService"] = None, settings_store: Optional["SettingsStore"] = None) -> None:
        """
        Initialize Tasks Widget.
        
        Args:
            task_service: TaskService instance for data operations
            sync_service: TaskSyncService instance for API sync (optional)
            settings_store: Optional SettingsStore instance for accessing settings
        """
        super().__init__()
        
        self.task_service = task_service
        self.sync_service = sync_service
        self.settings_store = settings_store
        self.current_date: str | None = None
        self.task_widgets: list[TaskItemWidget] = []
        
        # Auto-sync timer (optional)
        self.auto_sync_timer = QTimer()
        self.auto_sync_timer.timeout.connect(self._auto_sync_tasks)
        self.auto_sync_timer.setSingleShot(False)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Add Task Section
        add_task_group = QGroupBox("Add New Task")
        add_task_layout = QVBoxLayout(add_task_group)
        add_task_layout.setSpacing(5)
        
        # Task name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Task Name:"))
        self.task_name_edit = QLineEdit()
        self.task_name_edit.setPlaceholderText("Enter task name...")
        name_layout.addWidget(self.task_name_edit)
        add_task_layout.addLayout(name_layout)
        
        # Priority and Due Date row
        priority_date_layout = QHBoxLayout()
        
        # Priority - Star Rating Widget
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority:"))
        self.star_rating = StarRatingWidget()
        self.star_rating.set_rating(3)  # Default to 3 stars
        self.star_rating.setToolTip("Click stars to set priority (1 = Low, 5 = High)")
        priority_layout.addWidget(self.star_rating)
        priority_layout.addStretch()
        priority_date_layout.addLayout(priority_layout)
        
        # Due Date
        due_date_layout = QHBoxLayout()
        due_date_layout.addWidget(QLabel("Due Date:"))
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate())
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")
        due_date_layout.addWidget(self.due_date_edit)
        due_date_layout.addStretch()
        priority_date_layout.addLayout(due_date_layout)
        
        add_task_layout.addLayout(priority_date_layout)
        
        # Notes (optional)
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(QLabel("Notes (optional):"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("Add notes...")
        notes_layout.addWidget(self.notes_edit)
        add_task_layout.addLayout(notes_layout)
        
        # Add Task button
        add_button = QPushButton("Add Task")
        add_button.clicked.connect(self._add_task)
        add_task_layout.addWidget(add_button)
        
        main_layout.addWidget(add_task_group)
        
        # Tasks List Section
        tasks_group = QGroupBox("Tasks")
        tasks_layout = QVBoxLayout(tasks_group)
        
        # Task count, Sync button, and Clear Completed button
        header_layout = QHBoxLayout()
        self.task_count_label = QLabel("0/0 completed")
        header_layout.addWidget(self.task_count_label)
        header_layout.addStretch()
        
        # Sync button and status
        if self.sync_service:
            self.sync_button = QPushButton("Sync")
            self.sync_button.clicked.connect(self._sync_tasks)
            header_layout.addWidget(self.sync_button)
            
            self.sync_status_label = QLabel("")
            self.sync_status_label.setStyleSheet("color: gray; font-size: 9pt;")
            header_layout.addWidget(self.sync_status_label)
        
        clear_completed_button = QPushButton("Clear Completed")
        clear_completed_button.clicked.connect(self._clear_completed)
        header_layout.addWidget(clear_completed_button)
        
        tasks_layout.addLayout(header_layout)
        
        # Scrollable area for tasks
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(5)
        self.tasks_layout.addStretch()
        
        scroll_area.setWidget(self.tasks_container)
        tasks_layout.addWidget(scroll_area)
        
        main_layout.addWidget(tasks_group, stretch=1)
    
    def _add_task(self) -> None:
        """Add new task from form inputs."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        if not self.sync_service:
            QMessageBox.warning(self, "Error", "Sync service not available.")
            return
        
        # Get form values
        task_name = self.task_name_edit.text().strip()
        if not task_name:
            QMessageBox.warning(self, "Invalid Input", "Task name cannot be empty.")
            return
        
        priority = self.star_rating.get_rating()  # Get from star widget instead of spinbox
        due_date_qdate = self.due_date_edit.date()
        due_date_str = qdate_to_string(due_date_qdate) if due_date_qdate.isValid() else None
        notes = self.notes_edit.toPlainText().strip()
        
        # Convert due_date to ISO format if provided
        due_at = None
        if due_date_str:
            try:
                from datetime import datetime
                due_date_obj = datetime.strptime(due_date_str, "%Y-%m-%d")
                due_at = due_date_obj.strftime("%Y-%m-%dT23:59:59.490Z")
            except (ValueError, AttributeError):
                pass
        
        # Create task on API and refetch (server is source of truth)
        result = self.sync_service.create_task_and_refetch(
            date=self.current_date,
            title=task_name,
            description=notes,
            category="",
            priority=priority,
            due_at=due_at
        )
        
        if result["success"]:
            # Clear form but preserve due date
            self.task_name_edit.clear()
            self.star_rating.set_rating(3)  # Reset to default
            # Don't reset due date - keep the selected date
            # self.due_date_edit.setDate(QDate.currentDate())  # Removed - preserve selected date
            self.notes_edit.clear()
            
            # Refresh task list (tasks already replaced by refetch)
            self._refresh_task_list()
            
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            error_msg = "\n".join(result["errors"]) if result["errors"] else "Unknown error"
            QMessageBox.warning(self, "Error", f"Failed to create task:\n\n{error_msg}")
    
    def _delete_task(self, task_index: int) -> None:
        """Remove task at index."""
        if not self.current_date:
            return
        
        if not self.sync_service:
            QMessageBox.warning(self, "Error", "Sync service not available.")
            return
        
        # Get task to find its ID
        tasks = self.task_service.get_tasks(self.current_date)
        if task_index < 0 or task_index >= len(tasks):
            QMessageBox.warning(self, "Error", "Invalid task index.")
            return
        
        task = tasks[task_index]
        if not task.activity_id:
            QMessageBox.warning(self, "Error", "Task does not have an ID. Cannot delete from server.")
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Task",
            "Are you sure you want to delete this task?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete task on API and refetch (server is source of truth)
            result = self.sync_service.delete_task_and_refetch(
                date=self.current_date,
                task_id=task.activity_id
            )
            
            if result["success"]:
                # Refresh task list (tasks already replaced by refetch)
                self._refresh_task_list()
                # Emit signal to trigger analytics refresh
                self.data_saved.emit()
            else:
                error_msg = "\n".join(result["errors"]) if result["errors"] else "Unknown error"
                QMessageBox.warning(self, "Error", f"Failed to delete task:\n\n{error_msg}")
    
    def _toggle_task(self, task_index: int, checked: bool) -> None:
        """Toggle task completion status."""
        if not self.current_date:
            return
        
        if not self.sync_service:
            QMessageBox.warning(self, "Error", "Sync service not available.")
            return
        
        # Get task to find its ID
        tasks = self.task_service.get_tasks(self.current_date)
        if task_index < 0 or task_index >= len(tasks):
            return
        
        task = tasks[task_index]
        if not task.activity_id:
            # Task doesn't have ID yet - update locally and sync will handle it
            success = self.task_service.update_task(self.current_date, task_index, completed=checked)
            if success:
                self._refresh_task_list()
                self.data_saved.emit()
            return
        
        # Use POST /tasks/{id}/complete when marking complete; record for pending
        if checked:
            result = self.sync_service.complete_task_and_refetch(self.current_date, task.activity_id)
        else:
            record_data = {"status": "pending", "source": "linux"}
            if task.Notes:
                record_data["comment"] = task.Notes
            _, record_error = self.sync_service.api_client.create_record(
                activity_id=task.activity_id, data=record_data
            )
            if record_error:
                QMessageBox.warning(self, "Error", f"Failed to update task status: {record_error}")
                return
            result = self.sync_service.refetch_and_replace_tasks(self.current_date)
        if result["success"]:
            self._refresh_task_list()
            self.data_saved.emit()
        else:
            error_msg = "\n".join(result["errors"]) if result["errors"] else "Unknown error"
            QMessageBox.warning(self, "Error", f"Failed to sync after update:\n\n{error_msg}")
    
    def _clear_completed(self) -> None:
        """Remove all completed tasks via API then refetch."""
        if not self.current_date:
            return
        if not self.sync_service:
            QMessageBox.warning(self, "Error", "Sync service not available.")
            return
        reply = QMessageBox.question(
            self,
            "Clear Completed",
            "Are you sure you want to remove all completed tasks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.sync_service.clear_completed_and_refetch(self.current_date)
            if result["success"]:
                self._refresh_task_list()
                self.data_saved.emit()
            if result["errors"]:
                QMessageBox.warning(
                    self, "Clear Completed",
                    "Some tasks could not be deleted:\n\n" + "\n".join(result["errors"][:5])
                )
    
    def _refresh_task_list(self) -> None:
        """Reload and display tasks."""
        # Clear existing task widgets
        for widget in self.task_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.task_widgets.clear()
        
        if not self.current_date:
            self.task_count_label.setText("0/0 completed")
            return
        
        # Load tasks from service
        tasks = self.task_service.get_tasks(self.current_date)
        
        # Create task item widgets
        for index, task in enumerate(tasks):
            task_widget = TaskItemWidget(task, index)
            
            # Connect signals
            task_widget.completed_checkbox.stateChanged.connect(
                lambda state, idx=index: self._toggle_task(idx, state == Qt.CheckState.Checked.value)
            )
            
            # Connect notes button (always – view/edit notes for any task)
            task_widget.notes_button.clicked.connect(
                lambda checked=False, idx=index: self._show_notes_dialog(idx)
            )
            
            task_widget.delete_button.clicked.connect(
                lambda checked=False, idx=index: self._delete_task(idx)
            )
            
            self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, task_widget)
            self.task_widgets.append(task_widget)
        
        # Update task count
        completed_count = sum(1 for task in tasks if task.completed)
        total_count = len(tasks)
        self.task_count_label.setText(f"{completed_count}/{total_count} completed")
    
    def _show_notes_dialog(self, task_index: int) -> None:
        """
        Open dialog to view/edit task notes.
        
        Args:
            task_index: Index of the task in the list
        """
        if not self.current_date:
            return
        
        # Get task
        tasks = self.task_service.get_tasks(self.current_date)
        if task_index >= len(tasks):
            return
        
        task = tasks[task_index]
        
        # Create and show dialog
        dialog = TaskNotesDialog(task.name, task.Notes or "")
        
        success = False
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save updated notes
            new_notes = dialog.get_notes()
            success = self.task_service.update_task(
                self.current_date,
                task_index,
                notes=new_notes
            )
            
            if success:
                self._refresh_task_list()
                # Emit signal to trigger analytics refresh
                self.data_saved.emit()
            else:
                QMessageBox.warning(self, "Error", "Failed to update notes.")
    
    def _sync_tasks(self) -> None:
        """Sync tasks with API for current date."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        if not self.sync_service:
            QMessageBox.warning(self, "Error", "Sync service not available.")
            return
        
        # Update UI to show syncing
        self.sync_button.setEnabled(False)
        self.sync_status_label.setText("Syncing...")
        self.sync_status_label.setStyleSheet("color: blue; font-size: 9pt;")
        
        # Perform sync
        result = self.sync_service.sync_tasks_for_date(self.current_date)
        
        # Update UI based on result
        self.sync_button.setEnabled(True)
        
        if result["success"]:
            self.sync_status_label.setText(f"Synced: {result['tasks_synced']} tasks")
            self.sync_status_label.setStyleSheet("color: green; font-size: 9pt;")
            
            # Refresh task list to show synced data
            self._refresh_task_list()
            
            # Show summary message
            tasks_changed = result.get("tasks_synced", 0) + result.get("tasks_pushed", 0)
            if tasks_changed > 0:
                message = (
                    f"Sync completed!\n\n"
                    f"Tasks synced: {result.get('tasks_synced', 0)}\n"
                    f"Tasks added: {result.get('tasks_added', 0)}\n"
                    f"Tasks updated: {result.get('tasks_updated', 0)}\n"
                    f"Tasks pushed: {result.get('tasks_pushed', 0)}"
                )
                if result["errors"]:
                    message += f"\n\nErrors: {len(result['errors'])}"
                QMessageBox.information(self, "Sync Complete", message)
            else:
                QMessageBox.information(self, "Sync Complete", "No tasks found to sync for this date.")
            
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            # Show detailed error messages
            if result["errors"]:
                # Show all errors, not just first 3
                error_msg = "\n".join(result["errors"])
                # Truncate if too long for message box
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "\n\n... (truncated)"
            else:
                error_msg = "Unknown error occurred during sync"
            
            self.sync_status_label.setText("Sync failed")
            self.sync_status_label.setStyleSheet("color: red; font-size: 9pt;")
            QMessageBox.warning(
                self, 
                "Sync Failed", 
                f"Failed to sync tasks:\n\n{error_msg}"
            )
        
        # Clear status message after 5 seconds
        QTimer.singleShot(5000, lambda: self.sync_status_label.setText(""))
    
    def _auto_sync_tasks(self) -> None:
        """Auto-sync tasks (called by timer)."""
        if self.current_date and self.sync_service:
            # Only sync if Tasks tab is likely active (we can't check tab directly here)
            # Sync silently without showing messages
            result = self.sync_service.sync_tasks_for_date(self.current_date)
            if result["success"] and result["tasks_synced"] > 0:
                self._refresh_task_list()
                # Update status label briefly
                self.sync_status_label.setText(f"Auto-synced: {result['tasks_synced']} tasks")
                self.sync_status_label.setStyleSheet("color: green; font-size: 9pt;")
                QTimer.singleShot(3000, lambda: self.sync_status_label.setText(""))
                self.data_saved.emit()
    
    def set_auto_sync_enabled(self, enabled: bool, interval_seconds: int = 60) -> None:
        """
        Enable or disable auto-sync.
        
        Args:
            enabled: True to enable auto-sync, False to disable
            interval_seconds: Sync interval in seconds (default 60)
        """
        if enabled and self.sync_service:
            self.auto_sync_timer.start(interval_seconds * 1000)  # Convert to milliseconds
        else:
            self.auto_sync_timer.stop()
    
    def load_entry(self, date: str) -> None:
        """
        Load tasks for the given date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
        """
        self.current_date = date
        
        # Update due date selector to match the current view date
        # This way the due date automatically follows the day you're viewing
        if date:
            try:
                qdate = string_to_qdate(date)
                if qdate.isValid():
                    self.due_date_edit.setDate(qdate)
            except (ValueError, AttributeError):
                # If date conversion fails, use current date as fallback
                self.due_date_edit.setDate(QDate.currentDate())
        
        self._refresh_task_list()
