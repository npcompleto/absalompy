@echo off
SETLOCAL EnableDelayedExpansion

echo.
echo ===========================================
echo    Absalom OS - Windows Installer ^& Start
echo ===========================================
echo.

:: Verifica presenza Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python non trovato. Per favore installalo da python.org e assicurati che sia nel PATH.
    pause
    exit /b
)

:: Creazione Ambiente Virtuale se non esiste
if not exist venv (
    echo [INFO] Creazione ambiente virtuale Python (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Impossibile creare l'ambiente virtuale.
        pause
        exit /b
    )
)

:: Attivazione Ambiente Virtuale e installazione dipendenze
echo [INFO] Verifica e installazione dipendenze...
call venv\Scripts\activate
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Errore durante l'installazione delle dipendenze.
    pause
    exit /b
)

:: Verifica FFmpeg (necessario per ffplay)
ffplay -version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ATTENZIONE] 'ffplay' (componente di FFmpeg) non trovato nel PATH.
    echo Absalom non sara in grado di parlare senza FFmpeg.
    echo Per favore:
    echo 1. Scarica FFmpeg da https://ffmpeg.org/download.html
    echo 2. Estrai l'archivio
    echo 3. Aggiungi la cartella 'bin' alle variabili d'ambiente (PATH)
    echo.
    pause
)

:: Avvio Face Server in una finestra separata (minimizzata o in background)
echo [INFO] Avvio Robot Face API (faccia) in una nuova finestra...
start "Absalom Face Server" cmd /k "venv\Scripts\python face_server.py"

:: Attendi qualche secondo per permettere al server Flask di avviarsi
echo [INFO] Attesa boot del server (5s)...
timeout /t 5 >nul

:: Avvio Assistente Absalom principale
echo [INFO] Avvio Assistente Absalom...
echo.
python absalom.py %*

echo.
echo [INFO] Sessione Absalom terminata.
pause
