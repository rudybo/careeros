@echo off
echo ╔══════════════════════════════════════╗
echo ║     CareerOS Deploy → srvsviluppo   ║
echo ╚══════════════════════════════════════╝
echo.

echo [1/4] Push codice su GitHub...
git push origin main
if errorlevel 1 (
    echo ERRORE: git push fallito.
    pause & exit /b 1
)

echo.
echo [2/4] Clone o pull sul server...
ssh rudy@srvsviluppo "if [ ! -d ~/CareerOS ]; then git clone git@github.com:rudybo/careeros.git ~/CareerOS; else cd ~/CareerOS && git pull; fi"

echo.
echo [3/4] Copia file sensibili...
scp backend\credentials.json rudy@srvsviluppo:~/CareerOS/backend/
scp backend\token.json       rudy@srvsviluppo:~/CareerOS/backend/ 2>nul
scp backend\.env             rudy@srvsviluppo:~/CareerOS/backend/

echo.
echo [4/4] Setup completo sul server...
ssh rudy@srvsviluppo "bash ~/CareerOS/scripts/server-setup.sh"

echo.
echo ✓ Deploy completato!
echo   Apri http://srvsviluppo nel browser.
echo.
pause
