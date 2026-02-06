from PyQt6.QtWidgets import (
    QFormLayout, QLineEdit, QTabWidget, QWidget,
)
from ..base_dialogs import FormDialog
# UI constants
DIALOG_MIN_WIDTH = 400
DIALOG_MIN_HEIGHT = 300


class GroupDialog(FormDialog):
    """组属性对话框 - 使用统一基类"""

    def __init__(self, parent=None, suggested_name="Group1"):
        self.suggested_name = suggested_name
        # Store field references for easy access
        self.name_edit = None
        self.desc_edit = None
        super().__init__("Group Properties", parent)
        self.setMinimumSize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)

    def _setup_content(self):
        """Setup dialog content using form builder."""
        # General tab
        tab = QWidget()
        form = QFormLayout(tab)

        self.name_edit = QLineEdit(str(self.suggested_name) if self.suggested_name else "")
        self.desc_edit = QLineEdit("")

        form.addRow("Name:", self.name_edit)
        form.addRow("Description:", self.desc_edit)

        tabs = QTabWidget()
        tabs.addTab(tab, "General")
        self.content_layout.addWidget(tabs)

    def load_data(self, data):
        """加载数据"""
        if not data:
            return
        # 支持嵌套结构或平铺结构
        if isinstance(data.get("general"), dict):
            data = data["general"]

        if self.name_edit:
            self.name_edit.setText(str(data.get("name", "")))
        if self.desc_edit:
            self.desc_edit.setText(str(data.get("description", "")))

    def get_data(self):
        """获取数据"""
        name = self.name_edit.text() if self.name_edit else ""
        desc = self.desc_edit.text() if self.desc_edit else ""

        return {
            "name": name,
            "description": desc,
            "general": {
                "name": name,
                "description": desc,
            }
        }
