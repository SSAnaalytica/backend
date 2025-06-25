from fastapi import APIRouter, UploadFile, File
import zipfile
import os

upload_router = APIRouter()

UPLOAD_DIR = "static"

@upload_router.post("/upload-dzi")
async def upload_dzi(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Guardar el .zip en disco
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Descomprimir el zip
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(UPLOAD_DIR)

    # Eliminar el zip después de descomprimir
    os.remove(file_path)

    return {"message": f"Archivo {file.filename} subido y descomprimido correctamente"}
