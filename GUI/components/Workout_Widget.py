from typing import TYPE_CHECKING, Optional
import json as json_module

from PyQt6.QtCore import QTime, Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent

# #region agent log
LOG_PATH = "/home/LxSparda/Desktop/Journal/.cursor/debug.log"
def _log_widget(component, method, message, data=None, hypothesis_id=None):
    try:
        with open(LOG_PATH, 'a') as f:
            log_entry = {
                "sessionId": "template-test",
                "runId": "run1",
                "hypothesisId": hypothesis_id or "A",
                "location": f"Workout_Widget.py:{component}.{method}",
                "message": message,
                "data": data or {},
                "timestamp": __import__('time').time() * 1000
            }
            f.write(json_module.dumps(log_entry) + "\n")
    except: pass
# #endregion
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from GUI.Main_Window import qdate_to_string
from GUI.components.Load_Template_Dialog import LoadTemplateDialog

if TYPE_CHECKING:
    from Models import Exercise, Set, Workout
    from features.Workout_Service import WorkoutService
    from features.Workout_Template_Service import WorkoutTemplateService


class CollapsibleSection(QWidget):
    """
    Reusable collapsible section widget with header and content.
    """
    
    def __init__(self, header_text: str, parent=None, default_expanded: bool = True) -> None:
        """
        Initialize Collapsible Section.
        
        Args:
            header_text: Text to display in the header
            parent: Parent widget
            default_expanded: Whether section starts expanded (default True)
        """
        super().__init__(parent)
        self.header_text = header_text
        self.is_expanded = default_expanded
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header frame (clickable)
        self.header_frame = QFrame()
        self.header_frame.setFrameShape(QFrame.Shape.Box)
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 3px;
                padding: 5px;
            }
            QFrame:hover {
                background-color: #313131;
            }
        """)
        self.header_frame.setCursor(Qt.CursorShape.PointingHandCursor)
        
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_layout.setSpacing(5)
        
        # Toggle icon (▶ when collapsed, ▼ when expanded)
        self.toggle_icon = QLabel("▼" if self.is_expanded else "▶")
        self.toggle_icon.setStyleSheet("font-size: 12pt; font-weight: bold; color: #cccccc;")
        self.toggle_icon.setMinimumWidth(20)
        header_layout.addWidget(self.toggle_icon)
        
        # Header label
        self.header_label = QLabel(self.header_text)
        self.header_label.setStyleSheet("font-weight: bold; font-size: 11pt; color: #ffffff;")
        header_layout.addWidget(self.header_label, stretch=1)
        
        # Make header clickable (but allow child widgets to receive events)
        self.header_frame.mousePressEvent = self._on_header_clicked
        # Ensure child widgets can still receive mouse events
        self.header_frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        layout.addWidget(self.header_frame)
        
        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 5, 10, 5)
        self.content_layout.setSpacing(5)
        
        layout.addWidget(self.content_widget)
        
        # Set initial state
        self.set_expanded(self.is_expanded)
    
    def _on_header_clicked(self, event: QMouseEvent) -> None:
        """Handle header click to toggle expansion."""
        # Only toggle if clicking on the frame itself, not child widgets
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is on a child widget (like QLineEdit or QPushButton)
            child = self.header_frame.childAt(event.pos())
            # Only toggle if clicking on label or empty space, not interactive widgets
            if child is None or isinstance(child, QLabel):
                self.toggle()
            # Otherwise, let the child widget handle the event
    
    def toggle(self) -> None:
        """Toggle expanded/collapsed state."""
        self.set_expanded(not self.is_expanded)
    
    def set_expanded(self, expanded: bool) -> None:
        """
        Set expanded state.
        
        Args:
            expanded: True to expand, False to collapse
        """
        self.is_expanded = expanded
        self.content_widget.setVisible(expanded)
        self.toggle_icon.setText("▼" if expanded else "▶")
    
    def is_expanded_state(self) -> bool:
        """
        Get current expanded state.
        
        Returns:
            True if expanded, False if collapsed
        """
        return self.is_expanded
    
    def set_header_text(self, text: str) -> None:
        """
        Update header text.
        
        Args:
            text: New header text
        """
        self.header_text = text
        self.header_label.setText(text)
    
    def get_content_layout(self) -> QVBoxLayout:
        """
        Get the content layout for adding widgets.
        
        Returns:
            QVBoxLayout of the content area
        """
        return self.content_layout


class SetRowWidget(QWidget):
    """
    Widget for a single set row (reps, weight, comment).
    """
    
    def __init__(self, set_index: int, parent=None) -> None:
        """
        Initialize Set Row Widget.
        
        Args:
            set_index: Index of this set in the exercise
            parent: Parent widget
        """
        super().__init__(parent)
        self.set_index = set_index
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)
        
        # Set number label
        set_label = QLabel(f"Set {self.set_index + 1}:")
        set_label.setMinimumWidth(50)
        layout.addWidget(set_label)
        
        # Reps
        reps_label = QLabel("Reps:")
        self.reps_spinbox = QSpinBox()
        self.reps_spinbox.setMinimum(1)
        self.reps_spinbox.setMaximum(1000)
        self.reps_spinbox.setValue(10)
        self.reps_spinbox.setMaximumWidth(80)
        self.reps_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                background-color: #4a4a4a;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QMenu::item {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #5a5a5a;
                color: #ffffff;
            }
        """)
        layout.addWidget(reps_label)
        layout.addWidget(self.reps_spinbox)
        
        # Weight
        weight_label = QLabel("Weight:")
        self.weight_spinbox = QDoubleSpinBox()
        self.weight_spinbox.setMinimum(0.0)
        self.weight_spinbox.setMaximum(10000.0)
        self.weight_spinbox.setDecimals(1)
        self.weight_spinbox.setSuffix(" lbs")
        self.weight_spinbox.setValue(0.0)
        self.weight_spinbox.setMaximumWidth(120)
        self.weight_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                background-color: #4a4a4a;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QMenu::item {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #5a5a5a;
                color: #ffffff;
            }
        """)
        layout.addWidget(weight_label)
        layout.addWidget(self.weight_spinbox)
        
        # Comment
        comment_label = QLabel("Comment:")
        self.comment_edit = QLineEdit()
        self.comment_edit.setPlaceholderText("Optional comment...")
        self.comment_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: #333333;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        layout.addWidget(comment_label)
        layout.addWidget(self.comment_edit, stretch=1)
        
        # Remove button
        self.remove_button = QPushButton("Remove")
        self.remove_button.setMaximumWidth(80)
        layout.addWidget(self.remove_button)
    
    def get_set_data(self) -> dict:
        """
        Get set data from form inputs.
        
        Returns:
            Dictionary with set data
        """
        return {
            "reps": self.reps_spinbox.value(),
            "weight": self.weight_spinbox.value(),
            "comment": self.comment_edit.text().strip(),
        }
    
    def set_set_data(self, reps: int, weight: float, comment: str = "") -> None:
        """
        Set set data in form inputs.
        
        Args:
            reps: Number of reps
            weight: Weight
            comment: Optional comment
        """
        self.reps_spinbox.setValue(reps)
        self.weight_spinbox.setValue(weight)
        self.comment_edit.setText(comment)
    
    def validate(self) -> tuple[bool, str]:
        """
        Validate set form inputs.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        reps = self.reps_spinbox.value()
        if reps <= 0:
            return False, "Reps must be greater than 0"
        
        weight = self.weight_spinbox.value()
        if weight < 0:
            return False, "Weight cannot be negative"
        
        return True, ""
    
    def highlight_invalid(self, is_invalid: bool) -> None:
        """
        Highlight form fields if invalid.
        
        Args:
            is_invalid: Whether to show invalid styling
        """
        base_style = """
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                background-color: #4a4a4a;
            }
        """
        double_style = """
            QDoubleSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                background-color: #4a4a4a;
            }
        """
        if is_invalid:
            invalid_border = "border: 2px solid red;"
            self.reps_spinbox.setStyleSheet(base_style + invalid_border)
            self.weight_spinbox.setStyleSheet(double_style + invalid_border)
        else:
            self.reps_spinbox.setStyleSheet(base_style)
            self.weight_spinbox.setStyleSheet(double_style)


