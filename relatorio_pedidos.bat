@echo off
set PYTHON="C:\Program Files\Python314\python.exe"

set SCRIPT_PATH=C:\Automacoes\Gerador_Relatorio_Pedidos\main.py

cd /d C:\Automacoes\Gerador_Relatorio_Pedidos

%PYTHON% %SCRIPT_PATH% >> C:\Automacoes\Gerador_Relatorio_Pedidos\logs\saida_bat.log 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo [%DATE% %TIME%] Processo finalizado com codigo %EXIT_CODE% >> C:\Automacoes\Gerador_Relatorio_Pedidos\logs\saida_bat.log

exit %EXIT_CODE%
