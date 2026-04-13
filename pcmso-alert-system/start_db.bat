@echo off
setlocal

echo ==========================================
echo   PCMSO - Subir banco de dados
echo ==========================================

:: 1. Instalar dependencias minimas
echo.
echo [1/3] Instalando dependencias Python...
pip install --no-cache-dir python-dotenv sqlalchemy psycopg2-binary alembic python-dateutil python-bcrypt
if %errorlevel% neq 0 (
    echo ERRO: pip install falhou.
    pause
    exit /b 1
)

:: 2. Verificar se imagem existe localmente antes de subir
echo.
echo [2/3] Subindo PostgreSQL...
docker image inspect postgres:15 >nul 2>&1
if %errorlevel% neq 0 (
    echo Imagem postgres:15 nao encontrada localmente.
    echo Execute primeiro: configure_docker_mirror.bat
    pause
    exit /b 1
)
docker-compose up -d postgres
if %errorlevel% neq 0 (
    echo ERRO: docker-compose falhou. Verifique se o Docker Desktop esta rodando.
    pause
    exit /b 1
)

echo Aguardando PostgreSQL ficar pronto ^(15s^)...
timeout /t 15 /nobreak >nul

:: 3. Criar tabelas e seed
echo.
echo [3/3] Criando tabelas e dados de teste...
python scripts/init_database.py
if %errorlevel% neq 0 (
    echo ERRO: init_database.py falhou. Verifique se o container esta healthy.
    pause
    exit /b 1
)

python scripts/seed_test_data.py
if %errorlevel% neq 0 (
    echo AVISO: seed_test_data.py falhou.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Banco pronto! Conexao:
echo   Host:     localhost:5432
echo   Database: pcmso_alerts
echo   User:     pcmso_user
echo   Password: pcmso_password
echo ==========================================
pause
endlocal
