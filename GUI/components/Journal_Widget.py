from typing import TYPE_CHECKING

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence, QTextCharFormat, QTextOption
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
    from config.settings_store import SettingsStore
    from features.Journal_Service import JournalService


class NewJournalPageDialog(QDialog):
    """Create a page from an existing type or name a new one in one step."""

    def __init__(self, *, api_mode: bool, available_types: list[dict],
                 presets: list[str], parent: QWidget) -> None:
        super().__init__(parent)
        self.api_mode = api_mode
        self.setWindowTitle("New journal page")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Dreams")

        if api_mode:
            self.type_combo = QComboBox()
            for page_type in available_types:
                key = page_type.get("type_key")
                if key:
                    self.type_combo.addItem(page_type.get("display_name") or key, key)
            self.type_combo.addItem("Create a new page...", None)
            form.addRow("Page", self.type_combo)
            self.name_label = QLabel("New page name")
            form.addRow(self.name_label, self.name_edit)
            self.reuse_hint = QLabel("New page names can be reused on other days.")
            layout.addWidget(self.reuse_hint)
            self.type_combo.currentIndexChanged.connect(self._update_name_visibility)
            if not available_types:
                self.type_combo.setCurrentIndex(self.type_combo.count() - 1)
            self._update_name_visibility()
        else:
            form.addRow("Page name", self.name_edit)
            self.category_combo = QComboBox()
            self.category_combo.setEditable(True)
            self.category_combo.addItem("No category", None)
            for preset in presets:
                self.category_combo.addItem(preset, preset)
            self.category_combo.setCurrentIndex(0)
            form.addRow("Category (optional)", self.category_combo)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #b42318;")
        layout.addWidget(self.error_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create page")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if not api_mode or self.type_combo.currentData() is None:
            self.name_edit.setFocus()
        else:
            self.type_combo.setFocus()

    def _update_name_visibility(self) -> None:
        is_new_type = self.type_combo.currentData() is None
        self.name_label.setVisible(is_new_type)
        self.name_edit.setVisible(is_new_type)
        self.reuse_hint.setVisible(is_new_type)
        if is_new_type:
            self.name_edit.setFocus()

    def accept(self) -> None:
        if (not self.api_mode or self.type_combo.currentData() is None) and not self.name_edit.text().strip():
            self.error_label.setText("Enter a page name.")
            self.name_edit.setFocus()
            return
        super().accept()

    def selected_category(self) -> str | None:
        if self.api_mode:
            return None
        text = self.category_combo.currentText().strip()
        return None if not text or (self.category_combo.currentIndex() == 0 and text == "No category") else text


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
        self.setObjectName("journalPage")
        self.setStyleSheet("""
            QWidget#journalPage { background: #171b24; color: #e6ecf5; }
            QWidget#journalPage QWidget#journalSidebar,
            QWidget#journalPage QWidget#journalEditorSurface {
                background: #20242e; border: 1px solid #343b49; border-radius: 12px;
            }
            QWidget#journalPage QLabel { color: #e6ecf5; }
            QLabel#journalHeading { color: #f7f9fc; font-size: 14pt; font-weight: 700; }
            QLabel#journalMuted { color: #aeb8c8; }
            QWidget#journalPage QListWidget {
                background: #171b24; color: #f7f9fc; border: 1px solid #343b49;
                border-radius: 9px; outline: 0; padding: 4px;
            }
            QWidget#journalPage QListWidget::item {
                color: #e6ecf5; border-radius: 7px; padding: 10px 9px; margin: 2px;
            }
            QWidget#journalPage QListWidget::item:hover { background: #303b4c; }
            QWidget#journalPage QListWidget::item:selected { background: #35557a; color: #ffffff; }
            QWidget#journalPage QTextEdit, QWidget#journalPage QLineEdit {
                background: #171b24; color: #f7f9fc; border: 1px solid #343b49;
                border-radius: 8px; padding: 9px; selection-background-color: #377fd1;
            }
            QWidget#journalPage QTextEdit:focus, QWidget#journalPage QLineEdit:focus {
                border: 1px solid #5596e2;
            }
            QWidget#journalPage QPushButton, QWidget#journalPage QToolButton {
                background: #303b4c; color: #f7f9fc; border: 1px solid #526072;
                border-radius: 8px; padding: 8px 12px;
            }
            QWidget#journalPage QPushButton:hover, QWidget#journalPage QToolButton:hover {
                background: #3c4b60;
            }
            QWidget#journalPage QPushButton#journalPrimary {
                background: #377fd1; color: white; border: 0; font-weight: 700;
            }
            QWidget#journalPage QPushButton#journalPrimary:hover { background: #4c91dd; }
            QWidget#journalPage QPushButton#journalDanger { color: #ffc4cf; background: #3b2a32; border-color: #68414b; }
            QWidget#journalPage QToolButton:checked { background: #35557a; border-color: #5596e2; }
        """)
        # Main horizontal layout (sidebar + content)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(14)
        
        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Content area
        content_area = self._create_content_area()
        main_layout.addWidget(content_area, stretch=1)
    
    def _create_sidebar(self) -> QWidget:
        """Create sidebar with page list and management buttons."""
        sidebar = QWidget()
        sidebar.setObjectName("journalSidebar")
        sidebar.setFixedWidth(200)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)
        
        # Pages header with page count
        header_layout = QHBoxLayout()
        pages_label = QLabel("Pages")
        pages_label.setObjectName("journalHeading")
        header_layout.addWidget(pages_label)
        
        self.page_count_label = QLabel("")
        self.page_count_label.setObjectName("journalMuted")
        self.page_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.page_count_label)
        
        layout.addLayout(header_layout)
        
        # Page list (scrollable)
        self.page_list_widget = QListWidget()
        self.page_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.page_list_widget.customContextMenuRequested.connect(self._show_page_context_menu)
        layout.addWidget(self.page_list_widget, stretch=1)
        
        self.add_page_button = QPushButton("+ New page")
        self.add_page_button.setObjectName("journalPrimary")
        self.add_page_button.setToolTip("Choose an existing page or create a new one")
        layout.addWidget(self.add_page_button)
        
        # Delete Page button
        self.delete_page_button = QPushButton("Delete Page")
        self.delete_page_button.setObjectName("journalDanger")
        layout.addWidget(self.delete_page_button)
        
        return sidebar
    
    def _create_content_area(self) -> QWidget:
        """Create content area with toolbar and rich text editor."""
        content_widget = QWidget()
        content_widget.setObjectName("journalEditorSurface")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(12)
        
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
        toolbar.setObjectName("journalToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Bold button
        self.bold_button = QToolButton()
        self.bold_button.setText("B")
        self.bold_button.setStyleSheet("font-weight: bold; font-size: 12pt;")
        self.bold_button.setToolTip("Bold (Ctrl+B)")
        self.bold_button.setCheckable(True)
        layout.addWidget(self.bold_button)
        
        # Italic button
        self.italic_button = QToolButton()
        self.italic_button.setText("I")
        self.italic_button.setStyleSheet("font-style: italic; font-size: 12pt;")
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
        self.page_name_edit.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 6px 9px;")
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
        self.add_page_button.clicked.connect(self._on_add_page_clicked)
        self.delete_page_button.clicked.connect(self._on_delete_page_clicked)
        self.rename_page_button.clicked.connect(self._on_rename_page_clicked)
        
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
            self.page_list_widget.addItem(item)
        
        # Update delete button state
        can_delete = (
            bool(self.current_page_name)
            and self._can_delete_page(self.current_page_name)
        )
        self.delete_page_button.setEnabled(can_delete)
    
    def _is_main_page(self, page_name: str) -> bool:
        """True when the named page is the main journal page."""
        if not self.current_date:
            return False
        page = self.journal_service.get_page(self.current_date, page_name)
        if page and page.page_type:
            return page.page_type.lower().strip().replace(" ", "_") == "main"
        return page_name.strip().lower() == "main"

    def _can_delete_page(self, page_name: str) -> bool:
        """Whether the page can be deleted (not main, not the only page)."""
        if not self.current_date:
            return False
        pages = self.journal_service.get_pages(self.current_date)
        if len(pages) <= 1:
            return False
        return not self._is_main_page(page_name)
    
    def _on_page_selected(self, item: QListWidgetItem) -> None:
        """Switch to selected page."""
        page_name = item.text()
        if page_name == self.current_page_name:
            return  # Already on this page
        
        if self.unsaved_indicator.isVisible() and not self._save_current_page():
            self._refresh_page_list()
            QMessageBox.warning(self, "Save failed", "Save the current page before switching pages.")
            return
        
        # Load new page
        self._load_page(page_name)
    
    def _on_page_double_clicked(self, item: QListWidgetItem) -> None:
        """Rename page on double-click (local-only mode)."""
        if self.journal_service.uses_api:
            return
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
        rename_action.setEnabled(not self.journal_service.uses_api)
        rename_action.triggered.connect(lambda: self._rename_page_dialog(page_name))
        
        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(self._can_delete_page(page_name))
        delete_action.triggered.connect(lambda: self._delete_page_by_name(page_name))
        
        # Show menu at cursor position
        menu.exec(self.page_list_widget.mapToGlobal(position))
    
    def _delete_page_by_name(self, page_name: str) -> None:
        """Delete a page by name (used by context menu)."""
        if not self.current_date:
            return
        
        if self._is_main_page(page_name):
            QMessageBox.warning(self, "Error", "The main page cannot be deleted.")
            return

        if not self._can_delete_page(page_name):
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
    
    def _on_add_page_clicked(self) -> None:
        """Create a page through one dialog in both local and API modes."""
        if not self.current_date:
            QMessageBox.warning(self, "No Date", "Please select a date first.")
            return

        api_mode = self.journal_service.uses_api
        available_types = (
            self.journal_service.get_available_page_types(self.current_date)
            if api_mode else []
        )
        presets = (
            self.settings_store.get_journal_presets()
            if self.settings_store and not api_mode else []
        )
        dialog = NewJournalPageDialog(
            api_mode=api_mode,
            available_types=available_types,
            presets=presets,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Creating a page changes the editor selection. Keep the current text
        # visible when its save fails instead of silently discarding it.
        if self.unsaved_indicator.isVisible() and not self._save_current_page():
            QMessageBox.warning(self, "Save failed", "Save the current page before adding another.")
            return

        if api_mode:
            type_key = dialog.type_combo.currentData()
            created_type = type_key is None
            if created_type:
                display_name = dialog.name_edit.text().strip()
                type_key = display_name.lower().replace(" ", "_")
                success, error = self.journal_service.create_page_type(display_name)
                if not success:
                    QMessageBox.warning(self, "New page", error or "Could not create the page type.")
                    return
            else:
                display_name = dialog.type_combo.currentText()
            success = self.journal_service.create_page(
                self.current_date, display_name, page_type=type_key
            )
            if not success:
                message = f"Could not create the '{display_name}' page."
                if created_type:
                    message += " The page type was saved and can be selected next time."
                QMessageBox.warning(self, "New page", message)
                return
            pages = self.journal_service.get_pages(self.current_date)
            page = next((p for p in pages if p.page_type == type_key), None)
            page_name = page.name if page else display_name
        else:
            page_name = dialog.name_edit.text().strip()
            if self.journal_service.page_exists(self.current_date, page_name):
                QMessageBox.warning(self, "New page", "A page with that name already exists.")
                return
            category = dialog.selected_category()
            if not self.journal_service.create_page(
                self.current_date, page_name, tag=category
            ):
                QMessageBox.warning(self, "New page", "Could not create the page.")
                return
            if category and self.settings_store and category.casefold() not in {
                preset.casefold() for preset in presets
            }:
                self.settings_store.add_journal_preset(category)

        self._load_page(page_name)
        self.text_edit.setFocus()
        self.data_saved.emit()

    def _on_delete_page_clicked(self) -> None:
        """Delete current page."""
        if not self.current_date or not self.current_page_name:
            return
        
        if self._is_main_page(self.current_page_name):
            QMessageBox.warning(self, "Error", "The main page cannot be deleted.")
            return

        if not self._can_delete_page(self.current_page_name):
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
    
    def _save_current_page(self) -> bool:
        """Save current page content and report whether it succeeded."""
        if not self.current_date or not self.current_page_name:
            return True
        
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
        return success
    
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
        
        if self.journal_service.uses_api:
            result = self.journal_service.sync_from_api(date)
            if result.get("errors"):
                QMessageBox.warning(
                    self,
                    "Journal Sync",
                    "Could not load journal from API:\n" + "\n".join(result["errors"][:3]),
                )

        
        # Get pages
        pages = self.journal_service.get_pages(date)
        
        if not pages:
            if self.journal_service.uses_api:
                result = self.journal_service.sync_from_api(date)
                pages = self.journal_service.get_pages(date)
            else:
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
