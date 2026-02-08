# Boolean(Array) Tag 顯示問題分析與修復

## 🔍 問題診斷

### 症狀
- **X** tag（數據類型: `Boolean(Array)`，地址: `101024 [40]`）在 Runtime 標籤的監控表格中沒有顯示值
- Modbus 通信正常（ADU 日誌顯示 FC2 離散輸入讀取成功）
- 其他 Boolean tag 正常顯示
- 其他 Array tag (Long Array, Float Array) 正常顯示

### 根本原因
位置: [core/modbus/modbus_client.py#L978-L988](core/modbus/modbus_client.py#L978-L988)

在 `read_batch_async()` 函數中，處理線圈/離散輸入 (FC1/FC2) 的邏輯不支持 Boolean(Array) 類型：

```python
# ❌ 舊代碼 - 只提取單一比特
if fc in (1, 2):
    bits = getattr(res, 'bits_list', None) or []
    for t in tags:
        off = int(t.get('address', 0)) - start
        val = None
        if 0 <= off < len(bits):
            val = 1 if bits[off] else 0  # ❌ 只取一個元素！
        results.append({'tag': t, 'value': val, 'raw': None})
```

**問題分析：**
1. 代碼計算單一偏移量 `off`，然後提取該位置的單一比特
2. Boolean(Array) tags（如 `101024 [40]`）需要從指定地址提取 40 個連續比特
3. 當前邏輯無法處理 `[40]` 格式中的陣列大小信息

### 對比：Register Array 的處理方式
Register 類型的陣列（Long Array, Float Array）已正確實現（第 1000-1040 行）：
```python
# ✓ 正確實現 - 提取多個元素
if dtype.endswith('[]'):
    base = dtype[:-2]
    # ... 根據基本類型計算元素大小 ...
    for i in range(0, len(raw), elem_size_bytes):
        chunk = raw[i:i+elem_size_bytes]
        # ... 解碼並添加到 elems 列表 ...
    val = elems
```

## ✅ 修復方案

### 變更內容
檔案: [core/modbus/modbus_client.py](core/modbus/modbus_client.py)

修改 `read_batch_async()` 函數中 FC1/FC2 處理邏輯，支持 Boolean(Array)：

```python
# ✓ 新代碼 - 支持陣列
if fc in (1, 2):
    bits = getattr(res, 'bits_list', None) or []
    for t in tags:
        t_addr = int(t.get('address', 0))
        dtype = t.get('data_type') or 'Boolean'
        off = t_addr - start
        
        # 檢查是否為 Boolean(Array) 類型
        is_bool_array = dtype.lower() == 'boolean(array)' or dtype.endswith('[]')
        
        if is_bool_array:
            # 從地址中提取陣列大小，如 "101024 [40]" → 40
            array_elem_match = re.search(r'\[\s*(\d+)\s*\]', t.get('address', '') or "")
            array_elem_count = int(array_elem_match.group(1)) if array_elem_match else 1
            
            # 提取連續的多個比特
            elems = []
            for i in range(array_elem_count):
                bit_idx = off + i
                if 0 <= bit_idx < len(bits):
                    elems.append(1 if bits[bit_idx] else 0)
                else:
                    elems.append(None)
            val = elems
        else:
            # 單一 Boolean 值（保持原有邏輯）
            val = None
            if 0 <= off < len(bits):
                val = 1 if bits[off] else 0
        
        results.append({'tag': t, 'value': val, 'raw': None})
```

### 修復特點
✓ **向後兼容** - 單個 Boolean tag 仍使用原有邏輯  
✓ **格式靈活** - 支持 `101024 [40]`、`101024[40]`、`101024 [ 40 ]` 等格式  
✓ **邊界檢查** - 若請求超出可用比特數，填充 `None`  
✓ **與 Register Array 一致** - 使用相同的陣列提取方式  

## 🧪 驗證結果

執行 [test_boolean_array.py](test_boolean_array.py) 測試結果：

```
✓ 地址解析 (4/4 通過)
✓ 比特陣列提取 (成功提取 40 個元素)
✓ 數據類型檢測 (8/8 通過)
✓ JSON 配置加載 (找到 4 個 Boolean(Array) tags)
```

### Bai_Le_Hui.json 中的 Boolean(Array) Tags
```
1. Channel: Delta_42_1F → Device: HPW1 → X [101024, 40 elements]
2. Channel: Delta_42_1F → Device: HPW2 → X [101024, 24 elements]  
3. Channel: Kangan       → Device: Kan_HPW1 → X [101024, 24 elements]
4. Channel: Kangan       → Device: Kan_HPW2 → X [101024, 32 elements]
```

## 📋 預期改進

修復後：
1. **Runtime 標籤** 監控表格將顯示 X tag 的值，格式為 `[1, 0, 1, 1, ...]`
2. **OPC UA 伺服器** 將正確暴露這些值為 Boolean 陣列節點
3. **與其他陣列類型** (Long Array, Float Array) 行為一致

## 🔗 相關文件
- [core/modbus/modbus_client.py](core/modbus/modbus_client.py) - 修復位置
- [core/ui_models.py](core/ui_models.py) - UI 模型（已支持陣列顯示）
- [Bai_Le_Hui.json](Bai_Le_Hui.json) - 測試配置
