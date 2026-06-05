from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from features.Sleep_Service import SleepService


class SleepWidget(QWidget):
    """
    Simple sleep hours input widget with CSV import functionality.
    """
    
    # Signal emitted when sleep data is saved
    data_saved = pyqtSignal()
    
    def __init__(self, sleep_service: "SleepService") -> None:
        """
        Initialize Sleep Widget.
        
        Args:
            sleep_service: SleepService instance for data operations
        """
        super().__init__()
        
        self.sleep_service = sleep_service
        self.current_date: str | None = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # Sleep Hours Input Section
        input_group = QGroupBox("Sleep Hours")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(10)
        
        # Hours input row
        hours_layout = QHBoxLayout()
        hours_layout.addWidget(QLabel("Hours:"))
        
        self.hours_spinbox = QDoubleSpinBox()
        self.hours_spinbox.setMinimum(0.0)
        self.hours_spinbox.setMaximum(24.0)
        self.hours_spinbox.setSingleStep(0.25)  # Quarter-hour increments
        self.hours_spinbox.setDecimals(2)
        self.hours_spinbox.setSuffix(" hours")
        self.hours_spinbox.setValue(0.0)
        self.hours_spinbox.valueChanged.connect(self._on_hours_changed)
        hours_layout.addWidget(self.hours_spinbox)
        
        hours_layout.addStretch()
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.setStyleSheet("font-weight: bold;")
        self.save_button.clicked.connect(self._save_sleep_hours)
        hours_layout.addWidget(self.save_button)
        
        input_layout.addLayout(hours_layout)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10pt;")
        input_layout.addWidget(self.status_label)
        
        # Visual indicator (color-coded based on hours)
        self.indicator_label = QLabel()
        self.indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicator_label.setMinimumHeight(30)
        self.indicator_label.setStyleSheet("border-radius: 5px; font-weight: bold;")
        input_layout.addWidget(self.indicator_label)
        
        main_layout.addWidget(input_group)
        
        # Import Section
        import_group = QGroupBox("Import Sleep Data")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(10)
        
        # Import button
        import_button = QPushButton("Import from Samsung Health CSV...")
        import_button.clicked.connect(self._on_import_csv)
        import_layout.addWidget(import_button)
        
        # Import status/result label
        self.import_status_label = QLabel("No import performed yet")
        self.import_status_label.setStyleSheet("color: gray; font-size: 10pt;")
        self.import_status_label.setWordWrap(True)
        import_layout.addWidget(self.import_status_label)
        
        main_layout.addWidget(import_group)
        
        # Recent Sleep Display (optional)
        trend_group = QGroupBox("Recent Sleep Trend")
        trend_layout = QVBoxLayout(trend_group)
        
        self.trend_label = QLabel("No data available")
        self.trend_label.setStyleSheet("font-size: 11pt;")
        self.trend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trend_layout.addWidget(self.trend_label)
        
        main_layout.addWidget(trend_group)
        
        main_layout.addStretch()
    
    def _on_hours_changed(self, value: float) -> None:
        """
        Handle hours value change - update visual indicator.
        
        Args:
            value: New hours value
        """
        self._update_visual_indicator(value)
    
    def _update_visual_indicator(self, hours: float) -> None:
        """
        Update visual indicator based on sleep hours.
        
        Args:
            hours: Sleep hours value
        """
        if hours == 0.0:
            self.indicator_label.setText("No data")
            self.indicator_label.setStyleSheet(
                "background-color: #E0E0E0; color: #666; border-radius: 5px; font-weight: bold; padding: 5px;"
            )
        elif hours < 6.0:
            self.indicator_label.setText("⚠️ Low Sleep")
            self.indicator_label.setStyleSheet(
                "background-color: #FFCDD2; color: #C62828; border-radius: 5px; font-weight: bold; padding: 5px;"
            )
        elif hours < 7.0:
            self.indicator_label.setText("⚠️ Below Recommended")
            self.indicator_label.setStyleSheet(
                "background-color: #FFF9C4; color: #F57F17; border-radius: 5px; font-weight: bold; padding: 5px;"
            )
        elif hours <= 9.0:
            self.indicator_label.setText("✓ Good Sleep")
            self.indicator_label.setStyleSheet(
                "background-color: #C8E6C9; color: #2E7D32; border-radius: 5px; font-weight: bold; padding: 5px;"
            )
        else:
            self.indicator_label.setText("⚠️ Excessive Sleep")
            self.indicator_label.setStyleSheet(
                "background-color: #FFE0B2; color: #E65100; border-radius: 5px; font-weight: bold; padding: 5px;"
            )
    
    def _save_sleep_hours(self) -> None:
        """Save current hours to storage."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        hours = self.hours_spinbox.value()
        success = self.sleep_service.set_sleep_hours(self.current_date, hours)
        
        if success:
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet("color: green; font-size: 10pt;")
            
            # Reset status after 2 seconds
            QTimer.singleShot(2000, self._reset_status)
            
            # Update trend display
            self._display_sleep_trend()
            
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            self.status_label.setText("Error saving")
            self.status_label.setStyleSheet("color: red; font-size: 10pt;")
            QMessageBox.warning(self, "Error", "Failed to save sleep hours. Please check your input.")
    
    def _reset_status(self) -> None:
        """Reset status label to ready state."""
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10pt;")
    
    def _on_import_csv(self) -> None:
        """Open file dialog and trigger CSV import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Sleep Data from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        
        if not file_path:
            return  # User cancelled
        
        # Show progress message
        self.import_status_label.setText("Importing... Please wait...")
        self.import_status_label.setStyleSheet("color: orange; font-size: 10pt;")
        
        # Import via sleep service
        result = self.sleep_service.import_from_csv(file_path, skip_existing=True)
        
        # Handle import result
        self._handle_import_result(result)
        
        # Reload current date's sleep data
        if self.current_date:
            self.load_entry(self.current_date)
    
    def _handle_import_result(self, result: dict) -> None:
        """
        Display import summary.
        
        Args:
            result: Dictionary with import results (rows_processed, rows_imported, rows_skipped, errors)
        """
        rows_processed = result.get("rows_processed", 0)
        rows_imported = result.get("rows_imported", 0)
        rows_skipped = result.get("rows_skipped", 0)
        errors = result.get("errors", [])
        
        # Build status message
        status_parts = [
            f"Processed: {rows_processed}",
            f"Imported: {rows_imported}",
            f"Skipped: {rows_skipped}",
        ]
        
        if errors:
            status_parts.append(f"Errors: {len(errors)}")
        
        status_text = " | ".join(status_parts)
        
        # Update status label
        if errors:
            self.import_status_label.setStyleSheet("color: orange; font-size: 10pt;")
        else:
            self.import_status_label.setStyleSheet("color: green; font-size: 10pt;")
        
        self.import_status_label.setText(status_text)
        
        # Show detailed message box
        message = (
            f"Import completed!\n\n"
            f"Rows processed: {rows_processed}\n"
            f"Rows imported: {rows_imported}\n"
            f"Rows skipped: {rows_skipped}\n"
            f"Errors: {len(errors)}"
        )
        
        if errors:
            error_list = "\n".join(errors[:10])  # Show first 10 errors
            if len(errors) > 10:
                error_list += f"\n... and {len(errors) - 10} more errors"
            message += f"\n\nErrors:\n{error_list}"
        
        QMessageBox.information(self, "Import Results", message)
        
        # Emit signal to trigger analytics refresh if any rows were imported
        if rows_imported > 0:
            self.data_saved.emit()
        
        # Update trend display after import
        self._display_sleep_trend()
    
    def _display_sleep_trend(self) -> None:
        """Show recent sleep statistics (last 7 days average)."""
        if not self.current_date:
            self.trend_label.setText("No data available")
            return
        
        try:
            # Calculate date range (last 7 days including today)
            current_date_obj = datetime.strptime(self.current_date, "%Y-%m-%d").date()
            start_date = current_date_obj - timedelta(days=6)  # 7 days total (6 days back + today)
            end_date = current_date_obj
            
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            
            # Get sleep data for the range
            sleep_range = self.sleep_service.get_sleep_range(start_date_str, end_date_str)
            
            if not sleep_range:
                self.trend_label.setText("No sleep data for the last 7 days")
                return
            
            # Calculate average
            total_hours = sum(hours for _, hours in sleep_range)
            average_hours = total_hours / len(sleep_range)
            days_with_data = len(sleep_range)
            
            # Format trend text
            trend_text = (
                f"Last 7 days average: {average_hours:.2f} hours\n"
                f"({days_with_data} days with data)"
            )
            
            # Add color coding
            if average_hours < 6.0:
                color = "#C62828"  # Red
            elif average_hours < 7.0:
                color = "#F57F17"  # Orange
            elif average_hours <= 9.0:
                color = "#2E7D32"  # Green
            else:
                color = "#E65100"  # Orange (excessive)
            
            self.trend_label.setText(trend_text)
            self.trend_label.setStyleSheet(f"font-size: 11pt; color: {color}; font-weight: bold;")
        
        except Exception as e:
            self.trend_label.setText(f"Error calculating trend: {str(e)}")
            self.trend_label.setStyleSheet("font-size: 11pt; color: red;")
    
    def load_entry(self, date: str) -> None:
        """
        Load sleep hours for the given date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
        """
        self.current_date = date
        
        # Load sleep hours from service
        sleep_hours = self.sleep_service.get_sleep_hours(date)
        
        # Update spinbox (block signals to avoid triggering indicator update during load)
        self.hours_spinbox.blockSignals(True)
        if sleep_hours is not None:
            self.hours_spinbox.setValue(sleep_hours)
        else:
            self.hours_spinbox.setValue(0.0)
        self.hours_spinbox.blockSignals(False)
        
        # Update visual indicator
        current_value = self.hours_spinbox.value()
        self._update_visual_indicator(current_value)
        
        # Reset status
        self._reset_status()
        
        # Update trend display
        self._display_sleep_trend()
