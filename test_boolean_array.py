#!/usr/bin/env python3
"""
Test script to verify Boolean(Array) tag parsing and value extraction.
"""

import sys
import re
import json

# Test 1: Address parsing for Boolean(Array)
print("=" * 60)
print("TEST 1: Boolean(Array) Address Parsing")
print("=" * 60)

test_addresses = [
    ("101024 [40]", 40),
    ("101024[40]", 40),
    ("101024 [ 40 ]", 40),
    ("101024", None),
]

for addr, expected_count in test_addresses:
    array_elem_match = re.search(r'\[\s*(\d+)\s*\]', addr)
    count = int(array_elem_match.group(1)) if array_elem_match else None
    status = "✓" if count == expected_count else "✗"
    print(f"{status} Address '{addr}' -> count={count} (expected={expected_count})")

# Test 2: Bit extraction logic
print("\n" + "=" * 60)
print("TEST 2: Bit Array Extraction Logic")
print("=" * 60)

# Simulate Modbus response with 40 bits
bits = [bool(i % 2) for i in range(50)]  # Alternating True/False for first 50 bits

start_addr = 1024
tag_addr = 1024  # Same as start
array_elem_count = 40

off = tag_addr - start_addr
elems = []
for i in range(array_elem_count):
    bit_idx = off + i
    if 0 <= bit_idx < len(bits):
        elems.append(1 if bits[bit_idx] else 0)
    else:
        elems.append(None)

print(f"Start address: {start_addr}")
print(f"Tag address: {tag_addr}")
print(f"Offset: {off}")
print(f"Array element count: {array_elem_count}")
print(f"Total bits available: {len(bits)}")
print(f"Extracted array (first 10 elements): {elems[:10]}")
print(f"Extracted array (last 10 elements): {elems[-10:]}")
print(f"✓ Successfully extracted {len(elems)} boolean values")

# Test 3: Data type detection
print("\n" + "=" * 60)
print("TEST 3: Data Type Detection")
print("=" * 60)

test_types = [
    ("Boolean(Array)", True),
    ("boolean(array)", True),
    ("Boolean", False),
    ("boolean", False),
    ("Bool[]", True),
    ("bool[]", True),
    ("Word", False),
    ("Float Array", False),
]

for dtype, is_bool_array_expected in test_types:
    is_bool_array = dtype.lower() == 'boolean(array)' or dtype.endswith('[]')
    status = "✓" if is_bool_array == is_bool_array_expected else "✗"
    print(f"{status} Type '{dtype}' -> is_bool_array={is_bool_array} (expected={is_bool_array_expected})")

# Test 4: Configuration from JSON
print("\n" + "=" * 60)
print("TEST 4: Configuration Loading from Bai_Le_Hui.json")
print("=" * 60)

try:
    with open('Bai_Le_Hui.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Find Boolean(Array) tags
    bool_array_tags = []
    
    def find_tags(obj, path=""):
        if isinstance(obj, dict):
            if obj.get('type') == 'Tag':
                data_type = obj.get('general', {}).get('data_type', '')
                if 'Boolean(Array)' in data_type or 'boolean(array)' in data_type.lower():
                    tag_name = obj.get('text', 'Unknown')
                    address = obj.get('general', {}).get('address', '')
                    bool_array_tags.append({
                        'name': tag_name,
                        'address': address,
                        'data_type': data_type,
                        'path': path
                    })
            for key, value in obj.items():
                find_tags(value, path + f".{key}" if path else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_tags(item, f"{path}[{i}]")
    
    find_tags(config)
    
    print(f"Found {len(bool_array_tags)} Boolean(Array) tag(s):")
    for tag in bool_array_tags:
        print(f"  • {tag['name']}")
        print(f"    - Data Type: {tag['data_type']}")
        print(f"    - Address: {tag['address']}")
        
        # Parse address
        array_match = re.search(r'\[\s*(\d+)\s*\]', tag['address'])
        if array_match:
            count = int(array_match.group(1))
            print(f"    - Array Size: {count} elements")
    
except FileNotFoundError:
    print("✗ Bai_Le_Hui.json not found")
except Exception as e:
    print(f"✗ Error loading config: {e}")

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
