"""OPC UA Server for ModUA

Dynamic OPC UA server that maps project tags to OPC UA nodes.
All configuration comes from tree widget via data_manager, no hardcoding.
Supports bidirectional read/write operations.
"""

import asyncio
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List
from core.config.constants import MODBUS_DEFAULT_ENCODING

try:
    from asyncua import Server, ua
    from asyncua.common.callback import CallbackType
    from asyncua.server.user_managers import UserManager, User, UserRole
except ImportError:
    try:
        from opcua import Server, ua
        from opcua.common.callback import CallbackType
        UserManager = None
        User = None
        UserRole = None
    except ImportError:
        Server = None
        ua = None
        CallbackType = None
        UserManager = None
        User = None
        UserRole = None
        raise ImportError(
            "Neither asyncua nor opcua is installed. Please install one of them."
        )

# Certificate generation imports
try:
    from asyncua.crypto.cert_gen import generate_self_signed_app_certificate
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.x509 import GeneralName, DNSName, IPAddress, UniformResourceIdentifier
    from cryptography.x509.oid import ExtendedKeyUsageOID
    import ipaddress
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    generate_self_signed_app_certificate = None

try:
    from PyQt6.QtCore import Qt
except ImportError:
    try:
        from PyQt5.QtCore import Qt
    except ImportError:
        Qt = None
        raise ImportError("Neither PyQt6 nor PyQt5 is installed.")

logger = logging.getLogger(__name__)


class OPCUAUserManager(UserManager):
    """Custom user manager for OPC UA server authentication.

    Supports both anonymous and username/password authentication based on configuration.
    """

    def __init__(self, auth_config: Dict[str, Any]):
        """Initialize user manager with authentication configuration.

        Args:
            auth_config: Authentication configuration from settings
        """
        self.auth_config = auth_config or {}
        self.auth_type = self.auth_config.get("authentication", "Anonymous")
        self.username = self.auth_config.get("username", "")
        self.password = self.auth_config.get("password", "")

        logger.info(f"OPC UA User Manager initialized with auth type: {self.auth_type}")

    def get_user(self, iserver, username=None, password=None, certificate=None):
        """Authenticate user based on configured authentication type.

        Args:
            iserver: Internal server instance
            username: Username from client
            password: Password from client
            certificate: Client certificate (not used)

        Returns:
            User object if authentication successful, None otherwise
        """
        if self.auth_type == "Anonymous":
            # Allow anonymous access
            logger.debug("Anonymous authentication successful")
            return User(role=UserRole.Admin, name="anonymous")

        elif self.auth_type == "Username/Password":
            # Check username and password
            if username == self.username and password == self.password:
                logger.debug(f"Username/password authentication successful for user: {username}")
                return User(role=UserRole.Admin, name=username)
            else:
                logger.warning(f"Username/password authentication failed for user: {username}")
                return None

        else:
            # Unknown authentication type, default to anonymous
            logger.warning(f"Unknown authentication type: {self.auth_type}, defaulting to anonymous")
            return User(role=UserRole.Admin, name="anonymous")


class OPCUAWriteInterceptor:
    """DEPRECATED: Interceptor for OPC UA client write operations.

    This class was used to wrap the internal address space's write method.
    It has been replaced by subscribe_server_callback(CallbackType.PostWrite).

    Kept for reference only - no longer used.

    In asyncua, writes go through the InternalServer -> AddressSpaceManager.
    We hook into this by wrapping the write method.
    """

    def __init__(self, opcua_server, original_write_func):
        """Initialize the write interceptor.

        Args:
            opcua_server: Reference to the OPCUAServer instance
            original_write_func: The original write function to call
        """
        self.opcua_server = opcua_server
        self.original_write = original_write_func
        # Track paths being updated by server to avoid loops
        self._server_updating = set()

    async def write(self, params):
        """Intercept write operations and forward to Modbus.

        Args:
            params: WriteParameters from OPC UA client

        Returns:
            Result from original write operation
        """
        # Call original write first
        result = await self.original_write(params)

        # Process successful writes
        try:
            for idx, write_value in enumerate(params.NodesToWrite):
                # Check if write was successful
                if hasattr(result, "__iter__"):
                    status = result[idx] if idx < len(result) else None
                else:
                    status = result

                # Only process successful writes
                if status is not None and hasattr(status, "is_good"):
                    if not status.is_good():
                        continue
                elif status is not None:
                    # status might be a StatusCode value
                    try:
                        if int(status) != 0:  # 0 = Good
                            continue
                    except (TypeError, ValueError):
                        pass

                # Extract tag path from NodeId
                node_id = write_value.NodeId
                node_id_str = str(node_id)

                # Skip if we're currently updating this path from server side
                if node_id_str in self._server_updating:
                    continue

                # Extract path (format: ns=2;s=Channel1.Device1.Tag1)
                tag_path = None
                if hasattr(node_id, "Identifier") and isinstance(
                    node_id.Identifier, str
                ):
                    tag_path = node_id.Identifier
                elif ";s=" in node_id_str:
                    tag_path = node_id_str.split(";s=")[1]

                if not tag_path:
                    continue

                # Extract value from DataValue
                value = None
                if hasattr(write_value, "Value") and write_value.Value is not None:
                    dv = write_value.Value
                    if hasattr(dv, "Value"):
                        val = dv.Value
                        # Handle Variant wrapper
                        if hasattr(val, "Value"):
                            value = val.Value
                        else:
                            value = val
                    else:
                        value = dv

                if value is None:
                    continue

                # Forward to Modbus write handler
                logger.info(f"OPC UA client write detected: {tag_path} = {value}")
                try:
                    # Use write_tag_from_opcua which handles buffer update + Modbus write
                    self.opcua_server.write_tag_from_opcua(tag_path, value)
                except Exception as e:
                    logger.error(f"Error forwarding OPC UA write to Modbus: {e}")

        except Exception as e:
            logger.debug(f"Error processing write intercept: {e}")

        return result

    def mark_server_update(self, node_id_str: str):
        """Mark a node as being updated by server (to avoid loops)."""
        self._server_updating.add(node_id_str)

    def unmark_server_update(self, node_id_str: str):
        """Unmark a node after server update completes."""
        self._server_updating.discard(node_id_str)


class OPCUAWriteHandler:
    """Handler for OPC UA client write operations via subscription.

    This class is called when a monitored item's value changes.
    Used as fallback if write interceptor cannot be installed.
    """

    def __init__(self, opcua_server):
        """Initialize the write handler.

        Args:
            opcua_server: Reference to the OPCUAServer instance
        """
        self.opcua_server = opcua_server

    async def datachange_notification(self, node, val, data):
        """Called when a monitored item's value changes.

        Note: This is called for both server-side and client-side changes.
        We can use this to detect client writes if we're subscribed to our own variables.
        """
        try:
            # Get node ID as string
            node_id_str = str(node.nodeid)
            # Extract tag path from node ID (format: ns=2;s=Channel1.Device1.Tag1)
            if ";s=" in node_id_str:
                tag_path = node_id_str.split(";s=")[1]
                logger.debug(f"OPC UA data change: {tag_path} = {val}")
        except Exception as e:
            logger.debug(f"Error in datachange_notification: {e}")


def get_variant_type(data_type_str: str) -> ua.VariantType:
    """Map Modbus/UI data type to OPC UA VariantType.

    Args:
        data_type_str: Data type string (e.g., "Float", "Boolean", "Int32")

    Returns:
        OPC UA VariantType for the data type
    """
    if not data_type_str:
        return ua.VariantType.Double

    s = data_type_str.lower()

    # Boolean types
    if "boolean" in s or "bool" in s:
        return ua.VariantType.Boolean

    # Integer types (8-bit)
    if "byte" in s or "uint8" in s or "char" in s:
        return ua.VariantType.Byte

    # Integer types (16-bit)
    if "short" in s or "int16" in s:
        return ua.VariantType.Int16
    if "word" in s or "uint16" in s or "int" in s:
        return ua.VariantType.UInt16

    # Integer types (32-bit)
    if "long" in s or "int32" in s or "dword" in s or "uint32" in s:
        return ua.VariantType.Int32

    # Integer types (64-bit)
    if "llong" in s or "int64" in s or "qword" in s or "uint64" in s:
        return ua.VariantType.Int64

    # Float types
    if "float" in s or "real" in s:
        return ua.VariantType.Float
    if "double" in s:
        return ua.VariantType.Double

    # String type
    if "string" in s:
        return ua.VariantType.String

    # Default to Double
    return ua.VariantType.Double


def get_opcua_datatype(data_type_str: str) -> ua.NodeId:
    """Map Modbus/UI data type to OPC UA DataType NodeId.

    Args:
        data_type_str: Data type string (e.g., "Float", "Boolean", "Int32")

    Returns:
        OPC UA NodeId for the data type
    """
    if not data_type_str:
        return ua.NodeId(ua.ObjectIds.Double)

    s = data_type_str.lower()

    # Boolean types
    if "boolean" in s or "bool" in s:
        return ua.NodeId(ua.ObjectIds.Boolean)

    # Integer types (8-bit)
    if "byte" in s or "uint8" in s or "char" in s:
        return ua.NodeId(ua.ObjectIds.Byte)

    # Integer types (16-bit)
    if "short" in s or "int16" in s:
        return ua.NodeId(ua.ObjectIds.Int16)
    if "word" in s or "uint16" in s or "int" in s:
        return ua.NodeId(ua.ObjectIds.UInt16)

    # Integer types (32-bit)
    if "long" in s or "int32" in s or "dword" in s or "uint32" in s:
        return ua.NodeId(ua.ObjectIds.Int32)

    # Integer types (64-bit)
    if "llong" in s or "int64" in s or "qword" in s or "uint64" in s:
        return ua.NodeId(ua.ObjectIds.Int64)

    # Float types
    if "float" in s or "real" in s:
        return ua.NodeId(ua.ObjectIds.Float)
    if "double" in s:
        return ua.NodeId(ua.ObjectIds.Double)

    # String type
    if "string" in s:
        return ua.NodeId(ua.ObjectIds.String)

    # BCD types (store as Int16/Int32)
    if "lbcd" in s:
        return ua.NodeId(ua.ObjectIds.Int32)
    if "bcd" in s:
        return ua.NodeId(ua.ObjectIds.Int16)

    # Default to Double
    return ua.NodeId(ua.ObjectIds.Double)


