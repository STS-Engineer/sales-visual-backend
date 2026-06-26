# Sales Visual — Backend

FastAPI-based backend for the Sales Visual platform. Currently provides project scaffolding with a health-check endpoint; business logic will be added incrementally.

## Tech Stack

- **Python 3.11+**
- **FastAPI** – async web framework
- **Uvicorn** – ASGI server
- **Pydantic / Pydantic-Settings** – data validation & config management
- **httpx** – async HTTP client (used for Monday.com integration later)

## Project Structure

```
sales-visual-backend/
├── app/
│   ├── __init__.py
│   ├── core/          # Config, database, security, shared utilities
│   ├── api/           # Route definitions
│   ├── sync/          # Monday.com sync logic (to be implemented)
│   └── modules/       # Business-logic modules (to be implemented)
├── main.py            # Application entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11 or newer
- `pip` (or `uv` for faster installs)

### Setup

```bash
# 1. Navigate to the backend directory
cd sales-visual-backend

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
#    Windows:
.venv\Scripts\activate
#    macOS / Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy and review environment variables
cp .env.example .env
```

### Running the server

```bash
uvicorn main:app --reload
```

The API will be available at **http://localhost:8000**.  
Interactive docs (Swagger UI) at **http://localhost:8000/docs**.

### Verify

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

## Development

- Run tests: `pytest`
- Keep dependencies in `requirements.txt` updated
- All secrets / tokens go into `.env` (never committed)