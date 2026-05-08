# Araca Insights®

Araca Insights® is a Python application for semiconductor wafer polishing analytics, combining:

- a **PyQt6 desktop app** for project/file management and report workflows
- an embedded **Dash/Plotly dashboard** for interactive analysis and visualization
- an optional **local AI assistant** (Ollama + FLAML) for exploratory queries and removal prediction

## Repository structure

- `core/` — data parsing and report models (`RawFile`, `Report`)
- `desktop/` — PyQt6 desktop UI
- `dashboard/` — Dash application, plots, and analytics callbacks
- `ai/` — local LLM agent, tools, and AutoML manager
- `Sample_Full_Data/` — sample project fixture (`project.json` + `.dat` files)
- `docs/` — project and architecture notes

## Requirements

- Python 3.11+
- Dependencies from `requirements.txt`
- Optional for AI Agent tab: local [Ollama](https://ollama.com/) with model `qwen3.5:35b`

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

## Notes

- The desktop app hosts the dashboard internally (default local URL: `http://127.0.0.1:8050`).
- Use `Sample_Full_Data/project.json` to quickly load a representative dataset.
