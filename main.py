"""
Application entry point for Life Log Journal GUI.
"""

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from Storage import JSONStorage
from config.settings_store import SettingsStore
from features.API_Client import APIClient
from features.Journal_Service import JournalService
from features.Sleep_Service import SleepService
from features.Task_Service import TaskService
from features.Workout_Service import WorkoutService
from features.Workout_Template_Service import WorkoutTemplateService
from GUI.Main_Window import MainWindow

PROJECT_ROOT = Path(__file__).resolve().parent
APP_ICON_PATH = PROJECT_ROOT / "journal_icon.png"
APP_DESKTOP_NAME = "ernesto-journal"


def configure_application(app: QApplication) -> QIcon | None:
    """Set app identity so launchers/taskbars don't group this with other Python apps."""
    app.setOrganizationName("Ernesto")
    app.setApplicationName("Journal")
    app.setApplicationDisplayName("Journal")
    app.setDesktopFileName(APP_DESKTOP_NAME)

    icon = QIcon(str(APP_ICON_PATH)) if APP_ICON_PATH.is_file() else None
    if icon is not None and not icon.isNull():
        app.setWindowIcon(icon)
    return icon


def main() -> None:
    """Main application entry point."""
    # Use a stable argv[0] on Linux so WM_CLASS matches the .desktop StartupWMClass.
    if sys.platform.startswith("linux"):
        sys.argv[0] = APP_DESKTOP_NAME

    # Initialize storage
    storage = JSONStorage("data/lifelog.json")
    
    # Initialize settings store
    settings_store = SettingsStore()
    api_client = APIClient(settings_store.get_api_key())
    
    # Initialize services
    journal_service = JournalService(storage, api_client)
    task_service = TaskService(storage)
    workout_service = WorkoutService(storage, api_client)
    sleep_service = SleepService(storage)
    
    # Initialize template service (separate from storage, uses its own file)
    template_service = WorkoutTemplateService("data/workout_templates.json")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app_icon = configure_application(app)
    
    # Create and show main window (shared api_client for tasks sync and workout service)
    window = MainWindow(
        storage=storage,
        journal_service=journal_service,
        task_service=task_service,
        workout_service=workout_service,
        sleep_service=sleep_service,
        template_service=template_service,
        settings_store=settings_store,
        api_client=api_client,
    )
    if app_icon is not None:
        window.setWindowIcon(app_icon)
    window.show()
    
    # Run application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

