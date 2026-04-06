from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon, QPalette
import base64
import logging


def _is_light_theme():
    """檢測系統是否為淺色主題。"""
    app = QApplication.instance()
    if app:
        palette = app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        return window_color.lightness() > 128  # 亮度大於 128 視為淺色
    return False


class ConnectivityTree(QTreeWidget):
    # 定義自訂訊號
    request_new_channel = pyqtSignal(QTreeWidgetItem)
    request_new_device = pyqtSignal(QTreeWidgetItem)
    request_new_group = pyqtSignal(QTreeWidgetItem)
    request_new_tag = pyqtSignal(QTreeWidgetItem)

    request_edit_item = pyqtSignal(QTreeWidgetItem)
    request_delete_item = pyqtSignal(QTreeWidgetItem)
    request_copy_item = pyqtSignal(QTreeWidgetItem)
    request_paste_item = pyqtSignal(QTreeWidgetItem)
    request_cut_item = pyqtSignal(QTreeWidgetItem)
    request_import_csv = pyqtSignal(QTreeWidgetItem)
    request_export_csv = pyqtSignal(QTreeWidgetItem)
    request_device_diagnostics = pyqtSignal(QTreeWidgetItem)
    # New signal: request the main UI show the content page for an item (used for Group double-click)
    request_show_content = pyqtSignal(QTreeWidgetItem)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.root_node = QTreeWidgetItem(self)
        self.root_node.setText(0, "Project")
        self.root_node.setData(0, Qt.ItemDataRole.UserRole, "Project")
        self.conn_node = QTreeWidgetItem(self.root_node)
        self.conn_node.setText(0, "Connectivity")
        self.conn_node.setData(0, Qt.ItemDataRole.UserRole, "Connectivity")

        self.setHeaderHidden(True)
        self.setUniformRowHeights(True)
        self.setColumnCount(1)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(True)
        self.setIndentation(20)

        self._create_branch_symbols()
        self._setup_icons_and_tags()
        self.setExpandsOnDoubleClick(False)
        self.itemDoubleClicked.connect(self._handle_double_click)

    def _create_branch_symbols(self):
        try:

            def _make_symbol_pixmap(size, minus=False):
                pix = QPixmap(size, size)
                pix.fill(QColor(0, 0, 0, 0))
                p = QPainter(pix)
                pen = QPen(QColor(200, 200, 200))
                pen.setWidth(max(2, size // 8))
                p.setPen(pen)
                y = size // 2
                p.drawLine(size // 4, y, size * 3 // 4, y)
                if not minus:
                    x = size // 2
                    p.drawLine(x, size // 4, x, size * 3 // 4)
                p.end()
                return pix

            def _pixmap_to_dataurl(pix):
                buf = QBuffer()
                buf.open(QIODevice.OpenModeFlag.WriteOnly)
                pix.save(buf, "PNG")
                data = bytes(buf.data())
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:image/png;base64,{b64}"

            size = 28
            self._plus_icon = QIcon(_make_symbol_pixmap(size, minus=False))
            self._minus_icon = QIcon(_make_symbol_pixmap(size, minus=True))
            plus_url = _pixmap_to_dataurl(self._plus_icon.pixmap(size))
            minus_url = _pixmap_to_dataurl(self._minus_icon.pixmap(size))

            # 根據系統主題設定背景與選取顏色
            if _is_light_theme():
                bg_color = "#ffffff"
                text_color = "#000000"
                selected_bg = "#cce7ff"
                selected_hover = "#99d6ff"
            else:
                bg_color = "#2b2b2b"
                text_color = "#ffffff"
                selected_bg = "#0d47a1"
                selected_hover = "#1565c0"

            sheet = f"""
QTreeWidget::branch:closed:has-children {{ image: url({plus_url}); width: {size}px; height: {size}px; margin-left: 0px; margin-right: 5px; }}
QTreeWidget::branch:open:has-children {{ image: url({minus_url}); width: {size}px; height: {size}px; margin-left: 0px; margin-right: 5px; }}
QTreeWidget {{ 
    margin-left: 0px; 
    padding-left: 0px; 
    outline: none; 
    border: none;
    background-color: {bg_color};
}}
QTreeWidget::item {{ 
    padding-left: 0px; 
    outline: none; 
    border: none;
    background-color: {bg_color};
    color: {text_color};
}}
QTreeWidget::item:selected {{ 
    background-color: {selected_bg};
    color: {text_color};
    outline: none;
    border: none;
}}
QTreeWidget::item:selected:hover {{
    background-color: {selected_hover};
    outline: none;
    border: none;
}}
"""
            self.setStyleSheet(sheet)
        except Exception:
            logging.exception("Error creating branch symbols")

    def _setup_icons_and_tags(self):
        try:

            def _has_non_tag_child(node):
                if node is None:
                    return False
                for ii in range(node.childCount()):
                    ch = node.child(ii)
                    if ch is None:
                        continue
                    if ch.data(0, Qt.ItemDataRole.UserRole) != "Tag":
                        return True
                return False

            def _update_item_icon(item):
                if item is None:
                    return
                ntype = item.data(0, Qt.ItemDataRole.UserRole)
                if ntype == "Tag":
                    item.setHidden(True)
                    return

                if _has_non_tag_child(item):
                    if item.isExpanded():
                        item.setIcon(0, self._minus_icon)
                    else:
                        item.setIcon(0, self._plus_icon)
                else:
                    item.setIcon(0, QIcon())

            def _apply_recursive(node):
                if node is None:
                    return
                _update_item_icon(node)
                for i in range(node.childCount()):
                    _apply_recursive(node.child(i))

            self.itemExpanded.connect(lambda it: _update_item_icon(it))
            self.itemCollapsed.connect(lambda it: _update_item_icon(it))

            model = self.model()

            def _on_rows_inserted(parent_index, start, end):
                try:
                    if parent_index.isValid():
                        parent_item = self.itemFromIndex(parent_index)
                    else:
                        parent_item = self.invisibleRootItem()
                    for i in range(start, end + 1):
                        child = parent_item.child(i)
                        _apply_recursive(child)
                    _update_item_icon(parent_item)
                except Exception:
                    pass

            model.rowsInserted.connect(_on_rows_inserted)
            _apply_recursive(self.invisibleRootItem())
        except Exception:
            pass

    def drawBranches(self, painter, rect, index):
        # Override to completely skip drawing branch lines
        # This prevents the | symbols from appearing
        pass

    def drawTree(self, painter, region):
        # Skip drawing tree to prevent any branch lines
        # Call parent's item painting but not branch painting
        super().drawTree(painter, region)

    def hide_all_tags(self):
        # Public helper: walk the whole tree and hide any Tag-level nodes.
        try:

            def _walk(node):
                if node is None:
                    return
                try:
                    ntype = node.data(0, Qt.ItemDataRole.UserRole)
                    if ntype == "Tag":
                        try:
                            node.setHidden(True)
                        except Exception:
                            pass
                except Exception:
                    pass
                for i in range(node.childCount()):
                    _walk(node.child(i))

            _walk(self.invisibleRootItem())
        except Exception:
            pass

        # 若缺少 Project -> Connectivity 階層，則重新建立
        try:
            if not getattr(self, "root_node", None):
                self.root_node = QTreeWidgetItem(self)
                self.root_node.setText(0, "Project")
                self.root_node.setData(0, Qt.ItemDataRole.UserRole, "Project")
                try:
                    self.root_node.setExpanded(False)
                except Exception:
                    pass
            if not getattr(self, "conn_node", None):
                self.conn_node = QTreeWidgetItem(self.root_node)
                self.conn_node.setText(0, "Connectivity")
                self.conn_node.setData(0, Qt.ItemDataRole.UserRole, "Connectivity")
                try:
                    self.conn_node.setExpanded(False)
                except Exception:
                    pass
        except Exception:
            pass
        # 確保頂層節點使用和一般節點相同字型，避免粗體樣式造成高度差異
        try:
            default_font = self.font()
            self.root_node.setFont(0, default_font)
            self.conn_node.setFont(0, default_font)
        except Exception:
            pass

    def _has_non_tag_child(self, node):
        # Return True if node has any child that is not a Tag (Tags are hidden)
        try:
            if node is None:
                return False
            for ii in range(node.childCount()):
                try:
                    ch = node.child(ii)
                    if ch is None:
                        continue
                    try:
                        if ch.data(0, Qt.ItemDataRole.UserRole) != "Tag":
                            return True
                    except Exception:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _handle_double_click(self, item, _column):
        node_type = item.data(0, Qt.ItemDataRole.UserRole)

        if node_type in ["Project", "Connectivity"]:
            item.setExpanded(not item.isExpanded())
        elif node_type == "Group":
            self.setCurrentItem(item)
            self.request_show_content.emit(item)
        else:
            self.request_edit_item.emit(item)

    def mousePressEvent(self, event):
        # Override to make clicking the left indentation/icon area toggle expand/collapse
        try:
            pos = event.pos()
            item = self.itemAt(pos)
            if item is not None:
                # get visual rect for item text/icon
                try:
                    rect = self.visualItemRect(item)
                except Exception:
                    rect = None
                if rect is not None:
                    # define a branch-hit zone using our branch icon size (fallback to 28)
                    icon_w = getattr(self, "_branch_icon_size", None)
                    try:
                        if icon_w is None:
                            # attempt to infer from icon available
                            icon_w = (
                                self._plus_icon.actualSize(
                                    self._plus_icon.availableSizes()[0]
                                ).width()
                                if hasattr(self, "_plus_icon")
                                and self._plus_icon.availableSizes()
                                else 28
                            )
                    except Exception:
                        icon_w = 28
                    zone_left = rect.left()
                    x, y, w, h = (zone_left, rect.top(), icon_w + 8, rect.height())
                    if x <= pos.x() <= x + w and rect.top() <= pos.y() <= rect.bottom():
                        try:
                            # only toggle expand/collapse for items that have non-Tag children
                            if self._has_non_tag_child(item):
                                item.setExpanded(not item.isExpanded())
                                # update icon immediately
                                try:
                                    item.setIcon(
                                        0,
                                        self._minus_icon
                                        if item.isExpanded()
                                        else self._plus_icon,
                                    )
                                except Exception:
                                    pass
                            return
                        except Exception:
                            pass
        except Exception:
            pass
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        # 右鍵選單事件處理
        # Qt override - this method is invoked by the framework; keep it even if static analysis flags it.
        item = self.itemAt(event.pos())
        if not item:
            return

        node_type = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        # 根據節點類型顯示不同選項
        if node_type == "Connectivity":
            menu.addAction("新增 Channel", lambda: self.request_new_channel.emit(item))
        elif node_type == "Channel":
            menu.addAction("新增 Device", lambda: self.request_new_device.emit(item))
            menu.addSeparator()
            self._add_common_actions(menu, item)
        elif node_type in ["Device", "Group"]:
            menu.addAction("新增 Group", lambda: self.request_new_group.emit(item))
            menu.addAction("新增 Tag", lambda: self.request_new_tag.emit(item))
            menu.addSeparator()
            self._add_common_actions(menu, item)
            # Diagnostics only for Device (show per-device diagnostics window)
            if node_type == "Device":
                menu.addSeparator()
                menu.addAction(
                    "開啟 Diagnostics", lambda: self.request_device_diagnostics.emit(item)
                )
            # CSV import/export only on Device nodes
            if node_type == "Device":
                menu.addSeparator()
                menu.addAction("匯入 CSV", lambda: self.request_import_csv.emit(item))
                menu.addAction("匯出 CSV", lambda: self.request_export_csv.emit(item))
        elif node_type == "Tag":
            self._add_common_actions(menu, item)

        if not menu.isEmpty():
            menu.exec(event.globalPos())

    def _add_common_actions(self, menu, item):
        # 共用選單動作：剪下、複製、貼上、刪除、編輯
        menu.addAction("剪下", lambda: self.request_cut_item.emit(item))
        menu.addAction("複製", lambda: self.request_copy_item.emit(item))
        menu.addAction("貼上", lambda: self.request_paste_item.emit(item))
        menu.addSeparator()
        menu.addAction("刪除", lambda: self.request_delete_item.emit(item))
        menu.addAction("編輯", lambda: self.request_edit_item.emit(item))
