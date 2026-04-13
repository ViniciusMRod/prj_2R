@echo off
setlocal

echo ==========================================
echo   PCMSO Alert System - Inicializacao
echo ==========================================

:: 1. Instalar dependencias Python
echo.
echo [1/4] Instalando dependencias Python...
pip install --no-cache-dir -r requirements.txt
if %errorlevel% neq 0 (
    echo ERRO: pip install falhou.
    pause
    exit /b 1
)

:: 2. Subir PostgreSQL via Docker
echo.
echo [2/4] Subindo PostgreSQL (Docker)...
docker-compose up -d postgres
if %errorlevel% neq 0 (
    echo ERRO: docker-compose falhou. Verifique se o Docker Desktop esta rodando.
    pause
    exit /b 1
)

:: Aguardar banco ficar pronto
echo Aguardando PostgreSQL ficar pronto...
timeout /t 10 /nobreak >nul

:: 3. Inicializar banco e dados de teste
echo.
echo [3/4] Inicializando banco de dados...
python scripts/init_database.py
if %errorlevel% neq 0 (
    echo ERRO: init_database.py falhou.
    pause
    exit /b 1
)

python scripts/seed_test_data.py
if %errorlevel% neq 0 (
    echo AVISO: seed_test_data.py falhou (dados de teste nao carregados).
)

:: 4. Iniciar API FastAPI
echo.
echo [4/4] Iniciando FastAPI na porta 5000...
echo Acesse: http://localhost:5000/validacao
echo Pressione Ctrl+C para encerrar.
echo.
python -m uvicorn src.validation_interface.web_validator:app --reload --host 0.0.0.0 --port 5000

endlocal
