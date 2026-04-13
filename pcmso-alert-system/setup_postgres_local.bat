@echo off
setlocal

echo ==========================================
echo   PCMSO - Setup PostgreSQL Local
echo ==========================================

set "PGBIN=D:\vinic\PostgreSQL17\bin"
set "PATH=%PATH%;%PGBIN%"

:: Pedir senha uma vez
echo.
set /p PGPASSWORD="Digite a senha do usuario postgres: "
set PGPASSWORD=%PGPASSWORD%

echo.
echo Testando conexao como postgres...
"%PGBIN%\psql.exe" -U postgres -p 5433 -c "SELECT 1;" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: senha incorreta ou servico PostgreSQL nao esta rodando.
    echo Verifique:
    echo   1. O servico PostgreSQL17 esta iniciado? ^(services.msc^)
    echo   2. A senha digitada esta correta?
    pause
    exit /b 1
)
echo Conexao OK.

echo.
echo Criando usuario pcmso_user...
"%PGBIN%\psql.exe" -U postgres -p 5433 -c "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pcmso_user') THEN CREATE ROLE pcmso_user LOGIN PASSWORD 'pcmso_password'; END IF; END $$;"

echo.
echo Criando banco pcmso_alerts...
"%PGBIN%\psql.exe" -U postgres -p 5433 -tc "SELECT 1 FROM pg_database WHERE datname = 'pcmso_alerts'" | findstr /c:"1" >nul 2>&1
if %errorlevel% neq 0 (
    "%PGBIN%\psql.exe" -U postgres -p 5433 -c "CREATE DATABASE pcmso_alerts OWNER pcmso_user ENCODING 'UTF8';"
    echo Banco criado.
) else (
    echo Banco ja existe.
)

echo.
echo Concedendo privilegios...
"%PGBIN%\psql.exe" -U postgres -p 5433 -c "GRANT ALL PRIVILEGES ON DATABASE pcmso_alerts TO pcmso_user;"

echo.
echo Criando tabelas e dados de teste...
python scripts/init_database.py
if %errorlevel% neq 0 (
    echo ERRO: init_database.py falhou.
    pause
    exit /b 1
)

python scripts/seed_test_data.py
if %errorlevel% neq 0 (
    echo ERRO: seed_test_data.py falhou.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Banco pronto!
echo   Host:     localhost:5433
echo   Database: pcmso_alerts
echo   User:     pcmso_user
echo   Password: pcmso_password
echo ==========================================
pause
endlocal