class ExerciseFormWidget(QWidget):
    """
    Reusable widget for entering exercise details with multiple sets.
    """
    
    def __init__(self, exercise_index: int, parent=None, volume_callback=None, muscle_groups_list=None) -> None:
        """
        Initialize Exercise Form Widget.
        
        Args:
            exercise_index: Index of this exercise in the list
            parent: Parent widget
            volume_callback: Callback function to call when volume changes
            muscle_groups_list: List of available muscle groups
        """
        super().__init__(parent)
        self.exercise_index = exercise_index
        self.set_widgets: list[SetRowWidget] = []
        self.volume_callback = volume_callback
        self.muscle_groups_list = muscle_groups_list or []
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)
        
        # Outer collapsible section for the entire exercise
        self.exercise_collapsible = CollapsibleSection(
            f"Exercise {self.exercise_index + 1}:",
            default_expanded=True
        )
        
        # Customize header: Add exercise name input and remove button
        # Get the header layout
        header_layout = self.exercise_collapsible.header_frame.layout()
        
        # Exercise name label and input (in header so it's visible when collapsed)
        name_label = QLabel("Exercise Name:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Exercise name...")
        self.name_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: #333333;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        # Update header text when name changes
        self.name_edit.textChanged.connect(self._update_exercise_header)
        
        # Insert after header label
        header_layout.insertWidget(2, name_label)
        header_layout.insertWidget(3, self.name_edit)
        
        # Remove exercise button
        self.remove_button = QPushButton("Remove Exercise")
        self.remove_button.setMaximumWidth(120)
        header_layout.addWidget(self.remove_button)
        
        # Content area (visible when expanded)
        content_layout = self.exercise_collapsible.get_content_layout()
        
        # Inner collapsible 1: Muscle Groups (collapsed by default)
        self.muscle_groups_section = CollapsibleSection("Muscle Groups", default_expanded=False)
        muscle_content_layout = self.muscle_groups_section.get_content_layout()
        
        muscle_layout = QGridLayout()
        muscle_layout.setContentsMargins(0, 0, 0, 0)
        muscle_layout.setSpacing(5)
        
        self.muscle_checkboxes = {}
        row = 0
        col = 0
        max_cols = 4
        
        for muscle in self.muscle_groups_list:
            checkbox = QCheckBox(muscle)
            self.muscle_checkboxes[muscle] = checkbox
            muscle_layout.addWidget(checkbox, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Add grid layout to muscle groups content
        muscle_widget = QWidget()
        muscle_widget.setLayout(muscle_layout)
        muscle_content_layout.addWidget(muscle_widget)
        
        content_layout.addWidget(self.muscle_groups_section)
        
        # Inner collapsible 2: Sets (collapsed by default)
        self.sets_section = CollapsibleSection("Sets", default_expanded=False)
        sets_content_layout = self.sets_section.get_content_layout()
        
        # Sets container with scroll area
        sets_scroll = QScrollArea()
        sets_scroll.setWidgetResizable(True)
        sets_scroll.setMaximumHeight(200)
        sets_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self.sets_container = QWidget()
        self.sets_layout = QVBoxLayout(self.sets_container)
        self.sets_layout.setContentsMargins(0, 0, 0, 0)
        self.sets_layout.setSpacing(2)
        
        sets_scroll.setWidget(self.sets_container)
        sets_content_layout.addWidget(sets_scroll)
        
        # Add Set button
        add_set_button = QPushButton("Add Set")
        add_set_button.clicked.connect(self._add_set)
        sets_content_layout.addWidget(add_set_button)
        
        content_layout.addWidget(self.sets_section)
        
        # Add outer collapsible to main layout
        main_layout.addWidget(self.exercise_collapsible)
        
        # Add default 2 sets
        self._add_set()
        self._add_set()
    
    def _update_exercise_header(self) -> None:
        """Update exercise header text when name changes."""
        name = self.name_edit.text().strip()
        if name:
            self.exercise_collapsible.set_header_text(f"Exercise {self.exercise_index + 1}: {name}")
        else:
            self.exercise_collapsible.set_header_text(f"Exercise {self.exercise_index + 1}:")
    
    def set_exercise_index(self, index: int) -> None:
        """
        Update exercise index and refresh header.
        
        Args:
            index: New exercise index
        """
        self.exercise_index = index
        self._update_exercise_header()
    
    def _add_set(self) -> None:
        """Add a new set row."""
        set_widget = SetRowWidget(len(self.set_widgets))
        set_widget.remove_button.clicked.connect(
            lambda checked=False, idx=len(self.set_widgets): self._remove_set(idx)
        )
        
        # Connect to volume calculation callback
        if self.volume_callback:
            set_widget.reps_spinbox.valueChanged.connect(self.volume_callback)
            set_widget.weight_spinbox.valueChanged.connect(self.volume_callback)
        
        self.sets_layout.addWidget(set_widget)
        self.set_widgets.append(set_widget)
        
        # Update set numbers
        self._update_set_numbers()
    
    def _remove_set(self, index: int) -> None:
        """Remove set at index."""
        if 0 <= index < len(self.set_widgets) and len(self.set_widgets) > 1:
            widget = self.set_widgets[index]
            widget.setParent(None)
            widget.deleteLater()
            self.set_widgets.pop(index)
            
            # Re-index remaining sets
            self._update_set_numbers()
            if self.volume_callback:
                self.volume_callback()
    
    def _update_set_numbers(self) -> None:
        """Update set number labels."""
        for i, widget in enumerate(self.set_widgets):
            # Update the set label (first widget in the layout)
            layout = widget.layout()
            if layout and layout.count() > 0:
                label = layout.itemAt(0).widget()
                if isinstance(label, QLabel):
                    label.setText(f"Set {i + 1}:")
            widget.set_index = i
    
    
    def get_exercise_data(self) -> dict:
        """
        Get exercise data from form inputs.
        
        Returns:
            Dictionary with exercise data including list of sets and muscle groups
        """
        sets_data = []
        for widget in self.set_widgets:
            set_data = widget.get_set_data()
            sets_data.append(set_data)
        
        # Get selected muscle groups
        muscle_groups = [muscle for muscle, checkbox in self.muscle_checkboxes.items() if checkbox.isChecked()]
        
        return {
            "name": self.name_edit.text().strip(),
            "sets": sets_data,
            "muscle_groups": muscle_groups,
        }
    
    def set_exercise_data(self, name: str, sets: list[dict], muscle_groups: list[str] = None) -> None:
        """
        Set exercise data in form inputs.
        
        Args:
            name: Exercise name
            sets: List of set dictionaries with reps, weight, comment
            muscle_groups: List of muscle group names for this exercise
        """
        self.name_edit.setText(name)
        # Update header with name
        self._update_exercise_header()
        
        # Set muscle groups (only set checkboxes for muscles in the valid list)
        if muscle_groups is None:
            muscle_groups = []
        # Filter to only valid muscle groups (Option A - ignore legacy groups)
        valid_muscle_groups = [mg for mg in muscle_groups if mg in self.muscle_groups_list]
        for muscle, checkbox in self.muscle_checkboxes.items():
            checkbox.setChecked(muscle in valid_muscle_groups)
        
        # Clear existing sets
        for widget in self.set_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.set_widgets.clear()
        
        # Add sets from data
        if sets:
            for set_data in sets:
                set_widget = SetRowWidget(len(self.set_widgets))
                set_widget.set_set_data(
                    set_data.get("reps", 10),
                    set_data.get("weight", 0.0),
                    set_data.get("comment", ""),
                )
                set_widget.remove_button.clicked.connect(
                    lambda checked=False, idx=len(self.set_widgets): self._remove_set(idx)
                )
                if self.volume_callback:
                    set_widget.reps_spinbox.valueChanged.connect(self.volume_callback)
                    set_widget.weight_spinbox.valueChanged.connect(self.volume_callback)
                
                self.sets_layout.addWidget(set_widget)
                self.set_widgets.append(set_widget)
        else:
            # Add default 2 sets if none provided
            self._add_set()
            self._add_set()
        
        self._update_set_numbers()
    
    def validate(self) -> tuple[bool, str]:
        """
        Validate exercise form inputs.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        name = self.name_edit.text().strip()
        if not name:
            return False, "Exercise name cannot be empty"
        
        if len(self.set_widgets) == 0:
            return False, "Exercise must have at least one set"
        
        # Check if at least one muscle group is selected
        muscle_groups = [muscle for muscle, checkbox in self.muscle_checkboxes.items() if checkbox.isChecked()]
        if not muscle_groups:
            return False, "Exercise must have at least one muscle group selected"
        
        # Validate each set
        for i, set_widget in enumerate(self.set_widgets):
            is_valid, error_msg = set_widget.validate()
            if not is_valid:
                set_widget.highlight_invalid(True)
                return False, f"Set {i + 1}: {error_msg}"
            else:
                set_widget.highlight_invalid(False)
        
        return True, ""
    
    def highlight_invalid(self, is_invalid: bool) -> None:
        """
        Highlight form fields if invalid.
        
        Args:
            is_invalid: Whether to show invalid styling
        """
        base_style = """
            QLineEdit {
                background-color: white;
                color: #333333;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px;
            }
        """
        if is_invalid:
            self.name_edit.setStyleSheet(base_style + "border: 2px solid red;")
        else:
            self.name_edit.setStyleSheet(base_style)


class WorkoutWidget(QWidget):
    """
    Complex form widget for entering workout details with exercises and muscle groups.
    """
    
    # Signal emitted when workout data is saved
    data_saved = pyqtSignal()
    
    # Common muscle groups (restricted to 7 options)
    MUSCLE_GROUPS = [
        "Chest",
        "Back",
        "Shoulders",
        "Biceps",
        "Triceps",
        "Legs",
        "Cardio",
    ]
    
    def __init__(self, workout_service: "WorkoutService", template_service: "WorkoutTemplateService" = None) -> None:
        """
        Initialize Workout Widget.
        
        Args:
            workout_service: WorkoutService instance for data operations
            template_service: WorkoutTemplateService instance for template operations (optional)
        """
        super().__init__()
        
        self.workout_service = workout_service
        self.template_service = template_service
        self.current_date: str | None = None
        self.exercise_widgets: list[ExerciseFormWidget] = []
        self._current_session_id: str | None = None  # API session_id for delete/restore
        
        self._setup_ui()
    
    def _filter_valid_muscle_groups(self, muscle_groups: list[str]) -> list[str]:
        """
        Filter muscle groups to only include valid ones (Option A migration).
        Legacy muscle groups not in the new 7 are ignored/dropped.
        
        Args:
            muscle_groups: List of muscle group names (may include legacy groups)
            
        Returns:
            Filtered list containing only muscle groups in MUSCLE_GROUPS
        """
        return [mg for mg in muscle_groups if mg in self.MUSCLE_GROUPS]
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        # Set global menu styling for dropdown menus
        self.setStyleSheet("""
            QMenu {
                background-color: #E0E0E0;
                color: #333333;
                border: 1px solid #CCCCCC;
                padding: 2px;
            }
            QMenu::item {
                background-color: #E0E0E0;
                color: #333333;
                padding: 4px 20px 4px 8px;
            }
            QMenu::item:selected {
                background-color: #C0C0C0;
                color: #000000;
            }
            QMenu::item:disabled {
                color: #999999;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Workout Info Section
        info_group = QGroupBox("Workout Information")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(10)
        
        # Muscle Groups
        muscle_group = QGroupBox("Muscle Groups")
        muscle_layout = QGridLayout(muscle_group)
        
        self.muscle_checkboxes = {}
        row = 0
        col = 0
        max_cols = 4
        
        for muscle in self.MUSCLE_GROUPS:
            checkbox = QCheckBox(muscle)
            checkbox.stateChanged.connect(self._on_muscle_group_changed)
            self.muscle_checkboxes[muscle] = checkbox
            muscle_layout.addWidget(checkbox, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        info_layout.addWidget(muscle_group)
        
        # Duration and Notes row
        duration_notes_layout = QHBoxLayout()
        
        # Duration and Time row
        duration_time_layout = QHBoxLayout()
        
        # Duration
        duration_layout = QVBoxLayout()
        duration_layout.addWidget(QLabel("Duration (minutes):"))
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setMinimum(0)
        self.duration_spinbox.setMaximum(1440)  # 24 hours
        self.duration_spinbox.setValue(0)
        self.duration_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4a4a4a;
                border: 1px solid #555555;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
                background-color: #4a4a4a;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QMenu::item {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 4px 20px;
            }
            QMenu::item:selected {
                background-color: #5a5a5a;
                color: #ffffff;
            }
        """)
        duration_layout.addWidget(self.duration_spinbox)
        duration_time_layout.addLayout(duration_layout)
        
        # Time (optional)
        time_layout = QVBoxLayout()
        time_layout.addWidget(QLabel("Time (optional):"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())  # Default to current time
        self.time_edit.setCalendarPopup(False)
        # Allow clearing time (set to invalid time to represent "not set")
        time_layout.addWidget(self.time_edit)
        duration_time_layout.addLayout(time_layout)
        
        duration_notes_layout.addLayout(duration_time_layout)
        
        # Notes
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(QLabel("Workout Notes:"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Add workout notes...")
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                color: #333333;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        notes_layout.addWidget(self.notes_edit)
        duration_notes_layout.addLayout(notes_layout, stretch=1)
        
        info_layout.addLayout(duration_notes_layout)
        
        main_layout.addWidget(info_group)
        
        # Exercises Section
        exercises_group = QGroupBox("Exercises")
        exercises_layout = QVBoxLayout(exercises_group)
        
        # Header with Add button and Volume display
        header_layout = QHBoxLayout()
        
        self.add_exercise_button = QPushButton("Add Exercise")
        self.add_exercise_button.clicked.connect(self._add_exercise)
        header_layout.addWidget(self.add_exercise_button)
        
        header_layout.addStretch()
        
        self.volume_label = QLabel("Total Volume: 0.0 lbs")
        self.volume_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        header_layout.addWidget(self.volume_label)
        
        exercises_layout.addLayout(header_layout)
        
        # Scrollable area for exercises
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 3px;
            }
        """)
        
        self.exercises_container = QWidget()
        self.exercises_container.setStyleSheet("background-color: #2d2d2d;")
        self.exercises_layout = QVBoxLayout(self.exercises_container)
        self.exercises_layout.setContentsMargins(5, 5, 5, 5)
        self.exercises_layout.setSpacing(5)
        self.exercises_layout.addStretch()
        
        scroll_area.setWidget(self.exercises_container)
        exercises_layout.addWidget(scroll_area)
        
        main_layout.addWidget(exercises_group, stretch=1)
        
        # Day Type Status Label (for rest/missed days)
        self.day_type_label = QLabel("")
        self.day_type_label.setStyleSheet("font-weight: bold; font-size: 12pt; padding: 10px;")
        self.day_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.day_type_label.setVisible(False)
        main_layout.addWidget(self.day_type_label)
        
        # Rest/Missed Day Buttons
        rest_missed_layout = QHBoxLayout()
        rest_missed_layout.addStretch()
        
        self.mark_rest_button = QPushButton("Mark as Rest Day")
        self.mark_rest_button.setStyleSheet("background-color: #9370DB; color: white; font-weight: bold;")
        self.mark_rest_button.clicked.connect(self._mark_as_rest_day)
        rest_missed_layout.addWidget(self.mark_rest_button)
        
        self.mark_missed_button = QPushButton("Mark as Missed Day")
        self.mark_missed_button.setStyleSheet("background-color: #DC143C; color: white; font-weight: bold;")
        self.mark_missed_button.clicked.connect(self._mark_as_missed_day)
        rest_missed_layout.addWidget(self.mark_missed_button)
        
        self.clear_rest_missed_button = QPushButton("Clear Rest/Missed")
        self.clear_rest_missed_button.setStyleSheet("background-color: #666666; color: white;")
        self.clear_rest_missed_button.clicked.connect(self._clear_rest_missed)
        self.clear_rest_missed_button.setVisible(False)  # Only show when rest/missed is active
        rest_missed_layout.addWidget(self.clear_rest_missed_button)
        
        rest_missed_layout.addStretch()
        main_layout.addLayout(rest_missed_layout)
        
        # Action Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        clear_button = QPushButton("Clear Workout")
        clear_button.clicked.connect(self._clear_workout)
        buttons_layout.addWidget(clear_button)
        
        self.delete_workout_button = QPushButton("Delete from server")
        self.delete_workout_button.setStyleSheet("background-color: #8B0000; color: white;")
        self.delete_workout_button.clicked.connect(self._delete_workout_from_server)
        self.delete_workout_button.setVisible(False)
        buttons_layout.addWidget(self.delete_workout_button)
        
        self.restore_workout_button = QPushButton("Restore workout")
        self.restore_workout_button.clicked.connect(self._restore_workout)
        self.restore_workout_button.setVisible(False)
        buttons_layout.addWidget(self.restore_workout_button)
        
        # Save as Template button (only if template service is available)
        if self.template_service:
            save_template_button = QPushButton("Save as Template")
            save_template_button.clicked.connect(self._save_as_template)
            buttons_layout.addWidget(save_template_button)
            
            load_template_button = QPushButton("Load Template")
            load_template_button.clicked.connect(self._load_template)
            buttons_layout.addWidget(load_template_button)
        
        save_button = QPushButton("Save Workout")
        save_button.setStyleSheet("font-weight: bold;")
        save_button.clicked.connect(self._save_workout)
        buttons_layout.addWidget(save_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Store references to form widgets for enabling/disabling
        self.workout_form_widgets = [
            info_group, exercises_group, save_button, clear_button
        ]
    
    def _on_muscle_group_changed(self) -> None:
        """Update muscle group list when checkboxes change."""
        # This is called automatically when checkboxes change
        # Volume will be recalculated when needed
        pass
    
    def _get_selected_muscle_groups(self) -> list[str]:
        """
        Get list of selected muscle groups.
        
        Returns:
            List of selected muscle group names
        """
        return [muscle for muscle, checkbox in self.muscle_checkboxes.items() if checkbox.isChecked()]
    
    def _add_exercise(self) -> None:
        """Add new exercise form."""
        exercise_widget = ExerciseFormWidget(
            len(self.exercise_widgets),
            volume_callback=self._update_volume_display,
            muscle_groups_list=self.MUSCLE_GROUPS
        )
        exercise_widget.remove_button.clicked.connect(
            lambda checked=False, idx=len(self.exercise_widgets): self._remove_exercise(idx)
        )
        
        # Connect set changes to volume calculation for existing sets
        for set_widget in exercise_widget.set_widgets:
            set_widget.reps_spinbox.valueChanged.connect(self._update_volume_display)
            set_widget.weight_spinbox.valueChanged.connect(self._update_volume_display)
        
        self.exercises_layout.insertWidget(self.exercises_layout.count() - 1, exercise_widget)
        self.exercise_widgets.append(exercise_widget)
        
        self._update_volume_display()
    
    def _remove_exercise(self, index: int) -> None:
        """Remove exercise at index."""
        if 0 <= index < len(self.exercise_widgets):
            widget = self.exercise_widgets[index]
            widget.setParent(None)
            widget.deleteLater()
            self.exercise_widgets.pop(index)
            
            # Re-index remaining widgets
            for i, w in enumerate(self.exercise_widgets):
                w.set_exercise_index(i)
            
            self._update_volume_display()
    
    def _get_exercises_data(self) -> list[dict]:
        """
        Get exercise data from all exercise forms.
        
        Returns:
            List of exercise data dictionaries with sets list
        """
        exercises = []
        for widget in self.exercise_widgets:
            data = widget.get_exercise_data()
            if data["name"]:  # Only include if name is not empty
                exercises.append(data)
        return exercises
    
    def _validate_workout(self) -> tuple[bool, str]:
        """
        Validate workout data.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check exercises
        exercises = self._get_exercises_data()
        if not exercises:
            return False, "Please add at least one exercise"
        
        # Validate each exercise (each exercise validates its own muscle groups)
        for i, widget in enumerate(self.exercise_widgets):
            is_valid, error_msg = widget.validate()
            if not is_valid:
                widget.highlight_invalid(True)
                return False, f"Exercise {i + 1}: {error_msg}"
            else:
                widget.highlight_invalid(False)
        
        return True, ""
    
    def _calculate_volume(self) -> float:
        """
        Calculate total volume for all exercises.
        
        Returns:
            Total volume (sum of reps × weight for all sets in all exercises)
        """
        total_volume = 0.0
        for widget in self.exercise_widgets:
            data = widget.get_exercise_data()
            if data["name"]:
                # Sum volume for all sets in this exercise
                for set_data in data["sets"]:
                    volume = set_data["reps"] * set_data["weight"]
                    total_volume += volume
        return total_volume
    
    def _update_volume_display(self) -> None:
        """Update the volume display label."""
        volume = self._calculate_volume()
        self.volume_label.setText(f"Total Volume: {volume:,.1f} lbs")
    
    def _save_workout(self) -> None:
        """Validate and save workout to storage."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        # Validate workout
        is_valid, error_msg = self._validate_workout()
        if not is_valid:
            QMessageBox.warning(self, "Validation Error", error_msg)
            return
        
        # Get workout data
        muscle_groups = self._get_selected_muscle_groups()  # Already filtered (only valid checkboxes exist)
        exercises_data = self._get_exercises_data()
        duration = self.duration_spinbox.value()
        notes = self.notes_edit.toPlainText().strip()
        
        # Get workout time (optional)
        workout_time = None
        if self.time_edit.time().isValid():
            # Convert QTime to "HH:MM" string format
            time = self.time_edit.time()
            workout_time = f"{time.hour():02d}:{time.minute():02d}"
        
        # Create Exercise objects with Set objects
        from Models import Exercise, Set
        exercises = []
        for data in exercises_data:
            # Create Set objects from sets data
            set_objects = [
                Set(
                    reps=set_data["reps"],
                    weight=set_data["weight"],
                    comment=set_data.get("comment", ""),
                )
                for set_data in data["sets"]
            ]
            # Get muscle groups for this exercise and filter to valid ones (Option A)
            exercise_muscle_groups = data.get("muscle_groups", [])
            filtered_muscle_groups = self._filter_valid_muscle_groups(exercise_muscle_groups)
            exercises.append(Exercise(
                name=data["name"], 
                sets=set_objects,
                muscle_groups=filtered_muscle_groups
            ))
        
        # Collect all unique muscle groups from exercises for workout-level tracking
        all_muscle_groups = set()
        for exercise in exercises:
            all_muscle_groups.update(exercise.muscle_groups)
        
        # Save via API when configured, else storage
        if getattr(self.workout_service, "api_client", None):
            success, err = self.workout_service.create_workout_via_api(
                self.current_date,
                list(all_muscle_groups),
                exercises,
                duration_minutes=duration,
                notes=notes,
                workout_time=workout_time,
            )
            if not success:
                QMessageBox.warning(self, "Error", err or "Failed to save workout.")
                return
        else:
            success = self.workout_service.create_workout(
                self.current_date,
                list(all_muscle_groups),
                exercises,
                duration_minutes=duration,
                notes=notes,
                workout_time=workout_time,
            )
            if not success:
                QMessageBox.warning(self, "Error", "Failed to save workout. Please check your input.")
                return
        
        QMessageBox.information(self, "Success", "Workout saved successfully!")
        self.data_saved.emit()
        # Reload current date so widget shows saved workout from API cache
        self.load_entry(self.current_date)
    
    def _build_template_data(self) -> Optional[dict]:
        """
        Build template data dictionary from current workout form.
        Reuses the same logic as _save_workout but returns dict instead of saving.
        
        Returns:
            Dictionary with template data (muscle_groups, exercises, duration_minutes, notes)
            Returns None if validation fails
        """
        # #region agent log
        _log_widget("WorkoutWidget", "_build_template_data", "ENTRY", {}, "B")
        # #endregion
        # Get workout data (same as _save_workout, but without date requirement)
        muscle_groups = self._get_selected_muscle_groups()
        exercises_data = self._get_exercises_data()
        duration = self.duration_spinbox.value()
        notes = self.notes_edit.toPlainText().strip()
        
        # #region agent log
        _log_widget("WorkoutWidget", "_build_template_data", "BEFORE_BUILD", {"muscle_groups_count": len(muscle_groups), "exercises_count": len(exercises_data), "duration": duration}, "B")
        # #endregion
        
        # Get workout time (optional)
        workout_time = None
        if self.time_edit.time().isValid():
            # Convert QTime to "HH:MM" string format
            time = self.time_edit.time()
            workout_time = f"{time.hour():02d}:{time.minute():02d}"
        
        # Build template data structure (no date field)
        template_data = {
            "muscle_groups": muscle_groups,
            "exercises": exercises_data,  # Already in dict format with sets as dicts
            "duration_minutes": duration,
            "notes": notes,
            "workout_time": workout_time,
        }
        
        # #region agent log
        _log_widget("WorkoutWidget", "_build_template_data", "EXIT", {"has_date": "date" in template_data, "keys": list(template_data.keys()), "exercise_count": len(template_data.get("exercises", []))}, "B")
        # #endregion
        return template_data
    
    def _save_as_template(self) -> None:
        """
        Save current workout as a template.
        Validates workout, prompts for name, handles overwrite confirmation.
        """
        # #region agent log
        _log_widget("WorkoutWidget", "_save_as_template", "ENTRY", {"has_service": self.template_service is not None}, "C")
        # #endregion
        if not self.template_service:
            QMessageBox.warning(self, "Error", "Template service not available.")
            return
        
        # Validate workout first
        is_valid, error_msg = self._validate_workout()
        # #region agent log
        _log_widget("WorkoutWidget", "_save_as_template", "VALIDATION", {"is_valid": is_valid, "error": error_msg}, "C")
        # #endregion
        if not is_valid:
            QMessageBox.warning(self, "Validation Error", error_msg)
            return
        
        # Build template data
        template_data = self._build_template_data()
        if template_data is None:
            QMessageBox.warning(self, "Error", "Failed to build template data.")
            return
        
        # Prompt for template name
        # Prefill with workout notes if available, otherwise "Workout"
        prefilled_name = self.notes_edit.toPlainText().strip() or "Workout"
        
        name, ok = QInputDialog.getText(
            self,
            "Save as Template",
            "Template name:",
            text=prefilled_name
        )
        
        if not ok:
            return  # User cancelled
        
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Template name cannot be empty.")
            return
        
        # Check if template already exists
        exists = self.template_service.template_exists(name)
        # #region agent log
        _log_widget("WorkoutWidget", "_save_as_template", "BEFORE_OVERWRITE_CHECK", {"name": name, "exists": exists}, "C")
        # #endregion
        if exists:
            reply = QMessageBox.question(
                self,
                "Template Exists",
                f"Template '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            # #region agent log
            _log_widget("WorkoutWidget", "_save_as_template", "OVERWRITE_RESPONSE", {"user_choice": "yes" if reply == QMessageBox.StandardButton.Yes else "no"}, "C")
            # #endregion
            if reply != QMessageBox.StandardButton.Yes:
                return  # User chose not to overwrite
        
        # Save template
        success = self.template_service.save_template(name, template_data)
        # #region agent log
        _log_widget("WorkoutWidget", "_save_as_template", "EXIT", {"success": success, "name": name}, "C")
        # #endregion
        if success:
            QMessageBox.information(self, "Success", f"Template '{name}' saved successfully!")
        else:
            QMessageBox.warning(self, "Error", "Failed to save template.")
    
    def _load_template(self) -> None:
        """
        Load a workout template.
        Shows dialog to select template and load mode, then applies to current date.
        """
        # #region agent log
        _log_widget("WorkoutWidget", "_load_template", "ENTRY", {"has_service": self.template_service is not None, "current_date": self.current_date}, "D")
        # #endregion
        if not self.template_service:
            QMessageBox.warning(self, "Error", "Template service not available.")
            return
        
        # Get list of templates
        template_names = self.template_service.list_templates()
        # #region agent log
        _log_widget("WorkoutWidget", "_load_template", "TEMPLATE_LIST", {"count": len(template_names), "names": template_names}, "D")
        # #endregion
        if not template_names:
            QMessageBox.information(self, "No Templates", "No saved templates available.")
            return
        
        # Show load template dialog
        dialog = LoadTemplateDialog(template_names, self)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled
        
        # Check if delete was requested
        if dialog.should_delete():
            template_name = dialog.get_selected_template()
            success = self.template_service.delete_template(template_name)
            
            if success:
                QMessageBox.information(self, "Success", f"Template '{template_name}' deleted successfully.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to delete template '{template_name}'.")
            return
        
        # Get selected template and load mode
        template_name = dialog.get_selected_template()
        load_with_set_data = dialog.get_load_mode()
        # #region agent log
        _log_widget("WorkoutWidget", "_load_template", "BEFORE_LOAD", {"template_name": template_name, "load_with_set_data": load_with_set_data}, "D")
        # #endregion
        
        # Get template data
        template_data = self.template_service.get_template(template_name)
        
        if template_data is None:
            QMessageBox.warning(self, "Error", f"Could not load template '{template_name}'.")
            return
        
        # #region agent log
        _log_widget("WorkoutWidget", "_load_template", "TEMPLATE_DATA_LOADED", {"has_exercises": "exercises" in template_data, "exercise_count": len(template_data.get("exercises", []))}, "D")
        # #endregion
        
        # Check if user has unsaved changes (optional warning)
        # For now, we'll just load over existing data
        
        # Apply template to current date
        self._apply_template_to_form(template_data, load_with_set_data)
        
        # Show success message
        mode_text = "with set data" if load_with_set_data else "without set data"
        date_text = self.current_date if self.current_date else "current date"
        QMessageBox.information(
            self,
            "Template Loaded",
            f"Template '{template_name}' loaded {mode_text} for {date_text}."
        )
    
    def _apply_template_to_form(self, template_data: dict, load_with_set_data: bool) -> None:
        """
        Apply template data to the workout form.
        
        Args:
            template_data: Template data dictionary
            load_with_set_data: If True, use stored set data; if False, use blank defaults
        """
        # #region agent log
        _log_widget("WorkoutWidget", "_apply_template_to_form", "ENTRY", {"load_with_set_data": load_with_set_data, "exercise_count": len(template_data.get("exercises", []))}, "E")
        # #endregion
        # Clear existing workout form
        self._clear_workout_form()
        
        # Set workout-level muscle groups
        muscle_groups = template_data.get("muscle_groups", [])
        filtered_muscle_groups = self._filter_valid_muscle_groups(muscle_groups)
        for muscle, checkbox in self.muscle_checkboxes.items():
            checkbox.setChecked(muscle in filtered_muscle_groups)
        
        # Set duration, notes, and time
        self.duration_spinbox.setValue(template_data.get("duration_minutes", 0))
        self.notes_edit.setPlainText(template_data.get("notes", ""))
        
        # Set workout time if available
        workout_time = template_data.get("workout_time")
        if workout_time:
            try:
                # Parse "HH:MM" string to QTime
                hour, minute = map(int, workout_time.split(":"))
                self.time_edit.setTime(QTime(hour, minute))
            except (ValueError, AttributeError):
                # Invalid time format, leave as default
                self.time_edit.setTime(QTime.currentTime())
        else:
            # Clear time (set to current time as default)
            self.time_edit.setTime(QTime.currentTime())
        
        # Load exercises
        exercises = template_data.get("exercises", [])
        
        for exercise_data in exercises:
            exercise_name = exercise_data.get("name", "")
            exercise_muscle_groups = exercise_data.get("muscle_groups", [])
            sets_data = exercise_data.get("sets", [])
            
            # Filter muscle groups to valid ones
            filtered_exercise_muscle_groups = self._filter_valid_muscle_groups(exercise_muscle_groups)
            
            # Handle sets based on load mode
            if load_with_set_data:
                # Use sets as-is from template
                processed_sets = sets_data
                # #region agent log
                _log_widget("WorkoutWidget", "_apply_template_to_form", "SETS_PROCESSING", {"mode": "with_data", "set_count": len(processed_sets), "first_set": processed_sets[0] if processed_sets else None}, "E")
                # #endregion
            else:
                # Replace sets with blank defaults (keep number of sets)
                # Default values match SetRowWidget defaults: reps=10, weight=0, comment=""
                processed_sets = [
                    {
                        "reps": 10,
                        "weight": 0.0,
                        "comment": ""
                    }
                    for _ in sets_data
                ]
                # #region agent log
                _log_widget("WorkoutWidget", "_apply_template_to_form", "SETS_PROCESSING", {"mode": "without_data", "set_count": len(processed_sets), "first_set": processed_sets[0] if processed_sets else None}, "E")
                # #endregion
            
            # Create exercise widget
            exercise_widget = ExerciseFormWidget(
                len(self.exercise_widgets),
                volume_callback=self._update_volume_display,
                muscle_groups_list=self.MUSCLE_GROUPS
            )
            
            # Set exercise data
            exercise_widget.set_exercise_data(
                exercise_name,
                processed_sets,
                filtered_exercise_muscle_groups
            )
            
            # Connect remove button
            exercise_widget.remove_button.clicked.connect(
                lambda checked=False, idx=len(self.exercise_widgets): self._remove_exercise(idx)
            )
            
            # Connect set changes to volume calculation
            for set_widget in exercise_widget.set_widgets:
                set_widget.reps_spinbox.valueChanged.connect(self._update_volume_display)
                set_widget.weight_spinbox.valueChanged.connect(self._update_volume_display)
            
            # Add to layout
            self.exercises_layout.insertWidget(self.exercises_layout.count() - 1, exercise_widget)
            self.exercise_widgets.append(exercise_widget)
        
        # #region agent log
        _log_widget("WorkoutWidget", "_apply_template_to_form", "EXIT", {"exercise_widgets_count": len(self.exercise_widgets)}, "E")
        # #endregion
        
        # Update volume display
        self._update_volume_display()
    
    def _clear_workout_form(self) -> None:
        """Clear all workout data without showing confirmation dialog."""
        # Clear muscle group checkboxes
        for checkbox in self.muscle_checkboxes.values():
            checkbox.setChecked(False)
        
        # Clear duration, notes, and time
        self.duration_spinbox.setValue(0)
        self.notes_edit.clear()
        # Clear time (set to current time as default)
        self.time_edit.setTime(QTime.currentTime())
        
        # Clear exercises
        for widget in self.exercise_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.exercise_widgets.clear()
        
        self._update_volume_display()
    
    def _clear_workout(self) -> None:
        """Clear all workout data with confirmation dialog."""
        reply = QMessageBox.question(
            self,
            "Clear Workout",
            "Are you sure you want to clear all workout data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._clear_workout_form()
    
    def load_entry(self, date: str) -> None:
        """
        Load workout for the given date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
        """
        self.current_date = date
        
        # Check day type (workout, rest, missed, or None)
        day_type = self.workout_service.get_day_type(date)
        
        # Update UI based on day type
        if day_type == "rest":
            self._current_session_id = None
            self._update_delete_restore_buttons()
            self._show_rest_day_ui()
            return
        elif day_type == "missed":
            self._current_session_id = None
            self._update_delete_restore_buttons()
            self._show_missed_day_ui()
            return
        else:
            self._show_normal_workout_ui()
        
        # Load workout from service
        workout = self.workout_service.get_workout(date)
        
        if workout is None:
            # Clear form if no workout (without confirmation dialog)
            self._current_session_id = None
            self._update_delete_restore_buttons()
            self._clear_workout_form()
            return
        
        # Load muscle groups (filter to valid ones - Option A migration)
        workout_muscle_groups = workout.muscle_groups if workout.muscle_groups else []
        filtered_workout_muscle_groups = self._filter_valid_muscle_groups(workout_muscle_groups)
        for muscle, checkbox in self.muscle_checkboxes.items():
            checkbox.setChecked(muscle in filtered_workout_muscle_groups)
        
        # Load duration, notes, and time
        self.duration_spinbox.setValue(workout.duration_minutes)
        self.notes_edit.setPlainText(workout.notes)
        
        # Load workout time if available
        if workout.workout_time:
            try:
                # Parse "HH:MM" string to QTime
                hour, minute = map(int, workout.workout_time.split(":"))
                self.time_edit.setTime(QTime(hour, minute))
            except (ValueError, AttributeError):
                # Invalid time format, leave as default
                self.time_edit.setTime(QTime.currentTime())
        else:
            # Clear time (set to current time as default)
            self.time_edit.setTime(QTime.currentTime())
        
        # Clear existing exercises
        for widget in self.exercise_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.exercise_widgets.clear()
        
        # Load exercises
        for exercise in workout.exercises:
            exercise_widget = ExerciseFormWidget(
                len(self.exercise_widgets),
                volume_callback=self._update_volume_display,
                muscle_groups_list=self.MUSCLE_GROUPS
            )
            
            # Convert Set objects to dictionaries for set_exercise_data
            sets_data = [
                {
                    "reps": set_obj.reps,
                    "weight": set_obj.weight,
                    "comment": set_obj.comment,
                }
                for set_obj in exercise.sets
            ]
            
            # Get muscle groups for this exercise (handle old data without muscle_groups)
            # Filter to valid ones (Option A migration - ignore legacy groups)
            exercise_muscle_groups = getattr(exercise, 'muscle_groups', [])
            filtered_exercise_muscle_groups = self._filter_valid_muscle_groups(exercise_muscle_groups)
            exercise_widget.set_exercise_data(exercise.name, sets_data, filtered_exercise_muscle_groups)
            exercise_widget.remove_button.clicked.connect(
                lambda checked=False, idx=len(self.exercise_widgets): self._remove_exercise(idx)
            )
            
            # Connect set changes to volume calculation
            for set_widget in exercise_widget.set_widgets:
                set_widget.reps_spinbox.valueChanged.connect(self._update_volume_display)
                set_widget.weight_spinbox.valueChanged.connect(self._update_volume_display)
            
            self.exercises_layout.insertWidget(self.exercises_layout.count() - 1, exercise_widget)
            self.exercise_widgets.append(exercise_widget)
        
        self._current_session_id = getattr(workout, "session_id", None)
        self._update_delete_restore_buttons()
        self._update_volume_display()
    
    def _update_delete_restore_buttons(self) -> None:
        """Show Delete/Restore when API is used and we have a session_id."""
        has_api = bool(getattr(self.workout_service, "api_client", None))
        self.delete_workout_button.setVisible(has_api and bool(self._current_session_id))
        self.restore_workout_button.setVisible(False)  # Reserved for when we show deleted sessions
    
    def _delete_workout_from_server(self) -> None:
        """Delete current workout session from API and refetch."""
        if not self._current_session_id:
            return
        reply = QMessageBox.question(
            self,
            "Delete workout",
            "Delete this workout from the server?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, err = self.workout_service.delete_session_and_refetch(self._current_session_id)
        if ok:
            self._current_session_id = None
            self._update_delete_restore_buttons()
            self.load_entry(self.current_date)
            self.data_saved.emit()
        else:
            QMessageBox.warning(self, "Error", err or "Failed to delete workout.")
    
    def _restore_workout(self) -> None:
        """Restore a deleted workout session via API and refetch."""
        if not self._current_session_id:
            return
        ok, err = self.workout_service.restore_session_and_refetch(self._current_session_id)
        if ok:
            self.load_entry(self.current_date)
            self.data_saved.emit()
        else:
            QMessageBox.warning(self, "Error", err or "Failed to restore workout.")
    
    def _show_rest_day_ui(self) -> None:
        """Show UI for rest day - disable form and show label."""
        # Show rest day label
        self.day_type_label.setText("REST DAY")
        self.day_type_label.setStyleSheet("font-weight: bold; font-size: 14pt; padding: 15px; background-color: #9370DB; color: white; border-radius: 5px;")
        self.day_type_label.setVisible(True)
        
        # Show clear button
        self.clear_rest_missed_button.setVisible(True)
        
        # Disable workout form
        self._set_workout_form_enabled(False)
        
        # Clear form
        self._clear_workout_form()
    
    def _show_missed_day_ui(self) -> None:
        """Show UI for missed day - disable form and show label."""
        # Show missed day label
        self.day_type_label.setText("MISSED DAY")
        self.day_type_label.setStyleSheet("font-weight: bold; font-size: 14pt; padding: 15px; background-color: #DC143C; color: white; border-radius: 5px;")
        self.day_type_label.setVisible(True)
        
        # Show clear button
        self.clear_rest_missed_button.setVisible(True)
        
        # Disable workout form
        self._set_workout_form_enabled(False)
        
        # Clear form
        self._clear_workout_form()
    
    def _show_normal_workout_ui(self) -> None:
        """Show normal workout UI - enable form and hide day type label."""
        # Hide day type label
        self.day_type_label.setVisible(False)
        
        # Hide clear button
        self.clear_rest_missed_button.setVisible(False)
        
        # Enable workout form
        self._set_workout_form_enabled(True)
    
    def _set_workout_form_enabled(self, enabled: bool) -> None:
        """Enable or disable workout form widgets."""
        for widget in self.workout_form_widgets:
            widget.setEnabled(enabled)
        
        # Also enable/disable individual form elements
        for checkbox in self.muscle_checkboxes.values():
            checkbox.setEnabled(enabled)
        
        self.duration_spinbox.setEnabled(enabled)
        self.notes_edit.setEnabled(enabled)
        self.time_edit.setEnabled(enabled)
        self.add_exercise_button.setEnabled(enabled)
        
        for exercise_widget in self.exercise_widgets:
            exercise_widget.setEnabled(enabled)
    
    def _mark_as_rest_day(self) -> None:
        """Mark current date as rest day."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        success = self.workout_service.set_rest_day(self.current_date)
        if success:
            QMessageBox.information(self, "Success", "Date marked as rest day.")
            # Refresh UI
            self.load_entry(self.current_date)
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to mark date as rest day.")
    
    def _mark_as_missed_day(self) -> None:
        """Mark current date as missed day."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        success = self.workout_service.set_missed_day(self.current_date)
        if success:
            QMessageBox.information(self, "Success", "Date marked as missed day.")
            # Refresh UI
            self.load_entry(self.current_date)
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to mark date as missed day.")
    
    def _clear_rest_missed(self) -> None:
        """Clear rest/missed day flags for current date."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        success = self.workout_service.clear_rest_missed(self.current_date)
        if success:
            QMessageBox.information(self, "Success", "Rest/missed day flags cleared.")
            # Refresh UI
            self.load_entry(self.current_date)
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to clear rest/missed day flags.")
