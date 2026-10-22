import traceback
from datetime import date, datetime
from typing import TYPE_CHECKING, Union

from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from Storage import StorageInterface
    from features.Journal_Service import JournalService
    from features.Sleep_Service import SleepService
    from features.Task_Service import TaskService
    from features.Task_Sync_Service import TaskSyncService
    from features.Workout_Service import WorkoutService
    from features.Workout_Template_Service import WorkoutTemplateService


def qdate_to_string(qdate: QDate) -> str:
    """
    Convert QDate to "YYYY-MM-DD" string format.
    
    Args:
        qdate: QDate object to convert
        
    Returns:
        Date string in "YYYY-MM-DD" format
    """
    return qdate.toString("yyyy-MM-dd")


def string_to_qdate(date_str: str) -> QDate:
    """
    Convert "YYYY-MM-DD" string to QDate.
    
    Args:
        date_str: Date string in "YYYY-MM-DD" format
        
    Returns:
        QDate object (may be invalid if the string is malformed)
    """
    return QDate.fromString(date_str, "yyyy-MM-dd")


def ensure_qdate(
    value: Union[QDate, str, date, None],
    fallback: QDate | None = None,
) -> QDate:
    """Return a valid QDate, falling back when value is missing or invalid."""
    if fallback is None:
        fallback = QDate.currentDate()
    if isinstance(value, QDate):
        return value if value.isValid() else fallback
    if isinstance(value, str) and value.strip():
        qdate = QDate.fromString(value.strip(), "yyyy-MM-dd")
        return qdate if qdate.isValid() else fallback
    if isinstance(value, date):
        qdate = QDate(value.year, value.month, value.day)
        return qdate if qdate.isValid() else fallback
    return fallback


def safe_set_date(
    date_edit: QDateEdit,
    value: Union[QDate, str, date, None],
    *,
    block_signals: bool = False,
) -> None:
    """Set a QDateEdit date with validation and optional signal blocking."""
    qdate = ensure_qdate(value)
    print(f"safe_set_date: setting {qdate.toString('yyyy-MM-dd')} type={type(value).__name__} block={block_signals}")
    was_blocked = date_edit.signalsBlocked()
    if block_signals:
        date_edit.blockSignals(True)
    try:
        date_edit.setDate(qdate)
    finally:
        date_edit.blockSignals(was_blocked)
    print(f"safe_set_date: done {date_edit.objectName() or id(date_edit)}")


class BackgroundLoadWorker(QThread):
    """Runs task refetch and workout load in background so UI stays responsive."""
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, date_str: str, sync_service, workout_service, journal_service) -> None:
        super().__init__()
        self.date_str = date_str
        self.sync_service = sync_service
        self.workout_service = workout_service
        self.journal_service = journal_service

    def run(self) -> None:
        try:
            task_api = getattr(self.sync_service, "api_client", None)
            if self.sync_service and getattr(task_api, "api_key", None):
                result = self.sync_service.refetch_and_replace_tasks(self.date_str)
                errors = result.get("errors", []) if isinstance(result, dict) else []
                if isinstance(result, dict) and (not result.get("success") or errors):
                    self.error.emit("Task sync failed: " + ("; ".join(errors) or "unknown error"))
            workout_api = getattr(self.workout_service, "api_client", None)
            if self.workout_service and getattr(workout_api, "api_key", None):
                self.workout_service.invalidate_workout_cache()
                success, error = self.workout_service.load_workouts_from_api()
                if not success:
                    self.error.emit(f"Workout sync failed: {error or 'unknown error'}")
            if self.journal_service and getattr(self.journal_service, "uses_api", False):
                result = self.journal_service.sync_from_api(self.date_str)
                if isinstance(result, dict) and not result.get("skipped"):
                    errors = result.get("errors", [])
                    if not result.get("success") or errors:
                        self.error.emit("Journal sync failed: " + ("; ".join(errors) or "unknown error"))
        except Exception as exc:
            # Notify through a Qt signal so the message is handled on the GUI
            # thread without interrupting the queued-date lifecycle.
            self.error.emit(f"Background load failed: {exc}")
        finally:
            self.done.emit(self.date_str)


