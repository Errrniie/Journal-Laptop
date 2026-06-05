from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class TaskNotesDialog(QDialog):
    """
    Dialog for viewing and editing task notes.
    """
    
    def __init__(self, task_name: str, notes: str, parent=None) -> None:
        """
        Initialize Task Notes Dialog.
        
        Args:
            task_name: Name of the task
            notes: Current notes text
            parent: Parent widget
        """
        super().__init__(parent)
        self.task_name = task_name
        self.notes = notes or ""
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        self.setWindowTitle(f"Notes: {self.task_name}")
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Task name label
        name_label = QLabel(f"<b>Task:</b> {self.task_name}")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Notes text area (editable – view and edit)
        notes_label = QLabel("Notes (editable):")
        layout.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(False)
        self.notes_edit.setPlainText(self.notes)
        self.notes_edit.setPlaceholderText("Add or edit notes for this task...")
        layout.addWidget(self.notes_edit, stretch=1)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Delete notes button (only if notes exist)
        if self.notes.strip():
            delete_button = QPushButton("Delete Notes")
            delete_button.setStyleSheet("color: red;")
            delete_button.clicked.connect(self._delete_notes)
            button_layout.addWidget(delete_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        save_button = QPushButton("Save")
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(save_button)
        
        layout.addLayout(button_layout)
    
    def _delete_notes(self) -> None:
        """Clear notes after confirmation."""
        reply = QMessageBox.question(
            self,
            "Delete Notes",
            "Are you sure you want to delete these notes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.notes_edit.clear()
            self.accept()  # Close and save empty notes
    
    def get_notes(self) -> str:
        """
        Get notes text from editor.
        
        Returns:
            Notes text as string
        """
        return self.notes_edit.toPlainText()
