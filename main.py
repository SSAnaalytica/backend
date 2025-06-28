from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app import auth
from app.routes import router as main_router
from app.exceptions import TokenExpired
app = FastAPI()
@app.get("/")
def redirigir_a_login():
    return RedirectResponse(url="/login")
@app.exception_handler(TokenExpired)
async def token_expired_handler(request: Request, exc: TokenExpired):
    return RedirectResponse(url="/login?exp=1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="app/static"), name="assets")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth.auth_router)
app.include_router(main_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
