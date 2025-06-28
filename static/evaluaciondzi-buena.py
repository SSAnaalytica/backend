import os
import json
import torch
import numpy as np
from PIL import Image
from tqdm import tqdm
from torchvision import models, transforms
from torch.utils.data import Dataset, DataLoader

# === Configuración
carpeta_tiles = r"C:\Users\Rick\visor web\static\CE24-13094_files\17"
modelo_path = "herlev_best_model.pt"
tile_size = 256
umbral_blanco = 0.9
salida_json = r"C:\Users\Rick\visor web\static\predicciones_herlev.json"
batch_size = 64
# === Diccionario de clases
nombre_clases = {
    0: "HSIL",
    1: "LSIL",
    2: "ASC-US",
    3: "NORMAL",
    4: "NORMAL",
    5: "NORMAL",
    6: "ASC-US"
}

# === Modelo
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = models.resnet18()
model.fc = torch.nn.Linear(model.fc.in_features, 7)
model.load_state_dict(torch.load(modelo_path, map_location=device))
model.to(device)
model.eval()

# === Transformación
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5]*3, [0.5]*3)
])

# === Tile blanco
def es_blanco(pil_img, umbral_brillo=0.85, umbral_varianza=0.005):
    np_img = np.array(pil_img).astype(np.float32) / 255.0
    
    if np_img.ndim == 3 and np_img.shape[2] == 3:
        # === Brillo
        brillo = np.mean(np_img, axis=2)
        white_ratio = np.sum(brillo > umbral_brillo) / brillo.size

        # === Varianza (textura)
        varianza_total = np.var(np_img)

        # === Saturación básica (RMS de diferencias entre canales)
        r, g, b = np_img[:, :, 0], np_img[:, :, 1], np_img[:, :, 2]
        saturacion_aprox = np.std([r, g, b])

        # Condiciones para considerarse "blanco o sin información"
        if white_ratio > 0.65 and varianza_total < umbral_varianza and saturacion_aprox < 0.05:
            return True
    
    return False

# === Dataset
class TileDataset(Dataset):
    def __init__(self, carpeta, nombres, transform, umbral=0.9):
        self.data = []
        for nombre in nombres:
            ruta = os.path.join(carpeta, nombre)
            try:
                img = Image.open(ruta).convert("RGB")
                if not es_blanco(img, umbral):
                    self.data.append((nombre, transform(img)))
            except Exception:
                continue

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

# === Obtener lista de tiles
tiles = [f for f in os.listdir(carpeta_tiles) if f.lower().endswith(".jpg")]
dataset = TileDataset(carpeta_tiles, tiles, transform, umbral_blanco)
dataloader = DataLoader(dataset, batch_size=batch_size, collate_fn=lambda x: x)

# === Inicializar resultados
resultados = {nombre: [] for nombre in nombre_clases.values()}

# === Clasificación por lotes
for batch in tqdm(dataloader, desc="Clasificando en batch"):
    nombres_batch, x_batch = zip(*batch)
    x_batch = torch.stack(x_batch).to(device)

    with torch.no_grad():
        out = model(x_batch)
        probs = torch.softmax(out, dim=1)
        confidencias, clases_pred = torch.max(probs, dim=1)

    for i in range(len(nombres_batch)):
        nombre = nombres_batch[i]
        clase_id = clases_pred[i].item()
        confianza = round(confidencias[i].item(), 4)
        clase_str = nombre_clases[clase_id]

        # Extraer coordenadas desde nombre del tile: 0_107.jpg
        partes = nombre.replace(".jpg", "").split("_")
        if len(partes) == 2:
            try:
                col = int(partes[0])
                fila = int(partes[1])
                x = col * tile_size
                y = fila * tile_size
            except ValueError:
                x, y = 0, 0
        else:
            x, y = 0, 0

        resultados[clase_str].append({
            "x": x,
            "y": y,
            "confidence": confianza
        })

# === Guardar JSON
with open(salida_json, "w", encoding="utf-8") as f:
    json.dump(resultados, f, indent=2)

print(f"\n✅ Clasificación completada. Archivo guardado: {salida_json}")