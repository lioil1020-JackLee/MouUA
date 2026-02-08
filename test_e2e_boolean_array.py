#!/usr/bin/env python3
"""
End-to-end test for Boolean(Array) tag handling.
"""

import sys
sys.path.insert(0, '/e/py/ModUA')

from core.modbus.modbus_mapping import map_tag_to_pymodbus, _normalize_data_type
from core.modbus.modbus_scheduler import group_reads

# Simulate a Boolean(Array) tag from the configuration
tag_raw = {
    "Description": "X",
    "Data Type": "Boolean(Array)",
    "Client Access": "Read Only",
    "Address": "101024 [40]",
    "Scan Rate": "10",
}

device_raw = {
    "Device ID": 1,
    "Data Access": {"zero_based": 0, "zero_based_bit": 1},
    "Encoding": {
        "byte_order": 1,
        "word_order": 1,
        "dword_order": 1,
        "bit_order": 0,
        "treat_longs_as_decimals": 0,
    },
    "Block Sizes": {
        "out_coils": 2000,
        "in_coils": 2000,
        "int_regs": 120,
        "hold_regs": 120,
    },
}

channel_raw = {
    "Channel": "Delta_42_1F",
}

# Step 1: Normalize data type
print("=" * 60)
print("STEP 1: Normalize Data Type")
print("=" * 60)
dtype, count = _normalize_data_type(tag_raw["Data Type"])
print(f"Input: '{tag_raw['Data Type']}'")
print(f"Output: dtype='{dtype}', count={count}")
print()

# Step 2: Map to canonical format
print("=" * 60)
print("STEP 2: Map to Canonical Format")
print("=" * 60)
canonical = map_tag_to_pymodbus(tag_raw, device_raw, channel_raw)
print(f"Name: {canonical.get('name')}")
print(f"Data Type: {canonical.get('data_type')}")
print(f"Address Type: {canonical.get('address_type')}")
print(f"Address: {canonical.get('address')}")
print(f"Count: {canonical.get('count')}")
print(f"Is Array: {canonical.get('is_array')}")
print(f"Array Element Count: {canonical.get('array_element_count')}")
print()

# Step 3: Test grouping
print("=" * 60)
print("STEP 3: Group Reads")
print("=" * 60)
batches = group_reads([canonical], max_regs=120)
print(f"Number of batches: {len(batches)}")
for i, batch in enumerate(batches):
    print(f"Batch {i}:")
    print(f"  Address Type: {batch.get('address_type')}")
    print(f"  Unit ID: {batch.get('unit_id')}")
    print(f"  Start: {batch.get('start')}")
    print(f"  Count: {batch.get('count')}")
    print(f"  Number of tags: {len(batch.get('tags', []))}")
    for tag in batch.get('tags', []):
        print(f"    - Tag: {tag.get('name')}")
        print(f"      data_type: {tag.get('data_type')}")
        print(f"      is_array: {tag.get('is_array')}")
        print(f"      address: {tag.get('address')}")
        print(f"      count: {tag.get('count')}")

print("\n" + "=" * 60)
print("✓ Test completed")
print("=" * 60)
