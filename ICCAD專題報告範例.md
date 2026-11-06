# 國立清華大學資訊工程系專題報告範例
# 基於 ICCAD 2025 Problem C 的專題內容

---

## 專題名稱
基於深度學習的 VLSI 漸進式時序驅動佈局優化

---

## 參加競賽或計畫
- ☑ 參加對外競賽（ICCAD 2025 Contest - Problem C）
- ☐ 參與其他計畫
- ☐ 無參加對外競賽或任何計畫

---

## 摘要

本專題針對超大型積體電路（VLSI）設計中的增量佈局優化問題進行研究。隨著晶片設計複雜度的增加，設計週期中頻繁的工程變更單（ECO）需要快速且高品質的增量佈局解決方案。本研究採用 DREAMPlace 深度學習佈局工具為基礎，開發針對 ICCAD 2025 Contest Problem C 的增量時序優化方法。研究重點包括：(1) 分析增量佈局的特性與挑戰；(2) 設計基於深度學習的時序驅動佈局演算法；(3) 開發增量優化策略以最小化關鍵路徑延遲。實驗結果顯示，本方法在 ASAP7 製程的測試案例上，相較於基準方法可有效降低總負鬆弛時間（TNS）並改善最差負鬆弛時間（WNS），同時維持良好的 HPWL（Half-Perimeter Wire Length）指標。

---

# 1. 專題研究動機與目的

## 1.1 研究背景

隨著半導體製程技術的進步，現代晶片設計越來越複雜，包含數百萬甚至數十億個邏輯閘。在設計流程中，工程變更單（Engineering Change Order, ECO）是常見的需求，可能源自於：
- 功能性錯誤修正
- 效能優化需求
- 時序違規修正
- 功耗優化

傳統的全局重新佈局（full placement）方法雖然能獲得較好的結果，但需要大量的計算時間，不符合快速迭代的設計需求。因此，增量佈局優化（incremental placement optimization）成為重要的研究議題。

## 1.2 研究動機

ICCAD 2025 Contest Problem C 聚焦於增量式時序驅動佈局優化問題，具有以下特點：
1. **大規模設計**：測試案例包含數千至數十萬個 cell
2. **時序約束**：需同時考慮 setup 和 hold 時序約束
3. **增量優化**：僅能移動部分 cell，需維持原有佈局的穩定性
4. **多目標優化**：需同時優化 TNS、WNS 和 HPWL

## 1.3 研究目的

本專題的研究目的包括：
1. 深入理解增量佈局優化問題的本質與挑戰
2. 研究深度學習方法在 VLSI 佈局問題的應用
3. 開發有效的時序驅動增量佈局優化演算法
4. 參加 ICCAD 2025 競賽，驗證方法的實用性

---

# 2. 現有相關研究概況及比較

## 2.1 VLSI 佈局方法

### 2.1.1 傳統分析式佈局方法

**代表性工具**：
- **ePlace**：基於靜電系統模擬的分析式佈局器
- **RePlAce**：使用 Nesterov's method 的 GPU 加速佈局器
- **NTUPlace**：台灣大學開發的分區式佈局工具

**優點**：
- 數學基礎堅實
- 收斂性有保證
- 適用於大規模設計

**缺點**：
- 計算複雜度高
- 難以整合複雜約束
- 需要大量參數調整

### 2.1.2 深度學習佈局方法

**DREAMPlace**：
- 使用 PyTorch 深度學習框架
- 支援 GPU 加速
- 可微分的佈局目標函數
- 整合全局佈局、詳細佈局和合法化

**優點**：
- 計算效率高（相較於 CPU 方法有 30X 加速）
- 靈活的框架易於擴展
- 支援多種約束和目標函數

**缺點**：
- 需要 GPU 硬體支援
- 記憶體需求較高

## 2.2 時序驅動佈局方法

### 2.2.1 Net Weighting 方法

透過增加關鍵路徑上 net 的權重，引導佈局器縮短關鍵路徑：
- **Momentum-based Net Weighting**（DREAMPlace 4.0）
- **Path-based Net Weighting**

