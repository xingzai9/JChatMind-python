@echo off
echo ============================================================
echo  JChatMind DB Migration (via docker exec, no pg_dump needed)
echo  FROM: jchatmind-postgres  (localhost:5432/jchatmind)
echo  TO:   jchatmind-py-postgres (localhost:5433/jchatmind_py)
echo ============================================================

set BACKUP_FILE=%~dp0jchatmind_backup.dump

echo.
echo [1/4] Starting target container...
docker compose -f "%~dp0..\docker-compose.yml" up -d postgres
timeout /t 8 /nobreak >nul
echo Done.

echo.
echo [2/4] Dumping from source container jchatmind-postgres...
docker exec -e PGPASSWORD=postgres jchatmind-postgres pg_dump -U postgres -d jchatmind -Fc -f /tmp/backup.dump
if %errorlevel% neq 0 (
    echo ERROR: Dump failed. Is jchatmind-postgres running?
    pause
    exit /b 1
)
docker cp jchatmind-postgres:/tmp/backup.dump "%BACKUP_FILE%"
echo Dump saved to %BACKUP_FILE%

echo.
echo [3/4] Restoring to jchatmind-py-postgres...
docker cp "%BACKUP_FILE%" jchatmind-py-postgres:/tmp/backup.dump
docker exec -e PGPASSWORD=postgres jchatmind-py-postgres pg_restore -U postgres -d jchatmind_py --no-owner --no-privileges -Fc /tmp/backup.dump
echo Restore done (some extension warnings are normal).

echo.
echo [4/4] Migration complete!
echo.
echo Next step - update your .env file:
echo   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/jchatmind_py
echo.
pause