class MainWindow(QMainWindow):
    """
    Main application window that coordinates all features and manages date navigation.
    """
    
    def __init__(
        self,
        storage: "StorageInterface",
        journal_service: "JournalService",
        task_service: "TaskService",
        workout_service: "WorkoutService",
        sleep_service: "SleepService",
        template_service: "WorkoutTemplateService" = None,
        settings_store=None,
        api_client=None,
    ) -> None:
        """
        Initialize Main Window.
        
        Args:
            storage: StorageInterface instance
            journal_service: JournalService instance
            task_service: TaskService instance
            workout_service: WorkoutService instance
            sleep_service: SleepService instance
            template_service: WorkoutTemplateService instance (optional)
            settings_store: SettingsStore instance (optional)
            api_client: Optional shared APIClient (if None, one is created from settings)
        """
        super().__init__()
        
        self.storage = storage
        self.journal_service = journal_service
        self.task_service = task_service
        self.workout_service = workout_service
        self.sleep_service = sleep_service
        self.template_service = template_service
        self.settings_store = settings_store
        
        # Initialize sync service (use shared api_client if provided)
        from features.Task_Sync_Service import TaskSyncService
        from features.API_Client import APIClient
        if api_client is None and settings_store:
            api_client = APIClient(settings_store.get_api_key())
        self.sync_service = TaskSyncService(task_service, api_client)
        
        # Current date (default to today)
        self.current_date = QDate.currentDate()

        # Only one remote date load may run at a time. Date navigation can happen
        # much faster than the API responds, so retain the active QThread and
        # coalesce additional requests to the most recently selected date.
        self._load_worker: BackgroundLoadWorker | None = None
        self._pending_load_date: str | None = None
        
        # Initialize UI
        self._setup_ui()
        self._setup_menu()
        self._setup_date_navigation()
        self._setup_tabs()
        
        # Add sync menu after sync service is initialized
        self._setup_sync_menu()
        
        # Load today's entry
        self._load_entry_for_date(qdate_to_string(self.current_date))
        
        # Set up auto-sync if enabled
        if self.settings_store:
            if self.settings_store.get_sync_auto_enabled():
                interval = self.settings_store.get_sync_interval_seconds()
                self.tasks_widget.set_auto_sync_enabled(True, interval)
        
        # Set window properties
        self.setWindowTitle("Life Log Journal")
        self.setMinimumSize(800, 600)
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Date display and navigation will be in toolbar
        # Tab widget will be in central area
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
    
    def _setup_menu(self) -> None:
        """Create menu bar with File and View menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Import Sleep Data action
        import_action = QAction("&Import Sleep Data...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.setStatusTip("Import sleep data from Samsung Health CSV file")
        import_action.triggered.connect(self._on_import_sleep_data)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Analytics action
        analytics_action = QAction("&Analytics", self)
        analytics_action.setShortcut(QKeySequence("Ctrl+A"))
        analytics_action.setStatusTip("Show analytics view")
        analytics_action.triggered.connect(self._show_analytics)
        view_menu.addAction(analytics_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("&Settings")
        
        # Settings action
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.setStatusTip("Open settings dialog")
        settings_action.triggered.connect(self._show_settings)
        settings_menu.addAction(settings_action)
    
    def _setup_sync_menu(self) -> None:
        """Set up sync menu (called after sync service is initialized)."""
        if hasattr(self, 'sync_service') and self.sync_service:
            menubar = self.menuBar()
            sync_menu = menubar.addMenu("&Sync")
            
            # Manual sync action
            sync_action = QAction("&Sync Tasks Now", self)
            sync_action.setShortcut(QKeySequence("Ctrl+Shift+S"))  # Changed from Ctrl+S to avoid conflict
            sync_action.setStatusTip("Manually sync tasks with API")
            sync_action.triggered.connect(self._manual_sync_tasks)
            sync_menu.addAction(sync_action)
    
    def _setup_date_navigation(self) -> None:
        """Create date selector and navigation controls."""
        toolbar = QToolBar("Date Navigation")
        toolbar.setObjectName("dateNavigationToolbar")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar#dateNavigationToolbar {
                background: #20242e; border: 1px solid #343b49; spacing: 8px;
                padding: 8px 12px;
            }
            QToolBar#dateNavigationToolbar QPushButton {
                background: #303b4c; color: #f7f9fc; border: 1px solid #526072;
                border-radius: 8px; padding: 8px 13px; font-weight: 600;
            }
            QToolBar#dateNavigationToolbar QPushButton:hover { background: #3c4b60; }
            QToolBar#dateNavigationToolbar QPushButton#dateTodayButton {
                background: #377fd1; color: white; border: 0;
            }
            QToolBar#dateNavigationToolbar QPushButton#dateTodayButton:hover { background: #4c91dd; }
            QDateEdit#main_date_edit {
                background: #171b24; color: #f7f9fc; border: 1px solid #526072;
                border-radius: 9px; padding: 8px 12px; min-width: 170px;
                font-size: 11pt; font-weight: 700;
                selection-background-color: #377fd1;
            }
            QDateEdit#main_date_edit:focus { border: 1px solid #5596e2; }
            QDateEdit#main_date_edit::drop-down {
                subcontrol-origin: padding; subcontrol-position: right center;
                width: 30px; border-left: 1px solid #343b49;
            }
        """)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
        # Previous day button
        prev_button = QPushButton("◀ Prev")
        prev_button.setObjectName("dateNavigationButton")
        prev_button.setToolTip("Previous day (Left Arrow)")
        prev_button.clicked.connect(self._previous_day)
        toolbar.addWidget(prev_button)
        
        # Today button
        today_button = QPushButton("Today")
        today_button.setObjectName("dateTodayButton")
        today_button.setToolTip("Go to today (T)")
        today_button.clicked.connect(self._go_to_today)
        toolbar.addWidget(today_button)
        
        # Date selector
        self.date_edit = QDateEdit()
        self.date_edit.setObjectName("main_date_edit")
        self.date_edit.setCalendarPopup(True)
        safe_set_date(self.date_edit, self.current_date, block_signals=True)
        self.date_edit.setDisplayFormat("MMMM d, yyyy")
        self.date_edit.setToolTip("Choose the day to review across Journal, Tasks, Workouts, and Sleep")
        self.date_edit.calendarWidget().setStyleSheet("""
            QWidget { background: #20242e; color: #f7f9fc; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background: #303b4c; }
            QCalendarWidget QToolButton {
                background: transparent; color: #f7f9fc; border: 0; padding: 6px;
            }
            QCalendarWidget QToolButton:hover { background: #3c4b60; border-radius: 5px; }
            QCalendarWidget QSpinBox {
                background: #171b24; color: #f7f9fc; border: 1px solid #526072;
                border-radius: 5px; padding: 3px;
            }
            QCalendarWidget QTableView {
                background: #20242e; color: #f7f9fc; selection-background-color: #377fd1;
                selection-color: white; alternate-background-color: #252b37;
                gridline-color: #343b49; border: 0;
            }
        """)
        self.date_edit.dateChanged.connect(self._on_date_changed)
        toolbar.addWidget(self.date_edit)
        
        # Next day button
        next_button = QPushButton("Next ▶")
        next_button.setObjectName("dateNavigationButton")
        next_button.setToolTip("Next day (Right Arrow)")
        next_button.clicked.connect(self._next_day)
        toolbar.addWidget(next_button)
        
        toolbar.addSeparator()
        
        # Date display label (formatted)
        self.date_label = QLabel()
        self.date_label.setObjectName("dateNavigationLabel")
        self.date_label.setStyleSheet("color: #aeb8c8; font-weight: 600; padding-left: 8px;")
        self._update_date_label()
        toolbar.addWidget(self.date_label)
    
    def _setup_tabs(self) -> None:
        """Set up tab widget with all feature widgets."""
        # Import widgets
        from GUI.components.Journal_Widget import JournalWidget
        from GUI.components.Tasks_Widget import TasksWidget
        from GUI.components.Workout_Widget import WorkoutWidget
        from GUI.components.Sleep_Widget import SleepWidget
        from GUI.components.Analytics_View import AnalyticsView
        
        # Create widgets
        self.journal_widget = JournalWidget(self.journal_service, self.settings_store)
        self.tasks_widget = TasksWidget(self.task_service, self.sync_service, self.settings_store)
        self.workout_widget = WorkoutWidget(self.workout_service, self.template_service)
        self.sleep_widget = SleepWidget(self.sleep_service)
        self.analytics_widget = AnalyticsView(
            self.journal_service,
            self.task_service,
            self.workout_service,
            self.sleep_service,
        )
        
        # Connect data_saved signals to analytics refresh
        self.journal_widget.data_saved.connect(self._refresh_analytics)
        self.tasks_widget.data_saved.connect(self._refresh_analytics)
        self.workout_widget.data_saved.connect(self._refresh_analytics)
        self.sleep_widget.data_saved.connect(self._refresh_analytics)
        
        # Add tabs
        self.tab_widget.addTab(self.journal_widget, "Journal")
        self.tab_widget.addTab(self.tasks_widget, "Tasks")
        self.tab_widget.addTab(self.workout_widget, "Workout")
        self.tab_widget.addTab(self.sleep_widget, "Sleep")
        self.tab_widget.addTab(self.analytics_widget, "Analytics")
        
        # Connect tab change signal (optional: auto-save on tab change)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
    
    def _update_date_label(self) -> None:
        """Update the date display label with formatted date."""
        # Format: "Thursday, February 8, 2026"
        date_str = self.current_date.toString("dddd, MMMM d, yyyy")
        self.date_label.setText(f"  {date_str}")
    
    def _previous_day(self) -> None:
        """Navigate to previous day."""
        self.current_date = self.current_date.addDays(-1)
        safe_set_date(self.date_edit, self.current_date)
    
    def _next_day(self) -> None:
        """Navigate to next day."""
        self.current_date = self.current_date.addDays(1)
        safe_set_date(self.date_edit, self.current_date)
    
    def _go_to_today(self) -> None:
        """Navigate to today."""
        self.current_date = QDate.currentDate()
        safe_set_date(self.date_edit, self.current_date)
    
    def _on_date_changed(self, qdate: QDate) -> None:
        """
        Handler for date changes - reload all widgets.
        
        Args:
            qdate: New QDate selected
        """
        try:
            if not qdate.isValid():
                print(f"_on_date_changed: ignoring invalid QDate: {qdate}")
                return
            self.current_date = qdate
            self._update_date_label()
            date_str = qdate_to_string(qdate)
            self._load_entry_for_date(date_str)
        except Exception:
            print("_on_date_changed failed:")
            traceback.print_exc()
    
    def _load_entry_for_date(self, date_str: str) -> None:
        """
        Load and populate all widgets with entry data for the given date.
        Tasks and workouts are refetched from API in a background thread.
        """
        if self._load_worker is not None and self._load_worker.isRunning():
            self._pending_load_date = date_str
            self.setCursor(Qt.CursorShape.WaitCursor)
            return

        self._start_background_load(date_str)

    def _start_background_load(self, date_str: str) -> None:
        """Start one date load and retain its worker until the thread finishes."""
        self._load_worker = BackgroundLoadWorker(
            date_str,
            getattr(self, "sync_service", None),
            getattr(self, "workout_service", None),
            getattr(self, "journal_service", None),
        )
        self._load_worker.done.connect(self._on_background_load_done)
        self._load_worker.error.connect(self._on_background_load_error)
        self._load_worker.finished.connect(self._on_background_load_finished)
        self.setCursor(Qt.CursorShape.WaitCursor)
        self._load_worker.start()

    def _on_background_load_done(self, date_str: str) -> None:
        """Called when background refetch/workout load finishes; load widgets on main thread."""
        if date_str != qdate_to_string(self.current_date):
            return
        self.journal_widget.load_entry(date_str)
        self.tasks_widget.load_entry(date_str)
        self.workout_widget.load_entry(date_str)
        self.sleep_widget.load_entry(date_str)

    def _on_background_load_error(self, message: str) -> None:
        """Show background load failures briefly without blocking the UI."""
        self.statusBar().showMessage(message, 10000)

    def _on_background_load_finished(self) -> None:
        """Release a completed worker and run only the newest queued date load."""
        worker = self.sender()
        if worker is not self._load_worker:
            return

        finished_date = self._load_worker.date_str
        self._load_worker.deleteLater()
        self._load_worker = None

        pending_date = self._pending_load_date
        self._pending_load_date = None
        if pending_date and pending_date != finished_date:
            self._start_background_load(pending_date)
        else:
            self.unsetCursor()
    
    def _on_tab_changed(self, index: int) -> None:
        """
        Handler for tab changes (optional: auto-save current tab).
        
        Args:
            index: Index of the newly selected tab
        """
        # Refresh analytics when switching to analytics tab (index 4)
        if index == 4:
            self.analytics_widget.refresh_charts()
    
    def _refresh_analytics(self) -> None:
        """Refresh analytics charts when data is saved."""
        if hasattr(self, 'analytics_widget'):
            self.analytics_widget.refresh_charts()
    
    def _on_import_sleep_data(self) -> None:
        """Open file dialog and trigger CSV import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Sleep Data from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        
        if not file_path:
            return  # User cancelled
        
        # Show progress/status
        QMessageBox.information(
            self,
            "Importing...",
            f"Importing sleep data from:\n{file_path}\n\nPlease wait...",
        )
        
        # Import via sleep service
        result = self.sleep_service.import_from_csv(file_path, skip_existing=True)
        
        # Show results
        message = (
            f"Import completed!\n\n"
            f"Rows processed: {result['rows_processed']}\n"
            f"Rows imported: {result['rows_imported']}\n"
            f"Rows skipped: {result['rows_skipped']}\n"
            f"Errors: {len(result['errors'])}"
        )
        
        if result["errors"]:
            message += f"\n\nErrors:\n" + "\n".join(result["errors"][:10])
            if len(result["errors"]) > 10:
                message += f"\n... and {len(result['errors']) - 10} more errors"
        
        QMessageBox.information(self, "Import Results", message)
        
        # Reload current date's sleep data
        date_str = qdate_to_string(self.current_date)
        self.sleep_widget.load_entry(date_str)
    
    def _show_analytics(self) -> None:
        """Switch to analytics tab."""
        # Switch to analytics tab (index 4)
        self.tab_widget.setCurrentIndex(4)
    
    def _manual_sync_tasks(self) -> None:
        """Manually trigger task sync for current date."""
        if not hasattr(self, 'sync_service') or not self.sync_service:
            QMessageBox.warning(self, "Error", "Sync service not available.")
            return
        if not self.sync_service.api_client.api_key:
            QMessageBox.warning(self, "Sync", "Configure the API key before syncing tasks.")
            return
        
        date_str = qdate_to_string(self.current_date)
        result = self.sync_service.sync_tasks_for_date(date_str)
        
        if result["success"]:
            message = (
                f"Sync completed!\n\n"
                f"Tasks synced: {result['tasks_synced']}\n"
                f"Local tasks uploaded: {result.get('tasks_pushed', 0)}"
            )
            if result["errors"]:
                message += f"\n\nErrors: {len(result['errors'])}"
            QMessageBox.information(self, "Sync Complete", message)
            
            # Refresh tasks widget
            self.tasks_widget.load_entry(date_str)
        else:
            # Show detailed error messages
            if result["errors"]:
                error_msg = "\n".join(result["errors"])
                # Truncate if too long for message box
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "\n\n... (truncated)"
            else:
                error_msg = "Unknown error occurred during sync"
            QMessageBox.warning(self, "Sync Failed", f"Failed to sync tasks:\n\n{error_msg}")
    
    def _show_settings(self) -> None:
        """Open settings dialog."""
        from GUI.components.Settings_Dialog import SettingsDialog
        
        if self.settings_store is None:
            # Create settings store if not provided
            from config.settings_store import SettingsStore
            self.settings_store = SettingsStore()
        
        dialog = SettingsDialog(self.settings_store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Settings were saved (OK clicked)
            # Update API key in sync service if changed
            if hasattr(self, 'sync_service') and self.sync_service:
                new_api_key = self.settings_store.get_api_key()
                if hasattr(self.sync_service, 'api_client'):
                    self.sync_service.api_client.set_api_key(new_api_key)
            
            # Update auto-sync if sync service is available
            if hasattr(self, 'sync_service') and self.sync_service and hasattr(self, 'tasks_widget'):
                auto_enabled = self.settings_store.get_sync_auto_enabled()
                interval = self.settings_store.get_sync_interval_seconds()
                self.tasks_widget.set_auto_sync_enabled(auto_enabled, interval)
            
            # Refresh Analytics if visible
            if hasattr(self, 'analytics_widget') and self.tab_widget.currentIndex() == 4:
                self._refresh_analytics()
    
    def keyPressEvent(self, event) -> None:
        """
        Handle keyboard shortcuts for date navigation.
        
        Args:
            event: Key press event
        """
        if event.key() == Qt.Key.Key_Left:
            self._previous_day()
        elif event.key() == Qt.Key.Key_Right:
            self._next_day()
        elif event.key() == Qt.Key.Key_T:
            self._go_to_today()
        else:
            super().keyPressEvent(event)