### 2.2.2 直接時序優化方法

直接在目標函數中考慮時序延遲：
- 使用靜態時序分析（STA）計算延遲
- 優化 slack 分佈
- 考慮時序關聯性

## 2.3 增量佈局方法

### 2.3.1 局部搜尋方法
- Simulated Annealing
- Tabu Search
- Genetic Algorithm

### 2.3.2 分析式增量方法
- 固定部分 cell，僅優化需要移動的 cell
- 使用增量式合法化方法
- 保持原有佈局的拓撲結構

## 2.4 方法比較

| 方法類型 | 優化品質 | 執行時間 | 擴展性 | 適用場景 |
|---------|---------|---------|--------|---------|
| 傳統分析式 | 高 | 長 | 佳 | 全局佈局 |
| 深度學習式 | 高 | 短 | 佳 | 大規模設計 |
| 局部搜尋 | 中 | 中 | 差 | 小規模增量 |
| 分析式增量 | 中高 | 短 | 中 | ECO 場景 |

---

# 3. 設計原理

## 3.1 問題定義

給定：
- 初始佈局解（包含 cell 位置）
- 可移動的 cell 列表（movable cells）
- 時序約束（SDC 檔案）
- 標準元件庫（Liberty 格式）
- 互連延遲模型（SPEF 格式）

目標：
- 最小化 Total Negative Slack (TNS)
- 最小化 Worst Negative Slack (WNS)
- 最小化 Half-Perimeter Wire Length (HPWL)

約束：
- 僅能移動指定的可移動 cell
- Cell 不能重疊（需要合法化）
- Cell 必須在佈局區域內

## 3.2 系統架構

```
[輸入檔案]
    ├── DEF（佈局定義）
    ├── LEF（元件庫）
    ├── Liberty（時序資訊）
    ├── SDC（時序約束）
    └── SPEF（寄生參數）
           ↓
[前處理模組]
    ├── 解析輸入檔案
    ├── 建立資料結構
    └── 識別可移動 cell
           ↓
[時序分析模組]
    ├── 靜態時序分析
    ├── 計算 slack 分佈
    └── 識別關鍵路徑
           ↓
[增量優化模組]
    ├── DREAMPlace 佈局引擎
    ├── 時序驅動目標函數
    ├── Net weighting 策略
    └── 增量式優化
           ↓
[合法化模組]
    ├── Cell 重疊移除
    ├── 增量式詳細佈局
    └── 佈局品質驗證
           ↓
[輸出模組]
    └── 生成優化後的 DEF
```

## 3.3 核心演算法

### 3.3.1 時序驅動目標函數

目標函數包含三個部分：

\[
L_{total} = \lambda_1 L_{HPWL} + \lambda_2 L_{density} + \lambda_3 L_{timing}
\]

其中：
- \( L_{HPWL} \)：線長最小化項
- \( L_{density} \)：密度均勻化項
- \( L_{timing} \)：時序優化項

### 3.3.2 Momentum-based Net Weighting

根據 net 在關鍵路徑上的重要性調整權重：

\[
w_i^{(t+1)} = w_i^{(t)} + \alpha \cdot slack_i + \beta \cdot m_i^{(t)}
\]

其中：
- \( w_i \)：net i 的權重
- \( slack_i \)：net i 上最差的 slack
- \( m_i \)：動量項
- \( \alpha, \beta \)：超參數

### 3.3.3 增量優化策略

1. **識別階段**：分析初始佈局，識別時序違規路徑
2. **優先級排序**：根據 slack 值對可移動 cell 排序
3. **漸進式優化**：
   - 先優化高優先級 cell
   - 使用小的學習率避免破壞原有佈局
   - 迭代更新 net weighting
4. **局部精煉**：對時序敏感區域進行細部調整

---

# 4. 研究方法與步驟

## 4.1 研究方法

本研究採用實驗研究法，結合：
- **文獻研究**：分析現有 VLSI 佈局方法
- **演算法設計**：開發時序驅動增量優化演算法
- **實驗驗證**：使用 ICCAD 提供的測試案例驗證
- **迭代改進**：根據實驗結果調整方法

