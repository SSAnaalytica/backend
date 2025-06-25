from fastapi import APIRouter, Form, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import JWTError, jwt
from app.models import UserInDB, User
from app.utils import *
from app.config import *
import os
from fastapi.templating import Jinja2Templates
auth_router = APIRouter()
fake_users_db = load_json(USUARIOS_PATH)
templates = Jinja2Templates(directory="templates")
def get_user(username: str):
    if username in fake_users_db:
        return UserInDB(**fake_users_db[username])

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user or user.disabled or not verify_password(password, user.hashed_password):
        return None
    return user

@auth_router.post("/token")
async def login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrecta o sin confirmar")
    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="token", value=access_token, httponly=True)
    return response

async def get_current_user(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return get_user(username)
    except JWTError:
        return RedirectResponse(url="/login?exp=1")
    
@auth_router.get("/login", response_class=HTMLResponse)
async def serve_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@auth_router.get("/register", response_class=HTMLResponse)
async def serve_register():
    return HTMLResponse(open("templates/register.html", encoding="utf-8").read())

@auth_router.post("/register")
async def register_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...)
):
    if username in fake_users_db:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    for user in fake_users_db.values():
        if user["email"] == email:
            raise HTTPException(status_code=400, detail="El correo ya está en uso")

    hashed = hash_password(password)
    fake_users_db[username] = {
        "username": username,
        "full_name": full_name,
        "email": email,
        "hashed_password": hashed,
        "disabled": True
    }
    save_json(USUARIOS_PATH, fake_users_db)
    token = create_confirmation_token(email)
    await send_confirmation_email(email, token)
    return HTMLResponse("<h3>Usuario creado. Revisa tu correo para confirmar tu cuenta.</h3>")

@auth_router.get("/confirmar_email", response_class=HTMLResponse)
async def confirmar_email(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        for username, user in fake_users_db.items():
            if user.get("email") == email:
                fake_users_db[username]["disabled"] = False
                save_json(USUARIOS_PATH, fake_users_db)
                return HTMLResponse("<h3>✅ Correo confirmado. Ya puedes iniciar sesión.</h3>")
        return HTMLResponse("<h3>Usuario no encontrado</h3>")
    except JWTError:
        return HTMLResponse("<h3>Token inválido o expirado</h3>")
@auth_router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("token")
    return response