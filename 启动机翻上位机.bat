@echo off
cd /d %~dp0
python mt_gui.py
if errorlevel 1 pause
