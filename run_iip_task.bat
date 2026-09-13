@echo off
cd /d D:\IIP_Obsidian_Integration_v1.0\iip_obsidian_integration_v1

:: Forca o Python a tratar stdout/stderr em UTF-8
set PYTHONIOENCODING=utf-8

echo ======================================================== >> logs\agendador.log
echo Iniciando execucao automatica em %date% %time% >> logs\agendador.log

.venv\Scripts\python.exe run_iip_engine.py >> logs\agendador.log 2>&1

echo Execucao finalizada. >> logs\agendador.log