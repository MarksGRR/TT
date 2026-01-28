# app/main.py
from fastapi.responses import FileResponse 
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import contextlib

# Importamos la configuración y rutas
from app.core.mapa import cargar_mapa
from app.routers import endpoints

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Al iniciar la App: Cargar Mapa
    cargar_mapa()
    yield
    # Al apagar la App: (Aquí podríamos limpiar memoria o cerrar DB)
    pass

# Crear Instancia de FastAPI
app = FastAPI(title="Sistema Logístico Arquitecturado", lifespan=lifespan)

# Configurar CORS (Permisos para el Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir las rutas (Endpoints
app.include_router(endpoints.router)
@app.get("/")
def serve_home():
    return FileResponse("index.html")