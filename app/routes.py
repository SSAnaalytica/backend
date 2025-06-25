from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
import os, json
from fpdf import FPDF


from app.auth import get_current_user
from app.models import User
from app.utils import guardar_estado, estado_casos

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ──────────────────────────────────────────────
# BLOQUE 1: DASHBOARD
# ──────────────────────────────────────────────
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(get_current_user)):
    # Carga archivos .dzi desde static/
    files = os.listdir("static")
    dzi_files = [f for f in files if f.endswith(".dzi")]
    rows = ""
    for f in dzi_files:
        nombre = f[:-4]
        path = os.path.join("static", f)
        fecha_mod = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")

        tipo = "Citología cervical" if nombre.startswith("CE") else "Histología" if nombre.startswith("QE") else "Desconocido"
        estado = estado_casos.get(nombre, {})
        assigned = estado.get("assigned", "-")
        status = estado.get("status", "Abierto")
        reporte = estado.get("último_reporte")
        acciones = f"<button onclick=\"event.stopPropagation(); asignarCaso('{nombre}', this)\">Asignar caso</button>"
        if reporte:
            acciones += f"<br><a href='/{reporte}' target='_blank'>Ver reporte</a>"

        rows += f"<tr onclick=\"window.location='/viewer?slide={nombre}'\" style='cursor:pointer;'>"
        rows += f"<td>{nombre}</td><td>{tipo}</td><td>{assigned}</td><td>-</td><td>{fecha_mod}</td><td>{status}</td><td>{acciones}</td></tr>"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "rows": rows
    })


# ──────────────────────────────────────────────
# BLOQUE 2: VIEWER + REPORTE
# ──────────────────────────────────────────────
@router.get("/viewer", response_class=HTMLResponse)
async def serve_viewer(request: Request, user: User = Depends(get_current_user)):
    slide = request.query_params.get("slide", "sample")
    return templates.TemplateResponse("viewer.html", {
        "request": request,
        "slide": slide,
        "usuario": user.full_name
    })

@router.post("/guardar_reporte")
async def guardar_reporte(request: Request, user: User = Depends(get_current_user)):
    data = await request.json()
    slide = data.get("caso", "caso_desconocido")
    filename = f"reportes/{slide}_{user.full_name}.json"
    Path("reportes").mkdir(exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    estado_casos.setdefault(slide, {})
    estado_casos[slide]["último_reporte"] = filename
    guardar_estado()
    return {"status": "ok", "archivo": filename}

@router.post("/finalizar_caso")
async def finalizar(request: Request, user: User = Depends(get_current_user)):
    data = await request.json()
    caso = data.get("caso")
    if caso:
        estado_casos.setdefault(caso, {})
        estado_casos[caso]["status"] = "Cerrado"
        guardar_estado()
        return {"status": "ok"}
    return {"status": "error"}

@router.get("/descargar_pdf")
async def descargar_pdf(slide: str, user: User = Depends(get_current_user)):
    report_path = f"reportes/{slide}_{user.full_name}.json"
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Reporte del caso: {slide}", ln=True, align='C')
    pdf.ln(10)
    for key, value in data.items():
        pdf.multi_cell(0, 10, f"{key}: {value}")
    output_path = f"reportes/reporte_{slide}.pdf"
    pdf.output(output_path)
    return FileResponse(output_path, filename=f"reporte_{slide}.pdf", media_type='application/pdf')

@router.get("/leer_reporte")
async def leer_reporte(slide: str, user: User = Depends(get_current_user)):
    path = f"reportes/{slide}_{user.full_name}.json"
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# BLOQUE 3: ASIGNAR CASO
# ──────────────────────────────────────────────
@router.post("/assign")
async def assign_case(request: Request, user: User = Depends(get_current_user)):
    data = await request.json()
    case_id = data.get("case_id")

    if case_id:
        estado_casos.setdefault(case_id, {})
        estado_casos[case_id]["assigned"] = user.full_name
        estado_casos[case_id].setdefault("status", "Abierto")
        guardar_estado()
        return {"status": "ok", "assigned_to": user.full_name}

    return {"status": "error", "message": "ID de caso no proporcionado"}


@router.get("/listar_tiles")
def listar_tiles(slide: str, clase: str, offset: int = 0, limit: int = 20):
    path = f"static/tiles/{slide}/{clase}"
    if not os.path.exists(path):
        return JSONResponse(content={"error": "No encontrado"}, status_code=404)

    archivos = sorted([f for f in os.listdir(path) if f.endswith(".jpg")])
    subset = archivos[offset:offset+limit]
    urls = [f"/static/tiles/{slide}/{clase}/{f}" for f in subset]
    return {"imagenes": urls, "total": len(archivos)}