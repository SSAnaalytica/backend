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
from app.models import UserInDB

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

@router.get("/viewer/{slide}", response_class=HTMLResponse)
async def render_viewer(slide: str, request: Request, usuario: UserInDB = Depends(get_current_user)):
    url_base = "https://wsi-upload-ssa.s3.us-east-2.amazonaws.com/"
    tipo = obtener_tipo(slide)
    return templates.TemplateResponse("viewer_cito.html", {
    "request": request,
    "slide": slide,
    "usuario": usuario.full_name,
    "tipo": tipo,
    "url_base": url_base
})

def render_dashboard_por_tipo(tipo_deseado, request, user):
    path = "estado_casos.json"
    rows = ""
    url_base = "https://wsi-upload-ssa.s3.us-east-2.amazonaws.com/"

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for slide_id, info in data.items():
                    if info.get("TIPO") == tipo_deseado:
                        asignado = info.get("ASIGNADO", "—")
                        paciente = info.get("PACIENTE", "—")
                        fecha = info.get("FECHA", "—")
                        estado = info.get("ESTADO", "Abierto")
                        tipo = info.get("TIPO", "¿?")

                        # 🔁 CORREGIR RUTA SEGÚN TIPO   
                        if tipo == "Citología cervical":
                            ruta = f"/viewer/slide={slide_id}"
                        elif tipo == "Histología":
                            ruta = f"/viewer/slide={slide_id}"
                        else:
                            ruta = "#"

                        accion = (
                            f'<a href="{ruta}"><button>Ver visor</button></a>'
                            if asignado == user.full_name or asignado == "—"
                            else '<span style="color:gray;">No disponible</span>'
                        )

                        if asignado == "—" and estado == "Abierto":
                            accion = f'<button onclick="asignarCaso(\'{slide_id}\', this)">Asignar</button>'

                        rows += f"""
<tr class='clickable-row' data-slide='{slide_id}' data-tipo='{tipo}'>
    <td>{slide_id}</td>
    <td>{tipo}</td>
    <td>{asignado}</td>
    <td>{paciente}</td>
    <td>{fecha}</td>
    <td>{estado}</td>
    <td>Click para abrir</td>
</tr>
                        """
            except json.JSONDecodeError:
                print("Error: JSON inválido")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "usuario": user.full_name,
        "rows": rows,
        "url_base": url_base
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
    
    url_base = "https://wsi-upload-ssa.s3.us-east-2.amazonaws.com/"

    return templates.TemplateResponse("viewer_cito.html", {
        "request": request,
        "slide": slide,
        "usuario": user.full_name,
        "tipo": tipo,
        "url_base": url_base  # ✅ IMPORTANTE
    })


@router.get("/viewer/histologia", response_class=HTMLResponse)
async def viewer_histologia(slide: str, request: Request):
    user = await get_current_user(request)
    tipo = obtener_tipo(slide)
    if tipo != "Histología":  # Asegúrate que coincida exactamente con lo que devuelve `obtener_tipo`
        raise HTTPException(status_code=400, detail="Este visor es solo para histología")
    
    url_base = "https://wsi-upload-ssa.s3.us-east-2.amazonaws.com/"

    return templates.TemplateResponse("viewer_histo.html", {
        "request": request,
        "slide": slide,
        "usuario": user.full_name,
        "tipo": tipo,
        "url_base": url_base
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