def get_access_level(access_str: str) -> int:
    """Convert access string to OPC UA AccessLevel.

    Args:
        access_str: Access string (e.g., "Read/Write", "Read Only", "R/W", "RO")

    Returns:
        OPC UA AccessLevel value:
        - 0x01: CurrentRead (read-only)
        - 0x02: CurrentWrite (write-only)
        - 0x03: CurrentRead | CurrentWrite (read/write)
    """
    if not access_str:
        logger.debug(f"get_access_level: access_str is None or empty, returning 0x01")
        return 0x01

    s = str(access_str).lower().strip()
    logger.debug(f"get_access_level: input='{access_str}' -> normalized='{s}'")

    # Check for write permission - handle various formats
    # Try different common formats
    is_writable = (
        "read/write" in s  # "Read/Write"
        or "read/write" in s  # "Read/Write" (with space)
        or "r/w" in s  # "R/W"
        or "rw" in s  # "RW"
        or ("read" in s and "write" in s)  # Both words present
    )

    if is_writable:
        result = 0x03  # ReadWrite
        logger.debug(f"get_access_level: is_writable=True, returning 0x{result:02x}")
        return result
    elif "write" in s:
        result = 0x02  # WriteOnly
        logger.debug(f"get_access_level: write=True, returning 0x{result:02x}")
        return result
    else:
        result = 0x01  # ReadOnly
        logger.debug(f"get_access_level: readonly=True, returning 0x{result:02x}")
        return result


def get_default_value(
    data_type_str: str, is_array: bool = False, array_length: int = 0
) -> Any:
    """Get default value for a data type.

    Args:
        data_type_str: Data type string
        is_array: Whether this is an array type
        array_length: Length of the array (if is_array=True)

    Returns:
        Default value for the type
    """
    s = data_type_str.lower() if data_type_str else ""

    if is_array:
        if array_length <= 0:
            array_length = 1

        if "boolean" in s or "bool" in s:
            return [False] * array_length
        elif "float" in s or "real" in s:
            return [0.0] * array_length
        elif "double" in s:
            return [0.0] * array_length
        elif "byte" in s or "uint8" in s:
            return [0] * array_length
        elif "short" in s or "int16" in s:
            return [0] * array_length
        elif "word" in s or "uint16" in s:
            return [0] * array_length
        elif "long" in s or "int32" in s or "dword" in s or "uint32" in s:
            return [0] * array_length
        elif "llong" in s or "int64" in s or "qword" in s or "uint64" in s:
            return [0] * array_length
        elif "string" in s:
            return [""] * array_length
        else:
            return [0.0] * array_length
    else:
        if "boolean" in s or "bool" in s:
            return False
        elif "float" in s or "real" in s or "double" in s:
            return 0.0
        elif "string" in s:
            return ""
        else:
            return 0


def is_array_type(
    data_type_str: str, address: str = None, metadata: dict = None
) -> bool:
    """Determine if a tag is an array type.

    Checks multiple sources like monitor does:
    1. From data type string (contains "(Array)" or "[]")
    2. From address (contains "[n]" pattern)
    3. From metadata is_array flag

    Args:
        data_type_str: Data type string
        address: Address string (optional)
        metadata: Metadata dict (optional)

    Returns:
        True if array type, False otherwise
    """
    if data_type_str:
        s = data_type_str.lower()
        if "array" in s or "[]" in s or "(array)" in s:
            return True

    if address:
        if "[" in address and "]" in address:
            return True

    if metadata and isinstance(metadata, dict):
        if metadata.get("is_array", False):
            return True

    return False


def get_scaled_datatype(scaling: dict) -> Optional[str]:
    """Get the scaled data type from scaling config.

    If scaling is enabled, OPC UA should use the scaled data type.

    Args:
        scaling: Scaling configuration dict

    Returns:
        Scaled data type string, or None if no scaling
    """
    if not scaling or not isinstance(scaling, dict):
        return None

    scale_type = scaling.get("type", "").lower()
    if scale_type == "none" or not scale_type:
        return None

    # Return the scaled data type if scaling is enabled
    return scaling.get("scaled_type")


