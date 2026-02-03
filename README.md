# tender-tracker

追蹤台灣政府標案的 CLI 工具，為光聚晶電聯合（Star Fusion Group）篩選適合投標的案件。

## 安裝

```bash
uv sync
```

需求：Python >= 3.12

## 設定

### config.yaml

專案根目錄的 `config.yaml` 控制篩選條件：

```yaml
keywords:          # 關鍵字篩選（標案名稱 / 分類）
  - AI
  - 人工智慧
  - 系統開發
  - ...

orgs:              # 關注的招標機關
  - 數位發展部
  - 國防部
  - ...

budget:
  min: 150000      # 最低預算（NT$）
  max: 3000000     # 最高預算（NT$）

procurement_types: # 採購類別
  - 勞務

schedule:
  fetch_interval: "0 9,14 * * 1-5"  # 排程（參考用）
```

### 環境變數

`evaluate` 指令需要 Claude API：

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 指令

```bash
uv run python -m tender_tracker [OPTIONS] COMMAND [ARGS]
```

全域選項：

| 選項 | 說明 |
|------|------|
| `--config PATH` | 指定 config.yaml 路徑 |
| `--db PATH` | 指定 SQLite 資料庫路徑 |
| `-v` / `--verbose` | 顯示詳細日誌 |

### fetch — 抓取標案

依日期從 [mlwmlw API](https://pcc.mlwmlw.org) 抓取標案，再用 `config.yaml` 的關鍵字篩選後存入資料庫。

```bash
# 抓取今天的標案
uv run python -m tender_tracker fetch

# 抓取指定日期
uv run python -m tender_tracker fetch --date 2026-02-01

# 抓取最近 3 天
uv run python -m tender_tracker fetch --days 3
```

| 選項 | 說明 |
|------|------|
| `--date YYYY-MM-DD` | 指定起始日期（預設：今天） |
| `--days N` | 往前抓取天數（預設：1） |

### search — 搜尋標案

用自訂關鍵字直接搜尋 mlwmlw API，結果存入資料庫。

```bash
uv run python -m tender_tracker search "人工智慧"
```

### list — 列出標案

列出已存入資料庫的標案。

```bash
# 列出全部（最多 50 筆）
uv run python -m tender_tracker list

# 列出近 7 天、最多 20 筆
uv run python -m tender_tracker list --days 7 --limit 20

# 只看已評估的標案
uv run python -m tender_tracker list --evaluated
```

| 選項 | 說明 |
|------|------|
| `--days N` | 只顯示最近 N 天 |
| `--limit N` | 最多顯示幾筆（預設：50） |
| `--evaluated` | 只顯示已評估的標案 |

### evaluate — AI 評估

使用 Claude AI 評估尚未評估的標案，判斷是否適合投標。

```bash
# 評估最多 10 筆（預設）
uv run python -m tender_tracker evaluate

# 評估最多 5 筆
uv run python -m tender_tracker evaluate --limit 5
```

| 選項 | 說明 |
|------|------|
| `--limit N` | 最多評估幾筆（預設：10） |

評估結果包含：相關度分數（0.0–1.0）、是否適合投標、建議行動（bid / skip / review_further）、匹配能力、判斷理由。

### report — 統計摘要

顯示資料庫中的標案統計。

```bash
uv run python -m tender_tracker report
```

輸出：標案總數、已評估、適合投標、待評估數量。

### history — 追蹤記錄

查看近 N 天的標案與評估紀錄。

```bash
# 近 30 天（預設）
uv run python -m tender_tracker history

# 近 7 天
uv run python -m tender_tracker history --days 7
```

## 典型工作流程

```
fetch → list → evaluate → report
```

1. **fetch** — 抓取當天標案，關鍵字篩選後存入 DB
2. **list** — 瀏覽篩選結果
3. **evaluate** — 用 AI 評估適合度
4. **report** — 查看統計摘要

## 專案結構

```
tender-tracker/
├── config.yaml                    # 篩選設定
├── pyproject.toml
├── src/tender_tracker/
│   ├── __main__.py                # 進入點
│   ├── main.py                    # CLI 指令定義（Click）
│   ├── models.py                  # Pydantic 資料模型
│   ├── storage.py                 # SQLite 存取層
│   ├── config.py                  # 設定載入
│   ├── evaluator.py               # Claude AI 評估引擎
│   ├── filters.py                 # 標案篩選邏輯
│   ├── reports.py                 # Rich 終端輸出
│   └── sources/
│       ├── base.py                # TenderSource 抽象基底
│       ├── mlwmlw.py              # mlwmlw API（主要來源）
│       ├── g0v.py                 # g0v API（備用）
│       └── opendata.py            # 政府開放資料 XML
└── tests/
    ├── conftest.py
    ├── test_evaluator.py
    ├── test_filters.py
    ├── test_sources.py
    └── test_storage.py
```

## 開發

```bash
# 執行測試
uv run pytest tests/ -v

# 測試覆蓋率
uv run pytest --cov=src --cov-report=term-missing

# Lint + Format
uv run ruff check . --fix && uv run ruff format .
```
