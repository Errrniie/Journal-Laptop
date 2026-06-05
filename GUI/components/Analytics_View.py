from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.collections import PathCollection
from matplotlib.figure import Figure
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from GUI.Main_Window import qdate_to_string, string_to_qdate

if TYPE_CHECKING:
    from features.Journal_Service import JournalService
    from features.Sleep_Service import SleepService
    from features.Task_Service import TaskService
    from features.Workout_Service import WorkoutService


class AnalyticsView(QWidget):
    """
    Analytics widget displaying charts and statistics using matplotlib.
    """
    
    def __init__(
        self,
        journal_service: "JournalService",
        task_service: "TaskService",
        workout_service: "WorkoutService",
        sleep_service: "SleepService",
    ) -> None:
        """
        Initialize Analytics View.
        
        Args:
            journal_service: JournalService instance
            task_service: TaskService instance
            workout_service: WorkoutService instance
            sleep_service: SleepService instance
        """
        super().__init__()
        
        self.journal_service = journal_service
        self.task_service = task_service
        self.workout_service = workout_service
        self.sleep_service = sleep_service
        
        # Get storage from one of the services to access get_entries_range
        self.storage = workout_service.storage
        
        self._setup_ui()
        
        # Week navigation state for "By Days" view
        # Start with current week (initialize after _setup_ui so methods are available)
        today = date.today()
        self.current_week_start = self._get_week_start(today)
        
        # Month navigation state for "By Month" view
        # Start with current month (initialize after _setup_ui so methods are available)
        self.current_month_start = self._get_month_start(today)
        
        # Volume week navigation state for "By Week" view
        # Start with 4-week block containing today (current week and 3 preceding weeks)
        self.volume_week_window_start = self._get_week_start_for_volume(today)
        
        # Volume month navigation state for "By Month" view
        # Start with 4-month block containing today (current month and 3 preceding months)
        self.volume_month_window_start = self._get_month_start_for_volume(today)
        
        # Set default date range (last 30 days)
        end_date = QDate.currentDate()
        start_date = end_date.addDays(-29)
        self.start_date_edit.setDate(start_date)
        self.end_date_edit.setDate(end_date)
        
        # Update week label after UI is set up
        self._update_week_label()
        
        # Update month label after UI is set up
        self._update_month_label()
        
        # Update volume week label after UI is set up
        self._update_volume_week_label()
        
        # Update volume month label after UI is set up
        self._update_volume_month_label()
        
        # Initialize navigation widget visibility based on default button states
        # This ensures the correct nav widgets are shown/hidden on startup
        # (handlers will call _on_update_charts(), so we don't need to call it separately)
        self._on_frequency_view_changed()
        self._on_volume_period_changed()
    
    def _setup_ui(self) -> None:
        """Create chart tabs and matplotlib canvas."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Date Range Selector
        date_range_layout = QHBoxLayout()
        date_range_layout.addWidget(QLabel("Start Date:"))
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.start_date_edit)
        
        date_range_layout.addWidget(QLabel("End Date:"))
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.end_date_edit)
        
        # Auto-refresh when date range changes
        self.start_date_edit.dateChanged.connect(self._on_update_charts)
        self.end_date_edit.dateChanged.connect(self._on_update_charts)
        
        date_range_layout.addStretch()
        
        main_layout.addLayout(date_range_layout)
        
        # Chart Tabs
        self.chart_tabs = QTabWidget()
        
        # Create tabs with controls and matplotlib canvases
        self.workout_freq_canvas = self._create_canvas()
        self.volume_muscle_canvas = self._create_canvas()
        self.sleep_trends_canvas = self._create_canvas()
        self.task_completion_canvas = self._create_canvas()
        
        # Workout Frequency Tab with view mode selector
        workout_freq_tab_widget = QWidget()
        workout_freq_tab_layout = QVBoxLayout(workout_freq_tab_widget)
        workout_freq_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # View mode selector (buttons instead of dropdown)
        freq_control_layout = QHBoxLayout()
        freq_control_layout.addWidget(QLabel("View:"))
        
        # Create button group for exclusive selection
        self.frequency_button_group = QButtonGroup()
        self.frequency_button_group.setExclusive(True)
        
        # Create three checkable buttons
        self.frequency_by_days_button = QPushButton("By Days")
        self.frequency_by_days_button.setCheckable(True)
        self.frequency_button_group.addButton(self.frequency_by_days_button)
        freq_control_layout.addWidget(self.frequency_by_days_button)
        
        self.frequency_by_month_button = QPushButton("By Month")
        self.frequency_by_month_button.setCheckable(True)
        self.frequency_by_month_button.setChecked(True)  # Default
        self.frequency_button_group.addButton(self.frequency_by_month_button)
        freq_control_layout.addWidget(self.frequency_by_month_button)
        
        self.frequency_whole_year_button = QPushButton("Whole Year Summary")
        self.frequency_whole_year_button.setCheckable(True)
        self.frequency_button_group.addButton(self.frequency_whole_year_button)
        freq_control_layout.addWidget(self.frequency_whole_year_button)
        
        # Connect button clicks to handler
        self.frequency_button_group.buttonClicked.connect(self._on_frequency_view_changed)
        
        # Add styling for checked state
        button_style = """
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #888;
                border-radius: 3px;
                background-color: #808080;
                color: white;
            }
            QPushButton:checked {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #707070;
            }
            QPushButton:checked:hover {
                background-color: #357abd;
            }
        """
        self.frequency_by_days_button.setStyleSheet(button_style)
        self.frequency_by_month_button.setStyleSheet(button_style)
        self.frequency_whole_year_button.setStyleSheet(button_style)
        
        freq_control_layout.addStretch()
        
        workout_freq_tab_layout.addLayout(freq_control_layout)
        
        # Week navigation controls (for "By Days" view)
        week_nav_layout = QHBoxLayout()
        self.prev_week_button = QPushButton("← Previous Week")
        self.prev_week_button.clicked.connect(self._previous_week)
        week_nav_layout.addWidget(self.prev_week_button)
        
        self.week_label = QLabel("Week of ...")
        self.week_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        week_nav_layout.addWidget(self.week_label, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.next_week_button = QPushButton("Next Week →")
        self.next_week_button.clicked.connect(self._next_week)
        week_nav_layout.addWidget(self.next_week_button)
        
        # Initially hide week navigation (shown only for "By Days")
        self.week_nav_widget = QWidget()
        self.week_nav_widget.setLayout(week_nav_layout)
        self.week_nav_widget.setVisible(False)
        workout_freq_tab_layout.addWidget(self.week_nav_widget)
        
        # Month navigation controls (for "By Month" view)
        month_nav_layout = QHBoxLayout()
        self.prev_month_button = QPushButton("← Previous Month")
        self.prev_month_button.clicked.connect(self._previous_month)
        month_nav_layout.addWidget(self.prev_month_button)
        
        self.month_label = QLabel("January 2025")
        self.month_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        month_nav_layout.addWidget(self.month_label, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.next_month_button = QPushButton("Next Month →")
        self.next_month_button.clicked.connect(self._next_month)
        month_nav_layout.addWidget(self.next_month_button)
        
        # Initially hide month navigation (shown only for "By Month")
        self.month_nav_widget = QWidget()
        self.month_nav_widget.setLayout(month_nav_layout)
        self.month_nav_widget.setVisible(False)
        workout_freq_tab_layout.addWidget(self.month_nav_widget)
        
        # Year selector for "Whole Year Summary" view
        year_selector_layout = QHBoxLayout()
        year_selector_layout.addWidget(QLabel("Year:"))
        self.year_selector = QComboBox()
        # Add years from 2020 to current year + 1
        current_year = date.today().year
        for year in range(2020, current_year + 2):
            self.year_selector.addItem(str(year))
        self.year_selector.setCurrentText(str(current_year))  # Default to current year
        self.year_selector.currentTextChanged.connect(self._on_update_charts)
        year_selector_layout.addWidget(self.year_selector)
        year_selector_layout.addStretch()
        
        # Initially hide year selector (shown only for "Whole Year Summary")
        self.year_selector_widget = QWidget()
        self.year_selector_widget.setLayout(year_selector_layout)
        self.year_selector_widget.setVisible(False)
        workout_freq_tab_layout.addWidget(self.year_selector_widget)
        
        workout_freq_tab_layout.addWidget(self.workout_freq_canvas)
        
        self.chart_tabs.addTab(workout_freq_tab_widget, "Workout Frequency")
        
        # Volume by Muscle Group Tab with period selector
        volume_tab_widget = QWidget()
        volume_tab_layout = QVBoxLayout(volume_tab_widget)
        volume_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # Period selector (buttons instead of dropdown)
        volume_control_layout = QHBoxLayout()
        volume_control_layout.addWidget(QLabel("Period:"))
        
        # Create button group for exclusive selection
        self.volume_button_group = QButtonGroup()
        self.volume_button_group.setExclusive(True)
        
        # Create three checkable buttons
        self.volume_total_button = QPushButton("Total")
        self.volume_total_button.setCheckable(True)
        self.volume_total_button.setChecked(True)  # Default
        self.volume_button_group.addButton(self.volume_total_button)
        volume_control_layout.addWidget(self.volume_total_button)
        
        self.volume_by_week_button = QPushButton("By Week")
        self.volume_by_week_button.setCheckable(True)
        self.volume_button_group.addButton(self.volume_by_week_button)
        volume_control_layout.addWidget(self.volume_by_week_button)
        
        self.volume_by_month_button = QPushButton("By Month")
        self.volume_by_month_button.setCheckable(True)
        self.volume_button_group.addButton(self.volume_by_month_button)
        volume_control_layout.addWidget(self.volume_by_month_button)
        
        # Connect button clicks to handler
        self.volume_button_group.buttonClicked.connect(self._on_volume_period_changed)
        
        # Add styling for checked state (same as Workout Frequency)
        button_style = """
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #888;
                border-radius: 3px;
                background-color: #808080;
                color: white;
            }
            QPushButton:checked {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #707070;
            }
            QPushButton:checked:hover {
                background-color: #357abd;
            }
        """
        self.volume_total_button.setStyleSheet(button_style)
        self.volume_by_week_button.setStyleSheet(button_style)
        self.volume_by_month_button.setStyleSheet(button_style)
        
        volume_control_layout.addStretch()
        
        volume_tab_layout.addLayout(volume_control_layout)
        
        # Week navigation controls (for "By Week" view)
        volume_week_nav_layout = QHBoxLayout()
        self.volume_prev_week_button = QPushButton("← Previous")
        self.volume_prev_week_button.clicked.connect(self._volume_previous_weeks)
        volume_week_nav_layout.addWidget(self.volume_prev_week_button)
        
        self.volume_week_label = QLabel("")
        self.volume_week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        volume_week_nav_layout.addWidget(self.volume_week_label, stretch=1)
        
        self.volume_next_week_button = QPushButton("Next →")
        self.volume_next_week_button.clicked.connect(self._volume_next_weeks)
        volume_week_nav_layout.addWidget(self.volume_next_week_button)
        
        # Initially hide week navigation (shown only for "By Week")
        self.volume_week_nav_widget = QWidget()
        self.volume_week_nav_widget.setLayout(volume_week_nav_layout)
        self.volume_week_nav_widget.setVisible(False)
        volume_tab_layout.addWidget(self.volume_week_nav_widget)
        
        # Month navigation controls (for "By Month" view)
        volume_month_nav_layout = QHBoxLayout()
        self.volume_prev_month_button = QPushButton("← Previous")
        self.volume_prev_month_button.clicked.connect(self._volume_previous_months)
        volume_month_nav_layout.addWidget(self.volume_prev_month_button)
        
        self.volume_month_label = QLabel("")
        self.volume_month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        volume_month_nav_layout.addWidget(self.volume_month_label, stretch=1)
        
        self.volume_next_month_button = QPushButton("Next →")
        self.volume_next_month_button.clicked.connect(self._volume_next_months)
        volume_month_nav_layout.addWidget(self.volume_next_month_button)
        
        # Initially hide month navigation (shown only for "By Month")
        self.volume_month_nav_widget = QWidget()
        self.volume_month_nav_widget.setLayout(volume_month_nav_layout)
        self.volume_month_nav_widget.setVisible(False)
        volume_tab_layout.addWidget(self.volume_month_nav_widget)
        
        volume_tab_layout.addWidget(self.volume_muscle_canvas)
        
        self.chart_tabs.addTab(volume_tab_widget, "Volume by Muscle Group")
        self.chart_tabs.addTab(self.sleep_trends_canvas, "Sleep Trends")
        
        # Task Completion Tab with period selector
        task_tab_widget = QWidget()
        task_tab_layout = QVBoxLayout(task_tab_widget)
        task_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # Period selector (buttons instead of dropdown)
        task_control_layout = QHBoxLayout()
        task_control_layout.addWidget(QLabel("Period:"))
        
        # Create button group for period selection
        self.task_period_button_group = QButtonGroup()
        self.task_period_button_group.setExclusive(True)
        
        # Create four checkable buttons for period
        self.task_all_time_button = QPushButton("All Time")
        self.task_all_time_button.setCheckable(True)
        self.task_all_time_button.setChecked(True)  # Default
        self.task_period_button_group.addButton(self.task_all_time_button)
        task_control_layout.addWidget(self.task_all_time_button)
        
        self.task_by_day_button = QPushButton("By Day")
        self.task_by_day_button.setCheckable(True)
        self.task_period_button_group.addButton(self.task_by_day_button)
        task_control_layout.addWidget(self.task_by_day_button)
        
        self.task_by_week_button = QPushButton("By Week")
        self.task_by_week_button.setCheckable(True)
        self.task_period_button_group.addButton(self.task_by_week_button)
        task_control_layout.addWidget(self.task_by_week_button)
        
        self.task_by_month_button = QPushButton("By Month")
        self.task_by_month_button.setCheckable(True)
        self.task_period_button_group.addButton(self.task_by_month_button)
        task_control_layout.addWidget(self.task_by_month_button)
        
        # Connect period button clicks to chart refresh
        self.task_period_button_group.buttonClicked.connect(self._on_update_charts)
        
        # View type selector (buttons instead of dropdown)
        task_control_layout.addWidget(QLabel("View:"))
        
        # Create button group for view selection
        self.task_view_button_group = QButtonGroup()
        self.task_view_button_group.setExclusive(True)
        
        # Create two checkable buttons for view
        self.task_percentage_button = QPushButton("Percentage")
        self.task_percentage_button.setCheckable(True)
        self.task_percentage_button.setChecked(True)  # Default
        self.task_view_button_group.addButton(self.task_percentage_button)
        task_control_layout.addWidget(self.task_percentage_button)
        
        self.task_count_button = QPushButton("Count")
        self.task_count_button.setCheckable(True)
        self.task_view_button_group.addButton(self.task_count_button)
        task_control_layout.addWidget(self.task_count_button)
        
        # Connect view button clicks to chart refresh
        self.task_view_button_group.buttonClicked.connect(self._on_update_charts)
        
        # Add styling for checked state (same as other buttons)
        button_style = """
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #888;
                border-radius: 3px;
                background-color: #808080;
                color: white;
            }
            QPushButton:checked {
                background-color: #4a90e2;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #707070;
            }
            QPushButton:checked:hover {
                background-color: #357abd;
            }
        """
        # Apply styling to all task buttons
        self.task_all_time_button.setStyleSheet(button_style)
        self.task_by_day_button.setStyleSheet(button_style)
        self.task_by_week_button.setStyleSheet(button_style)
        self.task_by_month_button.setStyleSheet(button_style)
        self.task_percentage_button.setStyleSheet(button_style)
        self.task_count_button.setStyleSheet(button_style)
        
        task_control_layout.addStretch()
        
        task_tab_layout.addLayout(task_control_layout)
        task_tab_layout.addWidget(self.task_completion_canvas)
        
        self.chart_tabs.addTab(task_tab_widget, "Task Completion Rate")
        
        main_layout.addWidget(self.chart_tabs)
    
    def _create_canvas(self) -> FigureCanvasQTAgg:
        """
        Create a matplotlib canvas widget.
        
        Returns:
            FigureCanvasQTAgg widget
        """
        figure = Figure(figsize=(10, 6))
        canvas = FigureCanvasQTAgg(figure)
        return canvas
    
    def _on_update_charts(self) -> None:
        """Load data and regenerate charts."""
        self.refresh_charts()
    
    def refresh_charts(self) -> None:
        """
        Public method to refresh all charts with current date range.
        This ensures fresh data is loaded from storage.
        """
        # Get date range
        start_date = qdate_to_string(self.start_date_edit.date())
        end_date = qdate_to_string(self.end_date_edit.date())
        
        # Generate all charts
        self._generate_workout_frequency_chart(start_date, end_date)
        self._generate_volume_by_muscle_chart(start_date, end_date)
        self._generate_sleep_trends_chart(start_date, end_date)
        self._generate_task_completion_chart(start_date, end_date)
    
    def _get_weekday(self, date_str: str) -> str:
        """
        Get weekday name from date string.
        
        Args:
            date_str: Date string in "YYYY-MM-DD" format
            
        Returns:
            Weekday name (Monday, Tuesday, etc.)
        """
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.strftime("%A")  # Monday, Tuesday, etc.
    
    def _get_week_start(self, date_obj: date) -> date:
        """
        Get the Sunday (start) of the week containing the given date.
        Week = Sunday–Saturday.
        
        Args:
            date_obj: Date object
            
        Returns:
            Sunday date of the week
        """
        # Python weekday(): Monday = 0, Sunday = 6
        # Convert to Sunday-first: Sunday = 0, Monday = 1, ..., Saturday = 6
        days_since_sunday = (date_obj.weekday() + 1) % 7
        return date_obj - timedelta(days=days_since_sunday)
    
    def _get_week_end(self, week_start: date) -> date:
        """
        Get the Saturday (end) of the week starting with the given Sunday.
        
        Args:
            week_start: Sunday date of the week
            
        Returns:
            Saturday date of the week
        """
        return week_start + timedelta(days=6)
    
    def _get_month_start(self, date_obj: date) -> date:
        """
        Get the first day of the month containing the given date.
        
        Args:
            date_obj: Date object
            
        Returns:
            First day of the month (date object)
        """
        return date_obj.replace(day=1)
    
    def _get_month_end(self, month_start: date) -> date:
        """
        Get the last day of the month starting with the given first day.
        
        Args:
            month_start: First day of the month (date object)
            
        Returns:
            Last day of the month (date object)
        """
        # Get first day of next month, then subtract 1 day
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1, day=1)
        return next_month - timedelta(days=1)
    
    def _parse_workout_time(self, time_str: str | None) -> float:
        """
        Parse workout time string "HH:MM" to minutes from midnight.
        Returns default (noon = 720 minutes) if time_str is None or invalid.
        
        Args:
            time_str: Time string in "HH:MM" format, or None
            
        Returns:
            Minutes from midnight (0-1439), default 720 (noon) if None/invalid
        """
        if not time_str:
            return 720.0  # Default to noon (12:00 PM)
        
        try:
            hour, minute = map(int, time_str.split(":"))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour * 60.0 + minute
        except (ValueError, AttributeError):
            pass
        
        return 720.0  # Default to noon if invalid
    
    def _previous_week(self) -> None:
        """Navigate to previous week."""
        self.current_week_start = self.current_week_start - timedelta(days=7)
        self._update_week_label()
        self._on_update_charts()
    
    def _next_week(self) -> None:
        """Navigate to next week."""
        self.current_week_start = self.current_week_start + timedelta(days=7)
        self._update_week_label()
        self._on_update_charts()
    
    def _previous_month(self) -> None:
        """Navigate to previous month."""
        # Get first day of previous month
        if self.current_month_start.month == 1:
            self.current_month_start = self.current_month_start.replace(year=self.current_month_start.year - 1, month=12, day=1)
        else:
            self.current_month_start = self.current_month_start.replace(month=self.current_month_start.month - 1, day=1)
        self._update_month_label()
        self._on_update_charts()
    
    def _next_month(self) -> None:
        """Navigate to next month."""
        # Get first day of next month
        if self.current_month_start.month == 12:
            self.current_month_start = self.current_month_start.replace(year=self.current_month_start.year + 1, month=1, day=1)
        else:
            self.current_month_start = self.current_month_start.replace(month=self.current_month_start.month + 1, day=1)
        self._update_month_label()
        self._on_update_charts()
    
    def _update_month_label(self) -> None:
        """Update the month label with current month."""
        month_str = self.current_month_start.strftime("%B %Y")  # e.g., "January 2025"
        self.month_label.setText(month_str)
    
    def _update_week_label(self) -> None:
        """Update the week label with current week start date (Sunday)."""
        week_start_str = self.current_week_start.strftime("%b %d, %Y")
        # Get weekday abbreviation for Sunday
        weekday_abbr = self.current_week_start.strftime("%a")  # Should be "Sun"
        self.week_label.setText(f"Week of {weekday_abbr} {week_start_str}")
    
    def _update_volume_week_label(self) -> None:
        """Update the volume week label with current 4-week window."""
        _, _, week_keys = self._get_volume_4week_range()
        if week_keys:
            # Format: "Weeks 1–4, 2025" or "2025-W01 – 2025-W04"
            first_week = week_keys[0]
            last_week = week_keys[-1]
            # Extract year from first week
            year = first_week.split('-W')[0]
            # Extract week numbers
            week1_num = first_week.split('-W')[1]
            week4_num = last_week.split('-W')[1]
            self.volume_week_label.setText(f"Weeks {week1_num}–{week4_num}, {year}")
    
    def _volume_previous_weeks(self) -> None:
        """Navigate to previous 4-week window."""
        self.volume_week_window_start = self.volume_week_window_start - timedelta(weeks=4)
        self._update_volume_week_label()
        self._on_update_charts()
    
    def _volume_next_weeks(self) -> None:
        """Navigate to next 4-week window."""
        self.volume_week_window_start = self.volume_week_window_start + timedelta(weeks=4)
        self._update_volume_week_label()
        self._on_update_charts()
    
    def _update_volume_month_label(self) -> None:
        """Update the volume month label with current 4-month window."""
        _, _, month_keys = self._get_volume_4month_range()
        if month_keys:
            # Format: "Jan – Apr 2025"
            first_month = month_keys[0]
            last_month = month_keys[-1]
            # Extract year from first month
            year = first_month.split('-')[0]
            # Extract month numbers
            month1_num = int(first_month.split('-')[1])
            month4_num = int(last_month.split('-')[1])
            # Convert to month abbreviations
            month1_abbr = date(int(year), month1_num, 1).strftime("%b")
            month4_abbr = date(int(year), month4_num, 1).strftime("%b")
            self.volume_month_label.setText(f"{month1_abbr} – {month4_abbr} {year}")
    
    def _volume_previous_months(self) -> None:
        """Navigate to previous 4-month window."""
        # Move back 4 months
        if self.volume_month_window_start.month <= 4:
            # Need to go back to previous year
            year = self.volume_month_window_start.year - 1
            month = 12 - (4 - self.volume_month_window_start.month)
            self.volume_month_window_start = date(year, month, 1)
        else:
            self.volume_month_window_start = self.volume_month_window_start.replace(month=self.volume_month_window_start.month - 4)
        self._update_volume_month_label()
        self._on_update_charts()
    
    def _volume_next_months(self) -> None:
        """Navigate to next 4-month window."""
        # Move forward 4 months
        if self.volume_month_window_start.month <= 8:
            # Next 4 months are in same year
            self.volume_month_window_start = self.volume_month_window_start.replace(month=self.volume_month_window_start.month + 4)
        else:
            # Next 4 months are in next year
            year = self.volume_month_window_start.year + 1
            month = self.volume_month_window_start.month + 4 - 12
            self.volume_month_window_start = date(year, month, 1)
        self._update_volume_month_label()
        self._on_update_charts()
    
    def _on_volume_period_changed(self) -> None:
        """Handle volume period change - show/hide week/month navigation."""
        checked_button = self.volume_button_group.checkedButton()
        period = checked_button.text() if checked_button else "Total"  # Fallback to default
        # Show week navigation only for "By Week"
        self.volume_week_nav_widget.setVisible(period == "By Week")
        # Show month navigation only for "By Month"
        self.volume_month_nav_widget.setVisible(period == "By Month")
        self._on_update_charts()
    
    def _on_frequency_view_changed(self) -> None:
        """Handle frequency view mode change - show/hide week/month navigation and year selector."""
        checked_button = self.frequency_button_group.checkedButton()
        view_mode = checked_button.text() if checked_button else "By Month"  # Fallback to default
        # Show week navigation only for "By Days"
        self.week_nav_widget.setVisible(view_mode == "By Days")
        # Show month navigation only for "By Month"
        self.month_nav_widget.setVisible(view_mode == "By Month")
        # Show year selector only for "Whole Year Summary"
        self.year_selector_widget.setVisible(view_mode == "Whole Year Summary")
        self._on_update_charts()
    
    def _generate_workout_frequency_chart(self, start_date: str, end_date: str) -> None:
        """
        Create workout frequency chart with multiple view options.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format (may be ignored for week-based views)
            end_date: End date string in "YYYY-MM-DD" format (may be ignored for week-based views)
        """
        # Get view mode selection
        checked_button = self.frequency_button_group.checkedButton()
        view_mode = checked_button.text() if checked_button else "By Month"  # Fallback to default
        
        if view_mode == "By Days":
            # Use current week instead of date range
            self._generate_workout_frequency_by_days()
        elif view_mode == "By Month":
            # Use current month instead of date range
            self._generate_workout_frequency_by_month()
        elif view_mode == "Whole Year Summary":
            # Use selected year instead of date range
            self._generate_workout_frequency_whole_year_summary()
    
    def _generate_workout_frequency_by_days(self) -> None:
        """
        Create workout frequency chart showing one week at a time.
        X-axis = days of week (Sun-Sat), Y-axis = duration (minutes).
        Week = Sunday–Saturday.
        """
        # Get week start and end dates
        week_start = self.current_week_start
        week_end = self._get_week_end(week_start)
        
        # Convert to date strings
        start_date_str = week_start.strftime("%Y-%m-%d")
        end_date_str = week_end.strftime("%Y-%m-%d")
        
        # Get all entries in this week
        entries = self.storage.get_entries_range(start_date_str, end_date_str)
        
        # Collect data: (weekday_index, duration_minutes, tooltip_text)
        # weekday_index: 0=Sunday, 1=Monday, ..., 6=Saturday
        workout_points = []  # Blue: (x, y, tooltip)
        missed_points = []    # Red: (x, y, tooltip)
        rest_points = []      # Purple: (x, y, tooltip)
        
        for entry in entries:
            entry_date = datetime.strptime(entry.date, "%Y-%m-%d").date()
            # Convert from Python weekday (Mon=0, Sun=6) to Sunday-first (Sun=0, Sat=6)
            weekday_index = (entry_date.weekday() + 1) % 7
            
            if entry.workout is not None:
                # Workout point
                duration_minutes = entry.workout.duration_minutes or 0
                # Get muscle groups for tooltip
                muscle_groups = entry.workout.muscle_groups if entry.workout.muscle_groups else []
                tooltip_text = ", ".join(muscle_groups) if muscle_groups else "Workout"
                workout_points.append((weekday_index, duration_minutes, tooltip_text))
            elif entry.missed_day:
                # Missed day point (red, at 0, on curve)
                missed_points.append((weekday_index, 0, "Missed day"))
            elif entry.rest_day:
                # Rest day point (purple, at -2 min offset, not on curve)
                rest_points.append((weekday_index, -2, "Rest day"))
        
        # Update week label
        self._update_week_label()
        
        # Create chart
        figure = self.workout_freq_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        # Always build chart structure (axes, labels, title, grid)
        # Set x-axis: days of week (Sun-Sat)
        weekday_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        ax.set_xticks(range(7))
        ax.set_xticklabels(weekday_names)
        ax.set_xlabel('Day of Week', fontsize=10)
        ax.set_xlim(-0.5, 6.5)
        
        # Set y-axis: duration in minutes
        # Combine workout and missed points for curve (rest excluded)
        curve_points = workout_points + missed_points
        
        if workout_points or missed_points or rest_points:
            # Draw curve connecting workout and missed points (chronologically sorted by weekday)
            if curve_points:
                curve_points_sorted = sorted(curve_points, key=lambda p: p[0])  # Sort by weekday_index
                curve_x = [p[0] for p in curve_points_sorted]
                curve_y = [p[1] for p in curve_points_sorted]
                ax.plot(curve_x, curve_y, 'b-', linewidth=2, alpha=0.5, zorder=1, label='Workout/Missed')
            
            # Draw scatter plots for each type
            if workout_points:
                workout_x = [p[0] for p in workout_points]
                workout_y = [p[1] for p in workout_points]
                ax.scatter(workout_x, workout_y, s=100, color='steelblue', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7, label='Workout')
            
            if missed_points:
                missed_x = [p[0] for p in missed_points]
                missed_y = [p[1] for p in missed_points]
                ax.scatter(missed_x, missed_y, s=100, color='red', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7, label='Missed')
            
            if rest_points:
                rest_x = [p[0] for p in rest_points]
                rest_y = [p[1] for p in rest_points]
                ax.scatter(rest_x, rest_y, s=100, color='purple', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7, label='Rest')
            
            # Set y-axis limits based on data (include 0, add padding, account for rest offset)
            all_y = [p[1] for p in workout_points] + [p[1] for p in missed_points] + [p[1] for p in rest_points]
            y_min = min(-2, min(all_y) - 5) if all_y else -5  # Account for rest offset
            y_max = max(all_y) * 1.1 if all_y and max(all_y) > 0 else 60  # 10% padding above max, default 60 if no data
            
            # Add count text
            total_points = len(workout_points) + len(missed_points) + len(rest_points)
            ax.text(0.02, 0.98, f'Workouts: {len(workout_points)} | Missed: {len(missed_points)} | Rest: {len(rest_points)}', 
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        else:
            # No data: use default y-axis range (0-60 minutes)
            y_min = -5  # Account for rest offset
            y_max = 60
            
            # Add "No workouts this week" annotation inside plot area
            ax.text(0.5, 0.5, 'No workouts this week', 
                   transform=ax.transAxes, fontsize=12, 
                   ha='center', va='center', style='italic', color='gray',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        ax.set_ylim(y_min, y_max)
        
        ax.set_ylabel('Duration (min)', fontsize=10)
        ax.set_title(f'Workout Frequency (By Days) - Week of {week_start.strftime("%b %d, %Y")}', 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Add hover tooltips (pass scatter artists if available)
        scatter_artists = [child for child in ax.get_children() if isinstance(child, PathCollection)]
        self._setup_tooltips_by_days(ax, workout_points, missed_points, rest_points, scatter_artists)
        
        figure.tight_layout()
        self.workout_freq_canvas.draw()
    
    def _generate_workout_frequency_by_month(self) -> None:
        """
        Create workout frequency chart showing one month at a time.
        X-axis = day and date (e.g., "Sun 1", "Mon 2"), Y-axis = duration (minutes).
        """
        # Get month start and end dates
        month_start = self.current_month_start
        month_end = self._get_month_end(month_start)
        
        # Convert to date strings
        start_date_str = month_start.strftime("%Y-%m-%d")
        end_date_str = month_end.strftime("%Y-%m-%d")
        
        # Get all entries in this month
        entries = self.storage.get_entries_range(start_date_str, end_date_str)
        
        # Collect data: (day_of_month, duration_minutes, tooltip_text)
        # day_of_month: 1-31 (actual day number in the month)
        workout_points = []  # Blue: (x, y, tooltip)
        missed_points = []    # Red: (x, y, tooltip)
        rest_points = []      # Purple: (x, y, tooltip)
        
        for entry in entries:
            entry_date = datetime.strptime(entry.date, "%Y-%m-%d").date()
            day_of_month = entry_date.day  # 1-31
            
            if entry.workout is not None:
                # Workout point
                duration_minutes = entry.workout.duration_minutes or 0
                # Get muscle groups for tooltip
                muscle_groups = entry.workout.muscle_groups if entry.workout.muscle_groups else []
                tooltip_text = ", ".join(muscle_groups) if muscle_groups else "Workout"
                workout_points.append((day_of_month, duration_minutes, tooltip_text))
            elif entry.missed_day:
                # Missed day point (red, at 0, on curve)
                missed_points.append((day_of_month, 0, "Missed day"))
            elif entry.rest_day:
                # Rest day point (purple, at -2 min offset, not on curve)
                rest_points.append((day_of_month, -2, "Rest day"))
        
        # Update month label
        self._update_month_label()
        
        # Create chart
        figure = self.workout_freq_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        # Always build chart structure (axes, labels, title, grid)
        # Generate X-axis labels: "Sun 1", "Mon 2", "Tue 3", etc. for each day in the month
        days_in_month = month_end.day
        x_labels = []
        x_positions = []
        
        for day in range(1, days_in_month + 1):
            day_date = month_start.replace(day=day)
            weekday_abbr = day_date.strftime("%a")  # "Sun", "Mon", etc.
            x_labels.append(f"{weekday_abbr} {day}")
            x_positions.append(day)
        
        # Set x-axis: day and date (no year)
        # Show all days with rotated labels for readability
        ax.set_xticks(x_positions)
        ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
        ax.set_xlabel('Day', fontsize=10)
        ax.set_xlim(0.5, days_in_month + 0.5)
        
        # Set y-axis: duration in minutes
        # Combine workout and missed points for curve (rest excluded)
        curve_points = workout_points + missed_points
        
        if workout_points or missed_points or rest_points:
            # Draw curve connecting workout and missed points (chronologically sorted by day)
            if curve_points:
                curve_points_sorted = sorted(curve_points, key=lambda p: p[0])  # Sort by day_of_month
                curve_x = [p[0] for p in curve_points_sorted]
                curve_y = [p[1] for p in curve_points_sorted]
                ax.plot(curve_x, curve_y, 'b-', linewidth=2, alpha=0.5, zorder=1, label='Workout/Missed')
            
            # Draw scatter plots for each type
            if workout_points:
                workout_x = [p[0] for p in workout_points]
                workout_y = [p[1] for p in workout_points]
                ax.scatter(workout_x, workout_y, s=100, color='steelblue', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7, label='Workout')
            
            if missed_points:
                missed_x = [p[0] for p in missed_points]
                missed_y = [p[1] for p in missed_points]
                ax.scatter(missed_x, missed_y, s=100, color='red', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7, label='Missed')
            
            if rest_points:
                rest_x = [p[0] for p in rest_points]
                rest_y = [p[1] for p in rest_points]
                ax.scatter(rest_x, rest_y, s=100, color='purple', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7, label='Rest')
            
            # Set y-axis limits based on data (include 0, add padding, account for rest offset)
            all_y = [p[1] for p in workout_points] + [p[1] for p in missed_points] + [p[1] for p in rest_points]
            y_min = min(-2, min(all_y) - 5) if all_y else -5  # Account for rest offset
            y_max = max(all_y) * 1.1 if all_y and max(all_y) > 0 else 60  # 10% padding above max, default 60 if no data
            
            # Add count text
            ax.text(0.02, 0.98, f'Workouts: {len(workout_points)} | Missed: {len(missed_points)} | Rest: {len(rest_points)}', 
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        else:
            # No data: use default y-axis range (0-60 minutes)
            y_min = -5  # Account for rest offset
            y_max = 60
            
            # Add "No workouts this month" annotation inside plot area
            ax.text(0.5, 0.5, 'No workouts this month', 
                   transform=ax.transAxes, fontsize=12, 
                   ha='center', va='center', style='italic', color='gray',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        ax.set_ylim(y_min, y_max)
        
        ax.set_ylabel('Duration (min)', fontsize=10)
        ax.set_title(f'Workout Frequency (By Month) - {month_start.strftime("%B %Y")}', 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Add hover tooltips
        scatter_artists = [child for child in ax.get_children() if isinstance(child, PathCollection)]
        self._setup_tooltips_by_month(ax, workout_points, missed_points, rest_points, scatter_artists)
        
        figure.tight_layout()
        self.workout_freq_canvas.draw()
    
    def _generate_workout_frequency_by_weeks(self) -> None:
        """
        Create workout frequency chart showing one week at a time.
        X-axis = days of week (Sun-Sat), Y-axis = duration (minutes).
        Week = Sunday–Saturday.
        Toggle between Scatter and Bar chart types.
        """
        # Get chart type selection
        chart_type = self.weeks_chart_type_selector.currentText()  # "Scatter" or "Bar"
        
        # Get week start and end dates
        week_start = self.current_week_start
        week_end = self._get_week_end(week_start)
        
        # Convert to date strings
        start_date_str = week_start.strftime("%Y-%m-%d")
        end_date_str = week_end.strftime("%Y-%m-%d")
        
        # Get all entries in this week
        entries = self.storage.get_entries_range(start_date_str, end_date_str)
        
        # Collect workout data: (weekday_index, duration_minutes)
        # weekday_index: 0=Sunday, 1=Monday, ..., 6=Saturday
        workout_points = []
        
        for entry in entries:
            if entry.workout is not None:
                entry_date = datetime.strptime(entry.date, "%Y-%m-%d").date()
                # Convert from Python weekday (Mon=0, Sun=6) to Sunday-first (Sun=0, Sat=6)
                weekday_index = (entry_date.weekday() + 1) % 7
                
                # Get workout duration in minutes
                duration_minutes = entry.workout.duration_minutes or 0
                
                workout_points.append((weekday_index, duration_minutes))
        
        # Update week label
        self._update_week_label()
        
        # Create chart
        figure = self.workout_freq_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        # Always build chart structure (axes, labels, title, grid)
        # Weekday names for labels (Sunday-first)
        weekday_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        
        if chart_type == "Scatter":
            # Scatter: Same as By Days - X = day, Y = duration
            if workout_points:
                # Extract x and y coordinates
                x_coords = [point[0] for point in workout_points]
                y_coords = [point[1] for point in workout_points]
                
                ax.scatter(x_coords, y_coords, s=100, color='steelblue', marker='o', 
                          edgecolors='black', linewidths=1.5, zorder=3, alpha=0.7)
                
                # Set y-axis limits based on data (include 0, add padding)
                y_min = 0
                y_max = max(y_coords) * 1.1 if y_coords else 60  # 10% padding above max, default 60 if no data
            else:
                # No data: use default y-axis range (0-60 minutes)
                y_min = 0
                y_max = 60
                # Add "No workouts this week" annotation inside plot area
                ax.text(0.5, 0.5, 'No workouts this week', 
                       transform=ax.transAxes, fontsize=12, 
                       ha='center', va='center', style='italic', color='gray',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            
            # Set x-axis: days of week (Sun-Sat)
            ax.set_xticks(range(7))
            ax.set_xticklabels(weekday_names)
            ax.set_xlabel('Day of Week', fontsize=10)
            ax.set_xlim(-0.5, 6.5)
            
            ax.set_ylim(y_min, y_max)
            
            ax.set_ylabel('Duration (min)', fontsize=10)
            
        else:  # Bar chart
            if workout_points:
                # Extract y coordinates for x-axis limits
                y_coords = [point[1] for point in workout_points]
                
                # Bar: Horizontal bars - Y = day, X = duration
                # One bar per workout
                bar_width = 0.6  # Width of each bar
                colors = plt.cm.viridis(np.linspace(0, 1, len(workout_points)))
                
                # Create horizontal bars
                for i, (weekday_idx, duration_minutes) in enumerate(workout_points):
                    # Horizontal bar: y position = weekday, x position = duration
                    ax.barh(weekday_idx, duration_minutes, height=bar_width, 
                           color=colors[i], edgecolor='black', linewidth=0.5, alpha=0.7)
                
                # Set x-axis limits based on data (include 0, add padding)
                x_min = 0
                x_max = max(y_coords) * 1.1 if y_coords else 60  # 10% padding above max, default 60 if no data
            else:
                # No data: use default x-axis range (0-60 minutes)
                x_min = 0
                x_max = 60
                # Add "No workouts this week" annotation inside plot area
                ax.text(0.5, 0.5, 'No workouts this week', 
                       transform=ax.transAxes, fontsize=12, 
                       ha='center', va='center', style='italic', color='gray',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            
            # Set y-axis: days of week (Sun-Sat)
            ax.set_yticks(range(7))
            ax.set_yticklabels(weekday_names)
            ax.set_ylabel('Day of Week', fontsize=10)
            ax.set_ylim(-0.5, 6.5)
            
            ax.set_xlim(x_min, x_max)
            
            ax.set_xlabel('Duration (min)', fontsize=10)
        
        # Set title
        ax.set_title(f'Workout Frequency (By Weeks - {chart_type}) - Week of {week_start.strftime("%b %d, %Y")}', 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Add count text (only if there are workouts)
        if workout_points:
            ax.text(0.02, 0.98, f'Workouts this week: {len(workout_points)}', 
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        figure.tight_layout()
        self.workout_freq_canvas.draw()
    
    def _generate_workout_frequency_whole_year_summary(self) -> None:
        """
        Create workout frequency chart showing the entire year.
        X-axis = date (Jan 1 - Dec 31), Y-axis = duration (minutes).
        Scatter plot with one dot per workout.
        """
        # Get selected year
        selected_year = int(self.year_selector.currentText())
        
        # Get date range for the entire year
        start_date = date(selected_year, 1, 1)
        end_date = date(selected_year, 12, 31)
        
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Get all entries in this year
        entries = self.storage.get_entries_range(start_date_str, end_date_str)
        
        # Collect data: (date, duration_minutes, tooltip_text)
        workout_points = []  # Blue: (date, y, tooltip)
        missed_points = []    # Red: (date, y, tooltip)
        rest_points = []      # Purple: (date, y, tooltip)
        
        for entry in entries:
            entry_date = datetime.strptime(entry.date, "%Y-%m-%d").date()
            
            if entry.workout is not None:
                # Workout point
                duration_minutes = entry.workout.duration_minutes or 0
                # Get muscle groups for tooltip
                muscle_groups = entry.workout.muscle_groups if entry.workout.muscle_groups else []
                tooltip_text = ", ".join(muscle_groups) if muscle_groups else "Workout"
                workout_points.append((entry_date, duration_minutes, tooltip_text))
            elif entry.missed_day:
                # Missed day point (red, at 0, on curve)
                missed_points.append((entry_date, 0, "Missed day"))
            elif entry.rest_day:
                # Rest day point (purple, at -2 min offset, not on curve)
                rest_points.append((entry_date, -2, "Rest day"))
        
        # Create chart
        figure = self.workout_freq_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        # Always build chart structure (axes, labels, title, grid)
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Duration (min)', fontsize=10)
        ax.set_title(f'Workout Frequency (Whole Year Summary) - {selected_year}', 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        # Set x-axis limits to show full year
        ax.set_xlim(start_date, end_date)
        
        # Format x-axis dates: show month labels like "Jan 1", "Feb 1", etc.
        # Use matplotlib's date formatter to show month abbreviations and day
        from matplotlib.dates import MonthLocator, DateFormatter
        ax.xaxis.set_major_locator(MonthLocator())  # One tick per month
        ax.xaxis.set_major_formatter(DateFormatter("%b %d"))  # Format: "Jan 1", "Feb 1", etc.
        ax.tick_params(axis='x', rotation=45)
        figure.autofmt_xdate()
        
        # Combine workout and missed points for curve (rest excluded)
        curve_points = workout_points + missed_points
        
        if workout_points or missed_points or rest_points:
            # Draw curve connecting workout and missed points (chronologically sorted by date)
            if curve_points:
                curve_points_sorted = sorted(curve_points, key=lambda p: p[0])  # Sort by date
                curve_dates = [p[0] for p in curve_points_sorted]
                curve_durations = [p[1] for p in curve_points_sorted]
                ax.plot(curve_dates, curve_durations, 'b-', linewidth=1.5, alpha=0.5, zorder=1, label='Workout/Missed')
            
            # Draw scatter plots for each type
            if workout_points:
                workout_dates = [p[0] for p in workout_points]
                workout_durations = [p[1] for p in workout_points]
                ax.scatter(workout_dates, workout_durations, s=50, color='steelblue', marker='o', 
                          edgecolors='black', linewidths=0.5, zorder=3, alpha=0.7, label='Workout')
            
            if missed_points:
                missed_dates = [p[0] for p in missed_points]
                missed_durations = [p[1] for p in missed_points]
                ax.scatter(missed_dates, missed_durations, s=50, color='red', marker='o', 
                          edgecolors='black', linewidths=0.5, zorder=3, alpha=0.7, label='Missed')
            
            if rest_points:
                rest_dates = [p[0] for p in rest_points]
                rest_durations = [p[1] for p in rest_points]
                ax.scatter(rest_dates, rest_durations, s=50, color='purple', marker='o', 
                          edgecolors='black', linewidths=0.5, zorder=3, alpha=0.7, label='Rest')
            
            # Add summary text
            total_workouts = len(workout_points)
            total_missed = len(missed_points)
            total_rest = len(rest_points)
            total_duration = sum([p[1] for p in workout_points])
            avg_duration = total_duration / total_workouts if total_workouts > 0 else 0
            ax.text(0.02, 0.98, f'Workouts: {total_workouts} | Missed: {total_missed} | Rest: {total_rest} | Avg: {avg_duration:.1f} min', 
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            # Set y-axis limits based on data (include 0, add padding, account for rest offset)
            all_durations = [p[1] for p in workout_points] + [p[1] for p in missed_points] + [p[1] for p in rest_points]
            y_min = min(-2, min(all_durations) - 5) if all_durations else -5  # Account for rest offset
            y_max = max(all_durations) * 1.1 if all_durations and max(all_durations) > 0 else 60  # 10% padding above max, default 60 if no data
        else:
            # No data: use default y-axis range (0-60 minutes)
            y_min = -5  # Account for rest offset
            y_max = 60
            
            # Add "No workouts this year" annotation inside plot area
            ax.text(0.5, 0.5, f'No workout data available for {selected_year}', 
                   transform=ax.transAxes, fontsize=12, 
                   ha='center', va='center', style='italic', color='gray',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        
        ax.set_ylim(y_min, y_max)
        
        # Tooltips disabled for whole year summary (causing errors)
        # scatter_artists = [child for child in ax.get_children() if isinstance(child, PathCollection)]
        # self._setup_tooltips_by_year(ax, workout_points, missed_points, rest_points, scatter_artists)
        
        figure.tight_layout()
        self.workout_freq_canvas.draw()
    
    def _setup_tooltips_by_days(self, ax, workout_points: list, missed_points: list, rest_points: list, scatter_artists: list = None) -> None:
        """Setup hover tooltips for By Days view using mplcursors if available, otherwise matplotlib events."""
        # Store point data for tooltip lookup
        tooltip_data = {}
        all_points = []
        for x, y, tooltip in workout_points + missed_points + rest_points:
            tooltip_data[(x, y)] = tooltip
            all_points.append((x, y, tooltip))
        
        # Try mplcursors first
        try:
            import mplcursors
            if scatter_artists is None:
                scatter_artists = [child for child in ax.get_children() if isinstance(child, PathCollection)]
            if scatter_artists:
                # Attach cursor to all scatter plots
                cursor = mplcursors.cursor(scatter_artists, hover=True)
                @cursor.connect("add")
                def on_add(sel):
                    x, y = sel.target[0], sel.target[1]
                    # Find closest point
                    tooltip = tooltip_data.get((x, y), "")
                    if not tooltip:
                        # Find closest point within tolerance
                        min_dist = float('inf')
                        closest_tooltip = ""
                        for (px, py), tt in tooltip_data.items():
                            dist = abs(px - x) + abs(py - y)
                            if dist < min_dist and dist < 0.5:  # Tolerance
                                min_dist = dist
                                closest_tooltip = tt
                        tooltip = closest_tooltip
                    if tooltip:
                        sel.annotation.set_text(tooltip)
                        sel.annotation.set_bbox(dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            return
        except ImportError:
            pass
        
        # Fallback: Use matplotlib's motion_notify_event
        annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                           arrowprops=dict(arrowstyle='->'))
        annot.set_visible(False)
        
        def hover(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    ax.figure.canvas.draw_idle()
                return
            
            # Find closest point
            min_dist = float('inf')
            closest_point = None
            closest_tooltip = ""
            
            for px, py, tooltip in all_points:
                # Convert to display coordinates for distance calculation
                display_coords = ax.transData.transform([(px, py)])
                event_coords = ax.transData.transform([(event.xdata, event.ydata)])
                if display_coords.size > 0 and event_coords.size > 0:
                    dist = ((display_coords[0][0] - event_coords[0][0])**2 + 
                           (display_coords[0][1] - event_coords[0][1])**2)**0.5
                    if dist < min_dist and dist < 50:  # 50 pixels tolerance
                        min_dist = dist
                        closest_point = (px, py)
                        closest_tooltip = tooltip
            
            if closest_point and closest_tooltip:
                annot.xy = closest_point
                annot.set_text(closest_tooltip)
                annot.set_visible(True)
                ax.figure.canvas.draw_idle()
            else:
                if annot.get_visible():
                    annot.set_visible(False)
                    ax.figure.canvas.draw_idle()
        
        ax.figure.canvas.mpl_connect("motion_notify_event", hover)
    
    def _setup_tooltips_by_month(self, ax, workout_points: list, missed_points: list, rest_points: list, scatter_artists: list = None) -> None:
        """Setup hover tooltips for By Month view using mplcursors if available, otherwise matplotlib events."""
        # Store point data for tooltip lookup
        tooltip_data = {}
        all_points = []
        for x, y, tooltip in workout_points + missed_points + rest_points:
            tooltip_data[(x, y)] = tooltip
            all_points.append((x, y, tooltip))
        
        # Try mplcursors first
        try:
            import mplcursors
            if scatter_artists is None:
                scatter_artists = [child for child in ax.get_children() if isinstance(child, PathCollection)]
            if scatter_artists:
                cursor = mplcursors.cursor(scatter_artists, hover=True)
                @cursor.connect("add")
                def on_add(sel):
                    x, y = sel.target[0], sel.target[1]
                    tooltip = tooltip_data.get((x, y), "")
                    if not tooltip:
                        min_dist = float('inf')
                        closest_tooltip = ""
                        for (px, py), tt in tooltip_data.items():
                            dist = abs(px - x) + abs(py - y)
                            if dist < min_dist and dist < 0.5:
                                min_dist = dist
                                closest_tooltip = tt
                        tooltip = closest_tooltip
                    if tooltip:
                        sel.annotation.set_text(tooltip)
                        sel.annotation.set_bbox(dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            return
        except ImportError:
            pass
        
        # Fallback: Use matplotlib's motion_notify_event
        annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                           arrowprops=dict(arrowstyle='->'))
        annot.set_visible(False)
        
        def hover(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    ax.figure.canvas.draw_idle()
                return
            
            min_dist = float('inf')
            closest_point = None
            closest_tooltip = ""
            
            for px, py, tooltip in all_points:
                display_coords = ax.transData.transform([(px, py)])
                event_coords = ax.transData.transform([(event.xdata, event.ydata)])
                if display_coords.size > 0 and event_coords.size > 0:
                    dist = ((display_coords[0][0] - event_coords[0][0])**2 + 
                           (display_coords[0][1] - event_coords[0][1])**2)**0.5
                    if dist < min_dist and dist < 50:
                        min_dist = dist
                        closest_point = (px, py)
                        closest_tooltip = tooltip
            
            if closest_point and closest_tooltip:
                annot.xy = closest_point
                annot.set_text(closest_tooltip)
                annot.set_visible(True)
                ax.figure.canvas.draw_idle()
            else:
                if annot.get_visible():
                    annot.set_visible(False)
                    ax.figure.canvas.draw_idle()
        
        ax.figure.canvas.mpl_connect("motion_notify_event", hover)
    
    def _setup_tooltips_by_year(self, ax, workout_points: list, missed_points: list, rest_points: list, scatter_artists: list = None) -> None:
        """Setup hover tooltips for Whole Year Summary view using mplcursors if available, otherwise matplotlib events."""
        # Store point data for tooltip lookup
        tooltip_data = {}
        all_points = []
        for date_obj, y, tooltip in workout_points + missed_points + rest_points:
            # Convert date to numeric for lookup
            date_num = date_obj.toordinal()
            tooltip_data[(date_num, y)] = tooltip
            all_points.append((date_obj, y, tooltip))
        
        # Try mplcursors first
        try:
            import mplcursors
            if scatter_artists is None:
                scatter_artists = [child for child in ax.get_children() if isinstance(child, PathCollection)]
            if scatter_artists:
                cursor = mplcursors.cursor(scatter_artists, hover=True)
                @cursor.connect("add")
                def on_add(sel):
                    x, y = sel.target[0], sel.target[1]
                    # Convert x (date) to ordinal for lookup
                    if isinstance(x, (date, datetime)):
                        x_num = x.toordinal() if isinstance(x, date) else x.date().toordinal()
                    else:
                        # Already numeric (matplotlib date)
                        x_num = int(x)
                    tooltip = tooltip_data.get((x_num, y), "")
                    if not tooltip:
                        min_dist = float('inf')
                        closest_tooltip = ""
                        for (px, py), tt in tooltip_data.items():
                            dist = abs(px - x_num) + abs(py - y)
                            if dist < min_dist and dist < 1.0:  # Larger tolerance for dates
                                min_dist = dist
                                closest_tooltip = tt
                        tooltip = closest_tooltip
                    if tooltip:
                        sel.annotation.set_text(tooltip)
                        sel.annotation.set_bbox(dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            return
        except ImportError:
            pass
        
        # Fallback: Use matplotlib's motion_notify_event
        annot = ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
                           arrowprops=dict(arrowstyle='->'))
        annot.set_visible(False)
        
        def hover(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    ax.figure.canvas.draw_idle()
                return
            
            min_dist = float('inf')
            closest_point = None
            closest_tooltip = ""
            
            for date_obj, py, tooltip in all_points:
                # Convert date to display coordinates
                display_coords = ax.transData.transform([(date_obj, py)])
                event_coords = ax.transData.transform([(event.xdata, event.ydata)])
                if display_coords.size > 0 and event_coords.size > 0:
                    dist = ((display_coords[0][0] - event_coords[0][0])**2 + 
                           (display_coords[0][1] - event_coords[0][1])**2)**0.5
                    if dist < min_dist and dist < 50:
                        min_dist = dist
                        closest_point = (date_obj, py)
                        closest_tooltip = tooltip
            
            if closest_point and closest_tooltip:
                annot.xy = closest_point
                annot.set_text(closest_tooltip)
                annot.set_visible(True)
                ax.figure.canvas.draw_idle()
            else:
                if annot.get_visible():
                    annot.set_visible(False)
                    ax.figure.canvas.draw_idle()
        
        ax.figure.canvas.mpl_connect("motion_notify_event", hover)
    
    def _group_by_week(self, date_str: str) -> str:
        """
        Convert date string to week key (YYYY-W##).
        
        Args:
            date_str: Date string in "YYYY-MM-DD" format
            
        Returns:
            Week key string in format "YYYY-W##"
        """
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        year, week, _ = date_obj.isocalendar()
        return f"{year}-W{week:02d}"
    
    def _get_week_start_for_volume(self, date_obj: date) -> date:
        """
        Get the start of the 4-week window containing the given date.
        Returns the Monday of the first week in the 4-week block.
        The 4-week block contains the current week (as the 4th week) and 3 preceding weeks.
        
        Args:
            date_obj: Date object
            
        Returns:
            Monday of the first week in the 4-week block (date object)
        """
        # Get ISO week info
        year, week, weekday = date_obj.isocalendar()
        # weekday: 1=Monday, 7=Sunday
        # Calculate Monday of current week
        days_since_monday = (weekday - 1) % 7
        monday_of_current_week = date_obj - timedelta(days=days_since_monday)
        # Go back 3 weeks to get the start of the 4-week window
        # This makes the current week the 4th week in the window
        return monday_of_current_week - timedelta(weeks=3)
    
    def _get_volume_4week_range(self) -> tuple[date, date, list[str]]:
        """
        Get the date range and week keys for the current 4-week window.
        
        Returns:
            Tuple of (start_date, end_date, list of 4 week keys)
        """
        # Start from volume_week_window_start (Monday of first week)
        week_start = self.volume_week_window_start
        
        # Calculate end date (Sunday of 4th week)
        # 4 weeks = 28 days, but we need Sunday of week 4
        # Week 1: Mon-Sun (days 0-6)
        # Week 2: Mon-Sun (days 7-13)
        # Week 3: Mon-Sun (days 14-20)
        # Week 4: Mon-Sun (days 21-27)
        # So end date is Sunday of week 4 = week_start + 27 days
        week_end = week_start + timedelta(days=27)
        
        # Generate 4 week keys
        week_keys = []
        for i in range(4):
            week_date = week_start + timedelta(weeks=i)
            year, week, _ = week_date.isocalendar()
            week_keys.append(f"{year}-W{week:02d}")
        
        return week_start, week_end, week_keys
    
    def _get_month_start_for_volume(self, date_obj: date) -> date:
        """
        Get the start of the 4-month window containing the given date.
        Returns the 1st day of the first month in the 4-month block.
        The 4-month block contains the current month (as the 4th month) and 3 preceding months.
        
        Args:
            date_obj: Date object
            
        Returns:
            First day of the first month in the 4-month block (date object)
        """
        # Get first day of current month
        first_of_current_month = date_obj.replace(day=1)
        # Go back 3 months to get the start of the 4-month window
        if first_of_current_month.month <= 3:
            # Need to go back to previous year
            year = first_of_current_month.year - 1
            month = 12 - (3 - first_of_current_month.month)
            return date(year, month, 1)
        else:
            return first_of_current_month.replace(month=first_of_current_month.month - 3)
    
    def _get_volume_4month_range(self) -> tuple[date, date, list[str]]:
        """
        Get the date range and month keys for the current 4-month window.
        
        Returns:
            Tuple of (start_date, end_date, list of 4 month keys)
        """
        # Start from volume_month_window_start (1st of first month)
        month_start = self.volume_month_window_start
        
        # Calculate end date (last day of 4th month)
        # Get first day of 5th month, then subtract 1 day
        if month_start.month <= 8:
            # 5th month is in same year
            fifth_month_start = month_start.replace(month=month_start.month + 4)
        else:
            # 5th month is in next year
            fifth_month_start = month_start.replace(year=month_start.year + 1, month=month_start.month + 4 - 12)
        month_end = fifth_month_start - timedelta(days=1)
        
        # Generate 4 month keys
        month_keys = []
        current_month = month_start
        for i in range(4):
            month_keys.append(current_month.strftime("%Y-%m"))
            # Move to next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        return month_start, month_end, month_keys
    
    def _group_by_month(self, date_str: str) -> str:
        """
        Convert date string to month key (YYYY-MM).
        
        Args:
            date_str: Date string in "YYYY-MM-DD" format
            
        Returns:
            Month key string in format "YYYY-MM"
        """
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.strftime("%Y-%m")
    
    def _generate_volume_by_muscle_chart(self, start_date: str, end_date: str) -> None:
        """
        Create muscle group volume chart with time period options.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
        """
        # Get time period selection
        checked_button = self.volume_button_group.checkedButton()
        period = checked_button.text() if checked_button else "Total"  # Fallback to default
        
        if period == "Total":
            self._generate_volume_by_muscle_total(start_date, end_date)
        elif period == "By Week":
            self._generate_volume_by_muscle_weekly(start_date, end_date)
        elif period == "By Month":
            self._generate_volume_by_muscle_monthly(start_date, end_date)
    
    def _generate_volume_by_muscle_total(self, start_date: str, end_date: str) -> None:
        """
        Create total aggregate muscle group volume chart (original implementation).
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
        """
        # Get all entries in date range
        entries = self.storage.get_entries_range(start_date, end_date)
        
        # Calculate volume per muscle group
        volume_by_muscle = defaultdict(float)
        
        for entry in entries:
            if entry.workout is not None:
                workout = entry.workout
                # Calculate volume for each exercise
                for exercise in workout.exercises:
                    exercise_volume = 0.0
                    for set_obj in exercise.sets:
                        exercise_volume += set_obj.reps * set_obj.weight
                    
                    # Use exercise-level muscle groups (fallback to workout-level for old data)
                    exercise_muscle_groups = getattr(exercise, 'muscle_groups', None)
                    if exercise_muscle_groups and len(exercise_muscle_groups) > 0:
                        # Distribute volume across this exercise's muscle groups
                        volume_per_group = exercise_volume / len(exercise_muscle_groups)
                        for muscle_group in exercise_muscle_groups:
                            volume_by_muscle[muscle_group] += volume_per_group
                    elif workout.muscle_groups:
                        # Fallback: use workout-level muscle groups for old data
                        volume_per_group = exercise_volume / len(workout.muscle_groups)
                        for muscle_group in workout.muscle_groups:
                            volume_by_muscle[muscle_group] += volume_per_group
        
        if not volume_by_muscle:
            self._show_no_data_message(self.volume_muscle_canvas.figure, "No workout data available")
            self.volume_muscle_canvas.draw()
            return
        
        # Sort by volume (descending)
        sorted_muscles = sorted(volume_by_muscle.items(), key=lambda x: x[1], reverse=True)
        muscles = [m[0] for m in sorted_muscles]
        volumes = [m[1] for m in sorted_muscles]
        
        # Create chart
        figure = self.volume_muscle_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        bars = ax.barh(muscles, volumes, color='coral', edgecolor='black')
        ax.set_xlabel('Total Volume (lbs)', fontsize=10)
        ax.set_ylabel('Muscle Group', fontsize=10)
        ax.set_title('Workout Volume by Muscle Group (Total)', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2, 
                   f'{width:,.0f}', ha='left', va='center', fontsize=9)
        
        figure.tight_layout()
        self.volume_muscle_canvas.draw()
    
    def _generate_volume_by_muscle_weekly(self, start_date: str, end_date: str) -> None:
        """
        Create weekly breakdown of muscle group volume chart.
        Shows exactly 4 weeks at a time when using navigation.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format (ignored when using navigation)
            end_date: End date string in "YYYY-MM-DD" format (ignored when using navigation)
        """
        # Get 4-week window range and week keys
        week_start, week_end, week_keys = self._get_volume_4week_range()
        
        # Convert to date strings
        start_date_str = week_start.strftime("%Y-%m-%d")
        end_date_str = week_end.strftime("%Y-%m-%d")
        
        # Get all entries in the 4-week window
        entries = self.storage.get_entries_range(start_date_str, end_date_str)
        
        # Group volume by week and muscle group: {week: {muscle_group: volume}}
        # Only include weeks in our 4-week window
        volume_by_week_muscle = defaultdict(lambda: defaultdict(float))
        all_muscle_groups = set()
        
        for entry in entries:
            if entry.workout is not None:
                workout = entry.workout
                week_key = self._group_by_week(entry.date)
                
                # Only process if this week is in our 4-week window
                if week_key not in week_keys:
                    continue
                
                # Calculate volume for each exercise
                for exercise in workout.exercises:
                    exercise_volume = 0.0
                    for set_obj in exercise.sets:
                        exercise_volume += set_obj.reps * set_obj.weight
                    
                    # Use exercise-level muscle groups (fallback to workout-level for old data)
                    exercise_muscle_groups = getattr(exercise, 'muscle_groups', None)
                    if exercise_muscle_groups and len(exercise_muscle_groups) > 0:
                        # Distribute volume across this exercise's muscle groups
                        volume_per_group = exercise_volume / len(exercise_muscle_groups)
                        for muscle_group in exercise_muscle_groups:
                            volume_by_week_muscle[week_key][muscle_group] += volume_per_group
                            all_muscle_groups.add(muscle_group)
                    elif workout.muscle_groups:
                        # Fallback: use workout-level muscle groups for old data
                        volume_per_group = exercise_volume / len(workout.muscle_groups)
                        for muscle_group in workout.muscle_groups:
                            volume_by_week_muscle[week_key][muscle_group] += volume_per_group
                            all_muscle_groups.add(muscle_group)
        
        # Create figure (always draw chart structure, even if no data)
        figure = self.volume_muscle_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        # Use the 4 week keys in order (even if some have no data)
        sorted_weeks = week_keys
        sorted_muscles = sorted(all_muscle_groups) if all_muscle_groups else []
        
        if not volume_by_week_muscle and not sorted_muscles:
            # No data: show empty chart with axes and labels
            ax.set_xlabel('Week', fontsize=10)
            ax.set_ylabel('Volume (lbs)', fontsize=10)
            ax.set_title('Workout Volume by Muscle Group (Weekly Breakdown)', fontsize=12, fontweight='bold')
            ax.set_xticks(range(len(sorted_weeks)))
            ax.set_xticklabels(sorted_weeks, rotation=45)
            ax.grid(True, alpha=0.3, axis='y')
            # Optional: add "No data" text
            ax.text(0.5, 0.5, 'No workout data available for these weeks', 
                   transform=ax.transAxes, fontsize=12, 
                   ha='center', va='center', style='italic', color='gray',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            figure.tight_layout()
            self.volume_muscle_canvas.draw()
            return
        
        # Prepare data arrays for stacked bars
        bottom = np.zeros(len(sorted_weeks))
        colors = plt.cm.Set3(np.linspace(0, 1, len(sorted_muscles))) if sorted_muscles else []
        
        # Create stacked bars
        for i, muscle_group in enumerate(sorted_muscles):
            volumes = [volume_by_week_muscle[week][muscle_group] for week in sorted_weeks]
            ax.bar(sorted_weeks, volumes, bottom=bottom, label=muscle_group, 
                   color=colors[i], edgecolor='black', linewidth=0.5)
            bottom += np.array(volumes)
        
        ax.set_xlabel('Week', fontsize=10)
        ax.set_ylabel('Volume (lbs)', fontsize=10)
        ax.set_title('Workout Volume by Muscle Group (Weekly Breakdown)', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        if sorted_muscles:
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        
        # Rotate x-axis labels
        ax.tick_params(axis='x', rotation=45)
        
        figure.tight_layout()
        self.volume_muscle_canvas.draw()
    
    def _generate_volume_by_muscle_monthly(self, start_date: str, end_date: str) -> None:
        """
        Create monthly breakdown of muscle group volume chart.
        Shows exactly 4 months at a time when using navigation.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format (ignored when using navigation)
            end_date: End date string in "YYYY-MM-DD" format (ignored when using navigation)
        """
        # Get 4-month window range and month keys
        month_start, month_end, month_keys = self._get_volume_4month_range()
        
        # Convert to date strings
        start_date_str = month_start.strftime("%Y-%m-%d")
        end_date_str = month_end.strftime("%Y-%m-%d")
        
        # Get all entries in the 4-month window
        entries = self.storage.get_entries_range(start_date_str, end_date_str)
        
        # Group volume by month and muscle group: {month: {muscle_group: volume}}
        # Only include months in our 4-month window
        volume_by_month_muscle = defaultdict(lambda: defaultdict(float))
        all_muscle_groups = set()
        
        for entry in entries:
            if entry.workout is not None:
                workout = entry.workout
                month_key = self._group_by_month(entry.date)
                
                # Only process if this month is in our 4-month window
                if month_key not in month_keys:
                    continue
                
                # Calculate volume for each exercise
                for exercise in workout.exercises:
                    exercise_volume = 0.0
                    for set_obj in exercise.sets:
                        exercise_volume += set_obj.reps * set_obj.weight
                    
                    # Use exercise-level muscle groups (fallback to workout-level for old data)
                    exercise_muscle_groups = getattr(exercise, 'muscle_groups', None)
                    if exercise_muscle_groups and len(exercise_muscle_groups) > 0:
                        # Distribute volume across this exercise's muscle groups
                        volume_per_group = exercise_volume / len(exercise_muscle_groups)
                        for muscle_group in exercise_muscle_groups:
                            volume_by_month_muscle[month_key][muscle_group] += volume_per_group
                            all_muscle_groups.add(muscle_group)
                    elif workout.muscle_groups:
                        # Fallback: use workout-level muscle groups for old data
                        volume_per_group = exercise_volume / len(workout.muscle_groups)
                        for muscle_group in workout.muscle_groups:
                            volume_by_month_muscle[month_key][muscle_group] += volume_per_group
                            all_muscle_groups.add(muscle_group)
        
        # Create figure (always draw chart structure, even if no data)
        figure = self.volume_muscle_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        # Use the 4 month keys in order (even if some have no data)
        sorted_months = month_keys
        sorted_muscles = sorted(all_muscle_groups) if all_muscle_groups else []
        
        if not volume_by_month_muscle and not sorted_muscles:
            # No data: show empty chart with axes and labels
            ax.set_xlabel('Month', fontsize=10)
            ax.set_ylabel('Volume (lbs)', fontsize=10)
            ax.set_title('Workout Volume by Muscle Group (Monthly Breakdown)', fontsize=12, fontweight='bold')
            # Format month labels for display
            month_labels = []
            for month_key in sorted_months:
                year, month = month_key.split('-')
                month_date = date(int(year), int(month), 1)
                month_labels.append(month_date.strftime("%b %Y"))
            ax.set_xticks(range(len(sorted_months)))
            ax.set_xticklabels(month_labels, rotation=45)
            ax.grid(True, alpha=0.3, axis='y')
            # Optional: add "No data" text
            ax.text(0.5, 0.5, 'No workout data available for these months', 
                   transform=ax.transAxes, fontsize=12, 
                   ha='center', va='center', style='italic', color='gray',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
            figure.tight_layout()
            self.volume_muscle_canvas.draw()
            return
        
        # Format month labels for display
        month_labels = []
        for month_key in sorted_months:
            year, month = month_key.split('-')
            month_date = date(int(year), int(month), 1)
            month_labels.append(month_date.strftime("%b %Y"))
        
        # Prepare data arrays for stacked bars
        bottom = np.zeros(len(sorted_months))
        colors = plt.cm.Set3(np.linspace(0, 1, len(sorted_muscles))) if sorted_muscles else []
        
        # Create stacked bars
        for i, muscle_group in enumerate(sorted_muscles):
            volumes = [volume_by_month_muscle[month][muscle_group] for month in sorted_months]
            ax.bar(range(len(sorted_months)), volumes, bottom=bottom, label=muscle_group, 
                   color=colors[i], edgecolor='black', linewidth=0.5)
            bottom += np.array(volumes)
        
        ax.set_xlabel('Month', fontsize=10)
        ax.set_ylabel('Volume (lbs)', fontsize=10)
        ax.set_title('Workout Volume by Muscle Group (Monthly Breakdown)', fontsize=12, fontweight='bold')
        ax.set_xticks(range(len(sorted_months)))
        ax.set_xticklabels(month_labels, rotation=45)
        ax.grid(True, alpha=0.3, axis='y')
        if sorted_muscles:
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        
        figure.tight_layout()
        self.volume_muscle_canvas.draw()
    
    def _generate_sleep_trends_chart(self, start_date: str, end_date: str) -> None:
        """
        Create sleep trend chart (sleep hours over time).
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
        """
        # Get sleep data for date range
        sleep_data = self.sleep_service.get_sleep_range(start_date, end_date)
        
        if not sleep_data:
            self._show_no_data_message(self.sleep_trends_canvas.figure, "No sleep data available")
            self.sleep_trends_canvas.draw()
            return
        
        # Parse dates and extract values
        dates = [datetime.strptime(date_str, "%Y-%m-%d").date() for date_str, _ in sleep_data]
        hours = [hours for _, hours in sleep_data]
        
        # Create chart
        figure = self.sleep_trends_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        ax.plot(dates, hours, marker='o', linestyle='-', linewidth=2, markersize=6, color='teal')
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Sleep Hours', fontsize=10)
        ax.set_title('Sleep Trends Over Time', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Add horizontal lines for recommended sleep range
        ax.axhline(y=7, color='green', linestyle='--', alpha=0.5, label='Recommended (7h)')
        ax.axhline(y=9, color='green', linestyle='--', alpha=0.5, label='Recommended (9h)')
        ax.axhline(y=6, color='red', linestyle='--', alpha=0.5, label='Minimum (6h)')
        
        # Format x-axis dates
        ax.tick_params(axis='x', rotation=45)
        figure.autofmt_xdate()
        
        ax.legend(loc='upper right', fontsize=8)
        
        figure.tight_layout()
        self.sleep_trends_canvas.draw()
    
    def _generate_task_completion_chart(self, start_date: str, end_date: str) -> None:
        """
        Create task completion rate chart with time period options.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
        """
        # Get period and view type selection
        # Get period and view from button groups
        checked_period_button = self.task_period_button_group.checkedButton()
        period = checked_period_button.text() if checked_period_button else "All Time"  # Fallback to default
        
        checked_view_button = self.task_view_button_group.checkedButton()
        view_type = checked_view_button.text() if checked_view_button else "Percentage"  # Fallback to default
        
        if period == "All Time":
            self._generate_task_completion_all_time(start_date, end_date, view_type)
        elif period == "By Day":
            self._generate_task_completion_by_day(start_date, end_date, view_type)
        elif period == "By Week":
            self._generate_task_completion_by_week(start_date, end_date, view_type)
        elif period == "By Month":
            self._generate_task_completion_by_month(start_date, end_date, view_type)
    
    def _generate_task_completion_all_time(self, start_date: str, end_date: str, view_type: str) -> None:
        """
        Create overall task completion rate chart (original implementation).
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            view_type: "Percentage" or "Count"
        """
        # Get all entries in date range
        entries = self.storage.get_entries_range(start_date, end_date)
        
        # Count completed vs incomplete tasks
        completed = 0
        incomplete = 0
        
        for entry in entries:
            if entry.tasks:
                for task in entry.tasks:
                    if task.completed:
                        completed += 1
                    else:
                        incomplete += 1
        
        if completed == 0 and incomplete == 0:
            self._show_no_data_message(self.task_completion_canvas.figure, "No task data available")
            self.task_completion_canvas.draw()
            return
        
        # Create chart
        figure = self.task_completion_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        if view_type == "Percentage":
            # Pie chart
            labels = ['Completed', 'Incomplete']
            sizes = [completed, incomplete]
            colors = ['#4CAF50', '#F44336']
            explode = (0.05, 0)  # Slight separation for completed slice
            
            ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
                   shadow=True, startangle=90, textprops={'fontsize': 10})
            ax.set_title('Task Completion Rate (All Time)', fontsize=12, fontweight='bold')
            
            # Add count text
            total = completed + incomplete
            completion_rate = (completed / total * 100) if total > 0 else 0
            ax.text(0, -1.2, f'Total Tasks: {total}\nCompletion Rate: {completion_rate:.1f}%',
                   ha='center', va='center', fontsize=10, 
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        else:
            # Bar chart showing counts
            labels = ['Completed', 'Incomplete']
            counts = [completed, incomplete]
            colors = ['#4CAF50', '#F44336']
            
            bars = ax.bar(labels, counts, color=colors, edgecolor='black')
            ax.set_ylabel('Number of Tasks', fontsize=10)
            ax.set_title('Task Completion Rate (All Time)', fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='y')
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}', ha='center', va='bottom', fontsize=10)
            
            # Add total and percentage text
            total = completed + incomplete
            completion_rate = (completed / total * 100) if total > 0 else 0
            ax.text(0.5, 0.95, f'Total: {total} | Rate: {completion_rate:.1f}%',
                   transform=ax.transAxes, ha='center', fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        figure.tight_layout()
        self.task_completion_canvas.draw()
    
    def _generate_task_completion_by_day(self, start_date: str, end_date: str, view_type: str) -> None:
        """
        Create task completion chart showing completion per day.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            view_type: "Percentage" or "Count"
        """
        # Get all entries in date range
        entries = self.storage.get_entries_range(start_date, end_date)
        
        # Group tasks by day
        daily_completion = {}
        
        for entry in entries:
            if entry.tasks:
                completed = sum(1 for t in entry.tasks if t.completed)
                total = len(entry.tasks)
                daily_completion[entry.date] = {
                    'completed': completed,
                    'total': total,
                    'rate': (completed / total * 100) if total > 0 else 0
                }
        
        if not daily_completion:
            self._show_no_data_message(self.task_completion_canvas.figure, "No task data available")
            self.task_completion_canvas.draw()
            return
        
        # Sort by date
        sorted_dates = sorted(daily_completion.keys())
        date_objs = [datetime.strptime(date_str, "%Y-%m-%d").date() for date_str in sorted_dates]
        
        # Create chart
        figure = self.task_completion_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        if view_type == "Percentage":
            # Line chart showing completion rate over time
            rates = [daily_completion[date_str]['rate'] for date_str in sorted_dates]
            ax.plot(date_objs, rates, marker='o', linestyle='-', linewidth=2, markersize=5, color='teal')
            ax.set_ylabel('Completion Rate (%)', fontsize=10)
            ax.set_ylim(0, 105)
            ax.set_title('Task Completion Rate (By Day)', fontsize=12, fontweight='bold')
        else:
            # Stacked bar chart showing completed vs incomplete counts
            completed_counts = [daily_completion[date_str]['completed'] for date_str in sorted_dates]
            incomplete_counts = [daily_completion[date_str]['total'] - daily_completion[date_str]['completed'] 
                                for date_str in sorted_dates]
            
            ax.bar(date_objs, completed_counts, label='Completed', color='#4CAF50', edgecolor='black')
            ax.bar(date_objs, incomplete_counts, bottom=completed_counts, label='Incomplete', 
                   color='#F44336', edgecolor='black')
            ax.set_ylabel('Number of Tasks', fontsize=10)
            ax.set_title('Task Completion (By Day)', fontsize=12, fontweight='bold')
            ax.legend(loc='upper right', fontsize=9)
        
        ax.set_xlabel('Date', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax.tick_params(axis='x', rotation=45)
        figure.autofmt_xdate()
        
        figure.tight_layout()
        self.task_completion_canvas.draw()
    
    def _generate_task_completion_by_week(self, start_date: str, end_date: str, view_type: str) -> None:
        """
        Create task completion chart showing completion per week.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            view_type: "Percentage" or "Count"
        """
        # Get all entries in date range
        entries = self.storage.get_entries_range(start_date, end_date)
        
        # Group tasks by week
        weekly_completion = defaultdict(lambda: {'completed': 0, 'total': 0})
        
        for entry in entries:
            if entry.tasks:
                week_key = self._group_by_week(entry.date)
                for task in entry.tasks:
                    weekly_completion[week_key]['total'] += 1
                    if task.completed:
                        weekly_completion[week_key]['completed'] += 1
        
        if not weekly_completion:
            self._show_no_data_message(self.task_completion_canvas.figure, "No task data available")
            self.task_completion_canvas.draw()
            return
        
        # Calculate completion rates
        for week_key in weekly_completion:
            total = weekly_completion[week_key]['total']
            completed = weekly_completion[week_key]['completed']
            weekly_completion[week_key]['rate'] = (completed / total * 100) if total > 0 else 0
        
        # Sort by week
        sorted_weeks = sorted(weekly_completion.keys())
        
        # Create chart
        figure = self.task_completion_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        if view_type == "Percentage":
            # Line chart showing completion rate trend
            rates = [weekly_completion[week]['rate'] for week in sorted_weeks]
            ax.plot(sorted_weeks, rates, marker='o', linestyle='-', linewidth=2, markersize=6, color='teal')
            ax.set_ylabel('Completion Rate (%)', fontsize=10)
            ax.set_ylim(0, 105)
            ax.set_title('Task Completion Rate (By Week)', fontsize=12, fontweight='bold')
        else:
            # Stacked bar chart
            completed_counts = [weekly_completion[week]['completed'] for week in sorted_weeks]
            incomplete_counts = [weekly_completion[week]['total'] - weekly_completion[week]['completed'] 
                               for week in sorted_weeks]
            
            ax.bar(sorted_weeks, completed_counts, label='Completed', color='#4CAF50', edgecolor='black')
            ax.bar(sorted_weeks, incomplete_counts, bottom=completed_counts, label='Incomplete', 
                   color='#F44336', edgecolor='black')
            ax.set_ylabel('Number of Tasks', fontsize=10)
            ax.set_title('Task Completion (By Week)', fontsize=12, fontweight='bold')
            ax.legend(loc='upper right', fontsize=9)
        
        ax.set_xlabel('Week', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Rotate x-axis labels
        ax.tick_params(axis='x', rotation=45)
        
        figure.tight_layout()
        self.task_completion_canvas.draw()
    
    def _generate_task_completion_by_month(self, start_date: str, end_date: str, view_type: str) -> None:
        """
        Create task completion chart showing completion per month.
        
        Args:
            start_date: Start date string in "YYYY-MM-DD" format
            end_date: End date string in "YYYY-MM-DD" format
            view_type: "Percentage" or "Count"
        """
        # Get all entries in date range
        entries = self.storage.get_entries_range(start_date, end_date)
        
        # Group tasks by month
        monthly_completion = defaultdict(lambda: {'completed': 0, 'total': 0})
        
        for entry in entries:
            if entry.tasks:
                month_key = self._group_by_month(entry.date)
                for task in entry.tasks:
                    monthly_completion[month_key]['total'] += 1
                    if task.completed:
                        monthly_completion[month_key]['completed'] += 1
        
        if not monthly_completion:
            self._show_no_data_message(self.task_completion_canvas.figure, "No task data available")
            self.task_completion_canvas.draw()
            return
        
        # Calculate completion rates
        for month_key in monthly_completion:
            total = monthly_completion[month_key]['total']
            completed = monthly_completion[month_key]['completed']
            monthly_completion[month_key]['rate'] = (completed / total * 100) if total > 0 else 0
        
        # Sort by month
        sorted_months = sorted(monthly_completion.keys())
        
        # Create chart
        figure = self.task_completion_canvas.figure
        figure.clear()
        ax = figure.add_subplot(111)
        
        if view_type == "Percentage":
            # Line chart showing completion rate trend
            rates = [monthly_completion[month]['rate'] for month in sorted_months]
            ax.plot(sorted_months, rates, marker='o', linestyle='-', linewidth=2, markersize=6, color='teal')
            ax.set_ylabel('Completion Rate (%)', fontsize=10)
            ax.set_ylim(0, 105)
            ax.set_title('Task Completion Rate (By Month)', fontsize=12, fontweight='bold')
        else:
            # Stacked bar chart
            completed_counts = [monthly_completion[month]['completed'] for month in sorted_months]
            incomplete_counts = [monthly_completion[month]['total'] - monthly_completion[month]['completed'] 
                               for month in sorted_months]
            
            ax.bar(sorted_months, completed_counts, label='Completed', color='#4CAF50', edgecolor='black')
            ax.bar(sorted_months, incomplete_counts, bottom=completed_counts, label='Incomplete', 
                   color='#F44336', edgecolor='black')
            ax.set_ylabel('Number of Tasks', fontsize=10)
            ax.set_title('Task Completion (By Month)', fontsize=12, fontweight='bold')
            ax.legend(loc='upper right', fontsize=9)
        
        ax.set_xlabel('Month', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Rotate x-axis labels
        ax.tick_params(axis='x', rotation=45)
        
        figure.tight_layout()
        self.task_completion_canvas.draw()
    
    def _show_no_data_message(self, figure: Figure, message: str) -> None:
        """
        Display a "no data" message on the figure.
        
        Args:
            figure: Matplotlib figure
            message: Message to display
        """
        figure.clear()
        ax = figure.add_subplot(111)
        ax.text(0.5, 0.5, message, ha='center', va='center', 
               fontsize=14, transform=ax.transAxes, style='italic', color='gray')
        ax.axis('off')