## 4.2 研究步驟

### 步驟 1：環境建置（第 1-2 週）
- 安裝 DREAMPlace 及相關工具
- 配置 Docker 開發環境
- 熟悉 ASAP7 製程庫

### 步驟 2：問題分析（第 3-4 週）
- 研究 ICCAD 2025 Problem C 的規格
- 分析測試案例特性
- 理解評分標準

### 步驟 3：方法設計（第 5-6 週）
- 設計增量優化策略
- 開發時序驅動目標函數
- 實作 net weighting 機制

### 步驟 4：程式實作（第 7-10 週）
- 修改 DREAMPlace 源碼
- 實作增量優化模組
- 開發自動化腳本

### 步驟 5：實驗與調整（第 11-14 週）
- 在測試案例上進行實驗
- 調整演算法參數
- 分析結果並改進方法

### 步驟 6：文件整理（第 15-16 週）
- 整理實驗數據
- 撰寫專題報告
- 準備競賽提交

---

# 5. 系統實現與實驗

## 5.1 開發環境

| 項目 | 規格 |
|-----|------|
| 作業系統 | Ubuntu 20.04 / Docker |
| Python 版本 | 3.8 |
| PyTorch 版本 | 1.12 |
| CUDA 版本 | 11.3 |
| GPU | NVIDIA Tesla V100 |
| 記憶體 | 32 GB |

## 5.2 使用的工具與套件

### 5.2.1 主要工具
- **DREAMPlace**：深度學習佈局工具
- **OpenTimer**：靜態時序分析工具
- **OpenROAD**：開源 EDA 工具鏈（用於驗證）

### 5.2.2 Python 套件
- PyTorch：深度學習框架
- NumPy：數值計算
- Matplotlib：結果視覺化

## 5.3 系統實作細節

### 5.3.1 檔案解析模組

實作了以下格式的解析器：
- **DEF Parser**：解析佈局定義檔案
- **LEF Parser**：解析元件庫檔案
- **Liberty Parser**：解析時序資訊
- **SDC Parser**：解析時序約束

### 5.3.2 時序分析模組

整合 OpenTimer 進行靜態時序分析：
```python
# 偽代碼
def timing_analysis(design):
    # 讀取設計檔案
    timer = OpenTimer()
    timer.read_celllib(liberty_file)
    timer.read_verilog(verilog_file)
    timer.read_sdc(sdc_file)
    timer.read_spef(spef_file)
    
    # 執行時序分析
    timer.update_timing()
    
    # 提取時序資訊
    tns = timer.report_tns()
    wns = timer.report_wns()
    critical_paths = timer.report_critical_paths()
    
    return tns, wns, critical_paths
```

### 5.3.3 增量優化模組

實作增量優化的核心邏輯：
```python
# 偽代碼
def incremental_optimization(design, movable_cells):
    # 初始化
    placer = DREAMPlace(design)
    
    # 標記可移動和固定的 cell
    placer.set_movable_cells(movable_cells)
    
    # 迭代優化
    for iteration in range(max_iterations):
        # 時序分析
        tns, wns, critical_paths = timing_analysis(design)
        
        # 更新 net weighting
        net_weights = update_net_weights(critical_paths)
        placer.set_net_weights(net_weights)
        
        # 執行佈局優化
        placer.optimize(num_steps=50)
        
        # 檢查收斂
        if converged(tns, wns):
            break
    
    # 最終合法化
    placer.legalize()
    
    return placer.get_placement()
```

## 5.4 實驗設計

### 5.4.1 測試案例

ICCAD 2025 提供的測試案例：

| 案例名稱 | Cell 數量 | Pin 數量 | 特性 |
|---------|----------|----------|------|
| aes | ~5K | ~18K | 中型設計 |
| aes_cipher_top | ~12K | ~41K | 中大型設計 |
| ac97_top | ~8K | ~29K | 中型設計 |
| des | ~4K | ~15K | 小型設計 |
| pci_bridge32 | ~7K | ~25K | 中型設計 |
| ariane | ~106K | ~463K | 大型設計 |

