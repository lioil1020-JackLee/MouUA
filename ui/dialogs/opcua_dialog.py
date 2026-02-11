import sys, os
# Allow running this dialog file directly from the project folder.
# When executed directly, ensure the project root is on sys.path so
# imports like `ui.widgets.form_builder` resolve correctly.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QTabWidget, 
    QWidget, QHBoxLayout, QCheckBox, QFormLayout, QLineEdit
)
from PyQt6.QtCore import Qt
from ui.components import FormBuilder, get_form_field_style
# UI constants
SPACING = 6  # 統一的垂直間距
MARGIN_H = 12
MARGIN_V = 12
FORM_MAX_WIDTH = 600
from core.utils.network_utils import detect_outbound_ip, get_network_adapters

class OPCUADialog(QDialog):
    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle("OPC UA Server")
        self.resize(640, 560)
        self.setStyleSheet(get_form_field_style())

        # 建立主分頁控制項
        self.tabs = QTabWidget(self)

        # --- General / Settings Tab ---
        self.settings_tab = QWidget()
        s_layout = QVBoxLayout(self.settings_tab)
        s_layout.setSpacing(SPACING)
        s_layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)
        
        self.settings_form = FormBuilder(self.settings_tab)
        self.settings_form.layout.setSpacing(SPACING)
        self.settings_form.setMaximumWidth(FORM_MAX_WIDTH)
        self.settings_form.add_field('application_Name', 'Application Name')
            # removed host_name field: network adapter / adapter IP used instead
        self.settings_form.add_field('namespace', 'Namespace')
        self.settings_form.add_field('port', 'Port')
        # Product URI is now read-only, computed from network adapter IP + port
        self.product_uri_label = QLabel('opc.tcp://127.0.0.1:4848/')
        self.product_uri_label.setStyleSheet("color: #888;")
        self.settings_form.layout.addRow("Product URI (Application URI)", self.product_uri_label)
        # Network adapter selector (combo). We'll populate with adapter names and IPv4 addresses
        self.settings_form.add_field('network_adapter', 'Network Adapter', field_type='combo', options=[])
        # keep a hidden field for adapter ip so values() returns it
        from PyQt6.QtWidgets import QLineEdit
        self._adapter_ip_hidden = QLineEdit()
        self._adapter_ip_hidden.setVisible(False)
        self.settings_form.fields['network_adapter_ip'] = self._adapter_ip_hidden
        # 已移除「Auto Start OPC UA Server on application startup」選項
        self.settings_form.add_field('max_sessions', 'Max Sessions')
        self.settings_form.add_field('publish_interval', 'Publish Interval (ms)')
        
        s_layout.addWidget(self.settings_form)
        s_layout.addStretch()

        # --- 2. Authentication Tab (具備 Username/Password 動態顯示邏輯) ---
        self.auth_tab = QWidget()
        a_layout = QVBoxLayout(self.auth_tab)
        a_layout.setSpacing(SPACING)
        a_layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)
        
        self.auth_form = FormBuilder(self.auth_tab)
        self.auth_form.layout.setSpacing(SPACING)
        self.auth_form.setMaximumWidth(FORM_MAX_WIDTH)
        self.auth_form.add_field('authentication', 'Authentication', field_type='combo', 
                                 options=['Anonymous', 'Username/Password'], 
                                 default='Anonymous')
        self.auth_form.add_field('username', 'Username')
        self.auth_form.add_field('password', 'Password')
        
        a_layout.addWidget(self.auth_form)
        a_layout.addStretch()

        # --- Security Policies Tab ---
        self.sec_tab = QWidget()
        sec_layout = QVBoxLayout(self.sec_tab)
        sec_layout.setSpacing(SPACING)
        sec_layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)

        self.sec_checkboxes = {
            'policy_none': QCheckBox('None'),
            'policy_sign_aes128': QCheckBox('Sign - Aes128'),
            'policy_sign_aes256': QCheckBox('Sign - Aes256'),
            'policy_sign_basic256sha256': QCheckBox('Sign - Basic256Sha256'),
            'policy_encrypt_aes128': QCheckBox('Sign & Encrypt - Aes128'),
            'policy_encrypt_aes256': QCheckBox('Sign & Encrypt - Aes256'),
            'policy_encrypt_basic256sha256': QCheckBox('Sign & Encrypt - Basic256Sha256')
        }

        for cb in self.sec_checkboxes.values():
            sec_layout.addWidget(cb)
        sec_layout.addStretch()

        # --- Certificate Tab ---
        self.cert_tab = QWidget()
        cert_layout = QVBoxLayout(self.cert_tab)
        cert_layout.setSpacing(SPACING)
        cert_layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)
        
        self.auto_generate = QCheckBox('Auto Generate Certificate')
        cert_layout.addWidget(self.auto_generate)

        self.cert_form = FormBuilder(self.cert_tab)
        self.cert_form.layout.setSpacing(SPACING)
        self.cert_form.setMaximumWidth(FORM_MAX_WIDTH)
        
        self.common_name_label = QLabel('ModUA@ModUA')
        self.common_name_label.setStyleSheet("color: #888;")
        self.cert_form.layout.addRow("Common Name", self.common_name_label)
        
        self.cert_form.add_field('organization', 'Organization')
        self.cert_form.add_field('organization_unit', 'Organization Unit')
        self.cert_form.add_field('locality', 'Locality')
        self.cert_form.add_field('state', 'State')
        
        # Country + 提示說明
        country_h = QHBoxLayout()
        self.country_input = QLineEdit()
        country_h.addWidget(self.country_input)
        country_h.addWidget(QLabel("(e.g. DE, US, ...)") )
        self.cert_form.layout.addRow("Country", country_h)
        self.cert_form.fields['country'] = self.country_input

        # Validity + 提示說明
        validity_h = QHBoxLayout()
        self.validity_input = QLineEdit()
        validity_h.addWidget(self.validity_input)
        validity_h.addWidget(QLabel("(Years, 1 - 20)"))
        self.cert_form.layout.addRow("Certificate Validity", validity_h)
        self.cert_form.fields['cert_validity'] = self.validity_input

        cert_layout.addWidget(self.cert_form)
        cert_layout.addStretch()

        # --- 組裝主視圖 ---
        self.tabs.addTab(self.settings_tab, 'Settings')
        self.tabs.addTab(self.auth_tab, 'Authentication')
        self.tabs.addTab(self.sec_tab, 'Security Policies')
        self.tabs.addTab(self.cert_tab, 'Certificate')

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(MARGIN_H, MARGIN_V, MARGIN_H, MARGIN_V)
        main_layout.addWidget(QLabel('Configure OPC UA Server parameters below:'))
        main_layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        try:
            ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
            if ok_btn is not None:
                ok_btn.setText('Finish')
        except Exception:
            pass
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # 初始初始化
        self._apply_defaults(initial)
        self._connect_endpoint_updaters()
        self._setup_auth_visibility()
        self._update_endpoint_label()

    # --- 邏輯功能輔助方法 ---

    def _setup_auth_visibility(self):
        # 控制 Username 與 Password 欄位的動態顯示與隱藏
        combo = self.auth_form.fields.get('authentication')
        def toggle():
            is_up = combo.currentText() == 'Username/Password'
            for key in ['username', 'password']:
                widget = self.auth_form.fields.get(key)
                if widget:
                    widget.setVisible(is_up)
                    label = self.auth_form.layout.labelForField(widget)
                    if label: label.setVisible(is_up)
        if combo:
            combo.currentTextChanged.connect(toggle)
            toggle()

    def _update_endpoint_label(self):
        # 即時計算並顯示 opc.tcp 連線字串，優先使用選取的 network adapter IP 或自動偵測
        try:
            vals = self.settings_form.get_values()
            # prefer selected network adapter IP
            host = ''
            try:
                na_widget = self.settings_form.fields.get('network_adapter')
                if na_widget and hasattr(na_widget, 'currentData'):
                    ipdata = na_widget.currentData()
                    if ipdata:
                        host = str(ipdata).strip()
                if not host:
                    host = (vals.get('network_adapter_ip') or '').strip()
            except Exception:
                host = (vals.get('network_adapter_ip') or '').strip()

            port = (vals.get('port') or '').strip()

            # if host resolves to loopback or is empty, auto-detect a LAN IP
            try:
                if not host or host.lower() in ('localhost', '127.0.0.1', 'modua'):
                    h = detect_outbound_ip()
                else:
                    h = host
            except Exception:
                h = detect_outbound_ip()

            # expose chosen adapter ip in hidden field for persistence
            try:
                if hasattr(self, '_adapter_ip_hidden'):
                    self._adapter_ip_hidden.setText(h)
            except Exception:
                pass

            # Update product URI label with computed opc.tcp endpoint
            try:
                if port:
                    endpoint = f"opc.tcp://{h}:{port}/"
                else:
                    endpoint = f"opc.tcp://{h}:4848/"
                if hasattr(self, 'product_uri_label'):
                    self.product_uri_label.setText(endpoint)
            except Exception:
                pass
        except Exception:
            pass

    def _connect_endpoint_updaters(self):
        # update when port changes or network adapter selection changes
        for k in ['port', 'network_adapter']:
            w = self.settings_form.fields.get(k)
            try:
                if hasattr(w, 'textChanged'):
                    w.textChanged.connect(self._update_endpoint_label)
                elif hasattr(w, 'currentIndexChanged'):
                    w.currentIndexChanged.connect(self._on_adapter_changed)
            except Exception:
                pass
        # initially populate adapters
        try:
            self._populate_adapters()
        except Exception:
            pass

    def _on_adapter_changed(self, idx=None):
        try:
            na = self.settings_form.fields.get('network_adapter')
            if na and hasattr(na, 'currentData'):
                ip = na.currentData()
                try:
                    self._adapter_ip_hidden.setText(str(ip or ''))
                except Exception:
                    pass
            self._update_endpoint_label()
        except Exception:
            pass

    def _populate_adapters(self):
        # Populate the network adapter combo with available IPv4 addresses using network_utils.
        try:
            na_widget = self.settings_form.fields.get('network_adapter')
            if na_widget is None:
                return
            
            # Get current values before clearing
            try:
                current_vals = self.settings_form.get_values() or {}
                saved_ip = current_vals.get('network_adapter_ip') or None
                saved_name = current_vals.get('network_adapter') or None
            except Exception:
                saved_ip = None
                saved_name = None
            
            try:
                na_widget.clear()
            except Exception:
                pass

            # Get adapters using unified utility
            adapters = get_network_adapters()
            for display_name, ip_addr in adapters:
                na_widget.addItem(display_name, ip_addr)

            # Handle saved adapter IP selection
            try:
                if saved_ip:
                    idx = na_widget.findData(saved_ip)
                    if idx >= 0:
                        na_widget.setCurrentIndex(idx)
                        self._adapter_ip_hidden.setText(str(saved_ip))
                    else:
                        # target ip not present in detected adapters -> add a synthetic entry
                        try:
                            name = saved_name or ''
                            display = f"{name} ({saved_ip})" if name else f"Auto ({saved_ip})"
                            na_widget.addItem(display, saved_ip)
                            # select the newly added item
                            idx2 = na_widget.findData(saved_ip)
                            if idx2 >= 0:
                                na_widget.setCurrentIndex(idx2)
                                self._adapter_ip_hidden.setText(str(saved_ip))
                        except Exception:
                            pass
                elif saved_name:
                    # Try to match by adapter name if no IP saved
                    for i in range(na_widget.count()):
                        if na_widget.itemText(i) == saved_name:
                            na_widget.setCurrentIndex(i)
                            current_ip = na_widget.currentData()
                            if current_ip:
                                self._adapter_ip_hidden.setText(str(current_ip))
                            break
                    else:
                        # if no match, default to first adapter
                        if na_widget.count() > 0:
                            na_widget.setCurrentIndex(0)
                            current_ip = na_widget.currentData()
                            if current_ip:
                                self._adapter_ip_hidden.setText(str(current_ip))
                else:
                    # if no saved target, default to the first detected adapter
                    try:
                        if na_widget.count() > 0:
                            na_widget.setCurrentIndex(0)
                            # Set hidden field to the selected adapter's IP
                            current_ip = na_widget.currentData()
                            if current_ip:
                                self._adapter_ip_hidden.setText(str(current_ip))
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _apply_defaults(self, initial):
        defaults = {
            'application_Name': 'ModUA', 'namespace': 'ModUA', 'port': '48480',
            'policy_none': True, 'policy_sign_aes128': False, 'policy_sign_aes256': False,
            'policy_sign_basic256sha256': False, 'policy_encrypt_aes128': False,
            'policy_encrypt_aes256': False, 'policy_encrypt_basic256sha256': False,
            'auto_generate': True,
            # 預設憑證欄位
            'common_name': 'ModUA@lioil',
            'organization': 'Organization',
            'organization_unit': 'Unit',
            'locality': 'Locality',
            'state': 'State',
            'country': 'tw',
            'cert_validity': '20',
            # 其他預設
            'max_sessions': '4096', 'publish_interval': '1000'
        }
        self.set_values(defaults)
        if initial: self.set_values(initial)

    def set_values(self, data: dict):
        if not data: return
        for f in [self.settings_form, self.auth_form, self.cert_form]:
            f.set_values(data)
        for k, cb in self.sec_checkboxes.items():
            cb.setChecked(bool(data.get(k, False)))
        self.auto_generate.setChecked(bool(data.get('auto_generate', True)))
        # 支援設置 Common Name（在表單中為 QLabel）
        if 'common_name' in data and hasattr(self, 'common_name_label'):
            try:
                self.common_name_label.setText(str(data.get('common_name') or ''))
            except: pass

    def load_data(self, data: dict):
        # Accept nested or flat structures and populate the dialog
        if not data:
            return
        try:
            # Some callers provide a combined {**flat, **nested} structure where
            # nested sections like 'authentication' or 'general' are dicts.
            # FormBuilder.set_values expects flat key->value pairs. Build a
            # flattened view that prefers explicit top-level scalar keys but
            # will pull values from nested sections when present.
            flat = {}
            try:
                # copy non-dict top-level entries first
                for k, v in (data.items() if isinstance(data, dict) else []):
                    if not isinstance(v, dict):
                        flat[k] = v
            except Exception:
                pass

            # Pull from known nested sections to ensure fields like
            # authentication/username/password/network_adapter_ip are available
            for sec in ('general', 'authentication', 'security_policies', 'certificate'):
                try:
                    sub = data.get(sec) if isinstance(data.get(sec), dict) else None
                    if isinstance(sub, dict):
                        for k, v in sub.items():
                            # do not overwrite explicit top-level scalar keys
                            if k not in flat:
                                flat[k] = v
                except Exception:
                    pass

            # Fallback: if nothing found, use original data
            to_apply = flat if flat else data

            # Remove network_adapter from to_apply since _populate_adapters handles it
            to_apply = {k: v for k, v in to_apply.items() if k != 'network_adapter'}

            # reuse set_values for most fields
            self.set_values(to_apply)

            # ensure network_adapter_ip hidden field is set if provided
            na_ip = None
            try:
                na_ip = to_apply.get('network_adapter_ip') if isinstance(to_apply, dict) else None
            except Exception:
                na_ip = None
            try:
                if hasattr(self, '_adapter_ip_hidden') and na_ip is not None:
                    self._adapter_ip_hidden.setText(str(na_ip))
            except Exception:
                pass
        except Exception:
            pass

    def get_data(self):
        # Return both flat and nested representations for compatibility
        vals = {}
        try:
            vals = self.settings_form.get_values() or {}
        except Exception:
            vals = {}
        try:
            auth_vals = self.auth_form.get_values() or {}
            vals.update(auth_vals)
        except Exception:
            pass
        try:
            cert_vals = self.cert_form.get_values() or {}
        except Exception:
            cert_vals = {}

        policies = {k: bool(cb.isChecked()) for k, cb in self.sec_checkboxes.items()}

        adapter_ip = ''
        try:
            if hasattr(self, '_adapter_ip_hidden'):
                adapter_ip = self._adapter_ip_hidden.text() or ''
        except Exception:
            adapter_ip = ''

        # canonicalize application name key (support existing mixed-case)
        app_name = vals.get('application_Name') or vals.get('application_name') or ''

        # Get product_uri from the label (computed from adapter IP + port)
        product_uri = ''
        try:
            if hasattr(self, 'product_uri_label'):
                product_uri = self.product_uri_label.text() or ''
        except Exception:
            product_uri = ''

        nested = {
            'general': {
                'application_name': app_name,
                'namespace': vals.get('namespace', ''),
                'port': vals.get('port', ''),
                'product_uri': product_uri,
                'network_adapter': vals.get('network_adapter', ''),
                'network_adapter_ip': vals.get('network_adapter_ip', '') or adapter_ip,
                'max_sessions': vals.get('max_sessions', ''),
                'publish_interval': vals.get('publish_interval', ''),
            },
            'authentication': {
                'authentication': vals.get('authentication', 'Anonymous'),
                'username': vals.get('username', ''),
                'password': vals.get('password', ''),
            },
            'security_policies': policies,
            'certificate': {**cert_vals, 'auto_generate': bool(self.auto_generate.isChecked()), 'common_name': (self.common_name_label.text() if hasattr(self, 'common_name_label') else '')},
        }

        # flatten for legacy callers
        flat = {}
        flat.update(nested['general'])
        flat.update(nested['authentication'])
        flat.update(nested['security_policies'])
        flat.update(nested['certificate'])

        out = {**flat, **nested}
        return out
