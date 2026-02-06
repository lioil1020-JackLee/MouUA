# ModUA 專案參數設定指南

**更新時間**: 2026年2月2日  
**適用版本**: ModUA v2.x  
**文檔類型**: 參數配置參考

本文檔詳細說明 ModUA 專案中所有可配置參數的層次結構和設定選項。

## 🏗️ 配置架構總覽

ModUA 的配置採用層次樹狀結構，從通道到標籤逐級組織：

```
專案根層級
├── Modbus 子系統
│   ├── 通道層級 (Channel)
│   ├── 設備層級 (Device)
│   ├── 群組層級 (Group)
│   └── 標籤層級 (Tag)
└── OPC UA 子系統
    └── 服務器設定
```

## 📡 Modbus 配置參數

### 1️⃣ 通道層級設定 (Channel Properties)

#### 基本識別 (General)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Channel Name** | 字串 | 通道的唯一識別名稱 | - |
| **Description** | 字串 | 通道的描述說明 | 空 |

#### 驅動與通訊協定 (Driver)
| 參數 | 類型 | 說明 | 適用模式 | 預設值 |
|------|------|------|----------|--------|
| **Select Driver** | 選項 | Modbus 驅動類型選擇 | 全部 | Modbus TCP/IP Ethernet |
| **IP Address** | 字串 | 目標設備 IP 地址 | TCP | 192.168.1.100 |
| **Port** | 整數 | TCP 連接埠 | TCP | 502 |
| **Protocol** | 選項 | 傳輸協議版本 | TCP | TCP |

#### 實體通訊層設定 (Communication)

##### 網路設定 (適用 TCP 模式)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Network Adapter** | 選項 | 綁定特定網卡介面 | 自動選擇 |

##### 序列埠設定 (適用 RTU Serial 模式)
| 參數 | 類型 | 說明 | 有效值 | 預設值 |
|------|------|------|--------|--------|
| **COM ID** | 選項 | 序列埠編號 | COM1-COM256 | COM1 |
| **Baud Rate** | 整數 | 波特率 (bps) | 300-921600 | 9600 |
| **Data Bits** | 整數 | 資料位元數 | 5-8 | 8 |
| **Parity** | 選項 | 校驗位 | None/Even/Odd/Mark/Space | None |
| **Stop Bits** | 選項 | 停止位 | 1/1.5/2 | 1 |
| **Flow Control** | 選項 | 流量控制 | None/XON/XOFF/Hardware | None |

### 2️⃣ 設備層級設定 (Device Properties)

#### 設備識別 (General)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Device Name** | 字串 | 設備的唯一識別名稱 | - |
| **Description** | 字串 | 設備的描述說明 | 空 |
| **Device ID** | 整數 | Modbus 設備站號/Unit ID | 1 |

#### 定時與重試機制 (Timing)
| 參數 | 類型 | 單位 | 說明 | 預設值 |
|------|------|------|------|--------|
| **Connect Timeout** | 整數 | 秒 | TCP 連線逾時 | 5 |
| **Connect Attempts** | 整數 | 次 | RTU over TCP 重試次數 | 3 |
| **Request Timeout** | 整數 | 毫秒 | 單個請求逾時 | 1000 |
| **Attempts Before Timeout** | 整數 | 次 | 請求重試次數 | 2 |
| **Inter-Request Delay** | 整數 | 毫秒 | 請求間延遲 | 10 |

#### Modbus 標準功能設定 (Data Access)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Zero-Based Addressing** | 布林 | 啟用 0 基址模式 | 開啟 |
| **Zero-Based Bit Addr.** | 布林 | 位元地址 0 基址 | 關閉 |
| **Holding Register Bit** | 布林 | 允許保持暫存器位元寫入 | 開啟 |
| **Modbus Function 06** | 布林 | 啟用單一暫存器寫入 (0x06) | 開啟 |
| **Modbus Function 05** | 布林 | 啟用單一線圈寫入 (0x05) | 開啟 |

#### 資料解析與位元組順序 (Data Encoding)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Modbus Byte Order** | 選項 | 位元組順序 (Big/Little Endian) | Big Endian |
| **First Word Low** | 布林 | 高低字組交換 | 關閉 |
| **First Dword Low** | 布林 | 雙字組順序 | 關閉 |
| **Modicon Bit Order** | 布林 | Modicon 位元順序 | 關閉 |
| **Treat Longs as Dec.** | 布林 | 長整數作為十進制處理 | 關閉 |

#### 通訊打包優化 (Block Sizes)
| 參數 | 類型 | 說明 | 預設值 | 最大值 |
|------|------|------|------|--------|
| **Output Coils** | 整數 | 線圈最大打包長度 | 800 | 2000 |
| **Input Coils** | 整數 | 輸入線圈最大打包長度 | 800 | 2000 |
| **Internal Registers** | 整數 | 內部暫存器最大打包長度 | 100 | 125 |
| **Holding Registers** | 整數 | 保持暫存器最大打包長度 | 100 | 125 |

### 3️⃣ 群組層級設定 (Group Properties)

#### 群組基本識別 (General)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Name** | 字串 | 群組的唯一識別名稱 | - |
| **Description** | 字串 | 群組的描述說明 | 空 |

### 4️⃣ 標籤層級設定 (Tag Properties)

