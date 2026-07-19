# Hermes HUD Web UI — Windows installer
# uv (Python) + nvm-windows (Node.js) を前提とする。
#
# 実行ポリシーでブロックされる場合は以下のいずれかで実行してください:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"

Write-Host "☤ Hermes HUD Web UI — Install (Windows)"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# uv の存在チェック
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "✗ uv が見つかりません"
    Write-Host "  インストール: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
}
Write-Host "✔ uv: $(uv --version)"

# nvm-windows の存在チェック
if (-not (Get-Command nvm -ErrorAction SilentlyContinue)) {
    Write-Host "✗ nvm-windows が見つかりません"
    Write-Host "  インストール: https://github.com/coreybutler/nvm-windows"
    exit 1
}

# Node.js 22 (LTS) をセットアップ（既にインストール済みならスキップされる）
# frontend の vite@8 系が Node 20.19+/22.12+ を要求するため 18 系は不可。
Write-Host "→ Node.js 22 をセットアップ中..."
nvm install 22 | Out-Null
nvm use 22 | Out-Null

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "✗ Node.js のセットアップに失敗しました（nvm use 22 を確認してください）"
    exit 1
}

# nvm use は管理者権限がないと失敗することがあるため、実際のバージョンを検証する
$nodeMajor = [int]((node --version) -replace '^v', '' -split '\.')[0]
if ($nodeMajor -lt 20) {
    Write-Host "✗ Node.js の切り替えに失敗しました（現在: $(node --version)、必要: 20.19+/22.12+）"
    Write-Host "  管理者権限の PowerShell で 'nvm use 22' を実行してから再試行してください"
    exit 1
}
Write-Host "✔ Node: $(node --version)"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "✗ npm が見つかりません"
    exit 1
}

# Hermes データディレクトリの確認
$hermesDir = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:USERPROFILE ".hermes" }
if (-not (Test-Path $hermesDir)) {
    Write-Host ""
    Write-Host "⚠ Hermes データが見つかりません: $hermesDir"
    Write-Host "  Hermes エージェントが動くまでダッシュボードは空の状態になります。"
    Write-Host "  対処:"
    Write-Host "    1. 先に Hermes をインストールして実行する"
    Write-Host "    2. HERMES_HOME 環境変数でエージェントのデータディレクトリを指定する"
    Write-Host ""
}

# 仮想環境の作成（uv）
if (-not (Test-Path ".venv")) {
    Write-Host "→ 仮想環境を作成中..."
    uv venv --python 3.11
    Write-Host "✔ 仮想環境を作成しました"
} else {
    Write-Host "✔ 仮想環境は既に存在します"
}

# バックエンドのインストール
Write-Host "→ hermes-hudui をインストール中..."
uv pip install -e . -q
Write-Host "✔ バックエンドをインストールしました"

# フロントエンドのビルド
Write-Host "→ フロントエンドをビルド中..."
Push-Location frontend
npm install --silent
npm run build
Pop-Location

# 静的ファイルのデプロイ
Write-Host "→ フロントエンドをデプロイ中..."
New-Item -ItemType Directory -Force -Path "backend\static\assets" | Out-Null
Copy-Item "frontend\dist\index.html" "backend\static\" -Force
Copy-Item "frontend\dist\assets\*" "backend\static\assets\" -Force -Recurse
Write-Host "✔ フロントエンドのビルド・デプロイが完了しました"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "✔ 準備完了。起動方法:"
Write-Host ""
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  hermes-hudui"
Write-Host ""
Write-Host "  もしくは仮想環境を有効化せず:"
Write-Host "  uv run hermes-hudui"
Write-Host ""
Write-Host "  http://localhost:3001 を開いてください"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
