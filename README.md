# tender-tracker

追蹤台灣政府標案的 CLI 工具，透過 AI 評估標案與團隊能力的匹配度，篩選適合投標的案件。

## 功能特色

- 自動抓取政府電子採購網標案（mlwmlw API、ebuying 共契）
- 關鍵字 / 機關 / 預算 / 採購類別篩選
- **可插拔 LLM 後端**：支援本地 vLLM（開源模型）或 Claude API
- AI 評估標案相關度，產生投標建議
- SQLite 本地儲存，支援 CSV 匯出

## 安裝

```bash
git clone <repo-url>
cd tender-tracker
cp config.yaml.example config.yaml
# 編輯 config.yaml，填入你的 team_profile
uv sync
```

需求：Python >= 3.12

## 設定

### config.yaml

複製 `config.yaml.example` 為 `config.yaml`，並根據需求修改：

```yaml
keywords:          # 關鍵字篩選（標案名稱 / 分類）
  - AI
  - 人工智慧
  - 系統開發

orgs:              # 關注的招標機關
  - 數位發展部
  - 國防部

budget:
  min: 150000      # 最低預算（NT$）
  max: 3000000     # 最高預算（NT$）

procurement_types: # 採購類別
  - 勞務

llm:
  backend: vllm                      # "vllm" 或 "claude"
  model: Qwen/Qwen3-8B-Instruct      # 模型名稱
  api_base: http://localhost:8000/v1 # vLLM server URL
  team_profile: |
    貴公司核心技術能力：
    1. AI / ML
    2. 軟體開發
    ...
```

### LLM 後端設定

#### 選項 1：vLLM（本地開源模型，推薦）

```bash
# 在有 GPU 的機器上啟動 vLLM server
pip install vllm
vllm serve Qwen/Qwen3-8B-Instruct --port 8000 --max-model-len 8192
```

#### 選項 2：Claude API

需要已安裝並認證 [Claude Code CLI](https://github.com/anthropics/claude-code)：

```bash
npm install -g @anthropic-ai/claude-code
claude  # 登入
```

然後在 `config.yaml` 設定：
```yaml
llm:
  backend: claude
  model: claude-sonnet-4-5-20250929
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

```bash
# 抓取今天的標案
uv run python -m tender_tracker fetch

# 抓取指定日期
uv run python -m tender_tracker fetch --date 2026-02-01

# 抓取最近 3 天
uv run python -m tender_tracker fetch --days 3
```

### search — 搜尋標案

```bash
uv run python -m tender_tracker search "人工智慧"
```

### list — 列出標案

```bash
# 列出全部（最多 50 筆）
uv run python -m tender_tracker list

# 列出近 7 天、最多 20 筆
uv run python -m tender_tracker list --days 7 --limit 20

# 只看已評估的標案
uv run python -m tender_tracker list --evaluated
```

### evaluate — AI 評估

```bash
# 評估最多 10 筆（預設）
uv run python -m tender_tracker evaluate

# 評估最多 5 筆，並發 10
uv run python -m tender_tracker evaluate --limit 5 -c 10
```

### export — 匯出 CSV

```bash
uv run python -m tender_tracker export -o tenders.csv
```

### report — 統計摘要

```bash
uv run python -m tender_tracker report
```

## 典型工作流程

```
fetch → list → evaluate → export
```

1. **fetch** — 抓取當天標案
2. **list** — 瀏覽篩選結果
3. **evaluate** — AI 評估適合度
4. **export** — 匯出結果

## 專案結構

```
tender-tracker/
├── config.yaml.example            # 設定範例
├── pyproject.toml
├── src/tender_tracker/
│   ├── main.py                    # CLI 指令定義
│   ├── models.py                  # Pydantic 資料模型
│   ├── storage.py                 # SQLite 存取層
│   ├── evaluator.py               # AI 評估引擎
│   ├── llm/                       # LLM 後端抽象層
│   │   ├── base.py                # LLMBackend ABC
│   │   ├── config.py              # LLMConfig
│   │   ├── vllm_backend.py        # vLLM + Instructor
│   │   └── claude_backend.py      # Claude Agent SDK
│   └── sources/
│       ├── mlwmlw.py              # mlwmlw API
│       └── ebuying.py             # 共契電子採購
└── tests/
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

## License

MIT