### 5.4.2 評估指標

1. **Total Negative Slack (TNS)**：所有負 slack 的總和
2. **Worst Negative Slack (WNS)**：最差的負 slack
3. **Half-Perimeter Wire Length (HPWL)**：線長總和

評分公式：
\[
Score = \alpha \cdot TNS + \beta \cdot WNS + \gamma \cdot HPWL
\]

### 5.4.3 實驗參數設定

| 參數 | 值 | 說明 |
|-----|---|------|
| learning_rate | 0.01 | 學習率 |
| max_iterations | 100 | 最大迭代次數 |
| net_weight_alpha | 0.5 | Net weighting 參數 |
| net_weight_beta | 0.3 | 動量項係數 |

## 5.5 實驗結果

### 5.5.1 中小型測試案例結果

**表 1：aes 測試案例結果**

| 方法 | TNS (ps) | WNS (ps) | HPWL (μm) | 執行時間 (s) |
|-----|----------|----------|-----------|-------------|
| 初始解 | -1520.3 | -45.2 | 245678 | - |
| 基準方法 | -856.4 | -28.7 | 248923 | 180 |
| 本方法 | -623.1 | -22.5 | 247156 | 165 |
| **改善率** | **27.2%** | **21.6%** | **0.7%** | **8.3%** |

**表 2：aes_cipher_top 測試案例結果**

| 方法 | TNS (ps) | WNS (ps) | HPWL (μm) | 執行時間 (s) |
|-----|----------|----------|-----------|-------------|
| 初始解 | -2845.7 | -62.8 | 512340 | - |
| 基準方法 | -1678.3 | -38.4 | 518765 | 320 |
| 本方法 | -1234.6 | -31.2 | 515892 | 295 |
| **改善率** | **26.4%** | **18.8%** | **0.6%** | **7.8%** |

### 5.5.2 大型測試案例結果

**表 3：ariane 測試案例結果**

| 方法 | TNS (ps) | WNS (ps) | HPWL (μm) | 執行時間 (s) |
|-----|----------|----------|-----------|-------------|
| 初始解 | -15678.4 | -125.6 | 3456789 | - |
| 基準方法 | -9234.7 | -78.3 | 3502145 | 2580 |
| 本方法 | -7891.2 | -68.5 | 3489234 | 2410 |
| **改善率** | **14.5%** | **12.5%** | **0.4%** | **6.6%** |

### 5.5.3 結果視覺化

**圖 1：TNS 優化過程**

[此處應插入 TNS 隨迭代次數變化的折線圖]

**圖 2：佈局比較**

[此處應插入初始佈局與優化後佈局的對比圖]

**圖 3：關鍵路徑分佈**

[此處應插入關鍵路徑在晶片上的分佈熱圖]

## 5.6 結果分析

### 5.6.1 時序改善分析

實驗結果顯示：
1. TNS 平均改善 20-30%，證明方法有效降低整體時序違規
2. WNS 平均改善 15-22%，關鍵路徑得到優化
3. HPWL 增加幅度小於 1%，維持良好的線長

### 5.6.2 執行效率分析

1. 相較於基準方法，執行時間減少 6-8%
2. GPU 加速效果顯著，相較於 CPU 實作快 25X
3. 大型設計的優化效率略低，需進一步改善

### 5.6.3 方法優缺點

**優點**：
- 時序優化效果顯著
- 保持原有佈局的穩定性
- 適用於不同規模的設計

**缺點**：
- 參數敏感度較高，需針對不同案例調整
- 大型設計的記憶體需求高
- 某些極端案例收斂較慢

---

# 6. 專題重要貢獻

## 6.1 理論貢獻

1. **增量式時序驅動佈局方法**：提出結合深度學習與增量優化的新方法
2. **自適應 Net Weighting 策略**：開發基於動量的權重更新機制
3. **多目標優化框架**：平衡時序、線長和密度的目標函數設計

## 6.2 實作貢獻

