@echo off
echo ========================================
echo   Avvio CareerOS
echo ========================================

echo Libero la porta 8000 da eventuali backend zombie...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo Avvio backend (FastAPI :8000)...
start "CareerOS Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\uvicorn app.main:app --reload"

echo Avvio frontend (Vite :5173)...
start "CareerOS Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Attendo l'avvio dei servizi...
timeout /t 8 /nobreak >nul

echo Apro il browser su http://localhost:5173 ...
start "" http://localhost:5173

exit
