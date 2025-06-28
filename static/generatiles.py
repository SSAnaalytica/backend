import os
import json
import numpy as np
from PIL import Image
import openslide

# Parámetros
DZI_PATH = "C:/Users/Rick/integracion/static/CE24-13094.dzi"
JSON_PATH = "C:/Users/Rick/integracion/static/CE24-13094_predicciones.json"
OUTPUT_DIR = "C:/Users/Rick/integracion/static/tiles/CE24-13094"
TILE_SIZE = 256
CONFIDENCE_THRESHOLD = 0
SOURCE_LEVEL = 0  # nivel usado para evaluación del modelo

# Filtro mejorado de blancos
def es_tile_blanco(tile, umbral_pixeles_claros=1, umbral_varianza=10):
    np_tile = np.array(tile.convert("L"))
    proporcion_clara = np.mean(np_tile > 220)
    varianza = np.var(np_tile)
    return proporcion_clara > umbral_pixeles_claros or varianza < umbral_varianza

# Cargar predicciones
with open(JSON_PATH, "r") as f:
    predicciones = json.load(f)

# Abrir slide
slide = openslide.OpenSlide(DZI_PATH.replace(".dzi", ".tiff"))
dims_nivel = slide.level_dimensions[SOURCE_LEVEL]
factor_escala = slide.level_downsamples[SOURCE_LEVEL]

# Crear carpetas de salida
for clase in predicciones.keys():
    os.makedirs(os.path.join(OUTPUT_DIR, clase), exist_ok=True)

# Extraer y guardar tiles válidos
for clase, elementos in predicciones.items():
    for item in elementos:
        if item["confidence"] < CONFIDENCE_THRESHOLD:
            continue

        x, y = int(item["x"]), int(item["y"])
        tile = slide.read_region((x, y), SOURCE_LEVEL, (TILE_SIZE, TILE_SIZE)).convert("RGB")

        if es_tile_blanco(tile):
            continue

        nombre = f"{x}_{y}.jpg"
        tile_path = os.path.join(OUTPUT_DIR, clase, nombre)
        tile.save(tile_path)

print("Extracción completada.")
