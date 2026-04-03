# Meds For Iran --  supporting donations of medical supplies to Iran

FastAPI + HTMX mobile-responsive medicine inventory web app

## Features
- **Import PDF** — paste in a PDF with medicine data (serial, code, name, manufacturers, qty)
- **Create** medicines manually
- **Read** / search across name, code, and manufacturer
- **Edit** inline — click edit on any row
- **Delete** with confirmation
- **Mobile responsive** — table collapses to card stack on small screens
- **JSON persistence** — data saved locally in `medicines.json`

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
uvicorn main:app --reload

# 3. Open in browser
# http://127.0.0.1:8000
```

## PDF Format

Your PDF should contain a table with these 5 columns (headers are fuzzy-matched):

| Row / Serial | Generic Code | Medicine Name | Manufacturers | Required Qty |
|---|---|---|---|---|
| 1 | AMX500 | Amoxicillin 500mg | Pfizer, GSK | 200 boxes |
| 2 | PCM500 | Paracetamol 500mg | Cipla | 500 strips |

The parser uses `pdfplumber` to extract tables. For scanned PDFs, run OCR first (e.g. Adobe Acrobat or `ocrmypdf`).

## Project Structure

```
medicine_app/
├── main.py                  # FastAPI app + routes
├── requirements.txt
├── medicines.json           # Auto-created data store
├── static/                  # (optional static assets)
└── templates/
    ├── index.html           # Main page
    └── partials/
        ├── medicine_rows.html  # HTMX-swapped table
        └── edit_row.html       # Inline edit form
```
