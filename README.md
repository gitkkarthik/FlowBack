# FlowBack

Pick up exactly where you left off. FlowBack watches your recently modified files, sends them to Gemini, and hands you a focused briefing when you sit back down — per project, with recurring issue tracking via tags.

## How it works

**Pause** — point it at your project folders before stepping away, click *Save my context*.

**Resume** — come back to a per-project AI briefing: your goal, where you were stuck, next 3 steps, files changed, and auto-generated tags. Click any tag to see every past session where you hit the same issue.

## Stack

- **Backend** — Python, FastAPI, SQLite, Google Gemini 2.5 Flash
- **Frontend** — React 18, Vite, Tailwind CSS

## Setup

### Prerequisites

- Python 3.12+
- Node 18+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```
GEMINI_API_KEY=your_key_here
```

Start the server:

```bash
uvicorn main:app --reload
```

API runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`.

## Project structure

```
flowBack/
├── backend/
│   ├── main.py          # FastAPI routes
│   ├── capture.py       # File scanner
│   ├── gemini.py        # AI briefing generation
│   ├── database.py      # SQLite helpers
│   ├── models.py        # Pydantic models
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.jsx
        └── components/
            ├── PauseScreen.jsx
            ├── ResumeScreen.jsx
            ├── BriefingCard.jsx
            └── TagPanel.jsx
```

## Notes

- All data stays local — nothing leaves your machine except the file snippets sent to Gemini for analysis.
- Scans up to 5 recently modified files per folder (last 2 hours), skipping binaries, `node_modules`, `.git`, build output, and other noise.
- The folder picker (Choose button) requires macOS — it uses `osascript` under the hood. On other platforms, type the path manually.
