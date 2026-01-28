# app/core/config.py

# --- PUNTO MEDIO DEL MAPA ---
# Mantenemos este centro estratégico (Aeropuerto) y radio grande
# para que el sistema "vea" tanto Neza como tu nueva ubicación.
LAT_CENTRO = 19.4850
LON_CENTRO = -99.0900
RADIO_CARGA_MAPA = 10000  # 10 km de radio

# --- CENTROS DE GENERACIÓN ---
COORDS_ZONAS = {
    # Zona 1: Neza (Sin cambios)
    "neza": {
        "lat": 19.4938, 
        "lon": -99.0478
    },
    
    # Zona 2: Tu ubicación personalizada (19°29'29.3"N 99°08'26.3"W)
    "ipn":  {
        "lat": 19.491472, 
        "lon": -99.140639
    }  
}

# Radio de dispersión (Qué tan regados aparecen los puntos)
OFFSET_ALEATORIO = 0.015 

# --- REGLAS DE NEGOCIO (V-PLATA) ---
TIEMPO_SERVICIO_MIN = 5 
VEL_CALLE_KMH = 20
VEL_AVENIDA_KMH = 50
TIPOS_AVENIDA = ['primary', 'secondary', 'trunk', 'primary_link', 'secondary_link']

print(f">>> ⚙️ CONFIG CARGADA: Centro Map={LAT_CENTRO},{LON_CENTRO} | Radio={RADIO_CARGA_MAPA}m")
print(f">>> 📍 ZONAS: Neza={COORDS_ZONAS['neza']} | IPN={COORDS_ZONAS['ipn']}")