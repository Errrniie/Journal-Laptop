from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence, QTextCharFormat, QTextOption
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from features.Journal_Service import JournalService


class JournalWidget(QWidget):
    """
    Rich text journal widget with multi-page support.
    Provides page management, rich text formatting, and auto-save functionality.
    """
    
    # Signal emitted when journal data is saved
    data_saved = pyqtSignal()
    
    # Auto-save delay in milliseconds (2.5 seconds)
    AUTO_SAVE_DELAY = 2500
    
    def __init__(self, journal_service: "JournalService", settings_store: "SettingsStore | None" = None) -> None:
        """
        Initialize Journal Widget.
        
        Args:
            journal_service: JournalService instance for data operations
            settings_store: Optional SettingsStore instance for managing presets
        """
        super().__init__()
        
        self.journal_service = journal_service
        self.settings_store = settings_store
        self.current_date: str | None = None
        self.current_page_name: str | None = None
        
        # Auto-save timer
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_current_page)
        
        # Setup UI
        self._setup_ui()
        self._setup_connections()
    
    def _setup_ui(self) -> None:
        """Create and layout UI components."""
        # Main horizontal layout (sidebar + content)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Content area
        content_area = self._create_content_area()
        main_layout.addWidget(content_area, stretch=1)
    
    def _create_sidebar(self) -> QWidget:
        """Create sidebar with page list and management buttons."""
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background-color: #f5f5f5; border-right: 1px solid #ddd;")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Pages header with page count
        header_layout = QHBoxLayout()
        pages_label = QLabel("Pages")
        pages_label.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 5px; color: #000000;")
        header_layout.addWidget(pages_label)
        
        self.page_count_label = QLabel("")
        self.page_count_label.setStyleSheet("color: gray; font-size: 9pt;")
        self.page_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.page_count_label)
        
        layout.addLayout(header_layout)
        
        # Page list (scrollable)
        self.page_list_widget = QListWidget()
        self.page_list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: white;
                color: #333333;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
                border-radius: 3px;
                margin: 2px;
                color: #333333;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
                color: #000000;
            }
            QListWidget::item:selected {
                background-color: #c8d4f0;
                color: #000000;
            }
        """)
        self.page_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.page_list_widget.customContextMenuRequested.connect(self._show_page_context_menu)
        layout.addWidget(self.page_list_widget, stretch=1)
        
        # Button row: Add Tag and Add Page
        button_row = QHBoxLayout()
        button_row.setSpacing(5)
        
        self.add_tag_button = QPushButton("+ Add Tag")
        self.add_tag_button.setStyleSheet("font-weight: bold; color: #000000;")
        button_row.addWidget(self.add_tag_button)
        
        # Add Page button with dropdown menu for quick preset creation
        self.add_page_button = QPushButton("+ Add Page")
        self.add_page_button.setStyleSheet("font-weight: bold; color: #000000;")
        self.add_page_menu = QMenu(self)
        self.add_page_button.setMenu(self.add_page_menu)
        button_row.addWidget(self.add_page_button)
        
        layout.addLayout(button_row)
        
        # Delete Page button
        self.delete_page_button = QPushButton("Delete Page")
        self.delete_page_button.setStyleSheet("color: red;")
        layout.addWidget(self.delete_page_button)
        
        return sidebar
    
    def _create_content_area(self) -> QWidget:
        """Create content area with toolbar and rich text editor."""
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Rich text editor
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Start writing your journal entry...")
        self.text_edit.setAcceptRichText(True)  # Enable HTML formatting
        self.text_edit.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        
        # Set font size
        font = self.text_edit.font()
        font.setPointSize(11)
        self.text_edit.setFont(font)
        
        # Connect text change signal for auto-save
        self.text_edit.textChanged.connect(self._on_text_changed)
        
        # Connect cursor position change to update formatting buttons
        self.text_edit.cursorPositionChanged.connect(self._update_formatting_buttons)
        
        layout.addWidget(self.text_edit, stretch=1)
        
        # Status bar at bottom
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10pt;")
        status_layout.addWidget(self.status_label)
        
        # Character count (optional)
        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setStyleSheet("color: gray; font-size: 10pt;")
        self.char_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(self.char_count_label)
        
        layout.addLayout(status_layout)
        
        # Update character count when text changes
        self.text_edit.textChanged.connect(self._update_character_count)
        
        return content_widget
    
    def _create_toolbar(self) -> QWidget:
        """Create formatting toolbar with bold, italic, and page name."""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Bold button
        self.bold_button = QToolButton()
        self.bold_button.setText("B")
        self.bold_button.setStyleSheet("font-weight: bold; font-size: 12pt; padding: 5px;")
        self.bold_button.setToolTip("Bold (Ctrl+B)")
        self.bold_button.setCheckable(True)
        layout.addWidget(self.bold_button)
        
        # Italic button
        self.italic_button = QToolButton()
        self.italic_button.setText("I")
        self.italic_button.setStyleSheet("font-style: italic; font-size: 12pt; padding: 5px;")
        self.italic_button.setToolTip("Italic (Ctrl+I)")
        self.italic_button.setCheckable(True)
        layout.addWidget(self.italic_button)
        
        layout.addWidget(QLabel("|"))  # Separator
        
        # Page name display/editor with unsaved indicator
        page_name_label = QLabel("Page:")
        layout.addWidget(page_name_label)
        
        page_name_container = QWidget()
        page_name_layout = QHBoxLayout(page_name_container)
        page_name_layout.setContentsMargins(0, 0, 0, 0)
        page_name_layout.setSpacing(2)
        
        self.page_name_edit = QLineEdit()
        self.page_name_edit.setPlaceholderText("Page name...")
        self.page_name_edit.setReadOnly(True)  # Start as read-only, can be made editable
        self.page_name_edit.setStyleSheet("font-weight: bold; font-size: 11pt;")
        page_name_layout.addWidget(self.page_name_edit, stretch=1)
        
        # Unsaved changes indicator
        self.unsaved_indicator = QLabel("*")
        self.unsaved_indicator.setStyleSheet("color: orange; font-weight: bold; font-size: 12pt;")
        self.unsaved_indicator.setVisible(False)  # Hidden by default
        page_name_layout.addWidget(self.unsaved_indicator)
        
        layout.addWidget(page_name_container, stretch=1)
        
        # Rename button (optional - could also double-click page name)
        self.rename_page_button = QPushButton("Rename")
        self.rename_page_button.setMaximumWidth(70)
        layout.addWidget(self.rename_page_button)
        
        layout.addStretch()
        
        return toolbar
    
    def _setup_connections(self) -> None:
        """Set up signal connections for UI components."""
        # Page list
        self.page_list_widget.itemClicked.connect(self._on_page_selected)
        self.page_list_widget.itemDoubleClicked.connect(self._on_page_double_clicked)
        
        # Buttons
        self.add_tag_button.clicked.connect(self._on_add_tag_clicked)
        # Add Page button: left click for normal dialog, menu for quick presets
        self.add_page_button.clicked.connect(self._on_add_page_clicked)
        self.delete_page_button.clicked.connect(self._on_delete_page_clicked)
        self.rename_page_button.clicked.connect(self._on_rename_page_clicked)
        
        # Update preset menu when presets change
        self._update_preset_menu()
        
        # Formatting buttons
        self.bold_button.clicked.connect(self._on_bold_clicked)
        self.italic_button.clicked.connect(self._on_italic_clicked)
        
        # Keyboard shortcuts
        bold_action = QAction(self)
        bold_action.setShortcut(QKeySequence("Ctrl+B"))
        bold_action.triggered.connect(self._on_bold_clicked)
        self.addAction(bold_action)
        
        italic_action = QAction(self)
        italic_action.setShortcut(QKeySequence("Ctrl+I"))
        italic_action.triggered.connect(self._on_italic_clicked)
        self.addAction(italic_action)
    
    def _on_bold_clicked(self) -> None:
        """Toggle bold formatting."""
        cursor = self.text_edit.textCursor()
        format = cursor.charFormat()
        
        # Toggle bold weight
        if format.fontWeight() == QFont.Weight.Bold:
            format.setFontWeight(QFont.Weight.Normal)
            self.bold_button.setChecked(False)
        else:
            format.setFontWeight(QFont.Weight.Bold)
            self.bold_button.setChecked(True)
        
        cursor.setCharFormat(format)
        self.text_edit.setTextCursor(cursor)
    
    def _on_italic_clicked(self) -> None:
        """Toggle italic formatting."""
        cursor = self.text_edit.textCursor()
        format = cursor.charFormat()
        
        # Toggle italic
        format.setFontItalic(not format.fontItalic())
        self.italic_button.setChecked(format.fontItalic())
        
        cursor.setCharFormat(format)
        self.text_edit.setTextCursor(cursor)
    
    def _refresh_page_list(self) -> None:
        """Update the page list sidebar."""
        if not self.current_date:
            self.page_list_widget.clear()
            self.page_count_label.setText("")
            return
        
        pages = self.journal_service.get_pages(self.current_date)
        self.page_list_widget.clear()
        
        # Update page count display
        if pages:
            current_index = next((i for i, p in enumerate(pages) if p.name == self.current_page_name), 0)
            self.page_count_label.setText(f"({current_index + 1} of {len(pages)})")
        else:
            self.page_count_label.setText("")
        
        for page in pages:
            item = QListWidgetItem(page.name)
            if page.name == self.current_page_name:
                item.setBackground(QColor(200, 220, 255))  # Highlight current page
                item.setForeground(QColor(0, 0, 0))  # Black text for readability
            else:
                item.setBackground(QColor(255, 255, 255))  # White background for other items
                item.setForeground(QColor(51, 51, 51))  # Dark gray text for readability
            self.page_list_widget.addItem(item)
        
        # Update delete button state
        self.delete_page_button.setEnabled(len(pages) > 1)
    
    def _on_page_selected(self, item: QListWidgetItem) -> None:
        """Switch to selected page."""
        page_name = item.text()
        if page_name == self.current_page_name:
            return  # Already on this page
        
        # Save current page first
        self._save_current_page()
        
        # Load new page
        self._load_page(page_name)
    
    def _on_page_double_clicked(self, item: QListWidgetItem) -> None:
        """Rename page on double-click."""
        page_name = item.text()
        self._rename_page_dialog(page_name)
    
    def _show_page_context_menu(self, position: QPoint) -> None:
        """Show context menu for page list item."""
        item = self.page_list_widget.itemAt(position)
        if not item:
            return
        
        page_name = item.text()
        
        # Create context menu
        menu = QMenu(self)
        
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self._rename_page_dialog(page_name))
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_page_by_name(page_name))
        
        # Show menu at cursor position
        menu.exec(self.page_list_widget.mapToGlobal(position))
    
    def _delete_page_by_name(self, page_name: str) -> None:
        """Delete a page by name (used by context menu)."""
        if not self.current_date:
            return
        
        # Don't allow deleting if it's the only page
        pages = self.journal_service.get_pages(self.current_date)
        if len(pages) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the last page.")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Page",
            f"Are you sure you want to delete page '{page_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.journal_service.delete_page(
                self.current_date,
                page_name
            )
            
            if success:
                # If we deleted the current page, switch to first remaining page
                if page_name == self.current_page_name:
                    remaining_pages = self.journal_service.get_pages(self.current_date)
                    if remaining_pages:
                        self._load_page(remaining_pages[0].name)
                    else:
                        self.current_page_name = None
                        self.page_name_edit.clear()
                        self.text_edit.clear()
                self._refresh_page_list()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete page.")
    
    def _update_preset_menu(self) -> None:
        """Update the preset menu with current presets."""
        self.add_page_menu.clear()
        
        if not self.settings_store:
            return
        
        presets = self.settings_store.get_journal_presets()
        if presets:
            # Add quick actions for each preset
            for preset in presets:
                action = self.add_page_menu.addAction(f"Quick: {preset}")
                action.triggered.connect(lambda checked, tag=preset: self._quick_create_page_with_tag(tag))
            self.add_page_menu.addSeparator()
        
        # Always add "Custom..." option
        custom_action = self.add_page_menu.addAction("Custom...")
        custom_action.triggered.connect(self._on_add_page_clicked)
    
    def _quick_create_page_with_tag(self, tag: str) -> None:
        """Quickly create a page with a preset tag."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        # Use tag name as default page name, but allow customization
        default_name = tag
        page_name, ok = QInputDialog.getText(
            self,
            f"Add Page ({tag})",
            f"Page name (default: {default_name}):",
            text=default_name
        )
        
        if not ok or not page_name.strip():
            return
        
        page_name = page_name.strip()
        
        # Validate name (no duplicates, not empty)
        if self.journal_service.page_exists(self.current_date, page_name):
            QMessageBox.warning(self, "Error", "Page name already exists.")
            return
        
        # Create page with preset tag
        success = self.journal_service.create_page(
            self.current_date,
            page_name,
            tag=tag
        )
        
        if success:
            self._refresh_page_list()
            self._load_page(page_name)
        else:
            QMessageBox.warning(self, "Error", "Failed to create page.")
    
    def _on_add_tag_clicked(self) -> None:
        """Open dialog to add new preset tag."""
        if not self.settings_store:
            QMessageBox.warning(self, "Error", "Settings store not available.")
            return
        
        tag_name, ok = QInputDialog.getText(
            self,
            "Add Tag",
            "Preset tag name:",
            text=""
        )
        
        if ok and tag_name.strip():
            tag_name = tag_name.strip()
            
            # Check if tag already exists
            existing_presets = self.settings_store.get_journal_presets()
            if tag_name.lower() in [p.lower() for p in existing_presets]:
                QMessageBox.warning(self, "Error", "Tag already exists.")
                return
            
            # Add preset
            if self.settings_store.add_journal_preset(tag_name):
                QMessageBox.information(self, "Success", f"Tag '{tag_name}' added successfully.")
                # Update preset menu after adding new tag
                self._update_preset_menu()
            else:
                QMessageBox.warning(self, "Error", "Failed to add tag.")
    
    def _on_add_page_clicked(self) -> None:
        """Open dialog to add new page with optional preset selection."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return
        
        # Get page name
        page_name, ok = QInputDialog.getText(
            self,
            "Add Page",
            "Page name:",
            text=""
        )
        
        if not ok or not page_name.strip():
            return
        
        page_name = page_name.strip()
        
        # Validate name (no duplicates, not empty)
        if self.journal_service.page_exists(self.current_date, page_name):
            QMessageBox.warning(self, "Error", "Page name already exists.")
            return
        
        # Get preset tag if available
        selected_tag = None
        if self.settings_store:
            presets = self.settings_store.get_journal_presets()
            if presets:
                # Show dialog to select preset (optional)
                dialog = QDialog(self)
                dialog.setWindowTitle("Select Tag (Optional)")
                dialog.setModal(True)
                layout = QVBoxLayout(dialog)
                
                label = QLabel("Select a preset tag (optional):")
                layout.addWidget(label)
                
                combo = QComboBox()
                combo.addItem("(None)", None)
                for preset in presets:
                    combo.addItem(preset, preset)
                layout.addWidget(combo)
                
                buttons = QDialogButtonBox(
                    QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                )
                buttons.accepted.connect(dialog.accept)
                buttons.rejected.connect(dialog.reject)
                layout.addWidget(buttons)
                
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    selected_tag = combo.currentData()
        
        # Create page with optional tag
        success = self.journal_service.create_page(
            self.current_date,
            page_name,
            tag=selected_tag
        )
        
        if success:
            self._refresh_page_list()
            self._load_page(page_name)
        else:
            QMessageBox.warning(self, "Error", "Failed to create page.")
    
    def _on_delete_page_clicked(self) -> None:
        """Delete current page."""
        if not self.current_date or not self.current_page_name:
            return
        
        # Don't allow deleting if it's the only page
        pages = self.journal_service.get_pages(self.current_date)
        if len(pages) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the last page.")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Page",
            f"Are you sure you want to delete page '{self.current_page_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.journal_service.delete_page(
                self.current_date,
                self.current_page_name
            )
            
            if success:
                # Switch to first remaining page
                remaining_pages = self.journal_service.get_pages(self.current_date)
                if remaining_pages:
                    self._load_page(remaining_pages[0].name)
                self._refresh_page_list()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete page.")
    
    def _on_rename_page_clicked(self) -> None:
        """Rename current page."""
        if not self.current_page_name:
            return
        self._rename_page_dialog(self.current_page_name)
    
    def _rename_page_dialog(self, page_name: str) -> None:
        """Open dialog to rename a page."""
        if not self.current_date:
            return
        
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Page",
            "New page name:",
            text=page_name
        )
        
        if ok and new_name.strip() and new_name.strip() != page_name:
            new_name = new_name.strip()
            
            # Validate
            if self.journal_service.page_exists(self.current_date, new_name):
                QMessageBox.warning(self, "Error", "Page name already exists.")
                return
            
            success = self.journal_service.rename_page(
                self.current_date,
                page_name,
                new_name
            )
            
            if success:
                self.current_page_name = new_name
                self.page_name_edit.setText(new_name)
                self._refresh_page_list()
            else:
                QMessageBox.warning(self, "Error", "Failed to rename page.")
    
    def _save_current_page(self) -> None:
        """Save current page content."""
        if not self.current_date or not self.current_page_name:
            return
        
        content = self.text_edit.toHtml()  # Get HTML content
        success = self.journal_service.update_page(
            self.current_date,
            self.current_page_name,
            content
        )
        
        if success:
            # Hide unsaved changes indicator
            self.unsaved_indicator.setVisible(False)
            
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet("color: green; font-size: 10pt;")
            QTimer.singleShot(2000, self._reset_status)
            
            # Emit signal to trigger analytics refresh
            self.data_saved.emit()
        else:
            self.status_label.setText("Error saving")
            self.status_label.setStyleSheet("color: red; font-size: 10pt;")
    
    def _load_page(self, page_name: str) -> None:
        """Load a specific page."""
        if not self.current_date:
            return
        
        # Stop any pending auto-save
        self.save_timer.stop()
        
        # Update current page name
        self.current_page_name = page_name
        self.page_name_edit.setText(page_name)
        
        # Hide unsaved indicator when loading a page
        self.unsaved_indicator.setVisible(False)
        
        # Load page content
        page = self.journal_service.get_page(self.current_date, page_name)
        
        # Update text editor (block signals to avoid triggering auto-save)
        self.text_edit.blockSignals(True)
        if page and page.content:
            self.text_edit.setHtml(page.content)  # Use setHtml for rich text (preserves formatting)
        else:
            self.text_edit.clear()
        self.text_edit.blockSignals(False)
        
        # Update formatting button states based on current cursor position
        self._update_formatting_buttons()
        
        # Update character count
        self._update_character_count()
        
        # Reset status
        self._reset_status()
        
        # Refresh page list to update highlighting and page count
        self._refresh_page_list()
    
    def _update_formatting_buttons(self) -> None:
        """Update formatting button states based on current cursor position."""
        cursor = self.text_edit.textCursor()
        format = cursor.charFormat()
        
        # Update bold button state
        self.bold_button.setChecked(format.fontWeight() == QFont.Weight.Bold)
        
        # Update italic button state
        self.italic_button.setChecked(format.fontItalic())
    
    def _update_character_count(self) -> None:
        """Update the character count display."""
        # For rich text, count plain text characters
        text = self.text_edit.toPlainText()
        char_count = len(text)
        word_count = len(text.split()) if text.strip() else 0
        
        if word_count > 0:
            self.char_count_label.setText(f"{char_count} characters, {word_count} words")
        else:
            self.char_count_label.setText(f"{char_count} characters")
    
    def _on_text_changed(self) -> None:
        """
        Debounced auto-save handler.
        Restarts the timer whenever text changes.
        """
        if not self.current_date or not self.current_page_name:
            return
        
        # Show unsaved changes indicator
        self.unsaved_indicator.setVisible(True)
        
        # Update status to show "Saving..."
        self.status_label.setText("Saving...")
        self.status_label.setStyleSheet("color: orange; font-size: 10pt;")
        
        # Restart the timer (debounce)
        self.save_timer.stop()
        self.save_timer.start(self.AUTO_SAVE_DELAY)
    
    def _reset_status(self) -> None:
        """Reset status label to ready state."""
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10pt;")
    
    def load_entry(self, date: str) -> None:
        """
        Load journal pages for the given date.
        
        Args:
            date: Date string in "YYYY-MM-DD" format
        """
        # Save current page if switching dates
        if self.current_date and self.current_date != date:
            self._save_current_page()
        
        self.current_date = date
        
        # Update preset menu when loading entry (in case settings changed)
        self._update_preset_menu()
        
        # Get pages
        pages = self.journal_service.get_pages(date)
        
        if not pages:
            # Create default "Main" page
            self.journal_service.create_page(date, "Main")
            pages = self.journal_service.get_pages(date)
        
        # Load first page (or last viewed page if we track that)
        if pages:
            self._load_page(pages[0].name)
        else:
            self.current_page_name = None
            self.page_name_edit.clear()
            self.text_edit.clear()
        
        self._refresh_page_list()
    
    def save_entry(self, date: str | None = None) -> bool:
        """
        Explicitly save current page to storage.
        
        Args:
            date: Optional date string. If None, uses current_date.
            
        Returns:
            True on success, False otherwise
        """
        save_date = date if date else self.current_date
        if not save_date or not self.current_page_name:
            return False
        
        # Stop timer and save immediately
        self.save_timer.stop()
        
        content = self.text_edit.toHtml()
        success = self.journal_service.update_page(
            save_date,
            self.current_page_name,
            content
        )
        
        if success:
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet("color: green; font-size: 10pt;")
            QTimer.singleShot(2000, self._reset_status)
        else:
            self.status_label.setText("Error saving")
            self.status_label.setStyleSheet("color: red; font-size: 10pt;")
        
        return success
    
    def clear(self) -> None:
        """Clear the text editor."""
        # Stop any pending auto-save
        self.save_timer.stop()
        
        # Clear text (block signals to avoid triggering auto-save)
        self.text_edit.blockSignals(True)
        self.text_edit.clear()
        self.text_edit.blockSignals(False)
        
        # Update character count
        self._update_character_count()
        
        # Reset status
        self._reset_status()
        
        # Clear current date and page
        self.current_date = None
        self.current_page_name = None
        self.page_name_edit.clear()
        self.page_list_widget.clear()
