from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)


class LoadTemplateDialog(QDialog):
    """
    Dialog for loading a workout template with load mode selection.
    """
    
    def __init__(self, template_names: list[str], parent=None) -> None:
        """
        Initialize Load Template Dialog.
        
        Args:
            template_names: List of available template names
            parent: Parent widget
        """
        super().__init__(parent)
        self.template_names = template_names
        self.delete_requested = False
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        self.setWindowTitle("Load Template")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Template selection
        template_label = QLabel("Select Template:")
        layout.addWidget(template_label)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(self.template_names)
        layout.addWidget(self.template_combo)
        
        # Load mode selection
        mode_label = QLabel("Load Mode:")
        layout.addWidget(mode_label)
        
        self.with_set_data_radio = QRadioButton("Load with set data")
        self.with_set_data_radio.setChecked(True)  # Default to with set data
        self.with_set_data_radio.setToolTip("Load reps, weight, and comments from template")
        layout.addWidget(self.with_set_data_radio)
        
        self.without_set_data_radio = QRadioButton("Load without set data")
        self.without_set_data_radio.setToolTip("Load structure only; reps/weight/comment will be blank")
        layout.addWidget(self.without_set_data_radio)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Optional: Delete button
        self.delete_button = button_box.addButton("Delete", QDialogButtonBox.ButtonRole.ActionRole)
        self.delete_button.setStyleSheet("color: red;")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        
        layout.addWidget(button_box)
    
    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        from PyQt6.QtWidgets import QMessageBox
        
        template_name = self.get_selected_template()
        reply = QMessageBox.question(
            self,
            "Delete Template",
            f"Are you sure you want to delete template '{template_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested = True
            self.accept()  # Close dialog and signal deletion
        else:
            self.delete_requested = False
    
    def should_delete(self) -> bool:
        """
        Check if delete was requested.
        
        Returns:
            True if delete was requested, False otherwise
        """
        return getattr(self, 'delete_requested', False)
    
    def get_selected_template(self) -> str:
        """
        Get the selected template name.
        
        Returns:
            Selected template name
        """
        return self.template_combo.currentText()
    
    def get_load_mode(self) -> bool:
        """
        Get the selected load mode.
        
        Returns:
            True if loading with set data, False if without set data
        """
        return self.with_set_data_radio.isChecked()
