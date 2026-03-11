@echo off
setlocal
echo ==================================================
echo   交易鬧鐘 - 環境強制清理工具 (v2.7)
echo ==================================================
echo.
echo 正在偵測並清理可能的背景鬧鐘進程...
echo.

:: 殺掉 python.exe 和 pythonw.exe
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul

echo.
echo [檢查結果]：如果上方顯示「找不到工作」，代表該類進程已清理乾淨。
echo.
echo 正在清理暫存 Mutex 狀態...
timeout /t 2 >nul

echo.
echo 清理完成！
echo 現在您可以雙擊 TradingAlarm.bat 重新啟動「唯一一個」鬧鐘了。
echo.
pause
