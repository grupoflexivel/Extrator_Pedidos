@echo off
set PYTHON="C:\Program Files\Python314\python.exe"

set SCRIPT_PATH=C:\Automacoes\Gerador_Relatorio_Pedidos\main.py

%PYTHON% %SCRIPT_PATH%
set "EXIT_CODE=%ERRORLEVEL%"

echo Processo finalizado com codigo %EXIT_CODE%

exit /b %EXIT_CODE%
