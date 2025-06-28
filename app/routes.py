from fastapi import APIRouter, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
import os, json
from fpdf import FPDF
from collections import defaultdict
from app.auth import get_current_user
from app.models import User
from app.utils import guardar_estado, estado_casos
from app.exceptions import TokenExpired

router = APIRouter()
templates = Jinja2Templates(directory="templates")



def obtener_tipo(slide_id: str) -> str:
        path = "estado_casos.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    # slide_id podría ser "CE24-13094" o "QE24-15755-1.ome"
                    info = data.get(slide_id)
                    if info and "TIPO" in info:
                        return info["TIPO"]
                except json.JSONDecodeError:
                    print("Error: JSON inválido")
        return ""

    # ──────────────────────────────────────────────
    # BLOQUE 1: DASHBOARD
    # ──────────────────────────────────────────────
@router.get("/selector_tipo", response_class=HTMLResponse)
async def selector_tipo(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("selector_tipo.html", {"request": request, "user": user})

@router.get("/dashboard/citologia", response_class=HTMLResponse)
async def dashboard_citologia(request: Request, user: User = Depends(get_current_user)):
    return render_dashboard_por_tipo("Citología cervical", request, user)

@router.get("/dashboard/histologia", response_class=HTMLResponse)
async def dashboard_histologia(request: Request, user: User = Depends(get_current_user)):
    return render_dashboard_por_tipo("Histología", request, user)


def render_dashboard_por_tipo(tipo_deseado, request, user):
    files = os.listdir("static")
    dzi_files = [f for f in files if f.endswith(".dzi")]
    rows = ""
    cambios = False

    # Agrupar slides por base (antes del "_")
    casos_dict = defaultdict(list)
    for f in dzi_files:
        nombre = f[:-4]  # sin .dzi
        base_id = nombre.split("_")[0]
        casos_dict[base_id].append(nombre)

    for base_id, variantes in casos_dict.items():
        # Usamos la primera variante como representativa para cargar el viewer
        nombre = variantes[0]
        path = os.path.join("static", nombre + ".dzi")
        if not os.path.exists(path):
            continue

        tipo = "Citología cervical" if base_id.startswith("CE") else "Histología" if base_id.startswith("QE") else "Desconocido"
        if tipo != tipo_deseado:
            continue

        estado = estado_casos.setdefault(base_id, {})
        if "TIPO" not in estado:
            estado["TIPO"] = tipo
            cambios = True

        fecha_mod = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
        assigned = estado.get("assigned", "-")
        status = estado.get("status", "Abierto")
        reporte = estado.get("último_reporte")

        acciones = f"<button onclick=\"event.stopPropagation(); asignarCaso('{base_id}', this)\">Asignar caso</button>"
        if reporte:
            acciones += f"<br><a href='/{reporte}' target='_blank'>Ver reporte</a>"

        ruta_viewer = "/viewer/citologia" if tipo_deseado == "Citología cervical" else "/viewer/histologia"
        rows += f"<tr onclick=\"window.location='{ruta_viewer}?slide={nombre}'\" style='cursor:pointer;'>"
        rows += f"<td>{base_id}</td><td>{tipo}</td><td>{assigned}</td><td>-</td><td>{fecha_mod}</td><td>{status}</td><td>{acciones}</td></tr>"

    if cambios:
        guardar_estado()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "rows": rows
    })
    # ──────────────────────────────────────────────
    # BLOQUE 2: VIEWER + REPORTE
    # ──────────────────────────────────────────────
def encontrar_slides_asociados(nombre_slide: str):
    # Extrae el prefijo base antes del "_" si existe (ej: QE24-15755 de QE24-15755_0)
    base = nombre_slide.split("_")[0]
    slides = [f[:-4] for f in os.listdir("static") if f.endswith(".dzi") and f.startswith(base)]
    return sorted(slides)

@router.get("/viewer/citologia", response_class=HTMLResponse)
async def viewer_citologia(slide: str, request: Request):
    user = await get_current_user(request)
    tipo = obtener_tipo(slide)
    if tipo != "Citología cervical":
        raise HTTPException(status_code=400, detail="Este visor es solo para citología")
    
    return templates.TemplateResponse("viewer_cito.html", {
        "request": request,
        "slide": slide,
        "usuario": user.full_name,
        "tipo": tipo
    })


@router.get("/viewer/histologia", response_class=HTMLResponse)
async def viewer_histologia(slide: str, request: Request):
    user = await get_current_user(request)
    tipo = obtener_tipo(slide)
    if tipo != "Histología":
        raise HTTPException(status_code=400, detail="Este visor es solo para histología")

    slides_info = []
    relacionados = encontrar_slides_asociados(slide)
    for nombre in relacionados:
        miniatura = f"/static/{nombre}_files/8/0_0.jpg"
        slides_info.append({
            "nombre": nombre,
            "miniatura": miniatura
        })

    return templates.TemplateResponse("viewer_histo.html", {
        "request": request,
        "slide": slide,
        "usuario": user.full_name,
        "tipo": tipo,
        "slides": slides_info
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
        with open(report_patxh, "r", encoding="utf-8") as f:
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