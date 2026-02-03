# backend_arquitecturado/app/core/config.py

# ==========================================
# 1. CONFIGURACIÓN DEL MAPA (TERRENO DE JUEGO)
# ==========================================

# Usamos el Zócalo como epicentro para que el radio de 30km cubra:
# Norte (Ecatepec), Sur (Xochimilco), Este (Neza/Chalco), Oeste (Santa Fe)
LAT_CENTRO = 19.432608  
LON_CENTRO = -99.133209

# Radio de carga del mapa en metros.
# 30000 = 30km (Cubre toda la ZMVM)
DISTANCIA = 30000  

# Tipo de red ('drive' es lo más ligero para autos)
TIPO_RED = "drive"

# ==========================================
# 2. CONFIGURACIÓN DE GENERACIÓN (PUNTOS)
# ==========================================

# Radio de dispersión de los puntos aleatorios.
# 0.015 mantiene los puntos "juntitos" (tipo ruta local) aunque el mapa sea gigante.
OFFSET_ALEATORIO = 0.015 

# Centros donde aparecerán los puntos aleatorios
COORDS_ZONAS = {
    # Zona Neza (Centro)
    "neza": {
        "lat": 19.477781,
        "lon": -99.047402
    }, 
    
    # Zona IPN (Tus coordenadas personalizadas exactas)
    "ipn": {
        "lat": 19.491472, 
        "lon": -99.140639
    },

    # Nuevas zonas disponibles gracias al mapa de 30km
    "santa_fe": {
        "lat": 19.3610, 
        "lon": -99.2740
    },
    "sur": {
        "lat": 19.413391, 
        "lon": -99.175703
    }
}

# ==========================================
# 3. REGLAS DE NEGOCIO (PARA CÁLCULOS)
# ==========================================
# Estas variables son usadas por logica_rutas.py. 


TIEMPO_SERVICIO_MIN = 5  # Tiempo promedio de entrega por parada (minutos)

# Velocidades promedio para estimaciones si el mapa no trae datos
VEL_CALLE_KMH = 20 
VEL_AVENIDA_KMH = 50

# Tipos de vías que consideramos "rápidas"
TIPOS_AVENIDA = ['primary', 'secondary', 'trunk', 'primary_link', 'secondary_link']

# ==========================================
# 4. LOGS DE INICIO
# ==========================================
print(f">>> ⚙️ CONFIG CARGADA: Centro Map={LAT_CENTRO},{LON_CENTRO} | Radio={DISTANCIA}m")
print(f">>> 📍 ZONAS DISPONIBLES: {list(COORDS_ZONAS.keys())}")
print(f">>> 🚚 PARÁMETROS: Offset={OFFSET_ALEATORIO} | Vel.Calle={VEL_CALLE_KMH}km/h")