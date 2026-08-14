from datetime import date, timedelta
from typing import TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QColorDialog,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from GUI.Main_Window import ensure_qdate, safe_set_date

if TYPE_CHECKING:
    from config.settings_store import SettingsStore


class SettingsDialog(QDialog):
    """
    Settings dialog with General and Appearance tabs.
    """
    
    def __init__(self, settings_store: "SettingsStore", parent=None) -> None:
        """
        Initialize Settings Dialog.
        
        Args:
            settings_store: SettingsStore instance for loading/saving settings
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.settings_store = settings_store
        
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)
        
        # Load settings from store (ensure valid QDates)
        self.analytics_start_date = ensure_qdate(settings_store.get_analytics_start_date())
        self.analytics_end_date = ensure_qdate(settings_store.get_analytics_end_date())
        self.group_box_color = settings_store.get_group_box_color()
        self.api_key = settings_store.get_api_key()
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # General tab (Dates)
        general_tab = self._create_general_tab()
        self.tab_widget.addTab(general_tab, "General")
        
        # Appearance tab (Colors)
        appearance_tab = self._create_appearance_tab()
        self.tab_widget.addTab(appearance_tab, "Appearance")
        
        # Sync tab (API settings)
        sync_tab = self._create_sync_tab()
        self.tab_widget.addTab(sync_tab, "Sync")
        
        main_layout.addWidget(self.tab_widget)
        
        # Dialog buttons (OK, Cancel, Apply)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.clicked.connect(self._on_ok)
        
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        
        apply_button = button_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.clicked.connect(self._on_apply)
        
        main_layout.addWidget(button_box)
    
    def _create_general_tab(self) -> QWidget:
        """Create the General tab with date settings."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Analytics Date Range")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Note
        note_label = QLabel("Used for Analytics charts (Volume Total, Sleep, Task Completion).")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(note_label)
        
        layout.addSpacing(10)
        
        # Start Date
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start Date:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        safe_set_date(self.start_date_edit, self.analytics_start_date, block_signals=True)
        start_layout.addWidget(self.start_date_edit)
        start_layout.addStretch()
        layout.addLayout(start_layout)
        
        # End Date
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End Date:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        safe_set_date(self.end_date_edit, self.analytics_end_date, block_signals=True)
        end_layout.addWidget(self.end_date_edit)
        end_layout.addStretch()
        layout.addLayout(end_layout)
        
        layout.addStretch()
        
        return tab
    
    def _create_appearance_tab(self) -> QWidget:
        """Create the Appearance tab with color settings."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Box Colors")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Note
        note_label = QLabel("Customize the color of group boxes across the application.")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(note_label)
        
        layout.addSpacing(10)
        
        # Group Box Color
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Group Box Color:"))
        
        self.color_button = QPushButton()
        self.color_button.setFixedSize(60, 30)
        self._update_color_button()
        self.color_button.clicked.connect(self._on_color_button_clicked)
        color_layout.addWidget(self.color_button)
        
        reset_button = QPushButton("Reset to Default")
        reset_button.clicked.connect(self._on_reset_color)
        color_layout.addWidget(reset_button)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        layout.addStretch()
        
        return tab
    
    def _create_sync_tab(self) -> QWidget:
        """Create the Sync tab with API settings."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("API Sync Settings")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Note
        note_label = QLabel("Configure API settings for task synchronization.")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(note_label)
        
        layout.addSpacing(10)
        
        # API Key
        api_key_layout = QVBoxLayout()
        api_key_layout.addWidget(QLabel("API Key:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)  # Hide the key as it's typed
        self.api_key_edit.setPlaceholderText("Enter your API key...")
        self.api_key_edit.setText(self.api_key)
        api_key_layout.addWidget(self.api_key_edit)
        
        # Show/Hide toggle button
        show_key_button = QPushButton("Show")
        show_key_button.setMaximumWidth(80)
        show_key_button.clicked.connect(self._toggle_api_key_visibility)
        api_key_layout.addWidget(show_key_button)
        
        layout.addLayout(api_key_layout)
        
        # Warning note
        warning_label = QLabel("⚠️ Keep your API key secure. Do not share it with others.")
        warning_label.setStyleSheet("color: #d32f2f; font-style: italic; padding: 10px;")
        layout.addWidget(warning_label)
        
        layout.addStretch()
        
        return tab
    
    def _toggle_api_key_visibility(self) -> None:
        """Toggle API key visibility between password and normal mode."""
        button = self.sender()
        if self.api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("Show")
    
    def _update_color_button(self) -> None:
        """Update the color button to show the current color."""
        self.color_button.setStyleSheet(
            f"QPushButton {{ background-color: {self.group_box_color}; border: 1px solid #888; border-radius: 3px; }}"
        )
    
    def _on_color_button_clicked(self) -> None:
        """Open color dialog when color button is clicked."""
        from PyQt6.QtGui import QColor
        
        # Convert hex string to QColor
        color = QColor(self.group_box_color)
        
        # Open color dialog
        color = QColorDialog.getColor(color, self, "Select Group Box Color")
        
        if color.isValid():
            self.group_box_color = color.name()
            self._update_color_button()
    
    def _on_reset_color(self) -> None:
        """Reset group box color to default."""
        self.group_box_color = "#F0F0F0"
        self._update_color_button()
    
    def _on_ok(self) -> None:
        """Handle OK button - save and close."""
        self._on_apply()
        self.accept()
    
    def _on_apply(self) -> None:
        """Handle Apply button - save without closing."""
        # Update settings from UI
        self.analytics_start_date = ensure_qdate(self.start_date_edit.date())
        self.analytics_end_date = ensure_qdate(self.end_date_edit.date())
        self.api_key = self.api_key_edit.text().strip()
        
        # Save to settings store
        self.settings_store.set_analytics_start_date(self.analytics_start_date)
        self.settings_store.set_analytics_end_date(self.analytics_end_date)
        self.settings_store.set_group_box_color(self.group_box_color)
        self.settings_store.set_api_key(self.api_key)
    
    def get_analytics_start_date(self) -> QDate:
        """Get the analytics start date."""
        return self.analytics_start_date
    
    def get_analytics_end_date(self) -> QDate:
        """Get the analytics end date."""
        return self.analytics_end_date
    
    def get_group_box_color(self) -> str:
        """Get the group box color."""
        return self.group_box_color
    
    def set_analytics_start_date(self, qdate: QDate) -> None:
        """Set the analytics start date."""
        self.analytics_start_date = ensure_qdate(qdate)
        if hasattr(self, 'start_date_edit'):
            safe_set_date(self.start_date_edit, self.analytics_start_date, block_signals=True)
    
    def set_analytics_end_date(self, qdate: QDate) -> None:
        """Set the analytics end date."""
        self.analytics_end_date = ensure_qdate(qdate)
        if hasattr(self, 'end_date_edit'):
            safe_set_date(self.end_date_edit, self.analytics_end_date, block_signals=True)
    
    def set_group_box_color(self, color: str) -> None:
        """Set the group box color."""
        self.group_box_color = color
        if hasattr(self, 'color_button'):
            self._update_color_button()
