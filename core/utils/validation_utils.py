"""
Unified data validation utilities.

This module consolidates data validation and type checking logic
used across different parts of the application.
"""

from typing import Any, Union, Optional
import re


def validate_ip_address(ip: str) -> bool:
    """
    Validate IPv4 address format.

    Args:
        ip: IP address string to validate

    Returns:
        True if valid IPv4 address, False otherwise
    """
    if not ip or not isinstance(ip, str):
        return False

    # Basic IPv4 regex pattern
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(pattern, ip.strip())

    if not match:
        return False

    # Check each octet is 0-255
    for octet in match.groups():
        if not 0 <= int(octet) <= 255:
            return False

    return True


def validate_port(port: Union[str, int]) -> bool:
    """
    Validate port number.

    Args:
        port: Port number to validate (string or int)

    Returns:
        True if valid port (1-65535), False otherwise
    """
    try:
        port_num = int(port)
        return 1 <= port_num <= 65535
    except (ValueError, TypeError):
        return False


def normalize_numeric_value(value: Any, default: Union[int, float] = 0) -> Union[int, float]:
    """
    Normalize a value to a number, with fallback to default.

    Args:
        value: Value to normalize
        default: Default value if conversion fails

    Returns:
        Normalized numeric value
    """
    try:
        # Try int first, then float
        if isinstance(value, str) and '.' in value:
            return float(value)
        else:
            return int(value)
    except (ValueError, TypeError):
        return default


def safe_string_conversion(value: Any, default: str = "") -> str:
    """
    Safely convert value to string.

    Args:
        value: Value to convert
        default: Default string if conversion fails

    Returns:
        String representation of value
    """
    try:
        if value is None:
            return default
        return str(value)
    except Exception:
        return default


def validate_boolean_string(value: str) -> Optional[bool]:
    """
    Convert common string representations to boolean.

    Args:
        value: String value to convert

    Returns:
        True, False, or None if not recognized
    """
    if not isinstance(value, str):
        return None

    val_lower = value.strip().lower()
    if val_lower in ('1', 'true', 'yes', 'on', 'enable', 'enabled'):
        return True
    elif val_lower in ('0', 'false', 'no', 'off', 'disable', 'disabled'):
        return False

    return None


def clamp_value(value: Union[int, float], min_val: Union[int, float],
                max_val: Union[int, float]) -> Union[int, float]:
    """
    Clamp a value between min and max bounds.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def is_valid_modbus_address(address: Union[str, int]) -> bool:
    """
    Validate Modbus address range (0-65535).

    Args:
        address: Address to validate

    Returns:
        True if valid Modbus address
    """
    try:
        addr = int(address)
        return 0 <= addr <= 65535
    except (ValueError, TypeError):
        return False


def is_valid_modbus_function_code(fc: Union[str, int]) -> bool:
    """
    Validate Modbus function code.

    Args:
        fc: Function code to validate

    Returns:
        True if valid Modbus function code
    """
    try:
        code = int(fc)
        # Common Modbus function codes
        valid_codes = {1, 2, 3, 4, 5, 6, 15, 16, 23}
        return code in valid_codes
    except (ValueError, TypeError):
        return False