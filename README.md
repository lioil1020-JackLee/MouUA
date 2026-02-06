# ModUA - Modbus to OPC UA Bridge

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.10.1-green.svg)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**ModUA** 是一個專業的工業自動化橋接工具，將 Modbus 設備無縫整合至 OPC UA 生態系統。提供直觀的圖形化介面、實時數據監控、高效能通訊引擎，以及完整的診斷和配置管理功能。

**最新更新**: 2026年2月3日 - 完整 OPC UA 服務器實現，虛擬滾動表格支持，增強診斷系統（圖片已更新）

## ✨ 核心功能

## 📷 Screenshots

以下為 UI 截圖（使用相對路徑從 `images/` 讀取）：

（圖片已於 2026年2月3日更新）

![Main UI](images/Main%20UI.png)
![Channel - General](images/Channel%20-%20General.png)
![Channel - Driver](images/Channel%20-%20Driver.png)
![Channel - Communication](images/Channel%20-%20Communication.png)
![Device - General](images/Device%20-%20General.png)
![Device - Timing](images/Device%20-%20Timing.png)
![Device - DataAccess](images/Device%20-%20DataAccess.png)
![Device - DataEncoding](images/Device%20-%20DataEncoding.png)
![Device - Block Sizes](images/Device%20-%20Block%20Sizes.png)
![Group Properties](images/Group%20Properties.png)
![Tag - General](images/Tag%20-%20General.png)
![Tag - Scaling - Linear](images/Tag%20-%20Scaling%20-%20Linear.png)
![OPC UA - Settings](images/OPC%20UA%20-%20Settings.png)
![OPC UA - Authentication](images/OPC%20UA%20-%20Authentication.png)
![OPC UA - Security Policies](images/OPC%20UA%20-%20Security%20Policies.png)
![OPC UA - Certificate](images/OPC%20UA%20-%20Certificate.png)
![Diagnostics](images/Diagnostics.png)


### 🔗 工業通訊協議支援
- **Modbus TCP/RTU**: 完整支援 Modbus TCP、RTU over TCP 和串口 RTU
- **OPC UA 伺服器**: 完整實現的動態 OPC UA 伺服器，支援雙向讀寫操作和安全策略
- **多重功能碼**: 支援 coils、discrete inputs、input registers、holding registers
- **批量操作**: 優化批量讀寫操作，提升通訊效率

### 🎯 數據處理能力
- **多種數據類型**: Boolean、Integer、Float、Double、String、BCD 等
- **位元組順序處理**: 支援大端/小端字節順序和字組交換
- **地址映射**: 支援 0-based 和 1-based 地址模式
- **實時編碼**: 動態數據類型轉換和範圍驗證
- **虛擬滾動**: 支持數千標籤的高效能表格顯示

### 🖥️ 圖形化管理介面
- **專案樹狀結構**: Channel → Device → Group → Tag 的層次管理
- **即時監控**: 實時數據表格顯示和狀態指示，支持數千標籤
- **拖拽操作**: 支援拖拽複製和移動標籤
- **配置對話框**: 直觀的參數配置介面和統一的對話框樣式
- **虛擬滾動**: 高效能表格模型，避免大量標籤時的性能問題

### 📊 監控與診斷
- **實時數據監控**: 連續輪詢和狀態追蹤
- **診斷工具**: 增強的診斷終端，主要記錄 Modbus ADU 的傳輸和接收訊息
- **性能監控**: 通訊統計和延遲分析
- **日誌系統**: 詳細的操作日誌和錯誤記錄
- **線程安全**: 診斷系統的線程安全設計

## 🚀 快速開始

### 環境需求
- **Python**: 3.12 或更新版本
- **作業系統**: Windows 10/11
- **記憶體**: 至少 2GB RAM
- **網路**: 支援 TCP/IP 和串口通訊

### 安裝步驟

1. **複製專案**
```bash
git clone https://github.com/lioil1020-JackLee/ModUA.git
cd ModUA
```

2. **建立虛擬環境**
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

3. **安裝依賴**
```bash
pip install -r requirements.txt
```

4. **啟動應用程式**
```bash
python ModUA.py
```

## 📁 專案結構

```
ModUA/
├── ModUA.py                 # 主應用程式入口 (5148 行)
├── core/                    # 核心業務邏輯
│   ├── controllers/         # 控制器層
│   │   ├── base_controller.py    # 主控制器
│   │   ├── config_builder.py     # 配置建構器
│   │   ├── data_manager.py       # 數據管理器
│   │   ├── serializers.py        # 序列化器
│   │   └── validators.py         # 數據驗證器
│   ├── modbus/              # Modbus 通訊模塊
│   │   ├── modbus_client.py      # Modbus 客戶端
│   │   ├── modbus_worker.py      # 輪詢工作器
│   │   ├── modbus_mapping.py     # 地址映射
│   │   ├── modbus_monitor.py     # 通訊監控
│   │   ├── modbus_scheduler.py   # 調度器
│   │   ├── modbus_write_queue.py # 寫入隊列
│   │   └── data_buffer.py        # 數據緩衝
│   ├── OPC_UA/              # OPC UA 模塊
│   │   └── opcua_server.py      # 完整 OPC UA 伺服器 (2325 行)
│   ├── diagnostics.py       # 診斷管理器 (129 行)
│   ├── ui_models.py         # 虛擬表格模型 (242 行)
│   ├── utils.py             # 安全工具函數 (107 行)
│   └── config/              # 配置模塊
│       ├── constants.py          # 常量定義
│       └── __init__.py
├── ui/                      # 用戶介面層
│   ├── base_dialogs.py      # 基礎對話框類 (197 行)
│   ├── components.py        # UI 組件
│   ├── dragdrop_tree.py     # 樹狀控件
│   ├── terminal_window.py   # 診斷窗口 (491 行)
│   ├── clipboard.py         # 剪貼板操作
│   └── dialogs/             # 對話框
│       ├── channel_dialog.py     # 通道配置
│       ├── device_dialog.py      # 設備配置
│       ├── group_dialog.py       # 群組配置
│       ├── tag_dialog.py         # 標籤配置
│       ├── opcua_dialog.py       # OPC UA 配置
│       └── write_value_dialog.py # 寫入值對話框
├── *.json                   # 示例專案配置
├── requirements.txt         # Python 依賴
├── pyproject.toml          # 專案配置
├── LICENSE                 # 授權文件
└── README.md              # 專案說明
```