1. **擴展 DREAMPlace**：增加增量優化模組，豐富工具功能
2. **自動化流程**：開發完整的實驗腳本，便於重現結果
3. **開源貢獻**：將部分程式碼開源，促進學術交流

## 6.3 實用價值

1. **競賽驗證**：在 ICCAD 2025 Contest 獲得良好結果
2. **產業應用**：方法可應用於實際晶片設計的 ECO 階段
3. **教育價值**：程式碼和文件可供後續學習參考

---

# 7. 團隊合作方式

## 7.1 團隊組成

本專題由 4 位成員組成（請根據實際情況調整）：
- **組長**：負責整體規劃、程式整合
- **組員 A**：負責文獻研究、演算法設計
- **組員 B**：負責程式實作、系統測試
- **組員 C**：負責實驗分析、文件撰寫

## 7.2 工作分配

| 成員 | 主要職責 | 次要職責 |
|-----|---------|---------|
| 組長 | 專題規劃、進度管理、程式整合 | 演算法設計 |
| 組員 A | 文獻研究、演算法設計 | 實驗設計 |
| 組員 B | 程式實作、系統測試 | 文件撰寫 |
| 組員 C | 實驗分析、結果整理、文件撰寫 | 程式測試 |

## 7.3 協作方式

### 7.3.1 會議安排
- **每週定期會議**：每週一下午 2:00，討論進度與問題
- **技術討論會議**：遇到技術難題時召開
- **期中期末報告**：向老師報告進度

### 7.3.2 使用工具
- **版本控制**：Git + GitHub
- **文件協作**：Google Docs / Overleaf
- **即時溝通**：LINE 群組
- **專案管理**：Trello / Notion

### 7.3.3 程式碼管理
- 使用 Git 進行版本控制
- 遵循統一的程式碼風格
- 進行 Code Review
- 撰寫詳細的註解和文件

## 7.4 遇到的挑戰與解決

### 挑戰 1：DREAMPlace 學習曲線陡峭
**解決方式**：
- 組員分工研讀不同模組
- 定期技術分享會
- 建立內部文件庫

### 挑戰 2：實驗結果不穩定
**解決方式**：
- 建立系統化的實驗流程
- 記錄詳細的實驗參數
- 使用版本控制追蹤變更

### 挑戰 3：時間管理困難
**解決方式**：
- 使用專案管理工具
- 設定里程碑和截止日期
- 定期檢討進度

---

# 8. 效能評估與成果

## 8.1 評估方法

### 8.1.1 定量評估
使用以下指標評估系統效能：
- **TNS**：Total Negative Slack
- **WNS**：Worst Negative Slack
- **HPWL**：Half-Perimeter Wire Length
- **Runtime**：執行時間
- **Memory Usage**：記憶體使用量

### 8.1.2 定性評估
- 佈局品質視覺化檢查
- 與基準方法的比較分析
- 不同參數設定的敏感度分析

## 8.2 綜合效能評估

### 8.2.1 整體效能總結

**表 4：所有測試案例綜合結果**

| 測試案例 | TNS 改善 | WNS 改善 | HPWL 變化 | 綜合得分改善 |
|----------|----------|----------|-----------|-------------|
| aes | 27.2% | 21.6% | +0.7% | 24.3% |
| aes_cipher_top | 26.4% | 18.8% | +0.6% | 22.5% |
| ac97_top | 23.8% | 19.2% | +0.8% | 21.2% |
| des | 29.5% | 24.3% | +0.5% | 26.8% |
| pci_bridge32 | 25.1% | 20.7% | +0.7% | 22.9% |
| ariane | 14.5% | 12.5% | +0.4% | 13.4% |
| **平均** | **24.4%** | **19.5%** | **+0.6%** | **21.9%** |

### 8.2.2 效能特性分析

1. **中小型設計**：
   - 優化效果最佳（20-30% 改善）
   - 收斂速度快
   - 記憶體需求合理

2. **大型設計**：
   - 優化效果較為保守（10-15% 改善）
   - 需要更多迭代次數
   - 記憶體需求較高

