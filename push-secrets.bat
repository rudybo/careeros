@echo off
echo Copia file sensibili su srvsviluppo...
scp backend\credentials.json rudy@srvsviluppo:~/CareerOS/backend/
scp backend\token.json       rudy@srvsviluppo:~/CareerOS/backend/
scp backend\.env             rudy@srvsviluppo:~/CareerOS/backend/
echo.
echo Fatto - segreti aggiornati sul server.
pause
