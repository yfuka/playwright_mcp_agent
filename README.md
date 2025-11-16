# playwright-mcp-agent

ローカルの **LLM（例: Llama 3.1）** と **MCP (Playwright)** を組み合わせて、
ブラウザで調べものをしてくれるエージェントのサンプルです。

- LLM: 任意の OpenAI 互換 LLM（例: Ollama で動かす Llama 3.1）
- MCP サーバ:
  - [Playwright MCP](https://github.com/microsoft/playwright-mcp) – ブラウザ操作・要素取得など 
- Python: [uv](https://docs.astral.sh/uv/) による依存管理・実行 

---

## 1. 前提

### 1.1 必要なもの

- Node.js (Playwright MCP は Node 18+推奨) 
- Google Chrome（安定版） 
- Python 3.11 以上
- [uv](https://docs.astral.sh/uv/)（高速な Python パッケージ & プロジェクトマネージャ） 
- [Ollama](https://ollama.com)（ローカル LLM 実行環境）

---

## 2. uv でのセットアップ

### 2.1 uv のインストール

uv 本体のインストール方法は公式ドキュメントを参照してください。Linux/macOS では
インストールスクリプト、Windows ではインストーラが用意されています。

```bash
# 例 (Linux / macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
````

インストール後、バージョンを確認します。

```bash
uv --version
```

### 2.2 プロジェクトの作成

このリポジトリを clone 済みの場合は、そのまま `uv sync` で依存を入れられます。

```bash
cd playwright-mcp-agent

# 依存関係をインストール (.venv を自動で作成)
uv sync
```

依存は `pyproject.toml` に記載されており、以下が入ります。

* `mcp` – MCP Python SDK
* `openai` – OpenAI 互換クライアント
* `python-dotenv` – `.env` から LLM 設定を読み込むためのユーティリティ

### 2.3 `.env` の設定

LLM のモデル名・エンドポイント URL・API キーは `.env` に記載します。
プロジェクトルートに以下のようなファイルを置いてください（値は必要に応じて変更）。

```dotenv
MODEL_NAME=llama3.1
BASE_URL=http://localhost:11434/v1
API_KEY=ollama
```

`python-dotenv` によって自動的に読み込まれ、`llm_client.py` で利用されます。

---

## 3. Ollama で Llama 3.1 を起動する

### 3.1 Ollama のインストール

Ollama のインストール方法は公式サイトの手順に従ってください。

### 3.2 モデルの準備とサーバ起動

```bash
# Llama 3.1 モデルを取得
ollama pull llama3.1

# Ollama のバックグラウンドサーバを起動
ollama serve
```

Ollama はデフォルトで `http://localhost:11434/v1` に OpenAI 互換の
`/v1/chat/completions` を提供します。このエージェントはそのエンドポイントに対して
`model="llama3.1"` でリクエストを送ります。 `.env` の `BASE_URL` と `MODEL_NAME`
をここに合わせておけば、追加の設定変更は不要です。

---

## 4. MCP サーバ (Playwright)

### 4.1 Playwright MCP

Playwright MCP は Playwright を用いたブラウザ自動操作を MCP 経由で提供します。

Node.js と npm が入っていれば、グローバルインストールしておくとよいです。

```bash
npm install -g @playwright/mcp
```

本プロジェクトでは、Python 側から `npx @playwright/mcp@latest` で直接起動します。

---

## 5. エージェントの実行（uv 利用）

### 5.1 CLI コマンドで起動

`pyproject.toml` には `playwright-mcp-agent` というスクリプトエントリが定義されています。

```bash
cd playwright-mcp-agent

# 仮想環境付きで CLI を実行
uv run playwright-mcp-agent
```

もしくはモジュールとして実行することもできます。

```bash
uv run python -m playwright_mcp_agent
```

### 5.2 対話例

起動すると、使用可能な MCP ツール一覧が表示され、その後 `You>` プロンプトが出ます。

```text
You> https://developer.mozilla.org/ja/docs/Web/JavaScript を開いて、Promise の概要を調べて日本語で説明して。
```

Playwright MCP はページ遷移や要素取得、スクリーンショット取得などに向いています。

---

## 6. vLLM を使いたい場合（オプション）

Llama 3.1 を vLLM でホストして OpenAI 互換サーバ経由で叩くこともできます。

### 6.1 vLLM の OpenAI 互換サーバ起動

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --port 8000 \
  --api-key local-key
```

### 6.2 `.env` の変更

vLLM を利用する場合は `.env` を以下のように書き換えてください。

```dotenv
MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
BASE_URL=http://localhost:8000/v1
API_KEY=local-key
```

コードを触らずにエンドポイントを切り替えられます。

---

## 7. ファイル構成まとめ

```text
playwright-mcp-agent/
├── pyproject.toml         # uv / pip 互換のプロジェクト設定
├── README.md              # このファイル
└── src/
    └── playwright_mcp_agent/
        ├── __init__.py    # パッケージ概要
        ├── __main__.py    # python -m でのエントリ
        ├── llm_client.py  # LLM クライアント設定
        ├── mcp_servers.py # MCP サーバ管理・init_servers・dispatch_tool_call
        ├── agent_core.py  # SYSTEM_PROMPT と run_agent_once
        └── cli.py         # init_servers を使った CLI REPL
```
