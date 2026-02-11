from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLineEdit,
    QSpinBox,
    QLabel,
    QPushButton,
)
from PyQt6.QtCore import Qt
from ui.components import FormBuilder, get_form_field_style
# UI constants
DEFAULT_SPACING = 6  # 統一的垂直間距


class DeviceDialog(QDialog):
    def __init__(self, parent=None, suggested_name="", driver_type="Modbus RTU Serial"):
        super().__init__(parent)
        self.driver_type = str(driver_type)
        self.setWindowTitle("Device Properties")
        self.setMinimumSize(600, 550)
        self.setStyleSheet(get_form_field_style())

        # --- 根據 Driver 字串判斷顯示邏輯 ---
        self.is_serial = self.driver_type == "Modbus RTU Serial"
        self.is_over_tcp = self.driver_type == "Modbus RTU over TCP"
        self.is_ethernet = self.driver_type == "Modbus TCP/IP Ethernet"

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(DEFAULT_SPACING)  # 設置統一的垂直間距
        self.tabs = QTabWidget()

        # 1. General
        self._setup_general_tab(suggested_name)

        # 2. Timing (預設值參考邏輯圖)
        self._setup_timing_tab()

        # 3. DataAccess (預設值參考邏輯圖)
        self._setup_access_tab()

        # 4. Data Encoding (預設值參考邏輯圖)
        self._setup_encoding_tab()

        # 5. Block Sizes (預設值參考圖)
        self._setup_blocks_tab()

        main_layout.addWidget(self.tabs)

        # 按鈕列
        btns = QHBoxLayout()
        self.btn_finish = QPushButton("Finish")
        self.btn_cancel = QPushButton("Cancel")
        btns.addStretch()
        btns.addWidget(self.btn_finish)
        btns.addWidget(self.btn_cancel)
        main_layout.addLayout(btns)

        self.btn_finish.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _setup_general_tab(self, suggested_name):
        # 對應邏輯圖：Device Name, Description, Device ID
        self.tab_ident = QWidget()
        lay = QVBoxLayout(self.tab_ident)
        lay.setSpacing(DEFAULT_SPACING)  # 設置統一的垂直間距
        self.name_edit = QLineEdit(suggested_name)
        self.name_edit.setFixedHeight(22)  # 設置固定高度
        self.desc_edit = QLineEdit("")
        self.desc_edit.setFixedHeight(22)  # 設置固定高度
        self.id_spin = QSpinBox()
        self.id_spin.setRange(1, 65535)
        self.id_spin.setValue(1)
        self.id_spin.setFixedHeight(22)  # 設置與其他欄位相同的高度
        self.id_spin.setStyleSheet("QSpinBox { min-height: 22px; } QSpinBox QLineEdit { border: 1px solid #999; }")

        lay.addWidget(QLabel("Device Name:"))
        lay.addWidget(self.name_edit)
        lay.addWidget(QLabel("Description:"))
        lay.addWidget(self.desc_edit)
        lay.addWidget(QLabel("Device ID:"))
        lay.addWidget(self.id_spin)
        lay.addStretch()
        self.tabs.addTab(self.tab_ident, "General")

    # Ethernet settings are now handled at Channel/Driver level

    def _setup_timing_tab(self):
        # 對應邏輯圖：Request Timeout, Attempts, Inter-Request Delay
        self.tab_timing = QWidget()
        lay = QVBoxLayout(self.tab_timing)
        lay.setSpacing(DEFAULT_SPACING)  # 設置統一的垂直間距
        self.timing_builder = FormBuilder()

        from core.config.constants import MODBUS_DEFAULT_TIMING

        if self.is_over_tcp or self.is_ethernet:
            self.timing_builder.add_field(
                "connect_timeout", "Connect Timeout (s):", "text", default=MODBUS_DEFAULT_TIMING.get("connect_timeout", "")
            )

        if self.is_over_tcp:
            self.timing_builder.add_field(
                "connect_attempts", "Connect Attempts:", "text", default=MODBUS_DEFAULT_TIMING.get("connect_attempts", "")
            )

        # 使用預設值
        self.timing_builder.add_field(
            "req_timeout", "Request Timeout (ms):", "text", default=MODBUS_DEFAULT_TIMING.get("req_timeout", "")
        )
        self.timing_builder.add_field(
            "attempts", "Attempts Before Timeout:", "text", default=MODBUS_DEFAULT_TIMING.get("attempts", "")
        )
        self.timing_builder.add_field(
            "inter_req_delay", "Inter-Request Delay (ms):", "text", default=MODBUS_DEFAULT_TIMING.get("inter_req_delay", "")
        )

        lay.addWidget(self.timing_builder)
        self.tabs.addTab(self.tab_timing, "Timing")

    def _setup_access_tab(self):
        # 對應邏輯圖 DataAccess 節點
        self.tab_access = QWidget()
        lay = QVBoxLayout(self.tab_access)
        lay.setSpacing(DEFAULT_SPACING)  # 設置統一的垂直間距
        self.access_builder = FormBuilder()

        from core.config.constants import MODBUS_DEFAULT_DATA_ACCESS

        # 使用預設值
        self.access_builder.add_field(
            "zero_based",
            "Zero-Based Addressing:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_DATA_ACCESS.get("zero_based", ""),
        )
        self.access_builder.add_field(
            "zero_based_bit",
            "Zero-Based Bit Addressing:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_DATA_ACCESS.get("zero_based_bit", ""),
        )
        self.access_builder.add_field(
            "bit_writes",
            "Holding Register Bit Writes:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_DATA_ACCESS.get("bit_writes", ""),
        )
        self.access_builder.add_field(
            "func_06",
            "Modbus Function 06:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_DATA_ACCESS.get("func_06", ""),
        )
        self.access_builder.add_field(
            "func_05",
            "Modbus Function 05:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_DATA_ACCESS.get("func_05", ""),
        )

        lay.addWidget(self.access_builder)
        self.tabs.addTab(self.tab_access, "DataAccess")

    def _setup_encoding_tab(self):
        # 對應邏輯圖 Data Encoding 節點
        self.tab_encoding = QWidget()
        lay = QVBoxLayout(self.tab_encoding)
        lay.setSpacing(DEFAULT_SPACING)  # 設置統一的垂直間距
        self.encoding_builder = FormBuilder()

        from core.config.constants import MODBUS_DEFAULT_ENCODING

        # 使用預設值
        self.encoding_builder.add_field(
            "byte_order",
            "Modbus Byte Order:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_ENCODING.get("byte_order", ""),
        )
        self.encoding_builder.add_field(
            "word_order",
            "First Word Low:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_ENCODING.get("word_order", ""),
        )
        self.encoding_builder.add_field(
            "dword_order",
            "First Dword Low:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_ENCODING.get("dword_order", ""),
        )
        self.encoding_builder.add_field(
            "bit_order",
            "Modicon Bit Order:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_ENCODING.get("bit_order", ""),
        )
        self.encoding_builder.add_field(
            "treat_longs_as_decimals",
            "Treat Longs as Decimals:",
            "combo",
            options=["Enable", "Disable"],
            default=MODBUS_DEFAULT_ENCODING.get("treat_longs_as_decimals", ""),
        )

        lay.addWidget(self.encoding_builder)
        self.tabs.addTab(self.tab_encoding, "DataEncoding")

    def _setup_blocks_tab(self):
        # 對應邏輯圖 Block Sizes 節點
        self.tab_blocks = QWidget()
        lay = QVBoxLayout(self.tab_blocks)
        lay.setSpacing(DEFAULT_SPACING)  # 設置統一的垂直間距
        self.block_builder = FormBuilder()

        from core.config.constants import MODBUS_DEFAULT_BLOCK_SIZES

        # 使用預設值
        self.block_builder.add_field(
            "out_coils", "Output Coils:", "text", default=MODBUS_DEFAULT_BLOCK_SIZES.get("out_coils", "")
        )
        self.block_builder.add_field("in_coils", "Input Coils:", "text", default=MODBUS_DEFAULT_BLOCK_SIZES.get("in_coils", ""))
        self.block_builder.add_field(
            "int_regs", "Internal Registers:", "text", default=MODBUS_DEFAULT_BLOCK_SIZES.get("int_regs", "")
        )
        self.block_builder.add_field(
            "hold_regs", "Holding Registers:", "text", default=MODBUS_DEFAULT_BLOCK_SIZES.get("hold_regs", "")
        )

        lay.addWidget(self.block_builder)
        self.tabs.addTab(self.tab_blocks, "Block Sizes")

    def load_data(self, data):
        from core.utils import safe_getattr, safe_item_data

        if not data:
            return

        general = data.get("general") if isinstance(data.get("general"), dict) else None
        if not general:
            general = {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "device_id": data.get("device_id"),
            }

        self.name_edit.setText(general.get("name", ""))
        self.desc_edit.setText(general.get("description", ""))

        device_id = (
            general.get("device_id") if general is not None else data.get("device_id")
        )
        if not device_id and self.parent():
            current = safe_getattr(self.parent(), "tree", None)
            if current:
                current_item = safe_getattr(current, "currentItem", None)
                if current_item and safe_item_data(current_item, 0, None) == "Channel":
                    from core.utils import safe_call

                    controller = safe_getattr(self.parent(), "controller", None)
                    if controller:
                        device_id = safe_call(
                            controller.calculate_next_id,
                            current_item,
                            default=1,
                        )

        from core.utils import validate_and_get_int

        self.id_spin.setValue(
            validate_and_get_int(device_id, default=1, min_val=1, max_val=65535)
        )

        self._load_tab_data(data, general)

    def _load_tab_data(self, data, general):
        from core.config.constants import MODBUS_DEFAULT_TIMING, MODBUS_DEFAULT_DATA_ACCESS, MODBUS_DEFAULT_ENCODING, MODBUS_DEFAULT_BLOCK_SIZES
        
        timing = data.get("timing") or general.get("timing")
        if timing:
            # Map JSON keys to FormBuilder field IDs
            # JSON: request_timeout, attempts_before_timeout, inter_request_delay, connect_timeout, connect_attempts
            # FormBuilder: req_timeout, attempts, inter_req_delay, connect_timeout, connect_attempts
            timing_mapped = {}
            if isinstance(timing, dict):
                # Direct mappings (same key)
                if "connect_timeout" in timing:
                    timing_mapped["connect_timeout"] = timing["connect_timeout"]
                if "connect_attempts" in timing:
                    timing_mapped["connect_attempts"] = timing["connect_attempts"]
                # Key transformations
                if "request_timeout" in timing:
                    timing_mapped["req_timeout"] = timing["request_timeout"]
                elif "req_timeout" in timing:
                    timing_mapped["req_timeout"] = timing["req_timeout"]
                if "attempts_before_timeout" in timing:
                    timing_mapped["attempts"] = timing["attempts_before_timeout"]
                elif "attempts" in timing:
                    timing_mapped["attempts"] = timing["attempts"]
                if "inter_request_delay" in timing:
                    timing_mapped["inter_req_delay"] = timing["inter_request_delay"]
                elif "inter_req_delay" in timing:
                    timing_mapped["inter_req_delay"] = timing["inter_req_delay"]
            self.timing_builder.set_values(timing_mapped)

        access = data.get("data_access") or general.get("data_access")
        if access:
            access_display = self._convert_flags_to_display(
                access,
                ["zero_based", "zero_based_bit", "bit_writes", "func_06", "func_05"],
            )
            self.access_builder.set_values(access_display)

        enc = data.get("encoding") or general.get("encoding")
        if enc:
            enc_display = self._convert_flags_to_display(
                enc,
                [
                    "byte_order",
                    "word_order",
                    "dword_order",
                    "bit_order",
                    "treat_longs_as_decimals",
                ],
            )
            self.encoding_builder.set_values(enc_display)

        blocks = data.get("block_sizes") or general.get("block_sizes")
        if blocks:
            self.block_builder.set_values(blocks)

    def _convert_flags_to_display(self, flags_dict, flag_keys):
        display = {}
        if isinstance(flags_dict, dict):
            for k, v in flags_dict.items():
                if k in flag_keys:
                    display[k] = self._flag_to_display_value(v)
        return display

    def _flag_to_display_value(self, value):
        if value in (1, "1", "enable", "Enable", "true", "True"):
            return "Enable"
        elif value in (0, "0", "disable", "Disable", "false", "False"):
            return "Disable"
        return str(value)

    def get_data(self):
        # Return both flat and nested structures for compatibility
        nested = {
            "general": {
                "name": self.name_edit.text(),
                "description": self.desc_edit.text(),
                "device_id": self.id_spin.value(),
            },
            "timing": self.timing_builder.get_values(),
            "data_access": self.access_builder.get_values(),
            "encoding": self.encoding_builder.get_values(),
            # normalize block sizes to integers and canonical keys
            "block_sizes": self._normalize_block_sizes(self.block_builder.get_values()),
        }
        flat = {
            "name": self.name_edit.text(),
            "description": self.desc_edit.text(),
            "device_id": self.id_spin.value(),
            "timing": nested["timing"],
            "data_access": nested["data_access"],
            "encoding": nested["encoding"],
            "block_sizes": nested["block_sizes"],
        }
        # ethernet moved to Channel/Driver; Device no longer returns ethernet settings
        result = {**flat, **nested}
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(
            f"DeviceDialog.get_data() returning encoding: {result.get('encoding')}"
        )
        return result

    def _normalize_block_sizes(self, raw):
        # Coerce the block sizes dict values to ints and keep canonical keys.
        # Accepts dicts with keys like 'out_coils','in_coils','int_regs','hold_regs'
        # and will return a dict with those keys and integer values where possible.
        out = {}
        try:
            if not raw:
                return out
            if isinstance(raw, dict):
                for k, v in raw.items():
                    lk = str(k).strip()
                    try:
                        if v is None or str(v).strip() == "":
                            continue
                        vi = int(float(str(v).strip()))
                    except Exception:
                        continue
                    # keep only expected keys
                    if lk in ("out_coils", "in_coils", "int_regs", "hold_regs"):
                        out[lk] = vi
                    else:
                        # try to map common alternative names
                        lk2 = lk.lower()
                        if "hold" in lk2:
                            out.setdefault("hold_regs", vi)
                        elif (
                            "int" in lk2
                            or "internal" in lk2
                            or "input" in lk2
                            and "reg" in lk2
                        ):
                            out.setdefault("int_regs", vi)
                        elif "out" in lk2 and "coil" in lk2:
                            out.setdefault("out_coils", vi)
                        elif "in" in lk2 and "coil" in lk2:
                            out.setdefault("in_coils", vi)
            # if caller passed a single numeric value, apply to registers
            elif isinstance(raw, (int, float)):
                v = int(raw)
                out = {"hold_regs": v, "int_regs": v}
            elif isinstance(raw, str) and raw.strip().isdigit():
                v = int(raw.strip())
                out = {"hold_regs": v, "int_regs": v}
        except Exception:
            return {}
        return out
