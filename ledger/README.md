# LedgerAI

**An India-first AI accountant for small businesses and CA firms.**

You give it a goal like "close October books". It reads the bank statement,
ledger and invoices, reconciles them, investigates problems, prepares entries,
checks GST, and produces the trial balance, P&L and balance sheet - with proof
behind every number. The AI proposes; a qualified human approves.

All money is handled as whole **paise** using plain Python integers. No floats,
and no AI arithmetic. See `CLAUDE.md` for the full vision, rules and build order.

---

## What exists today (Phases 0-1)

- Installed in editable mode: `pip install -e .` works from `.venv`.
- Paise-only money module (`src/ledgerai/money.py`).
- Fake Indian dataset generator for October 2025 with six messy cases.
- SQLite schema + CRUD with double-entry enforcement and evidence tracking.
- Tests: `47 passed`.

No Streamlit app yet - coming in **Phase 4.5**.

---

## Setup

```powershell
cd D:\ledger
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

---

## Commands

**Generate fake data:**
```powershell
cd D:\ledger
.\.venv\Scripts\python.exe scripts\generate_fake_data.py
```

**Run tests:**
```powershell
cd D:\ledger
.\.venv\Scripts\python.exe -m pytest
```

**Quick import test:**
```powershell
cd D:\ledger
.\.venv\Scripts\python.exe -c "from ledgerai.money import format_inr; print(format_inr(100000))"
```

---

## Folders

```
D:\ledger
  CLAUDE.md, PROGRESS.md
  src\ledgerai\        app code
  tests\               pytest
  data\fake\           fake data
  data\real\           real data (never commit)
  app.py               Streamlit app (Phase 4.5)
  .env                 secrets
```

---

## Safety
- Use fake data only in development.
- API keys in `.env` only.
- AI proposes, human approves.
- Mark uncertain items as "needs review" / "NEEDS CA REVIEW".
- GST = draft for CA review, not filing.
