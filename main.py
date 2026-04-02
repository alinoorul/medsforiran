from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader, Environment
import pdfplumber
import json
import os
import re
from typing import Optional

app = FastAPI(title="Medicine Inventory")
# -------------------------------------------------------
# 🔑  Change this to your desired admin password
ADMIN_PASSWORD = "rahbar"
# -------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
templates = Jinja2Templates(env=jinja_env)

DB_FILE = os.path.join(BASE_DIR, "medicines.json")


# ---------- Persistence ----------

def load_db() -> list[dict]:
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return []


def save_db(data: list[dict]):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


def next_id(data: list[dict]) -> int:
    return max((m["id"] for m in data), default=0) + 1


# ---------- Auth helper ----------

def require_admin(password: str):
    """Raise 403 if password is wrong."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password.")


# ---------- PDF Parsing ----------

def parse_pdf(file_bytes: bytes) -> list[dict]:
    import io
    medicines = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if not table:
                        continue
                    header = [str(c).strip().lower() if c else "" for c in table[0]]

                    def col(keywords):
                        for kw in keywords:
                            for i, h in enumerate(header):
                                if kw in h:
                                    return i
                        return None

                    idx_row  = col(["row", "serial", "s/n", "sn", "#", "no"])
                    idx_code = col(["code", "generic code", "gcode"])
                    idx_name = col(["name", "medicine", "drug"])
                    idx_mfr  = col(["manuf", "maker", "producer", "supplier"])
                    idx_qty  = col(["qty", "quantity", "required", "amount"])

                    for row in table[1:]:
                        if not any(row):
                            continue

                        def cell(idx):
                            if idx is not None and idx < len(row) and row[idx]:
                                return str(row[idx]).strip()
                            return ""

                        medicines.append({
                            "serial":        cell(idx_row) or str(len(medicines) + 1),
                            "generic_code":  cell(idx_code),
                            "name":          cell(idx_name),
                            "manufacturers": cell(idx_mfr),
                            "quantity":      cell(idx_qty),
                        })
            else:
                text = page.extract_text() or ""
                lines = text.splitlines()
                for line in lines:
                    parts = re.split(r"\t|  {2,}", line.strip())
                    parts = [p.strip() for p in parts if p.strip()]
                    if len(parts) >= 4:
                        medicines.append({
                            "serial":        parts[0] if len(parts) > 0 else "",
                            "generic_code":  parts[1] if len(parts) > 1 else "",
                            "name":          parts[2] if len(parts) > 2 else "",
                            "manufacturers": parts[3] if len(parts) > 3 else "",
                            "quantity":      parts[4] if len(parts) > 4 else "",
                        })

    return medicines


# ---------- Routes: Pages ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    medicines = load_db()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "medicines": medicines,
        "count": len(medicines),
    })

# ---------- Auth route ----------

@app.post("/auth/verify", response_class=JSONResponse)
async def verify_password(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        return {"ok": True}
    return JSONResponse({"ok": False}, status_code=403)


# ---------- Routes: HTMX Partials ----------

@app.get("/medicines", response_class=HTMLResponse)
async def list_medicines(request: Request, search: str = ""):
    data = load_db()
    if search:
        q = search.lower()
        data = [m for m in data if
                q in m.get("name", "").lower() or
                q in m.get("generic_code", "").lower() or
                q in m.get("manufacturers", "").lower()]
    return templates.TemplateResponse("partials/medicine_rows.html", {
        "request": request,
        "medicines": data,
        "count": len(data),
        "admin": False,   # search results don't know admin state; JS handles button visibility
    })


@app.post("/medicines", response_class=HTMLResponse)
async def create_medicine(
    request: Request,
    password: str = Form(...),
    serial: str = Form(""),
    generic_code: str = Form(...),
    name: str = Form(...),
    manufacturers: str = Form(...),
    quantity: str = Form(...),
):
    require_admin(password)
    data = load_db()
    new_id = next_id(data)
    entry = {
        "id": new_id,
        "serial": serial or str(new_id),
        "generic_code": generic_code,
        "name": name,
        "manufacturers": manufacturers,
        "quantity": quantity,
    }
    data.append(entry)
    save_db(data)
    return templates.TemplateResponse("partials/medicine_rows.html", {
        "request": request,
        "medicines": data,
        "count": len(data),
    })


@app.get("/medicines/{med_id}/edit", response_class=HTMLResponse)
async def edit_form(request: Request, med_id: int, password: str = ""):
    require_admin(password)
    data = load_db()
    medicine = next((m for m in data if m["id"] == med_id), None)
    if not medicine:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("partials/edit_row.html", {
        "request": request,
        "medicine": medicine,
        "password": password,
    })


@app.put("/medicines/{med_id}", response_class=HTMLResponse)
async def update_medicine(
    request: Request,
    med_id: int,
    password: str = Form(...),
    serial: str = Form(""),
    generic_code: str = Form(...),
    name: str = Form(...),
    manufacturers: str = Form(...),
    quantity: str = Form(...),
):
    require_admin(password)
    data = load_db()
    for m in data:
        if m["id"] == med_id:
            m["serial"] = serial or m["serial"]
            m["generic_code"] = generic_code
            m["name"] = name
            m["manufacturers"] = manufacturers
            m["quantity"] = quantity
            break
    save_db(data)
    return templates.TemplateResponse("partials/medicine_rows.html", {
        "request": request,
        "medicines": data,
        "count": len(data),
    })


@app.delete("/medicines/{med_id}", response_class=HTMLResponse)
async def delete_medicine(request: Request, med_id: int, password: str = ""):
    require_admin(password)
    data = load_db()
    data = [m for m in data if m["id"] != med_id]
    save_db(data)
    return templates.TemplateResponse("partials/medicine_rows.html", {
        "request": request,
        "medicines": data,
        "count": len(data),
    })


# ---------- Routes: PDF Upload ----------

@app.post("/upload-pdf", response_class=HTMLResponse)
async def upload_pdf(
    request: Request,
    password: str = Form(...),
    pdf_file: UploadFile = File(...),
):
    require_admin(password)

    if not pdf_file.filename.endswith(".pdf"):
        return HTMLResponse(
            '<p style="color:var(--danger)">Please upload a valid PDF file.</p>',
            status_code=400,
        )
    contents = await pdf_file.read()
    parsed = parse_pdf(contents)

    if not parsed:
        return HTMLResponse(
            '<p style="color:var(--danger)">No table data found in PDF. Check format.</p>',
            status_code=422,
        )

    data = load_db()
    imported = 0
    for row in parsed:
        if not row.get("name"):
            continue
        new_id = next_id(data)
        data.append({
            "id": new_id,
            "serial": row.get("serial", str(new_id)),
            "generic_code": row.get("generic_code", ""),
            "name": row.get("name", ""),
            "manufacturers": row.get("manufacturers", ""),
            "quantity": row.get("quantity", ""),
        })
        imported += 1
    save_db(data)

    return templates.TemplateResponse("partials/medicine_rows.html", {
        "request": request,
        "medicines": data,
        "count": len(data),
        "import_count": imported,
    })
