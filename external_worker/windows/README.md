# External AI Image Worker (Windows)

This folder contains the standalone Windows client for FjordLens external AI image descriptions.

## Files

- `ai_billedbeskriver.py`: core image analysis script (CLI)
- `ai_billedbeskriver_gui.pyw`: GUI client that can process one image or run the external queue
- `Start AI Billedbeskriver.vbs`: helper launcher that starts the GUI without a console window
- `requirements.txt`: Python dependencies for this worker

## Prerequisites

1. Windows with Python 3.10+ installed
2. Ollama installed locally and running
3. A vision model in Ollama (for example `qwen2.5vl:7b`)
4. External AI descriptions enabled in FjordLens settings

## Setup

Open PowerShell in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

### GUI mode

- Double-click `Start AI Billedbeskriver.vbs`, or
- Run `pythonw.exe .\ai_billedbeskriver_gui.pyw`

In the GUI:

1. Paste your FjordLens connection link
2. Click `Kor ekstern ko`
3. Keep the app open while it processes queue items

### CLI mode (single image)

```powershell
python .\ai_billedbeskriver.py "C:\path\to\image.jpg"
```

## Environment variables

- `OLLAMA_HOST` (default: `http://localhost:11434`)
- `OLLAMA_VISION_MODEL` (default: `qwen2.5vl:7b`)

Example:

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$env:OLLAMA_VISION_MODEL = "qwen2.5vl:7b"
pythonw.exe .\ai_billedbeskriver_gui.pyw
```