3. **極限案例**：
   - 初始解品質差時，改善空間大
   - 時序違規路徑少時，優化效果有限

## 8.3 競賽成果

### 8.3.1 ICCAD 2025 Contest 參賽結果
- **參賽隊伍名稱**：[隊伍名稱]
- **最終排名**：[排名]（若已知）
- **獲獎情況**：[若有獲獎請填寫]

### 8.3.2 與其他隊伍比較
[此部分可在競賽結束後補充]

## 8.4 其他成果

### 8.4.1 技術報告
完成 ICCAD Contest 要求的技術報告，詳細描述方法與結果

### 8.4.2 程式碼
- 開發約 5,000 行 Python 程式碼
- 建立完整的實驗腳本
- 撰寫詳細的使用文件

### 8.4.3 學習成果
- 深入理解 VLSI 佈局問題
- 掌握深度學習在 EDA 的應用
- 培養大型專題開發能力
- 增進團隊合作經驗

---

# 9. 結論

## 9.1 研究總結

本專題針對 VLSI 增量式時序驅動佈局優化問題進行深入研究，主要成果包括：

1. **方法創新**：
   - 提出結合 DREAMPlace 與增量優化的新方法
   - 開發自適應 net weighting 策略
   - 設計多目標優化框架

2. **實驗驗證**：
   - 在 ICCAD 2025 測試案例上驗證方法有效性
   - TNS 平均改善 24.4%，WNS 平均改善 19.5%
   - 維持良好的線長品質（HPWL 增加小於 1%）

3. **實用價值**：
   - 方法可應用於實際晶片設計流程
   - 執行效率滿足工業需求
   - 程式碼具有良好的擴展性

4. **團隊成長**：
   - 培養系統化解決複雜問題的能力
   - 掌握現代 EDA 工具的使用
   - 增進團隊協作與專案管理能力

## 9.2 研究限制

本研究仍存在以下限制：

1. **演算法層面**：
   - 參數敏感度較高，不同案例需調整
   - 大型設計的優化效果有待提升
   - 收斂速度在極端案例下較慢

2. **實作層面**：
   - 記憶體需求對超大型設計仍是挑戰
   - 某些進階特性尚未實作
   - 程式碼優化仍有改進空間

3. **實驗層面**：
   - 僅在 ASAP7 製程上測試
   - 缺乏更多真實工業案例驗證
   - 參數調整尚未完全系統化

## 9.3 未來展望

未來可從以下方向繼續改進：

### 9.3.1 短期改進（3-6 個月）

1. **演算法優化**：
   - 開發自動參數調整機制
   - 改進大型設計的優化策略
   - 加速收斂速度

2. **功能擴展**：
   - 支援更多時序約束類型
   - 整合功耗優化
   - 增加可繞線性考量

3. **程式優化**：
   - 降低記憶體使用量
   - 提升計算效率
   - 改善程式碼品質

### 9.3.2 中長期研究（6-12 個月）

1. **理論深化**：
   - 研究增量佈局的理論界限
   - 探索機器學習輔助決策
   - 開發新的優化目標函數

2. **應用擴展**：
   - 支援 3D IC 佈局
   - 整合其他 EDA 工具
   - 應用於其他製程節點

3. **產業合作**：
   - 與晶片公司合作驗證
   - 在真實設計案例上測試
   - 收集工業界反饋

### 9.3.3 學術研究

1. 將成果整理成學術論文投稿
2. 參加更多相關競賽驗證方法
3. 開源程式碼促進學術交流

## 9.4 心得與感想

透過本專題，我們獲得了寶貴的經驗：

1. **技術成長**：
   - 從零開始學習 VLSI 設計流程
   - 掌握大型開源專案的使用方法
   - 培養解決實際工程問題的能力

2. **團隊合作**：
   - 學習如何有效分工與協作
   - 培養溝通與協調能力
   - 體會團隊合作的重要性

3. **專案管理**：
   - 學習如何規劃長期專題
   - 培養時間管理能力
   - 累積專案開發經驗

4. **研究態度**：
   - 培養持續學習的習慣
   - 學習面對挑戰與挫折
   - 體會研究的樂趣與成就感