#### 點位基本通訊設定 (General)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Tag Name** | 字串 | 標籤的唯一識別名稱 | - |
| **Description** | 字串 | 標籤的描述說明 | 空 |
| **Data Type** | 選項 | 資料類型 | Word |
| **Access** | 選項 | 存取權限 | Read/Write |
| **Address** | 字串 | Modbus 地址 | 40001 |
| **Scan Rate** | 整數 | 掃描頻率 (ms) | 1000 |

##### 支援的資料類型
- **基本類型**: Word, Boolean, Float, Double, String
- **陣列類型**: Word(Array), Boolean(Array), Float(Array), Double(Array)

#### 數據換算設定 (Scaling)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Scaling Type** | 選項 | 換算類型 | Linear |
| **Raw Low** | 數值 | 原始值下限 | 0 |
| **Raw High** | 數值 | 原始值上限 | 65535 |
| **Scaled Data Type** | 選項 | 換算後資料類型 | Float |
| **Scaled Low** | 數值 | 換算後下限 | 0.0 |
| **Scaled High** | 數值 | 換算後上限 | 100.0 |
| **Clamp Low** | 布林 | 箝位低限 | 開啟 |
| **Clamp High** | 布林 | 箝位高限 | 開啟 |
| **Negate Value** | 布林 | 數值取反 | 關閉 |
| **Units** | 字串 | 工程單位 | 空 |

## 🔧 OPC UA 服務器配置

### 基礎運行參數 (Settings)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Application Name** | 字串 | OPC UA 應用程式名稱 | ModUA Server |
| **Host Name** | 字串 | 服務器主機名稱 | localhost |
| **Namespace** | 字串 | 自訂命名空間 URI | http://modua.example.com |
| **Port** | 整數 | 服務監聽埠 | 4840 |
| **Network Adapter** | 選項 | 綁定網卡介面 | 0.0.0.0 (全部) |
| **Max Sessions** | 整數 | 最大並發連線數 | 100 |
| **Publish Interval** | 整數 | 數據發佈間隔 (ms) | 100 |

### 身份驗證設定 (Authentication)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Type** | 選項 | 驗證類型 | Anonymous |
| **Username** | 字串 | 用戶名 | - |
| **Password** | 字串 | 密碼 | - |

#### 支援的驗證類型
- **Anonymous**: 匿名訪問
- **Username/Password**: 用戶名密碼驗證

### 安全策略選擇 (Security Policies)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Policies** | 多選 | 啟用的安全策略 | None |

#### 支援的安全策略
- **None**: 無加密
- **Basic128Rsa15**: 基礎 128 位元 RSA
- **Basic256**: 基礎 256 位元
- **Basic256Sha256**: 增強 256 位元

### 憑證資訊設定 (Certificate)
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Auto Generate** | 布林 | 自動產生憑證 | 開啟 |
| **Organization** | 字串 | 組織名稱 | 公司名稱 |
| **Organization Unit** | 字串 | 部門單位 | IT Department |
| **Locality** | 字串 | 所在地城市 | 城市名稱 |
| **State** | 字串 | 州/省份 | 省份名稱 |
| **Country** | 字串 | 國家代碼 (ISO) | TW |
| **Validity** | 整數 | 憑證有效期 (天) | 365 |

## 📊 診斷與監控設定

### 診斷系統配置
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Enable Diagnostics** | 布林 | 啟用診斷日誌 | 開啟 |
| **Log Level** | 選項 | 日誌詳細程度 | INFO |
| **Max Log Entries** | 整數 | 最大日誌條目數 | 5000 |
| **TX/RX Only Mode** | 布林 | 僅記錄通訊數據 | 關閉 |

### 性能監控
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| **Enable Performance Stats** | 布林 | 啟用性能統計 | 開啟 |
| **Stats Interval** | 整數 | 統計更新間隔 (秒) | 30 |
| **Alert Thresholds** | 字典 | 告警閾值設定 | 預設閾值 |

## 🔄 配置驗證規則

### 必填參數檢查
- Channel Name: 必須唯一且不為空
- Device ID: 範圍 1-247
- IP Address: 有效 IPv4 地址格式
- Port: 範圍 1-65535
- COM Port: 系統存在的序列埠

### 參數依賴關係
- TCP 模式: IP Address, Port 為必填
- Serial 模式: COM ID, Baud Rate 等為必填
- Scaling: 啟用時 Raw Low/High, Scaled Low/High 為必填

### 範圍限制
- Scan Rate: 最小 10ms
- Block Sizes: 根據 Modbus 標準限制
- Timeouts: 正整數值

## 💡 配置最佳實踐

### 性能優化
1. **Block Sizes**: 根據設備能力調整打包大小
2. **Scan Rate**: 根據應用需求平衡實時性和負載
3. **Inter-Request Delay**: 避免設備過載

### 可靠性設定
1. **Timeouts**: 根據網路條件調整逾時設定
2. **Retry Counts**: 設置適當的重試次數
3. **Error Handling**: 啟用診斷日誌以便故障排除

### 安全考慮
1. **OPC UA Security**: 生產環境使用加密策略
2. **Authentication**: 根據需求選擇適當驗證方式
3. **Certificate**: 使用有效憑證確保通訊安全

---

**配置指南維護者**: AI Assistant  
**最後更新**: 2026年2月2日  
**相關文檔**: [Architecture Analysis](architecture_analysis_full.md), [Role Architecture](role_architecture.md)
````