## ⚙️ 配置指南

### Modbus 通道配置
- **TCP 模式**: 指定 IP 地址、端口和網路適配器
- **RTU 模式**: 配置串口參數（波特率、資料位元、校驗位等）
- **通訊參數**: 連接超時、重試次數、請求間延遲

### 設備與標籤管理
- **設備站號**: Modbus 設備的唯一識別碼
- **數據類型**: 根據設備手冊選擇正確的數據類型
- **地址映射**: 正確設置 Modbus 地址和功能碼
- **讀寫權限**: 配置標籤的讀寫屬性

### OPC UA 伺服器配置
- **應用程式資訊**: 設定伺服器名稱和描述
- **網路設定**: 配置監聽端口和網路介面
- **安全策略**: 完整的安全策略支持（None、Basic128Rsa15等）
- **動態節點**: 自動從 Modbus 標籤創建 OPC UA 節點
- **雙向同步**: 支持從 OPC UA 客戶端讀寫 Modbus 設備
- **時間戳支持**: 每個值包含時間戳和品質指示

## 🔧 開發指南

### 架構設計原則
- **關注點分離**: UI、業務邏輯、數據存儲完全分離
- **模塊化設計**: 每個功能模塊獨立開發和測試
- **異步處理**: 使用 asyncio 處理網路 I/O 操作
- **錯誤處理**: 完善的異常處理和錯誤恢復機制
- **虛擬化UI**: 高效能的虛擬滾動表格，支持大量數據
- **線程安全**: 診斷系統和數據管理的線程安全設計

### 擴展開發
- **自訂協議**: 在 `core/` 下添加新的通訊協議支援
- **UI 組件**: 擴展 `ui/components.py` 和 `ui/base_dialogs.py` 添加自訂介面元素
- **數據處理**: 在 `core/controllers/` 中添加新的數據處理邏輯
- **OPC UA 擴展**: 在 `core/OPC_UA/` 中添加方法調用和歷史數據支持
- **診斷增強**: 擴展 `core/diagnostics.py` 添加自訂監控指標

### 測試與除錯
- 使用內建診斷終端查看 Modbus ADU 傳輸記錄
- 檢查日誌系統中的錯誤記錄
- 驗證 OPC UA 伺服器連接和數據同步

## 📋 系統需求

### 硬體需求
- **處理器**: 雙核心 2.0GHz 或更高（建議四核心）
- **記憶體**: 4GB RAM（建議 8GB，支持大量標籤）
- **儲存空間**: 500MB 可用空間
- **網路**: 100Mbps 乙太網路（建議 1Gbps）

### 軟體需求
- **Python**: 3.12+
- **作業系統**: Windows 10/11
- **依賴套件**: 見 `requirements.txt`
- **OPC UA 客戶端**: 支持標準 OPC UA 客戶端連接

## 🤝 貢獻指南

歡迎參與 ModUA 專案的開發！

1. Fork 此專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

### 開發規範
- 遵循 PEP 8 編碼規範
- 添加適當的文檔字串
- 為新功能編寫單元測試
- 確保向後相容性

## 📄 授權

本專案採用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 文件

## 📞 聯絡資訊

- **專案維護者**: lioil1020
- **問題回報**: [GitHub Issues](https://github.com/lioil1020-JackLee/ModUA/issues)
- **功能請求**: [GitHub Discussions](https://github.com/lioil1020-JackLee/ModUA/discussions)

## 🙏 致謝

感謝所有為此專案做出貢獻的開發者和使用者。特別感謝：

- PyQt6 團隊提供的優秀 GUI 框架
- Pymodbus 團隊的 Modbus 協議實現
- AsyncUA/FreeOPCUA 團隊的完整 OPC UA 服務器支援
- 開源社區提供的虛擬滾動表格和線程安全設計模式

---

## 🚀 最新功能亮點 (2026年2月)

### ✨ 完整 OPC UA 服務器實現
- 動態節點創建和雙向數據同步
- 完整的安全策略支持
- 時間戳和品質指示
- 從 OPC UA 客戶端直接寫入 Modbus 設備

### 🎯 高性能虛擬表格
- 支持數千標籤的高效能顯示
- 記憶體優化，避免 UI 卡頓
- 即時滾動和數據更新

### 🔧 增強診斷系統
- 線程安全的診斷管理器
- 實時監聽器和事件過濾
- 詳細的通訊追蹤和統計

### 🛡️ 安全工具函數
- 統一的錯誤處理和數據訪問
- 防止 UI 崩潰的保護機制
- 標準化的對話框樣式

---

**ModUA** - 讓工業自動化更簡單、更可靠！ 
