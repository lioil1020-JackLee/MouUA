"""
Base dialog classes for consistent UI patterns across the application.

This module provides base dialog classes that standardize common UI patterns
like button layouts, form building, and validation to reduce code duplication.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox,
    QWidget, QLabel, QFormLayout, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any, Optional, List
from .components import FormBuilder

# UI constants (avoiding circular import)
FORM_FIELD_STYLE = "QLineEdit { min-height: 22px; }"
SPACING = 6
MARGIN_H = 12
MARGIN_V = 12
FORM_MAX_WIDTH = 600
ROW_HEIGHT = 22
FORM_ROW_SPACING = 2


class BaseDialog(QDialog):
    """
    Base dialog class with standardized button layout and common functionality.

    Provides consistent Finish/Cancel button layout and basic dialog setup.
    Subclasses should override _setup_content() to add their specific UI elements.
    """

    def __init__(self, title: str = "", parent=None, use_button_box: bool = False):
        """
        Initialize base dialog.

        Args:
            title: Dialog window title
            parent: Parent widget
            use_button_box: If True, use QDialogButtonBox; if False, use manual buttons
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.use_button_box = use_button_box

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(SPACING)
        self.main_layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)

        # Content area (to be filled by subclasses)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(SPACING)
        self.main_layout.addWidget(self.content_widget)

        # Setup content (subclass hook)
        self._setup_content()

        # Add buttons
        self._setup_buttons()

        # Set minimum size and style
        self.setMinimumWidth(400)
        self.setStyleSheet(FORM_FIELD_STYLE)

    def _setup_content(self):
        """Override this method to add dialog-specific content."""
        pass

    def _setup_buttons(self):
        """Setup standardized button layout."""
        if self.use_button_box:
            # Use QDialogButtonBox
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            # Try to set OK button text to "Finish"
            try:
                ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
                if ok_btn:
                    ok_btn.setText("Finish")
            except Exception:
                pass
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)
            self.main_layout.addWidget(self.button_box)
        else:
            # Manual button layout
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            self.finish_button = QPushButton("Finish")
            self.finish_button.clicked.connect(self.accept)
            button_layout.addWidget(self.finish_button)

            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.clicked.connect(self.reject)
            button_layout.addWidget(self.cancel_button)

            self.main_layout.addLayout(button_layout)

    def set_button_texts(self, finish_text: str = "Finish", cancel_text: str = "Cancel"):
        """Set custom button texts."""
        if self.use_button_box:
            try:
                ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
                cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
                if ok_btn:
                    ok_btn.setText(finish_text)
                if cancel_btn:
                    cancel_btn.setText(cancel_text)
            except Exception:
                pass
        else:
            self.finish_button.setText(finish_text)
            self.cancel_button.setText(cancel_text)


class FormDialog(BaseDialog):
    """
    Dialog with integrated form building capabilities.

    Extends BaseDialog with FormBuilder integration for consistent form handling.
    """

    def __init__(self, title: str = "", parent=None, use_button_box: bool = False):
        self.form_builder = None
        super().__init__(title, parent, use_button_box)

    def _setup_content(self):
        """Setup form builder in content area."""
        self.form_builder = FormBuilder(self.content_widget)
        self.content_layout.addWidget(self.form_builder)

    def add_form_field(self, field_id: str, label_text: str, field_type: str = "text",
                      options: Optional[List[str]] = None, default: str = ""):
        """Add a field to the form."""
        if self.form_builder:
            self.form_builder.add_field(field_id, label_text, field_type, options, default)

    def get_form_values(self) -> Dict[str, Any]:
        """Get all form values."""
        return self.form_builder.get_values() if self.form_builder else {}

    def set_form_values(self, values: Dict[str, Any]):
        """Set form values."""
        if self.form_builder:
            self.form_builder.set_values(values)


class EnhancedFormBuilder(FormBuilder):
    """
    Enhanced form builder with additional field types and validation.

    Extends the basic FormBuilder with more field types and common validation patterns.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    def add_numeric_field(self, field_id: str, label_text: str, min_val: Optional[int] = None,
                         max_val: Optional[int] = None, default: int = 0):
        """Add a numeric input field with validation."""
        from PyQt6.QtWidgets import QSpinBox

        label = QLabel(label_text)
        label.setFixedHeight(ROW_HEIGHT)

        widget = QSpinBox()
        if min_val is not None:
            widget.setMinimum(min_val)
        if max_val is not None:
            widget.setMaximum(max_val)
        widget.setValue(default)
        widget.setFixedHeight(ROW_HEIGHT)

        self.layout.addRow(label, widget)
        self.fields[field_id] = widget

    def add_ip_field(self, field_id: str, label_text: str, default: str = "127.0.0.1"):
        """Add an IP address field with basic validation."""
        label = QLabel(label_text)
        label.setFixedHeight(ROW_HEIGHT)

        widget = QLineEdit()
        widget.setText(default)
        widget.setFixedHeight(ROW_HEIGHT)
        # Could add IP validation here

        self.layout.addRow(label, widget)
        self.fields[field_id] = widget

    def add_port_field(self, field_id: str, label_text: str, default: int = 502):
        """Add a port field (1-65535)."""
        self.add_numeric_field(field_id, label_text, min_val=1, max_val=65535, default=default)