參加 ICCAD Contest 是一次珍貴的經驗，不僅驗證了我們的學習成果，也讓我們了解到學術研究與工業應用之間的差距。這些經驗將對我們未來的學習和職涯發展產生深遠的影響。

---

# 參考文獻

## 中文參考文獻

無

## 英文參考文獻

[1] Yibo Lin et al., "DREAMPlace: Deep Learning Toolkit-Enabled GPU Acceleration for Modern VLSI Placement," in *Proceedings of the 56th Annual Design Automation Conference (DAC)*, Las Vegas, NV, USA, 2019, pp. 1-6.

[2] Yibo Lin et al., "DREAMPlace: Deep Learning Toolkit-Enabled GPU Acceleration for Modern VLSI Placement," *IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems (TCAD)*, vol. 40, no. 4, pp. 748-761, 2021.

[3] Peiyu Liao et al., "DREAMPlace 4.0: Timing-driven Global Placement with Momentum-based Net Weighting," in *Proceedings of Design, Automation and Test in Europe (DATE)*, Antwerp, Belgium, 2022, pp. 939-944.

[4] Chung-Kuan Cheng et al., "RePlAce: Advancing Solution Quality and Routability Validation in Global Placement," *IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems (TCAD)*, vol. 38, no. 9, pp. 1717-1730, 2019.

[5] Tao Luo et al., "DREAMPlace 2.0: Open-Source GPU-Accelerated Global and Detailed Placement for Large-Scale VLSI Designs," *China Semiconductor Technology International Conference (CSTIC)*, Shanghai, China, 2020.

[6] Jiaqi Gu et al., "DREAMPlace 3.0: Multi-Electrostatics Based Robust VLSI Placement with Region Constraints," in *IEEE/ACM International Conference on Computer-Aided Design (ICCAD)*, Nov. 2020, pp. 1-9.

[7] Yifan Chen et al., "Stronger Mixed-Size Placement Backbone Considering Second-Order Information," in *IEEE/ACM International Conference on Computer-Aided Design (ICCAD)*, San Francisco, CA, USA, Oct. 2023.

[8] Andrew B. Kahng et al., "VLSI Physical Design: From Graph Partitioning to Timing Closure," Springer, 2011.

[9] Tung-Chieh Chen et al., "NTUplace3: An Analytical Placer for Large-Scale Mixed-Size Designs With Preplaced Blocks and Density Constraints," *IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems (TCAD)*, vol. 27, no. 7, pp. 1228-1240, 2008.

[10] Synopsys, "PrimeTime: Industry's Gold Standard Timing Signoff Solution," [Online]. Available: https://www.synopsys.com/implementation-and-signoff/signoff/primetime.html

[11] L. Cheng et al., "ePlace: Electrostatics-Based Placement Using Fast Fourier Transform and Nesterov's Method," *ACM Transactions on Design Automation of Electronic Systems (TODAES)*, vol. 20, no. 2, pp. 1-34, 2015.

[12] OpenROAD Project, "OpenROAD: Foundations and Realization of Open, Accessible Design," [Online]. Available: https://theopenroadproject.org/

[13] ASAP7 Predictive Process Design Kit, [Online]. Available: http://asap.asu.edu/asap/

---

**中華民國 113 年 12 月**

---

## 附錄說明

本範例報告提供完整的架構和內容建議，請根據您的實際專題進展情況：

1. **調整內容細節**：根據實際實作結果填入具體數據
2. **補充圖表**：添加實驗結果圖表和系統架構圖
3. **更新時間**：調整研究步驟的時間安排
4. **團隊資訊**：填入真實的組長組員資料
5. **競賽結果**：等競賽結束後補充最終成績

## 撰寫建議

1. **保持客觀**：用數據和事實說話
2. **邏輯清晰**：確保章節之間邏輯連貫
3. **圖文並茂**：適當使用圖表輔助說明
4. **格式統一**：嚴格遵守格式規定
5. **引用準確**：確保參考文獻格式正確






