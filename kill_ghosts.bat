@echo off
echo 正在清理所有背景中的交易鬧鐘進程...
taskkill /F /IM python.exe /T
echo.
echo 清理完成！現在您可以重新啟動 TradingAlarm.bat 使用新版本了。
pause
