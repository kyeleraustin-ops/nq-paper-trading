@echo off
cd /d "%~dp0"
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting NQ Paper Trading Bot...
python main.py
pause