class OPCUAServer:
    """Dynamic OPC UA Server for ModUA

    Features:
    - All tags from tree widget mapped to OPC UA nodes
    - No hardcoded values - all from tree/data_manager
    - Bidirectional read/write support
    - Proper data type, access level handling
    - Scaled data type support
    - Array tag path mapping (buffer path -> OPC node path)
    """

    def __init__(self, settings: dict = None):
        """Initialize OPC UA server.

        Args:
            settings: OPC UA settings dict (from app.opcua_settings)
        """
        self.server = None
        self.is_running = False
        self.server_thread = None
        self.loop = None
        self._stop_event = None
        self.settings = settings or {}

        # Data sources (to be set externally)
        self.tree_widget = None
        self.data_buffer = None

        # Runtime monitor reference for write operations
        self.runtime_monitor = None

        # Tag cache for fast lookup
        self._tag_nodes = {}  # {tag_path: (node, tag_info)}
        self._tag_info = {}  # {tag_path: tag_info_dict}

        # ✅ NEW: Array element path mapping for bidirectional sync
        # Maps buffer paths (with [idx]) to base OPC node path
        # E.g., "Channel1.Device1.TOU_Array [0]" -> "Channel1.Device1.TOU_Array"
        self._array_element_map = {}  # {buffer_path: (opc_node_path, array_index)}

        # Hierarchy folder cache for Channel/Device/Group structures
        self._folder_nodes = {}  # {folder_path: folder_node}

        # ✅ Heartbeat mechanism for monitoring server health
        self._last_heartbeat = None  # Track last successful operation
        self._heartbeat_interval = 5.0  # Check every 5 seconds
        self._server_error = None  # Track server startup errors

        # ✅ Write interceptor for bidirectional sync
        self._write_interceptor = None  # Installed on server start

        # ✅ Track paths being updated by server to avoid feedback loops
        self._server_updating_paths = set()

        # ✅ Write request callback for routing to Monitor/app.py
        # Signature: callback(tag_path: str, value: Any, tag_info: dict) -> bool
        self._write_request_callback = None

    def set_data_sources(
        self, tree_widget=None, data_buffer=None, runtime_monitor=None
    ):
        """Set data sources for OPC UA server.

        Args:
            tree_widget: ConnectivityTree widget
            data_buffer: ModbusDataBuffer for live values
            runtime_monitor: RuntimeMonitor for write operations
        """
        if tree_widget is not None:
            self.tree_widget = tree_widget
        if data_buffer is not None:
            self.data_buffer = data_buffer
        if runtime_monitor is not None:
            self.runtime_monitor = runtime_monitor

    def set_write_request_callback(self, callback):
        """Set callback for handling OPC UA write requests.

        The callback will be invoked when an OPC UA client writes to a tag.
        This allows routing writes through the Monitor/app.py layer which
        handles proper Modbus encoding.

        Args:
            callback: Function with signature (tag_path: str, value: Any, tag_info: dict) -> bool
                     Returns True if write was successfully queued, False otherwise.
        """
        self._write_request_callback = callback
        logger.info(f"OPC UA write request callback registered: {callback is not None}")

    def is_server_healthy(self) -> bool:
        """✅ Check if OPC UA server is in healthy state.

        Returns:
            True if server is running and responsive, False otherwise
        """
        if not self.is_running or self.server is None:
            return False

        # ✅ Check if event loop is still alive and responsive
        if self.loop is None or self.loop.is_closed():
            return False

        # ✅ Check if server thread is still alive
        if self.server_thread is None or not self.server_thread.is_alive():
            return False

        return True

    def get_server_status(self) -> dict:
        """✅ Get detailed server status information.

        Returns:
            Dictionary with server status details
        """
        return {
            "is_running": self.is_running,
            "server_exists": self.server is not None,
            "loop_alive": self.loop is not None and not self.loop.is_closed(),
            "thread_alive": self.server_thread is not None
            and self.server_thread.is_alive(),
            "is_healthy": self.is_server_healthy(),
            "last_error": self._server_error,
            "tag_count": len(self._tag_nodes),
            "folder_count": len(self._folder_nodes),
        }

    def _get_server_config(self) -> dict:
        """Extract server configuration from settings.

        Returns:
            Dict with host, port, app_name, namespace, product_uri
        """
        try:
            gen = (
                self.settings.get("general", {})
                if isinstance(self.settings.get("general"), dict)
                else {}
            )
        except Exception:
            gen = {}

        # Get application name first (handle both cases: application_name and application_Name)
        app_name = (
            gen.get("application_name")
            or gen.get("application_Name")
            or self.settings.get("application_name")
            or self.settings.get("application_Name")
            or "ModUA"
        )

        # Get product_uri - this is the endpoint, used for display only
        product_uri = gen.get("product_uri", self.settings.get("product_uri", ""))

        return {
            "host": gen.get("network_adapter_ip")
            or self.settings.get("network_adapter_ip", "0.0.0.0"),
            "port": int(gen.get("port", self.settings.get("port", 4848))),
            "app_name": app_name,
            "namespace": gen.get("namespace", self.settings.get("namespace", "ModUA")),
            "product_uri": product_uri,
        }

    def _get_security_policies(self) -> List[ua.SecurityPolicyType]:
        """Get security policies from settings.

        Returns:
            List of security policy types from user configuration.

        Raises:
            ValueError: If no security policies are enabled in the configuration.
        """
        # Mapping from UI policy names to actual SecurityPolicyType values
        policy_mapping = {
            'policy_none': ua.SecurityPolicyType.NoSecurity,
            'policy_sign_aes128': ua.SecurityPolicyType.Aes128Sha256RsaOaep_Sign,
            'policy_sign_aes256': ua.SecurityPolicyType.Aes256Sha256RsaPss_Sign,
            'policy_sign_basic256sha256': ua.SecurityPolicyType.Basic256Sha256_Sign,
            'policy_encrypt_aes128': ua.SecurityPolicyType.Aes128Sha256RsaOaep_SignAndEncrypt,
            'policy_encrypt_aes256': ua.SecurityPolicyType.Aes256Sha256RsaPss_SignAndEncrypt,
            'policy_encrypt_basic256sha256': ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
        }

        try:
            sec = (
                self.settings.get("security_policies", {})
                if isinstance(self.settings.get("security_policies"), dict)
                else {}
            )
        except Exception:
            sec = {}

        # Map enabled policies to SecurityPolicyType
        policies = []
        for policy_name, enabled in sec.items():
            if enabled:
                try:
                    if policy_name in policy_mapping:
                        policies.append(policy_mapping[policy_name])
                    else:
                        logger.warning(f"Unknown security policy: {policy_name}")
                except Exception as e:
                    logger.warning(f"Error processing security policy {policy_name}: {e}")

        # Require at least one security policy to be enabled
        if not policies:
            raise ValueError(
                "No security policies enabled. Please enable at least one security policy "
                "in the OPC UA settings dialog (Security Policies tab)."
            )

        return policies

    def _needs_certificate(self, policies: List) -> bool:
        """Check if any of the security policies require a certificate.

        Args:
            policies: List of SecurityPolicyType values

        Returns:
            True if any policy other than NoSecurity is enabled
        """
        for policy in policies:
            if policy != ua.SecurityPolicyType.NoSecurity:
                return True
        return False

    def _get_certificate_paths(self) -> tuple:
        """Get paths for server certificate and private key files.

        In packaged exe environment, certificates are stored in user app data directory.
        In development environment, certificates are stored in project certs/ directory.

        Returns:
            Tuple of (cert_path, key_path)
        """
        import sys

        # Check if running in packaged exe environment
        is_packaged = getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')

        if is_packaged:
            # In packaged exe, store certificates in user app data directory
            try:
                if sys.platform == 'win32':
                    # Windows: %APPDATA%\ModUA\certs\
                    appdata = os.environ.get('APPDATA', '')
                    if appdata:
                        certs_dir = Path(appdata) / "ModUA" / "certs"
                    else:
                        # Fallback to exe directory
                        exe_dir = Path(sys.executable).parent
                        certs_dir = exe_dir / "certs"
                else:
                    # Linux/Mac: ~/.modua/certs/
                    home = os.path.expanduser("~")
                    certs_dir = Path(home) / ".modua" / "certs"
            except Exception:
                # Fallback to exe directory
                exe_dir = Path(sys.executable).parent
                certs_dir = exe_dir / "certs"
        else:
            # In development environment, store in project certs/ directory
            certs_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent / "certs"

        # Ensure directory exists
        certs_dir.mkdir(parents=True, exist_ok=True)

        cert_path = certs_dir / "server_certificate.der"
        key_path = certs_dir / "server_private_key.pem"

        return cert_path, key_path

    def _generate_server_certificate(self, app_name: str, host: str, port: int) -> tuple:
        """Generate a self-signed server certificate for OPC UA.

        Args:
            app_name: Application name for the certificate
            host: Server host/IP address
            port: Server port

        Returns:
            Tuple of (cert_path, key_path) if successful, (None, None) otherwise
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography library not available, cannot generate certificates")
            return None, None

        try:
            cert_path, key_path = self._get_certificate_paths()

            # Check if certificate already exists and is valid
            if cert_path.exists() and key_path.exists():
                logger.info(f"Using existing certificate: {cert_path}")
                return cert_path, key_path

            logger.info("Generating new self-signed server certificate...")

            # Generate RSA private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

            # Certificate subject names - use full X.509 attribute names as required by asyncua
            names = {
                "countryName": self._get_cert_config("country", "TW"),
                "stateOrProvinceName": self._get_cert_config("state", ""),
                "localityName": self._get_cert_config("locality", ""),
                "organizationName": self._get_cert_config("organization", "ModUA Organization"),
                "organizationalUnitName": self._get_cert_config("organization_unit", "OPC UA Server"),
            }
            # Remove empty values
            names = {k: v for k, v in names.items() if v}

            # Subject Alternative Names
            subject_alt_names = []

            # Add application URI
            app_uri = f"urn:{app_name}:server"
            subject_alt_names.append(UniformResourceIdentifier(app_uri))

            # Add DNS names
            subject_alt_names.append(DNSName(app_name))
            
            # Add local hostname
            import socket
            try:
                local_hostname = socket.gethostname()
                if local_hostname and local_hostname != app_name:
                    subject_alt_names.append(DNSName(local_hostname))
            except Exception:
                pass

            # Add IP addresses
            try:
                if host and host not in ("0.0.0.0", "::"):
                    ip = ipaddress.ip_address(host)
                    subject_alt_names.append(IPAddress(ip))
            except ValueError:
                # Not a valid IP, try as hostname
                subject_alt_names.append(DNSName(host))

            # Always add localhost
            subject_alt_names.append(DNSName("localhost"))
            subject_alt_names.append(IPAddress(ipaddress.ip_address("127.0.0.1")))

            # Extended key usage - for server authentication
            extended = [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]

            # Certificate validity
            validity_years = int(self._get_cert_config("cert_validity", "20"))
            validity_days = validity_years * 365

            # Generate certificate
            certificate = generate_self_signed_app_certificate(
                private_key=private_key,
                common_name=app_name,
                names=names,
                subject_alt_names=subject_alt_names,
                extended=extended,
                days=validity_days,
            )

            # Save private key
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            key_path.write_bytes(key_pem)
            logger.info(f"Private key saved to: {key_path}")

            # Save certificate in DER format (OPC UA preferred)
            cert_der = certificate.public_bytes(serialization.Encoding.DER)
            cert_path.write_bytes(cert_der)
            logger.info(f"Certificate saved to: {cert_path}")

            return cert_path, key_path

        except Exception as e:
            logger.error(f"Failed to generate server certificate: {e}", exc_info=True)
            return None, None

    def _get_cert_config(self, key: str, default: str) -> str:
        """Get certificate configuration value from settings.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        try:
            cert_config = self.settings.get("certificate", {})
            if isinstance(cert_config, dict):
                return cert_config.get(key, default)
        except Exception:
            pass
        return default

    async def _setup_certificate_validator(self):
        """Setup certificate validator for encrypted connections.

        For testing/development purposes, this validator automatically trusts
        client certificates. In production, you should implement proper
        certificate validation and trust management.
        """
        try:
            from asyncua.ua import StatusCodes
            from asyncua.common.status_codes import ServiceError

            # Certificate trust store - in production this should be persistent
            self._trusted_certificates = set()

            async def certificate_validator(certificate, application_description):
                """Validate client certificates.

                Args:
                    certificate: Client certificate (cryptography.x509.Certificate)
                    application_description: Client application description

                Raises:
                    ServiceError: If certificate is not trusted
                """
                if certificate is None:
                    # Allow connections without certificates (for None security policy)
                    logger.debug("Client connected without certificate (None security policy)")
                    return

                # Get certificate fingerprint for identification
                try:
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives import serialization

                    # Calculate certificate fingerprint
                    cert_fingerprint = certificate.fingerprint(hashes.SHA256()).hex()

                    logger.info(f"Client certificate received: {application_description.ApplicationName}")
                    logger.info(f"Certificate fingerprint: {cert_fingerprint}")
                    logger.info(f"Certificate subject: {certificate.subject}")

                    # For development/testing: automatically trust all certificates
                    # In production, you should:
                    # 1. Check against a trusted certificate store
                    # 2. Implement proper certificate validation
                    # 3. Possibly prompt user for approval

                    if cert_fingerprint not in self._trusted_certificates:
                        logger.warning(f"Auto-trusting new client certificate: {cert_fingerprint}")
                        self._trusted_certificates.add(cert_fingerprint)

                    logger.info(f"Client certificate trusted: {cert_fingerprint}")

                except Exception as e:
                    logger.error(f"Certificate validation error: {e}")
                    # For testing purposes, allow the connection even if validation fails
                    logger.warning("Allowing connection despite certificate validation error")

            # Set the certificate validator
            self.server.set_certificate_validator(certificate_validator)
            logger.info("Certificate validator set up for automatic client certificate trusting")

        except Exception as e:
            logger.warning(f"Failed to set up certificate validator: {e}")
            # Continue without validator - some security policies may not work

    def _run_server_in_thread(self, host: str, port: int):
        try:
            # ✅ Create event loop first
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._stop_event = asyncio.Event()

            # ✅ Run cleanup delay inside event loop (async sleep)
            # This allows the event loop to remain responsive
            async def startup_with_cleanup():
                logger.debug("Waiting for cleanup before starting server...")
                await asyncio.sleep(2)  # ✅ Non-blocking sleep in event loop
                await self._start_server_async(host, port)
                # ✅ Update heartbeat after successful startup
                self._last_heartbeat = time.time()

            # Run the async server start with cleanup delay
            logger.info(
                f"Starting OPC UA async server on {host}:{port} in event loop..."
            )
            self.loop.run_until_complete(startup_with_cleanup())

            # Keep server running until stop is requested
            logger.info("OPC UA server initialized, waiting for stop event...")
            self.loop.run_until_complete(self._stop_event.wait())
            logger.info("Stop event received, initiating graceful shutdown...")

        except asyncio.CancelledError:
            logger.debug("Server task was cancelled")
            self.is_running = False
        except Exception as e:
            # ✅ Capture and store server startup errors
            error_msg = f"Server thread error: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._server_error = error_msg
            self.is_running = False
        finally:
            # Cleanup
            logger.info("Server thread cleanup starting...")
            try:
                if self.loop and not self.loop.is_closed():
                    try:
                        if self.server:
                            logger.debug("Stopping OPC UA server...")
                            self.loop.run_until_complete(self.server.stop())

                        # Cancel all pending tasks
                        try:
                            pending = asyncio.all_tasks(self.loop)
                        except RuntimeError:
                            pending = []

                        for task in pending:
                            task.cancel()

                        # Close the loop
                        self.loop.close()
                        logger.info("Event loop closed successfully")
                    except Exception as e:
                        logger.warning(f"Cleanup error: {type(e).__name__}: {str(e)}")
                        try:
                            self.loop.close()
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Unexpected cleanup error: {type(e).__name__}: {str(e)}")
            finally:
                # Final state reset
                self.is_running = False
                self.server = None
                self.loop = None
                logger.info("Server thread cleanup complete")

    async def _start_server_async(self, host: str, port: int):
        """Async server startup."""
        try:
            # ✅ 在啟動伺服器時儲存當前的 event loop 引用
            # 這對於後續使用 run_coroutine_threadsafe 至關重要
            self.loop = asyncio.get_running_loop()
            logger.debug(f"Captured asyncio event loop: {self.loop}")

            config = self._get_server_config()

            # Create user manager based on authentication settings
            auth_config = self.settings.get("authentication", {})
            if UserManager is not None:
                user_manager = OPCUAUserManager(auth_config)
                self.server = Server(user_manager=user_manager)
            else:
                # Fallback for older opcua library
                self.server = Server()
                logger.warning("UserManager not available, authentication may not work properly")

            # Set endpoint
            endpoint = f"opc.tcp://{host}:{port}/"
            self.server.set_endpoint(endpoint)
            logger.info(f"OPC UA Endpoint: {endpoint}")

            # Set server name
            self.server.set_server_name(config["app_name"])
            logger.info(f"OPC UA Server Name: {config['app_name']}")

            # ✅ Set application URI BEFORE security setup (must match certificate)
            app_urn = f"urn:{config['app_name']}:server"
            self.server._application_uri = app_urn
            logger.info(f"OPC UA Application URI: {app_urn}")

            # ✅ Get and set security policies BEFORE init()
            # This is critical for proper endpoint configuration
            policies = self._get_security_policies()
            self.server.set_security_policy(policies)
            policy_names = [str(p).split(".")[-1] for p in policies]
            logger.info(f"OPC UA Security Policies: {policy_names}")

            # ✅ Load or generate server certificate if needed for secure endpoints
            if self._needs_certificate(policies):
                logger.info("Secure endpoints requested, setting up server certificate...")
                cert_path, key_path = self._generate_server_certificate(
                    config["app_name"], host, port
                )
                if cert_path and key_path and cert_path.exists() and key_path.exists():
                    await self.server.load_certificate(str(cert_path))
                    await self.server.load_private_key(str(key_path))
                    logger.info(f"Server certificate loaded: {cert_path}")
                    logger.info(f"Server private key loaded: {key_path}")
                else:
                    logger.warning(
                        "Could not load server certificate. "
                        "Secure endpoints (Sign/SignAndEncrypt) may not work. "
                        "Only NoSecurity endpoint will be available."
                    )
            else:
                logger.info("Only NoSecurity policy enabled, no certificate required")

            # Initialize server (this creates endpoints based on security settings)
            await self.server.init()

            # ✅ Install write interceptor to capture client writes
            await self._install_write_interceptor()

            # Set certificate validator for encrypted connections
            await self._setup_certificate_validator()
            logger.info("OPC UA Certificate validator configured")

            # Start server
            logger.debug(f"Starting server on {endpoint}...")
            await self.server.start()
            self.is_running = True

            # Log available endpoints
            try:
                endpoints = await self.server.get_endpoints()
                logger.info(f"Server started with {len(endpoints)} endpoint(s):")
                for ep in endpoints:
                    policy_name = str(ep.SecurityPolicyUri).split('#')[-1]
                    mode_name = str(ep.SecurityMode).split('.')[-1]
                    logger.info(f"  - Policy: {policy_name}, Mode: {mode_name}")
            except Exception as e:
                logger.debug(f"Could not list endpoints: {e}")

            logger.info("OPC UA Server started successfully")

        except OSError as e:
            # Handle port in use error specifically
            error_str = str(e).lower()
            if (
                "address already in use" in error_str
                or "only one usage" in error_str
                or "10048" in str(e)  # Windows SOCKET_ERROR 10048
            ):
                logger.error(
                    f"OPC UA Port {port} is already in use. "
                    f"Please stop other OPC UA server or change the port. "
                    f"Error: {e}"
                )
            else:
                logger.error(f"OSError when starting OPC server: {e}")

            self.is_running = False
            self.server = None
            raise
        except Exception as e:
            logger.error(f"Failed to start OPC UA server: {e}")
            self.is_running = False
            self.server = None
            raise

    async def _install_write_interceptor(self):
        """Install write interceptor to capture OPC UA client writes.

        Uses asyncua's official subscribe_server_callback API with CallbackType.PostWrite
        to detect when clients write to variable nodes, enabling bidirectional sync with Modbus.
        """
        try:
            if not self.server:
                logger.warning(
                    "Cannot install write interceptor: server not initialized"
                )
                return

            if CallbackType is None:
                logger.warning(
                    "CallbackType not available - write interception disabled"
                )
                return

            # Use official callback API for write interception
            # PostWrite callback is called after a write operation completes
            self.server.subscribe_server_callback(
                CallbackType.PostWrite, self._handle_post_write_callback
            )
            logger.info(
                "OPC UA write interceptor installed via subscribe_server_callback (PostWrite)"
            )

        except Exception as e:
            logger.warning(f"Failed to install write interceptor: {e}")
            # Non-fatal - server can still run without bidirectional write support

    async def _handle_post_write_callback(self, event, dispatcher):
        """Handle PostWrite callback from OPC UA server.

        This callback is triggered after a client successfully writes to a node.
        We extract the node ID and value, then forward to Modbus.

        Args:
            event: ServerItemCallback containing request/response params
            dispatcher: CallbackService dispatcher (unused)
        """
        try:
            # Check if this is an external client write (not internal server update)
            if hasattr(event, "is_external") and not event.is_external:
                # Skip internal writes to avoid feedback loops
                return

            # Get the write request parameters
            request_params = getattr(event, "request_params", None)
            response_params = getattr(event, "response_params", None)

            if not request_params:
                return

            # NodesToWrite is a list of WriteValue objects
            nodes_to_write = getattr(request_params, "NodesToWrite", None)
            if not nodes_to_write:
                return

            # Process each write
            for idx, write_value in enumerate(nodes_to_write):
                try:
                    # Check if write was successful
                    if response_params:
                        if hasattr(response_params, "__iter__"):
                            if idx < len(response_params):
                                status = response_params[idx]
                                if hasattr(status, "is_good") and not status.is_good():
                                    continue
                                elif hasattr(status, "value") and status.value != 0:
                                    continue

                    # Extract NodeId
                    node_id = write_value.NodeId
                    if not node_id:
                        continue

                    # Extract tag path from NodeId
                    tag_path = None
                    if hasattr(node_id, "Identifier") and isinstance(
                        node_id.Identifier, str
                    ):
                        tag_path = node_id.Identifier
                    else:
                        # Try to parse from string representation
                        node_id_str = str(node_id)
                        if ";s=" in node_id_str:
                            tag_path = node_id_str.split(";s=")[1]

                    if not tag_path:
                        continue

                    # Skip if this is a server-side update (check our tracking set)
                    if (
                        hasattr(self, "_server_updating_paths")
                        and tag_path in self._server_updating_paths
                    ):
                        continue

                    # Extract value from WriteValue
                    value = None
                    if hasattr(write_value, "Value") and write_value.Value is not None:
                        dv = write_value.Value
                        # DataValue structure
                        if hasattr(dv, "Value"):
                            val = dv.Value
                            # Handle Variant wrapper
                            if hasattr(val, "Value"):
                                value = val.Value
                            else:
                                value = val
                        else:
                            value = dv

                    if value is None:
                        continue

                    # Forward to Modbus write handler
                    logger.info(f"OPC UA client write detected: {tag_path} = {value}")
                    try:
                        success = self.write_tag_from_opcua(tag_path, value)
                        if success:
                            logger.debug(
                                f"OPC UA write forwarded to Modbus: {tag_path}"
                            )
                        else:
                            logger.warning(f"OPC UA write forward failed: {tag_path}")
                    except Exception as e:
                        logger.error(f"Error forwarding OPC UA write to Modbus: {e}")

                except Exception as e:
                    logger.debug(f"Error processing write value at index {idx}: {e}")

        except Exception as e:
            logger.debug(f"Error in PostWrite callback: {e}")

    def start_server(self, host: str = None, port: int = None):
        """Start OPC UA server in background thread.

        Args:
            host: Override host from settings
            port: Override port from settings

        Returns:
            True if server thread started successfully, False otherwise
        """
        # Early exit if already running
        if self.is_running:
            logger.warning("OPC UA server already running")
            return False

        try:
            # Get config
            config = self._get_server_config()
            host = host or config["host"]
            port = port or config["port"]

            logger.info(f"Preparing to start OPC UA server on {host}:{port}")

            # Stop and cleanup existing server completely
            # This is crucial before starting a new one
            if self.server is not None or self.is_running:
                logger.info("Cleaning up existing OPC UA server...")
                self.stop_server()
                # ✅ Cleanup delay moved to background thread to avoid UI freeze
                # No longer sleep here - let it happen in background

            # Create new event for this session
            self._stop_event = asyncio.Event()

            # Clear any existing tags/nodes
            # Always clear on fresh start to ensure clean state
            self._tag_nodes.clear()
            self._tag_info.clear()
            self._folder_nodes.clear()

            # ✅ Clear any previous errors
            self._server_error = None

            # Start in background thread
            self.server_thread = threading.Thread(
                target=self._run_server_in_thread, args=(host, port), daemon=True
            )
            self.server_thread.start()

            logger.info(f"OPC UA server thread started on {host}:{port}")
            return True

        except Exception as e:
            # ✅ Capture and store startup errors
            error_msg = (
                f"Failed to start OPC UA server thread: {type(e).__name__}: {str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            self._server_error = error_msg
            return False

    def reload_tags(self) -> bool:
        """Reload all tags - clears old nodes and creates new ones.

        DEPRECATED: Use reload_tags_async instead to avoid UI blocking.
        This method is kept for backward compatibility only.

        Use reload_tags_async when:
        - Called from UI (prevents 30 second freeze)
        - A new project is opened
        - Project tags have changed
        - User requests a refresh from OPC UA settings

        Returns:
            True on success, False on failure
        """
        logger.warning(
            "reload_tags() is deprecated and blocks UI. Use reload_tags_async() instead."
        )
        return self._reload_tags_blocking()

    def _reload_tags_blocking(self) -> bool:
        """Internal blocking version of reload_tags.

        Returns:
            True on success, False on failure
        """
        if not self.is_running or not self.server:
            logger.warning("OPC UA server not running, cannot reload tags")
            return False

        if not self.tree_widget:
            logger.warning("Tree widget not set")
            return False

        try:
            # Clear old nodes first - both from server and internal tracking
            logger.info("Reloading OPC UA tags - clearing old nodes...")

            # Clear internal tracking dictionaries first
            self._tag_nodes.clear()
            self._tag_info.clear()
            self._folder_nodes.clear()

            # Clear nodes from OPC UA server (async operation)
            # Use run_coroutine_threadsafe to wait for completion
            if self.loop and not self.loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self._clear_all_nodes_async(), self.loop
                    )
                    # Wait for completion with timeout (increased to allow full cleanup)
                    # WARNING: This blocks the calling thread for up to 30 seconds!
                    future.result(timeout=30)
                    logger.debug("OPC UA nodes cleared successfully")
                except Exception as e:
                    logger.warning(f"Error during node clearing: {e}")

            # Add delay to ensure server state is fully updated before creating new nodes
            # This gives the OPC UA server time to fully process node deletions
            # ✅ Safe to use time.sleep() here because this is already running in a background thread
            import time

            time.sleep(2.0)

            # Load all tags from scratch
            return self.load_all_tags()

        except Exception as e:
            logger.error(f"Error reloading tags: {e}", exc_info=True)
            return False

    def reload_tags_async(self, on_complete_callback=None):
        """Reload all tags asynchronously without blocking UI.

        Recommended way to reload tags - runs clearing and loading in background thread.

        Args:
            on_complete_callback: Optional callable that receives (success: bool) when done
                                 Example: lambda success: print(f"Reload {'succeeded' if success else 'failed'}")
        """
        if not self.is_running or not self.server:
            logger.warning("OPC UA server not running, cannot reload tags")
            if on_complete_callback:
                on_complete_callback(False)
            return

        if not self.tree_widget:
            logger.warning("Tree widget not set")
            if on_complete_callback:
                on_complete_callback(False)
            return

        # Run reload in background thread to avoid blocking UI
        def _reload_background():
            try:
                success = self._reload_tags_blocking()
                if on_complete_callback:
                    on_complete_callback(success)
            except Exception as e:
                logger.error(f"Error in background reload: {e}", exc_info=True)
                if on_complete_callback:
                    on_complete_callback(False)

        # Start reload in daemon thread
        reload_thread = threading.Thread(target=_reload_background, daemon=True)
        reload_thread.start()

    def stop_server(self):
        """Stop OPC UA server gracefully."""
        if not self.is_running and self.server is None:
            logger.debug("OPC UA server is not running, skipping stop")
            return

        try:
            logger.info("Stopping OPC UA server...")

            # Mark as not running immediately to prevent new operations
            self.is_running = False

            # Signal server to stop
            # Note: asyncio.Event.set() is synchronous, not a coroutine
            # Don't wrap it in asyncio.run_coroutine_threadsafe()
            if self._stop_event:
                try:
                    self._stop_event.set()
                    logger.debug("Stop event set successfully")
                except Exception as e:
                    logger.warning(f"Error setting stop event: {e}")

            # Wait for thread to finish (with timeout)
            if self.server_thread and self.server_thread.is_alive():
                logger.debug("Waiting for server thread to finish...")
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    logger.warning("Server thread did not finish within timeout")

            # Force cleanup references
            try:
                if self.server:
                    # Try to close server if not already closed
                    if hasattr(self.server, "_iter_management_nodes"):
                        # Server has been initialized, try graceful close
                        try:
                            # Close existing connections
                            if hasattr(self.server, "_server"):
                                self.server._server = None
                        except:
                            pass
                    self.server = None
            except Exception as e:
                logger.debug(f"Error cleaning server object: {e}")
                self.server = None

            # Clean up loop
            try:
                if self.loop:
                    self.loop = None
            except:
                pass

            self.server_thread = None

            # Clear node tracking dicts
            self._tag_nodes.clear()
            self._tag_info.clear()
            self._folder_nodes.clear()

            logger.info("OPC UA server stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping OPC UA server: {e}")
            # Force cleanup even on error
            self.is_running = False
            self.server = None
            self.server_thread = None
            self.loop = None
            self._tag_nodes.clear()
            self._tag_info.clear()
            self._folder_nodes.clear()

    def load_all_tags(self) -> bool:
        """Load all tags from tree widget to OPC UA server.

        Similar to how monitor extracts all tags using tree_root.
        Note: Does NOT clear old nodes - use reload_tags() for that.

        Returns:
            True on success, False on failure
        """
        if not self.is_running or not self.server:
            logger.error("OPC UA server not running, cannot load tags")
            return False

        if not self.tree_widget:
            logger.warning("Tree widget not set")
            return False

        try:
            # Use tree_root like monitor does - this walks ALL items including hidden tags
            tree_root = getattr(self.tree_widget, "root_node", None)
            if not tree_root:
                logger.warning("No root node in tree")
                return False

            tag_count = [0]  # Use list for mutable reference

            # Walk tree: Project -> Connectivity -> Channel -> Device -> [Group] -> Tag
            # Similar to monitor's _extract_all_tags method
            def walk_tree(item, parent_channel=None, parent_device=None):
                """Recursively walk tree collecting tags."""
                if not item:
                    return

                try:
                    item_type = item.data(0, Qt.ItemDataRole.UserRole)
                except Exception as e:
                    logger.debug(f"Could not get item type: {e}")
                    item_type = None

                # Update parent context
                if item_type == "Channel":
                    parent_channel = item
                elif item_type == "Device":
                    parent_device = item
                elif item_type == "Tag":
                    # Add tag to OPC UA
                    try:
                        if self._add_tag_to_opcua(item):
                            tag_count[0] += 1
                    except Exception as e:
                        logger.error(
                            f"Error adding tag '{item.text(0)}' to OPC UA: {e}"
                        )
                    # Don't recurse further for tags
                    return

                # Recurse to children (including Group children)
                for i in range(item.childCount()):
                    walk_tree(item.child(i), parent_channel, parent_device)

            # Start from root node (like monitor)
            walk_tree(tree_root)

            logger.info(f"Loaded {tag_count[0]} tags to OPC UA server")
            logger.info(f"  _tag_nodes count: {len(self._tag_nodes)}")
            logger.info(f"  _array_element_map count: {len(self._array_element_map)}")
            return True

        except Exception as e:
            logger.error(f"Error loading tags to OPC UA: {e}", exc_info=True)
            return False

    def _add_tag_to_opcua(self, tag_item) -> bool:
        """Add a single tag from tree item to OPC UA server.

        Extracts all tag properties from tree item and creates OPC UA node.
        Uses same extraction logic as monitor and modbus_mapping.

        Args:
            tag_item: QTreeWidgetItem for the tag

        Returns:
            True on success, False on failure
        """
        try:
            # Extract tag properties (same as monitor/modbus_monitor)
            tag_name = tag_item.text(0)
            tag_path = self._get_tag_path(tag_item)

            # Get parent info for full path
            description = tag_item.data(1, Qt.ItemDataRole.UserRole) or ""
            data_type = tag_item.data(2, Qt.ItemDataRole.UserRole) or "Float"
            access = tag_item.data(3, Qt.ItemDataRole.UserRole) or "Read Only"
            address = tag_item.data(4, Qt.ItemDataRole.UserRole) or ""
            scan_rate = tag_item.data(5, Qt.ItemDataRole.UserRole) or "1000"
            scaling = tag_item.data(6, Qt.ItemDataRole.UserRole) or {}
            metadata = tag_item.data(7, Qt.ItemDataRole.UserRole) or {}

            # Debug: log access value from tree
            logger.debug(
                f"Tag '{tag_name}' access from tree: '{access}' (type: {type(access)})"
            )

            # ✅ Extract device encoding info for Modbus write operations
            # Walk up tree to find parent Device and get its encoding
            device_encoding = self._get_device_encoding_from_tag(tag_item)

            # Extract array element count from address if present (e.g., "428672 [58]")
            array_element_count = None
            is_array = is_array_type(data_type, address, metadata)
            if is_array and address:
                import re

                match = re.search(r"\[(\d+)\]", str(address))
                if match:
                    array_element_count = int(match.group(1))
                    logger.debug(
                        f"Array tag '{tag_name}': element_count={array_element_count}"
                    )

            # Build tag info dict
            tag_info = {
                "path": tag_path,
                "name": tag_name,
                "description": description,
                "data_type": data_type,
                "access": access,
                "address": address,
                "scan_rate": scan_rate,
                "scaling": scaling,
                "metadata": metadata,
                "is_array": is_array,
                "array_element_count": array_element_count,
                # ✅ Include device encoding for Modbus write operations
                "byte_order": device_encoding.get("byte_order", 1),
                "word_order": device_encoding.get("word_order", 1),
                "dword_order": device_encoding.get("dword_order", 1),
                "bit_order": device_encoding.get("bit_order", 0),
                "treat_longs_as_decimals": device_encoding.get(
                    "treat_longs_as_decimals", False
                ),
            }

            # Get scaled data type if scaling is enabled
            scaled_type = get_scaled_datatype(scaling)
            if scaled_type:
                tag_info["opcua_datatype"] = scaled_type
            else:
                tag_info["opcua_datatype"] = data_type

            # Add node asynchronously
            if self.loop and not self.loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self._add_opcua_node_async(tag_info), self.loop
                )
                node = future.result(timeout=5)

                if node:
                    # Store node and info for later use
                    self._tag_nodes[tag_path] = (node, tag_info)
                    self._tag_info[tag_path] = tag_info

                    # ✅ NEW: For array tags, create mapping from element paths to base path
                    # ModbusDataBuffer stores array elements as "Path [0]", "Path [1]", etc.
                    # OPC UA stores the entire array as a single node at "Path"
                    # This mapping allows sync_data_to_opcua to correctly match paths
                    if is_array and array_element_count:
                        for idx in range(array_element_count):
                            element_path = f"{tag_path} [{idx}]"
                            self._array_element_map[element_path] = (tag_path, idx)
                        logger.debug(
                            f"Created array element mapping for '{tag_path}': {array_element_count} elements"
                        )

                    # Update data_buffer with tag info
                    if self.data_buffer:
                        access_code = "RW" if "Write" in access else "R"
                        self.data_buffer.set_tag_info(tag_path, data_type, access_code)

                    logger.info(
                        f"Added OPC UA node: {tag_path} (type={data_type}, access={access}, is_array={is_array}, opcua_level={get_access_level(access):04x})"
                    )
                    return True

            return False

        except Exception as e:
            logger.error(f"Error adding tag '{tag_item.text(0)}' to OPC UA: {e}")
            return False

    async def _add_opcua_node_async(self, tag_info: dict):
        """Async method to add OPC UA variable node.

        Args:
            tag_info: Tag information dict

        Returns:
            OPC UA variable node
        """
        try:
            from core.config import GROUP_SEPARATOR

            path_parts = tag_info["path"].split(GROUP_SEPARATOR)

            # Always get fresh Objects node reference each time (don't cache)
            # This ensures we always have a valid reference after clearing
            parent_node = self.server.get_objects_node()

            # Verify Objects node is valid before using it
            try:
                await parent_node.read_node_class()
            except Exception as e:
                logger.error(f"Objects node is invalid: {e}")
                return None

            # Create folder hierarchy: Channel -> Device -> [Group]
            # Channel level (first part)
            if len(path_parts) > 1:
                channel_path = path_parts[0]
                try:
                    channel_node = await self._get_or_create_folder(
                        channel_path, channel_path, parent_node
                    )
                    if channel_node:
                        parent_node = channel_node
                    else:
                        logger.error(
                            f"Failed to create/get Channel folder: {channel_path}"
                        )
                        return None
                except Exception as e:
                    logger.error(f"Error creating Channel folder {channel_path}: {e}")
                    return None

            # Device level (second part)
            if len(path_parts) > 2:
                device_path = GROUP_SEPARATOR.join(path_parts[:2])
                try:
                    device_node = await self._get_or_create_folder(
                        device_path, path_parts[1], parent_node
                    )
                    if device_node:
                        parent_node = device_node
                    else:
                        logger.error(
                            f"Failed to create/get Device folder: {device_path}"
                        )
                        return None
                except Exception as e:
                    logger.error(f"Error creating Device folder {device_path}: {e}")
                    return None

            # Group level (third part - if exists)
            if len(path_parts) > 3:
                group_path = GROUP_SEPARATOR.join(path_parts[:3])
                try:
                    group_node = await self._get_or_create_folder(
                        group_path, path_parts[2], parent_node
                    )
                    if group_node:
                        parent_node = group_node
                    else:
                        logger.error(f"Failed to create/get Group folder: {group_path}")
                        return None
                except Exception as e:
                    logger.error(f"Error creating Group folder {group_path}: {e}")
                    return None

            # Build node ID for the tag
            node_id = f"ns=2;s={tag_info['path']}"

            # Get OPC UA data type
            opcua_datatype = get_opcua_datatype(tag_info["opcua_datatype"])

            # Get default value
            is_array = tag_info.get("is_array", False)
            array_length = tag_info.get("array_element_count", 0)
            default_value = get_default_value(
                tag_info["opcua_datatype"], is_array, array_length
            )

            # Get access level first
            access_level = get_access_level(tag_info["access"])
            logger.debug(
                f"Creating node '{tag_info['path']}': access_str='{tag_info['access']}' -> level=0x{access_level:02x}"
            )

            # Check if node already exists and delete it
            try:
                existing = await self.server.get_node(ua.NodeId.from_string(node_id))
                # Delete existing node before recreating
                await existing.delete()
                logger.debug(f"Deleted existing node: {tag_info['path']}")
            except Exception:
                # Node doesn't exist, that's fine
                pass

            # Create variable node under parent (folder or objects)
            # Always wrap value in Variant to ensure correct OPC UA type
            variant_type = get_variant_type(tag_info["opcua_datatype"])
            variant = ua.Variant(default_value, variant_type)
            var_node = await parent_node.add_variable(
                ua.NodeId.from_string(node_id),
                tag_info["name"],
                variant,
                datatype=opcua_datatype,
            )

            # Set node properties
            if tag_info.get("description"):
                try:
                    desc = ua.LocalizedText(tag_info["description"])
                    await var_node.set_attribute(ua.AttributeIds.Description, desc)
                except Exception:
                    pass

            # Set access level - try multiple approaches for asyncua compatibility
            if access_level == 0x03:  # Read/Write
                try:
                    # Method 1: set_writable() (asyncua method)
                    await var_node.set_writable()
                    logger.debug(
                        f"Node '{tag_info['path']}' set as writable via set_writable()"
                    )
                except Exception as e1:
                    logger.debug(f"set_writable() failed: {e1}")
                    # Method 2: Set AccessLevel attribute directly
                    try:
                        await var_node.set_attribute(
                            ua.AttributeIds.AccessLevel, access_level
                        )
                        logger.debug(
                            f"AccessLevel set via set_attribute: 0x{access_level:02x}"
                        )
                    except Exception as e2:
                        logger.debug(f"set_attribute(AccessLevel) failed: {e2}")
            # For read-only nodes (0x01), no action needed - nodes are read-only by default

            # Set access level
            access_level = get_access_level(tag_info["access"])
            logger.debug(
                f"Setting AccessLevel for '{tag_info['path']}': access_str='{tag_info['access']}' -> level=0x{access_level:02x}"
            )
            try:
                await var_node.set_attribute(ua.AttributeIds.AccessLevel, access_level)
            except Exception as e:
                logger.debug(f"Error setting AccessLevel: {e}")
                pass

            # Set access level
            access_level = get_access_level(tag_info["access"])
            try:
                from opcua import ua as ua_module

                await var_node.set_attribute(
                    ua_module.AttributeIds.AccessLevel, access_level
                )
            except Exception:
                pass

            # Set array type if needed
            if tag_info.get("is_array"):
                try:
                    await var_node.set_attribute(ua.AttributeIds.ValueRank, 1)
                    # Set ArrayDimensions attribute (required for arrays in OPC UA)
                    array_length = tag_info.get("array_element_count", 0)
                    if array_length > 0:
                        await var_node.set_attribute(
                            ua.AttributeIds.ArrayDimensions, [array_length]
                        )
                        logger.debug(
                            f"Array tag '{tag_info['path']}': ArrayDimensions=[{array_length}], ValueRank=1"
                        )
                    else:
                        logger.debug(
                            f"Array tag '{tag_info['path']}': ValueRank=1 (unknown length)"
                        )
                except Exception as e:
                    logger.debug(f"Error setting array attributes: {e}")
                    pass

            return var_node

        except Exception as e:
            logger.error(f"Error creating OPC UA node for '{tag_info['path']}': {e}")
            return None

    def _clear_all_nodes(self):
        """Clear all variable nodes from OPC UA server."""
        if not self.is_running or not self.server:
            return

        try:
            if self.loop and not self.loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self._clear_all_nodes_async(), self.loop
                )
                future.result(timeout=10)
        except Exception as e:
            logger.warning(f"Error clearing OPC UA nodes: {e}")

    async def _clear_all_nodes_async(self):
        """Async method to clear all variable and folder nodes in namespace 2.

        ✅ Optimized: Batch deletion instead of individual deletions
        - Collects all namespace 2 nodes first
        - Deletes in a single batch operation for maximum efficiency
        - Recursive deletion handles all child nodes automatically
        """
        try:
            objects = self.server.get_objects_node()

            try:
                children = await objects.get_children()
            except Exception:
                logger.warning("Failed to get children from Objects root")
                # Still clear tracking
                self._tag_nodes.clear()
                self._tag_info.clear()
                self._folder_nodes.clear()
                return

            # ✅ Collect all namespace 2 nodes for batch deletion
            nodes_to_delete = []

            for child in children:
                try:
                    node_id = child.nodeid
                    if (
                        hasattr(node_id, "NamespaceIndex")
                        and node_id.NamespaceIndex == 2
                    ):
                        try:
                            node_class = await child.read_node_class()
                            # Collect both Variable and Organizer (folder) nodes
                            if node_class in (
                                ua.NodeClass.Variable,
                                ua.NodeClass.Object,
                            ):
                                nodes_to_delete.append(child)
                        except Exception:
                            pass
                except Exception:
                    continue

            # ✅ Batch delete all collected nodes at once
            # This is much more efficient than parallel deletion loops
            deleted = 0
            if nodes_to_delete:
                try:
                    # Delete all nodes in a single operation
                    await self.server.delete_nodes(nodes_to_delete, recursive=True)
                    deleted = len(nodes_to_delete)
                    logger.info(f"Cleared {deleted} OPC UA nodes in batch operation")
                except Exception as e:
                    logger.warning(
                        f"Batch deletion failed: {e}, falling back to individual deletion"
                    )
                    # Fallback: delete individually if batch fails
                    for child in nodes_to_delete:
                        try:
                            await self.server.delete_nodes([child], recursive=True)
                            deleted += 1
                        except Exception as child_err:
                            logger.debug(f"Failed to delete node: {child_err}")
                    logger.info(
                        f"Cleared {deleted}/{len(nodes_to_delete)} OPC UA nodes (fallback)"
                    )

        except Exception as e:
            logger.error(f"Error in _clear_all_nodes_async: {e}")
        finally:
            # ALWAYS clear internal tracking, even on error
            # This ensures we don't have stale references
            self._tag_nodes.clear()
            self._tag_info.clear()
            self._folder_nodes.clear()
            self._array_element_map.clear()

    def _get_tag_path(self, tag_item) -> str:
        """Get full tag path from tree item (e.g., "Channel1.Device1.Data.Tag1").

        Exactly like RuntimeMonitor._get_tag_tree_path
        """
        path_parts = []
        current = tag_item

        # Get tree root to know when to stop
        tree_root = getattr(self.tree_widget, "root_node", None)

        while current and current != tree_root:
            try:
                text = current.text(0)
                if text and text != "Connectivity":
                    path_parts.insert(0, text)
            except Exception:
                pass
            try:
                current = current.parent()
            except Exception:
                break

        from core.config import GROUP_SEPARATOR

        return (
            GROUP_SEPARATOR.join(path_parts)
            if path_parts
            else tag_item.text(0) or "Unknown"
        )

    def _get_device_encoding_from_tag(self, tag_item) -> dict:
        """Extract device encoding configuration from tag's parent Device node.

        Walks up the tree to find the parent Device and extracts its encoding settings.
        This ensures OPC UA writes use the same encoding as Modbus reads.

        Args:
            tag_item: QTreeWidgetItem for the tag

        Returns:
            Dict with encoding settings: byte_order, word_order, dword_order, bit_order, treat_longs_as_decimals
        """
        encoding = MODBUS_DEFAULT_ENCODING.copy()
        encoding["treat_longs_as_decimals"] = False  # Ensure boolean for OPC UA

        try:
            # Walk up the tree to find parent Device
            current = tag_item
            tree_root = getattr(self.tree_widget, "root_node", None)

            while current and current != tree_root:
                try:
                    item_type = current.data(0, Qt.ItemDataRole.UserRole)
                    if item_type == "Device":
                        # Found the Device node - extract encoding from column 5
                        device_encoding = current.data(5, Qt.ItemDataRole.UserRole)
                        if isinstance(device_encoding, dict):
                            encoding["byte_order"] = device_encoding.get(
                                "byte_order", 1
                            )
                            encoding["word_order"] = device_encoding.get(
                                "word_order", 1
                            )
                            encoding["dword_order"] = device_encoding.get(
                                "dword_order", 1
                            )
                            encoding["bit_order"] = device_encoding.get("bit_order", 0)
                            encoding["treat_longs_as_decimals"] = device_encoding.get(
                                "treat_longs_as_decimals", False
                            )
                            logger.debug(
                                f"Found device encoding for tag: byte_order={encoding['byte_order']}, "
                                f"word_order={encoding['word_order']}"
                            )
                        break
                except Exception as e:
                    logger.debug(f"Error reading device encoding: {e}")

                try:
                    current = current.parent()
                except Exception:
                    break

        except Exception as e:
            logger.debug(f"Error getting device encoding: {e}")

        return encoding

    def _get_hierarchy_path(self, tag_item) -> dict:
        """Get full hierarchy info from tag item.

        Returns:
            Dict with 'channel', 'device', 'group' paths
        """
        hierarchy = {"channel": None, "device": None, "group": None}
        current = tag_item

        # Get tree root to know when to stop
        tree_root = getattr(self.tree_widget, "root_node", None)

        try:
            item_type = tag_item.data(0, Qt.ItemDataRole.UserRole)
        except Exception:
            item_type = None

        # Walk up the tree to find parent levels
        while current and current != tree_root:
            try:
                current_type = current.data(0, Qt.ItemDataRole.UserRole)
                current_text = current.text(0)

                if current_type == "Channel" and not hierarchy["channel"]:
                    hierarchy["channel"] = current_text
                elif current_type == "Device" and not hierarchy["device"]:
                    hierarchy["device"] = current_text
                elif current_type == "Group" and not hierarchy["group"]:
                    hierarchy["group"] = current_text
            except Exception:
                pass

            try:
                current = current.parent()
            except Exception:
                break

        return hierarchy

    async def _get_or_create_folder(
        self, folder_path: str, folder_name: str, parent_node=None
    ) -> any:
        """Get or create a folder node for hierarchy structure.

        Includes strict cache validation to ensure cached nodes are still valid.

        Args:
            folder_path: Full path to folder (e.g., "Channel1" or "Channel1.Device1")
            folder_name: Display name of folder
            parent_node: Parent node to add folder to (None = objects root)

        Returns:
            OPC UA folder node or None on failure
        """
        # Check internal cache first
        if folder_path in self._folder_nodes:
            cached_node = self._folder_nodes[folder_path]
            try:
                # Verify cached node still exists on server by reading its properties
                node_class = await cached_node.read_node_class()

                # Verify parent is also valid if provided
                if parent_node:
                    try:
                        await parent_node.read_node_class()
                    except Exception as parent_err:
                        logger.warning(
                            f"Parent node is invalid, will recreate folder: {folder_path} ({parent_err})"
                        )
                        # Parent is invalid, invalidate cache and recreate
                        del self._folder_nodes[folder_path]
                        return await self._get_or_create_folder(
                            folder_path, folder_name, parent_node
                        )

                # All checks passed, return cached node
                logger.debug(f"Using cached folder node: {folder_path}")
                return cached_node

            except Exception as cache_err:
                # Cached node is stale or deleted from server, remove from cache
                logger.debug(
                    f"Cached node is stale for {folder_path}, will recreate ({cache_err})"
                )
                del self._folder_nodes[folder_path]

        try:
            if parent_node is None:
                parent_node = self.server.get_objects_node()

            # Verify parent_node is valid before using it
            try:
                await parent_node.read_node_class()
            except Exception as e:
                logger.error(f"Parent node invalid for creating {folder_path}: {e}")
                return None

            # Build node ID
            node_id = f"ns=2;s={folder_path}"

            # Check if node already exists on server
            try:
                existing = await self.server.get_node(ua.NodeId.from_string(node_id))
                # Node exists, verify it's still valid
                try:
                    node_class = await existing.read_node_class()
                    # Node is valid, cache and return it
                    self._folder_nodes[folder_path] = existing
                    logger.debug(f"Reusing existing OPC UA folder: {folder_path}")
                    return existing
                except Exception as node_err:
                    # Node exists but is invalid, delete and recreate
                    logger.debug(
                        f"Existing node is invalid, deleting: {folder_path} ({node_err})"
                    )
                    try:
                        await parent_node.delete(existing, recursive=True)
                        logger.debug(f"Deleted invalid node: {folder_path}")
                    except Exception as del_err:
                        logger.warning(
                            f"Could not delete invalid node {folder_path}: {del_err}"
                        )
            except Exception:
                # Node doesn't exist, that's fine, we'll create it below
                pass

            # Create folder as an Organizer object under the specified parent
            try:
                folder_node = await parent_node.add_folder(
                    ua.NodeId.from_string(node_id), folder_name
                )

                self._folder_nodes[folder_path] = folder_node
                logger.debug(f"Created OPC UA folder: {folder_path}")
                return folder_node
            except Exception as e:
                logger.error(f"Error creating folder {folder_path}: {e}")
                return None

        except Exception as e:
            logger.error(f"Error in _get_or_create_folder for {folder_path}: {e}")
            return None

    def sync_values(self):
        """Synchronize tag values from data_buffer to OPC UA.

        Called periodically (e.g., every 200ms) to push latest values.
        ✅ Optimized to batch write operations for better performance with large tag counts.
        ✅ Single tag errors don't affect other tags - each has isolated error handling.
        ✅ Robust error handling: failed tags are logged but don't interrupt sync process.
        """
        if not self.is_running or not self.data_buffer or not self._tag_nodes:
            return

        if not self.loop or self.loop.is_closed():
            return

        try:
            # Collect all pending updates
            update_tasks = []

            for tag_path, (node, tag_info) in self._tag_nodes.items():
                try:
                    # ✅ Get value from buffer - each tag has isolated error handling
                    value = self.data_buffer.get_tag_value(tag_path)

                    if value is not None:
                        # Create update task - type conversion is handled in _update_node_value_async
                        update_tasks.append(
                            self._update_node_value_async(node, value, tag_info)
                        )
                except Exception as e:
                    # ✅ Error getting tag value from buffer - skip this tag, continue with others
                    logger.debug(
                        f"Error preparing tag '{tag_path}' for sync: {type(e).__name__}: {e}. Skipping this tag."
                    )
                    continue

            # ✅ Batch send all updates at once
            # This prevents flooding the async event loop with individual requests
            if update_tasks:
                try:
                    # ✅ Send batched tasks to the event loop - batch write errors also don't break the sync
                    asyncio.run_coroutine_threadsafe(
                        asyncio.gather(*update_tasks, return_exceptions=True),
                        self.loop,
                    )
                except Exception as e:
                    logger.debug(
                        f"Error sending batched updates to event loop: {type(e).__name__}: {e}"
                    )
        except Exception as e:
            logger.error(f"Unexpected error in sync_values: {type(e).__name__}: {e}")

    async def sync_values_batch_async(self):
        """✅ Alternative: Batch write all values in a single OPC UA operation.

        This is more efficient than individual write operations for very large tag counts (1000+).
        Use this instead of sync_values() for better performance with massive datasets.

        ✅ Enhanced with safety checks for data type conversion and None values.
        """
        if (
            not self.is_running
            or not self.data_buffer
            or not self._tag_nodes
            or not self.server
        ):
            return

        try:
            nodes_to_write = []
            values_to_write = []

            for tag_path, (node, tag_info) in self._tag_nodes.items():
                try:
                    value = self.data_buffer.get_tag_value(tag_path)

                    # ✅ Skip None values
                    if value is None:
                        continue

                    # ✅ Safety check: try to convert to correct data type
                    opcua_datatype = tag_info.get("opcua_datatype", "")
                    try:
                        variant_type = get_variant_type(opcua_datatype)
                        
                        # ✅ Convert value to match the expected OPC UA type
                        converted_value = value
                        try:
                            if variant_type == ua.VariantType.Double:
                                converted_value = float(value) if not isinstance(value, (list, tuple)) else [float(v) for v in value]
                            elif variant_type == ua.VariantType.Float:
                                converted_value = float(value) if not isinstance(value, (list, tuple)) else [float(v) for v in value]
                            elif variant_type in (ua.VariantType.Int16, ua.VariantType.Int32, ua.VariantType.Int64):
                                converted_value = int(value) if not isinstance(value, (list, tuple)) else [int(v) for v in value]
                            elif variant_type in (ua.VariantType.UInt16, ua.VariantType.UInt32, ua.VariantType.UInt64, ua.VariantType.Byte):
                                converted_value = int(value) if not isinstance(value, (list, tuple)) else [int(v) for v in value]
                            elif variant_type == ua.VariantType.Boolean:
                                converted_value = bool(value) if not isinstance(value, (list, tuple)) else [bool(v) for v in value]
                        except (ValueError, TypeError):
                            converted_value = value
                        
                        variant = ua.Variant(converted_value, variant_type)
                    except (ValueError, TypeError) as convert_err:
                        logger.debug(
                            f"Type conversion failed for '{tag_path}': {convert_err}"
                        )
                        # Try without explicit type
                        try:
                            variant = ua.Variant(value)
                        except Exception as fallback_err:
                            logger.debug(
                                f"Failed to create variant for '{tag_path}': {fallback_err}"
                            )
                            continue

                    nodes_to_write.append(node)
                    # Create DataValue with timestamp and status (pass all in constructor for asyncua compatibility)
                    dv = ua.DataValue(
                        Value=variant,
                        SourceTimestamp=datetime.utcnow(),
                    )
                    values_to_write.append(dv)

                except Exception as e:
                    logger.debug(f"Error preparing batch write for '{tag_path}': {e}")

            # ✅ Write all values in a single batch operation
            if nodes_to_write and values_to_write:
                try:
                    # Gather all write operations with timeout protection
                    await asyncio.gather(
                        *[
                            asyncio.wait_for(node.write_value(val), timeout=1.0)
                            for node, val in zip(nodes_to_write, values_to_write)
                        ],
                        return_exceptions=True,
                    )
                except Exception as e:
                    logger.debug(f"Batch write failed: {e}")

        except Exception as e:
            logger.error(f"Error in sync_values_batch_async: {e}")

    async def _update_node_value_async(self, node, value, tag_info):
        """Async method to update node value with status and timestamp.

        ✅ Enhanced with data type safety checks and proper type conversion for scaled values

        Args:
            node: OPC UA variable node
            value: Value to write
            tag_info: Tag information dict
        """
        try:
            # ✅ Safety check: ensure value is not None
            if value is None:
                logger.debug(f"Skipping None value for node")
                return

            is_array = tag_info.get("is_array", False)
            opcua_datatype = tag_info.get("opcua_datatype", "")

            # ✅ Safety check: ensure datatype is valid
            try:
                variant_type = get_variant_type(opcua_datatype)
            except Exception as type_err:
                logger.warning(
                    f"Invalid data type '{opcua_datatype}': {type_err}, using Double"
                )
                variant_type = ua.VariantType.Double

            # ✅ Convert value to match the expected OPC UA type
            # This is important when scaling converts int to float
            converted_value = value
            try:
                if variant_type == ua.VariantType.Double:
                    converted_value = float(value) if not isinstance(value, (list, tuple)) else [float(v) for v in value]
                elif variant_type == ua.VariantType.Float:
                    converted_value = float(value) if not isinstance(value, (list, tuple)) else [float(v) for v in value]
                elif variant_type in (ua.VariantType.Int16, ua.VariantType.Int32, ua.VariantType.Int64):
                    converted_value = int(value) if not isinstance(value, (list, tuple)) else [int(v) for v in value]
                elif variant_type in (ua.VariantType.UInt16, ua.VariantType.UInt32, ua.VariantType.UInt64, ua.VariantType.Byte):
                    converted_value = int(value) if not isinstance(value, (list, tuple)) else [int(v) for v in value]
                elif variant_type == ua.VariantType.Boolean:
                    converted_value = bool(value) if not isinstance(value, (list, tuple)) else [bool(v) for v in value]
            except (ValueError, TypeError) as conv_err:
                logger.debug(f"Value conversion warning: {conv_err}, using original value")
                converted_value = value

            # ✅ Try to convert/coerce the value to the correct type
            try:
                # Create variant with proper type
                variant = ua.Variant(converted_value, variant_type)
            except (ValueError, TypeError) as convert_err:
                logger.debug(
                    f"Type conversion failed for value {converted_value} to {opcua_datatype}: {convert_err}"
                )
                # Try to create variant without explicit type (let asyncua handle it)
                try:
                    variant = ua.Variant(converted_value)
                except Exception as fallback_err:
                    logger.debug(f"Failed to create variant: {fallback_err}")
                    return

            # Create DataValue with timestamp and status information (pass all in constructor for asyncua compatibility)
            dv = ua.DataValue(
                Value=variant,
                SourceTimestamp=datetime.utcnow(),
            )

            # ✅ Write value with timeout protection
            try:
                await asyncio.wait_for(node.write_value(dv), timeout=1.0)
            except asyncio.TimeoutError:
                logger.debug(f"Timeout writing value to node")

        except Exception as e:
            logger.debug(f"Error writing value to node: {e}")

    def write_tag_from_opcua(self, tag_path: str, value: Any) -> bool:
        """Handle write from OPC UA client to tag.

        Called when OPC UA client writes to a node.
        Updates data_buffer and triggers Modbus write through RuntimeMonitor.

        ✅ ENHANCED: Now implements complete bidirectional sync
        - Updates ModbusDataBuffer with new value
        - Triggers actual Modbus write via WriteQueueManager

        Args:
            tag_path: Full tag path (e.g., "Channel1.Device1.Data.TagName")
            value: Value to write

        Returns:
            True on success, False on failure
        """
        try:
            # 1. Update data_buffer first (for immediate feedback)
            if self.data_buffer:
                self.data_buffer.write_tag_value(tag_path, value)
                logger.debug(f"OPC UA write to buffer: {tag_path} = {value}")

            # 2. Check if tag is writable
            tag_info = self._tag_info.get(tag_path)
            if not tag_info:
                logger.warning(
                    f"OPC UA write failed: tag '{tag_path}' not found in tag_info"
                )
                return False

            access = tag_info.get("access", "Read Only")
            if "Write" not in access and "R/W" not in access and "RW" not in access:
                logger.warning(
                    f"OPC UA write rejected: tag '{tag_path}' is read-only (access={access})"
                )
                return False

            # 3. Trigger Modbus write through callback (routes to app.py/Monitor)
            # This allows app.py to handle proper Modbus encoding using existing Monitor logic
            if self._write_request_callback:
                try:
                    success = self._write_request_callback(tag_path, value, tag_info)
                    if success:
                        logger.info(
                            f"OPC UA write routed via callback: {tag_path} = {value}"
                        )
                    else:
                        logger.warning(
                            f"OPC UA write callback returned False: {tag_path}"
                        )
                    return success
                except Exception as e:
                    logger.error(f"OPC UA write callback error: {e}")
                    return False
            else:
                # Fallback: try legacy direct enqueue if no callback registered
                if not self.runtime_monitor:
                    logger.warning(
                        f"OPC UA write: no callback and no RuntimeMonitor available"
                    )
                    return True  # Buffer updated, but no actual Modbus write

                try:
                    success = self._enqueue_modbus_write(tag_path, value, tag_info)
                    if success:
                        logger.info(
                            f"OPC UA write queued for Modbus (legacy): {tag_path} = {value}"
                        )
                    else:
                        logger.warning(
                            f"OPC UA write: failed to queue Modbus write for {tag_path}"
                        )
                    return success
                except Exception as e:
                    logger.error(f"OPC UA write: error queueing Modbus write: {e}")
                    return False

        except Exception as e:
            logger.error(f"Error handling OPC UA write: {e}")
            return False

    # NOTE: _enqueue_modbus_write method was removed in architecture refactoring.
    # OPC UA writes are now routed through app.py via _write_request_callback,
    # which uses the Monitor's proven encoding logic for proper Modbus writes.

    async def update_opc_node_values(self, data_dict: dict):
        """Update OPC UA node values from a data dictionary.

        Called from app.py via asyncio.run_coroutine_threadsafe to safely update nodes
        across thread boundaries.

        ✅ ENHANCED: Now handles array element paths correctly
        - Buffer stores array elements as "Path [0]", "Path [1]", etc.
        - OPC UA stores the entire array as a single node at "Path"
        - This method aggregates array elements and updates the array node

        Args:
            data_dict: Dictionary mapping tag_path to values {path: value}
        """
        # Enhanced early return logging
        if not self.is_running:
            logger.debug("[OPC_NODE_UPDATE] 跳過: server not running")
            return
        if not self.server:
            logger.debug("[OPC_NODE_UPDATE] 跳過: server is None")
            return
        if not self._tag_nodes:
            logger.warning("[OPC_NODE_UPDATE] 跳過: _tag_nodes 是空的（標籤還未載入）")
            return

        try:
            matched_count = 0
            array_skipped = 0

            # ✅ NEW: Aggregate array element values before updating
            # Key: base_path, Value: {index: value}
            array_values_pending = {}

            for tag_path, value in data_dict.items():
                try:
                    # ✅ Check if this is an array element path
                    if tag_path in self._array_element_map:
                        base_path, idx = self._array_element_map[tag_path]
                        if base_path not in array_values_pending:
                            array_values_pending[base_path] = {}
                        array_values_pending[base_path][idx] = value
                        array_skipped += 1
                        continue

                    # 查找對應的節點 (scalar tags)
                    if tag_path not in self._tag_nodes:
                        continue

                    node, tag_info = self._tag_nodes[tag_path]
                    matched_count += 1

                    if value is None:
                        continue

                    # 準備數據類型和變量 (pass all in constructor for asyncua compatibility)
                    variant_type = get_variant_type(tag_info.get("opcua_datatype", ""))
                    
                    # ✅ Convert value to match the expected OPC UA type
                    converted_value = value
                    try:
                        if variant_type == ua.VariantType.Double:
                            converted_value = float(value)
                        elif variant_type == ua.VariantType.Float:
                            converted_value = float(value)
                        elif variant_type in (ua.VariantType.Int16, ua.VariantType.Int32, ua.VariantType.Int64):
                            converted_value = int(value)
                        elif variant_type in (ua.VariantType.UInt16, ua.VariantType.UInt32, ua.VariantType.UInt64, ua.VariantType.Byte):
                            converted_value = int(value)
                        elif variant_type == ua.VariantType.Boolean:
                            converted_value = bool(value)
                    except (ValueError, TypeError):
                        converted_value = value
                    
                    variant = ua.Variant(converted_value, variant_type)
                    dv = ua.DataValue(
                        Value=variant,
                        SourceTimestamp=datetime.utcnow(),
                    )

                    # 更新節點值
                    await node.write_value(dv)

                except Exception as e:
                    logger.debug(f"更新節點 '{tag_path}' 失敗: {e}")
                    continue

            # ✅ NEW: Update array nodes with aggregated values
            array_matched = 0
            for base_path, indexed_values in array_values_pending.items():
                try:
                    if base_path not in self._tag_nodes:
                        continue

                    node, tag_info = self._tag_nodes[base_path]
                    array_count = tag_info.get("array_element_count", 0)

                    if not array_count:
                        # Try to infer from collected values
                        array_count = (
                            max(indexed_values.keys()) + 1 if indexed_values else 0
                        )

                    if array_count <= 0:
                        continue

                    # Build array value from indexed values
                    # Fill missing indices with 0 or None
                    array_value = []
                    for idx in range(array_count):
                        if idx in indexed_values:
                            array_value.append(indexed_values[idx])
                        else:
                            # Use default value based on data type
                            array_value.append(0)

                    # Write array value to OPC UA node (pass all in constructor for asyncua compatibility)
                    variant_type = get_variant_type(tag_info.get("opcua_datatype", ""))
                    
                    # ✅ Convert array values to match the expected OPC UA type
                    converted_array = array_value
                    try:
                        if variant_type == ua.VariantType.Double:
                            converted_array = [float(v) for v in array_value]
                        elif variant_type == ua.VariantType.Float:
                            converted_array = [float(v) for v in array_value]
                        elif variant_type in (ua.VariantType.Int16, ua.VariantType.Int32, ua.VariantType.Int64):
                            converted_array = [int(v) for v in array_value]
                        elif variant_type in (ua.VariantType.UInt16, ua.VariantType.UInt32, ua.VariantType.UInt64, ua.VariantType.Byte):
                            converted_array = [int(v) for v in array_value]
                        elif variant_type == ua.VariantType.Boolean:
                            converted_array = [bool(v) for v in array_value]
                    except (ValueError, TypeError):
                        converted_array = array_value
                    
                    variant = ua.Variant(converted_array, variant_type)
                    dv = ua.DataValue(
                        Value=variant,
                        SourceTimestamp=datetime.utcnow(),
                    )

                    await node.write_value(dv)
                    array_matched += 1

                except Exception as e:
                    logger.debug(f"更新陣列節點 '{base_path}' 失敗: {e}")
                    continue

            logger.info(
                    f"[OPC_NODE_UPDATE] 成功匹配 標量={matched_count}, 陣列={array_matched} (元素={array_skipped})"
                )
        except Exception as e:
            logger.error(f"批量更新 OPC UA 節點失敗: {e}")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.stop_server()
        except Exception:
            pass


# For backwards compatibility
OPCServer = OPCUAServer
