"""
Network utilities for IP detection and adapter management.

This module consolidates IP detection logic used across the application
to avoid code duplication.
"""

import socket
from typing import Optional, List, Tuple, Dict, Any

try:
    import psutil
except ImportError:
    psutil = None


def detect_outbound_ip() -> str:
    """
    Detect the local IP that would be used for outbound connections.

    Creates a dummy connection to 8.8.8.8:80 and reads the source IP.
    Falls back to 127.0.0.1 if detection fails.

    Returns:
        Detected IP address as string
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_network_adapters() -> List[Tuple[str, str]]:
    """
    Get list of available network adapters with their IPv4 addresses.

    Returns:
        List of tuples (display_name, ip_address)
        Display name format: "interface_name (ip_address)"
    """
    adapters = []

    if not psutil:
        # Fallback: just return localhost
        adapters.append(("Default (127.0.0.1)", "127.0.0.1"))
        return adapters

    try:
        infos = psutil.net_if_addrs()
        for ifname, addrs in infos.items():
            for a in addrs:
                try:
                    fam = getattr(a, 'family', None)
                    if fam and (getattr(fam, 'name', '').endswith('AF_INET') or fam == 2):
                        ip = a.address
                        if ip and not ip.startswith('127.'):
                            display = f"{ifname} ({ip})"
                            adapters.append((display, ip))
                except Exception:
                    try:
                        ip = getattr(a, 'address', None) or str(a)
                        if ip and ':' not in ip and not ip.startswith('127.'):
                            display = f"{ifname} - {ip}"
                            adapters.append((display, ip))
                    except Exception:
                        pass

        # If no adapters found, add auto-detected IP
        if not adapters:
            detected = detect_outbound_ip()
            adapters.append((f"Auto ({detected})", detected))

    except Exception:
        # Fallback on error
        detected = detect_outbound_ip()
        adapters.append((f"Auto ({detected})", detected))

    return adapters


def find_adapter_for_ip(target_ip: str) -> Optional[str]:
    """
    Find the network adapter name that has the given IP address.

    Args:
        target_ip: IP address to search for

    Returns:
        Adapter name if found, None otherwise
    """
    if not psutil:
        return None

    try:
        for ifname, addrs in psutil.net_if_addrs().items():
            for addr_info in addrs:
                try:
                    family = getattr(addr_info, 'family', None)
                    address = getattr(addr_info, 'address', None)
                    if family == socket.AF_INET and address == str(target_ip):
                        return ifname
                except Exception:
                    continue
        return None
    except Exception:
        return None


def format_adapter_display(adapter_name: str, ip_address: str) -> str:
    """
    Format adapter display string consistently.

    Args:
        adapter_name: Network adapter name
        ip_address: IP address

    Returns:
        Formatted display string
    """
    if adapter_name and ip_address:
        return f"{adapter_name} ({ip_address})"
    elif ip_address:
        return f"Auto ({ip_address})"
    else:
        return "Default (127.0.0.1)"