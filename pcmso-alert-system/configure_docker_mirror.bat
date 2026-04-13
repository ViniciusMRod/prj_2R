@echo off
setlocal

echo ==========================================
echo   Configurar mirror Docker Hub
echo ==========================================

:: Caminho do daemon.json do Docker Desktop
set DOCKER_CONFIG=%USERPROFILE%\.docker
set DAEMON_FILE=%DOCKER_CONFIG%\daemon.json

:: Criar pasta se nao existir
if not exist "%DOCKER_CONFIG%" mkdir "%DOCKER_CONFIG%"

:: Gravar daemon.json com mirrors
echo Gravando %DAEMON_FILE%...
(
echo {
echo   "registry-mirrors": [
echo     "https://mirror.gcr.io",
echo     "https://dockerhub.azk8s.cn",
echo     "https://docker.mirrors.ustc.edu.cn"
echo   ]
echo }
) > "%DAEMON_FILE%"

echo.
echo Arquivo gravado:
type "%DAEMON_FILE%"

echo.
echo Reiniciando Docker Desktop...
taskkill /f /im "Docker Desktop.exe" >nul 2>&1
timeout /t 3 /nobreak >nul
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

echo.
echo Aguardando Docker reiniciar (30s)...
timeout /t 30 /nobreak >nul

:: Testar se o daemon esta respondendo
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker ainda nao respondeu. Aguarde mais 20s...
    timeout /t 20 /nobreak >nul
)

docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Docker nao respondeu. Abra o Docker Desktop manualmente e aguarde ficar pronto.
    pause
    exit /b 1
)

echo Docker pronto! Tentando pull do postgres:15...
docker pull postgres:15

if %errorlevel% neq 0 (
    echo.
    echo FALHA no pull mesmo com mirror.
    echo Tente as alternativas abaixo manualmente:
    echo   docker pull bitnami/postgresql:15
    echo   docker pull goharbor/harbor-db:v2.9.0
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   postgres:15 baixado com sucesso!
echo   Agora rode: start_db.bat
echo ==========================================
pause
endlocal
