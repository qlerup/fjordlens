# External AI image worker for Windows

The standalone FjordLens client for local Ollama image descriptions. This worker is separate from built-in AI containers and the manual ChatGPT account-analysis experiment.

## Files

- `ai_billedbeskriver.py`: single-image CLI analysis.
- `ai_billedbeskriver_gui.pyw`: GUI for a single image or the server's external queue.
- `Start AI Billedbeskriver.vbs`: GUI launcher without a console window.
- `requirements.txt`: worker Python dependencies.

## Prerequisites

Windows with Python 3.10+, a running local [Ollama](https://ollama.com/download), the `qwen2.5vl:7b` vision model, and external descriptions enabled in FjordLens.

Install Ollama, open PowerShell and pull the model:

```powershell
ollama pull qwen2.5vl:7b
ollama list
```

Start it with `ollama serve` if it is not already running. See the [model catalog](https://ollama.com/library) for available models.

## Setup

Open PowerShell in this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

Double-click `Start AI Billedbeskriver.vbs`, or run `pythonw.exe .\ai_billedbeskriver_gui.pyw`. Paste the generated FjordLens connection link, select Run external queue and leave the program open while jobs run. The worker uses local Ollama and posts captions/tags through scoped external APIs; do not share the connection secret.

For a single image:

```powershell
python .\ai_billedbeskriver.py "C:\path\to\image.jpg"
```

Optional environment overrides:

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
$env:OLLAMA_VISION_MODEL = "qwen2.5vl:7b"
pythonw.exe .\ai_billedbeskriver_gui.pyw
```

Defaults are `http://localhost:11434` and `qwen2.5vl:7b`. Configure server-side concurrency/device settings separately in FjordLens; installing this client does not change browser/media settings.
