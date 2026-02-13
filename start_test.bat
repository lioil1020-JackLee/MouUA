@echo off
REM ModUA 測試腳本 - 啟動選項測試

echo ModUA 啟動選項:
echo 1. 正常啟動
echo 2. 自動啟動 Runtime
echo 3. 載入專案並自動啟動 Runtime
echo 4. 以最小化狀態啟動
echo.

set /p choice="請選擇啟動方式 (1-4): "

if "%choice%"=="1" goto normal
if "%choice%"=="2" goto runtime
if "%choice%"=="3" goto project
if "%choice%"=="4" goto minimized
goto end

:normal
echo 正常啟動 ModUA...
python ModUA.py
goto end

:runtime
echo 啟動 ModUA 並自動啟動 Runtime...
python ModUA.py --start-runtime
goto end

:project
echo 啟動 ModUA，載入專案並自動啟動 Runtime...
if exist "1_serial.json" (
    python ModUA.py --load-project "1_serial.json" --start-runtime
) else (
    echo 找不到專案文件，將正常啟動
    python ModUA.py --start-runtime
)
goto end

:minimized
echo 以最小化狀態啟動 ModUA...
python ModUA.py --minimized
goto end

:end
pause