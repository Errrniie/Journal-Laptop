"""
Application entry point for Life Log Journal GUI.
"""

import sys

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


def main() -> None:
    """Main application entry point."""
    # Initialize storage
    storage = JSONStorage("data/lifelog.json")
    
    # Initialize settings store
    settings_store = SettingsStore()
    api_client = APIClient(settings_store.get_api_key())
    
    # Initialize services
    journal_service = JournalService(storage)
    task_service = TaskService(storage)
    workout_service = WorkoutService(storage, api_client)
    sleep_service = SleepService(storage)
    
    # Initialize template service (separate from storage, uses its own file)
    template_service = WorkoutTemplateService("data/workout_templates.json")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Life Log Journal")
    
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
    window.show()
    
    # Run application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

