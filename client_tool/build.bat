@echo off
REM WoWS Replay Auto Uploader ビルドスクリプト

echo ================================
echo WoWS Replay Auto Uploader Build
echo ================================
echo.

REM 依存パッケージのインストール確認
echo 依存パッケージをインストール中...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo エラー: 依存パッケージのインストールに失敗しました
    pause
    exit /b 1
)
echo.

REM 既存のビルドディレクトリを削除
echo 既存のビルドディレクトリを削除中...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.

REM PyInstallerでビルド
echo ビルド中...
pyinstaller build.spec
if %ERRORLEVEL% NEQ 0 (
    echo エラー: ビルドに失敗しました
    pause
    exit /b 1
)
echo.

REM 成果物を確認
if exist dist\wows_replay_uploader.exe (
    echo ================================
    echo ビルド成功！
    echo ================================
    echo.
    echo 実行ファイル: dist\wows_replay_uploader.exe
    echo.

    REM config.yaml.templateもコピー
    copy config.yaml.template dist\config.yaml.template
    echo 設定ファイルテンプレートをコピーしました: dist\config.yaml.template
    echo.

    REM READMEもコピー
    copy README.md dist\README.md
    echo READMEをコピーしました: dist\README.md
    echo.

    echo 配布用ファイル:
    echo   - dist\wows_replay_uploader.exe
    echo   - dist\config.yaml.template
    echo   - dist\README.md
    echo.
) else (
    echo エラー: 実行ファイルが生成されませんでした
    pause
    exit /b 1
)

pause
