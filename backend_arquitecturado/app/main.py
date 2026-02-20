from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import endpoints
from app.core.mapa import get_grafo  # <-- CORRECCIÓN: Antes decía 'cargar_mapa'

app = FastAPI(title="Fleet Master Pro API")

# --- CONFIGURACIÓN DE CORS ---
# Permite que tu frontend (HTML) se comunique con el backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUIR RUTAS
app.include_router(endpoints.router)

# --- EVENTO DE INICIO ---
@app.on_event("startup")
async def startup_event():
    """
    Se ejecuta automáticamente al iniciar el servidor.
    Intenta cargar el mapa en memoria RAM de una vez para que
    la primera petición del usuario no sea lenta.
    """
    print(">>> 🚀 INICIANDO SERVIDOR FLEET MASTER PRO...")
    
    # Llamamos a la función con el nombre NUEVO
    grafo = get_grafo()
    
    if grafo:
        print(">>> ✅ MAPA CARGADO Y SISTEMA LISTO")
    else:
        print(">>> ⚠️ ADVERTENCIA: El mapa no se pudo cargar al inicio (se intentará de nuevo en la primera petición)")