import json
import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt
from email.message import EmailMessage
import aiosmtplib
from app.config import *
ESTADO_PATH = "estado_casos.json"
if os.path.exists(ESTADO_PATH):
    with open(ESTADO_PATH, "r", encoding="utf-8") as f:
        estado_casos = json.load(f)
else:
    estado_casos = {}
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def load_json(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_confirmation_token(email: str):
    expire = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
def guardar_estado():
    with open(ESTADO_PATH, "w", encoding="utf-8") as f:
        json.dump(estado_casos, f, indent=4, ensure_ascii=False)
async def send_confirmation_email(to_email: str, token: str):
    link = f"http://localhost:8000/confirmar_email?token={token}"
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = "Confirma tu cuenta"
    msg.set_content(f"Hola,\nConfirma tu cuenta aquí:\n{link}")
    await aiosmtplib.send(
        msg,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        start_tls=True,
        username=EMAIL_FROM,
        password=EMAIL_PASSWORD
    )
