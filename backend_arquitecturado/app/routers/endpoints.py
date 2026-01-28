from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import random
import numpy as np
import networkx as nx
import osmnx as ox

# --- IMPORTAMOS LA CONFIGURACIÓN ---
from app.core.config import LAT_CENTRO, LON_CENTRO, COORDS_ZONAS, OFFSET_ALEATORIO
from app.core.mapa import get_grafo
from app.services.logica_rutas import calcular_metricas, optimizar_indices

router = APIRouter()

# --- CACHE EN MEMORIA ---
CACHE_SIMULACION = {
    "puntos": [], "full_matrix_time": None, "nodos_totales": [],
    "id_inicio": None, "id_fin": None     
}

COLORES_ZONAS = ["#00E5FF", "#E040FB", "#C6FF00", "#FF9100", "#FF4081", "#7C4DFF"]

# =============================================================================
# 1. ENDPOINT SIMULACIÓN
# =============================================================================
@router.get("/simulacion-leaflet")
def simulacion_leaflet(
    id_inicio: str = None, id_fin: str = None, 
    accion_id: str = None, accion_tipo: str = None, valor_extra: int = None,
    lat_manual: float = None, lon_manual: float = None,
    zona_generacion: str = "neza", # <--- Aquí recibimos "ipn" o "neza"
    reset: bool = False
):
    global CACHE_SIMULACION
    G = get_grafo()
    if G is None: raise HTTPException(503, "Cargando grafo...")

    if reset: 
        CACHE_SIMULACION = {
            "puntos": [], "full_matrix_time": None, "nodos_totales": [],
            "id_inicio": None, "id_fin": None
        }

    puntos_totales = CACHE_SIMULACION.get("puntos", [])
    
    if accion_tipo:
        
        # ---------------------------------------------------------
        # CASO 1: GENERAR PUNTOS ALEATORIOS (DECISIÓN DE ZONA)
        # ---------------------------------------------------------
        if accion_tipo == "generar_random":
            
            print(f"\n>>> 🎲 SOLICITUD DE GENERACIÓN. ZONA RECIBIDA: '{zona_generacion}'")

            # --- DECISIÓN ESTRICTA ---
            if zona_generacion == "ipn":
                print(">>> ✅ USANDO COORDENADAS: IPN / LINDAVISTA")
                centro = COORDS_ZONAS["ipn"]
            else:
                print(">>> ✅ USANDO COORDENADAS: NEZA (Default)")
                centro = COORDS_ZONAS["neza"]
            
            # Extraemos lat/lon del centro elegido
            c_lat = centro["lat"]
            c_lon = centro["lon"]
            
            # Definimos el recuadro alrededor de ese centro
            mn_lat, mx_lat = c_lat - OFFSET_ALEATORIO, c_lat + OFFSET_ALEATORIO
            mn_lon, mx_lon = c_lon - OFFSET_ALEATORIO, c_lon + OFFSET_ALEATORIO
            
            lats_t, lons_t = [], []
            
            # Generamos 32 puntos al azar dentro de ese recuadro
            for _ in range(32):
                lats_t.append(random.uniform(mn_lat, mx_lat))
                lons_t.append(random.uniform(mn_lon, mx_lon))
            
            try:
                # Buscamos los nodos del mapa más cercanos a esos puntos aleatorios
                nodos_raw = ox.distance.nearest_nodes(G, lons_t, lats_t)
                nodos = [int(n) for n in nodos_raw]
                
                # Calculamos matriz de tiempos
                num = len(nodos); ft = np.zeros((num, num))
                for i in range(num):
                    for j in range(i+1, num):
                        try:
                            t = nx.shortest_path_length(G, nodos[i], nodos[j], weight='travel_time')
                            ft[i][j]=t; ft[j][i]=t
                        except: ft[i][j]=9e9; ft[j][i]=9e9
                
                puntos_totales = []
                for i, nid in enumerate(nodos):
                    nd = G.nodes[nid]
                    rol = "VIP" if random.random() < 0.20 else "NORMAL"
                    puntos_totales.append({
                        "id": f"P-{i+1}", "lat": nd['y'], "lon": nd['x'], 
                        "estado": "PENDIENTE", "idx": i, "rol_base": rol, "cluster_manual": None
                    })

                CACHE_SIMULACION.update({"puntos": puntos_totales, "full_matrix_time": ft, "nodos_totales": nodos})
                
                # Definimos inicio y fin automáticamente
                if puntos_totales:
                    CACHE_SIMULACION["id_inicio"] = puntos_totales[0]["id"]
                    CACHE_SIMULACION["id_fin"] = puntos_totales[-1]["id"]
                    
            except Exception as e: 
                print(f"!!! ERROR EN GENERACIÓN: {e}")

        # ---------------------------------------------------------
        # CASO 2: CREAR UN PUNTO MANUALMENTE (CLIC O BÚSQUEDA)
        # ---------------------------------------------------------
        elif accion_tipo == "crear_manual" and lat_manual and lon_manual:
            try:
                # Aquí NO usamos zona, usamos la lat/lon exacta que mandó el usuario
                nuevo_nodo = int(ox.distance.nearest_nodes(G, lon_manual, lat_manual))
                nd = G.nodes[nuevo_nodo]
                
                if isinstance(CACHE_SIMULACION["nodos_totales"], np.ndarray):
                    CACHE_SIMULACION["nodos_totales"] = CACHE_SIMULACION["nodos_totales"].tolist()
                CACHE_SIMULACION["nodos_totales"].append(nuevo_nodo)
                
                # Actualizar matriz
                old_m = CACHE_SIMULACION["full_matrix_time"]
                nodos = CACHE_SIMULACION["nodos_totales"]
                s = len(nodos)
                new_m = np.zeros((s, s))
                if old_m is not None: new_m[:s-1, :s-1] = old_m
                
                target = nuevo_nodo
                for i in range(s-1):
                    try:
                        d = nx.shortest_path_length(G, nodos[i], target, weight='travel_time')
                        new_m[i][s-1] = d; new_m[s-1][i] = d
                    except: new_m[i][s-1]=9e9; new_m[s-1][i]=9e9
                
                CACHE_SIMULACION["full_matrix_time"] = new_m
                puntos_totales.append({
                    "id": f"P-{len(puntos_totales)+1}", "lat": nd['y'], "lon": nd['x'], 
                    "estado": "PENDIENTE", "idx": s-1, "rol_base": "NORMAL", "cluster_manual": None
                })
                CACHE_SIMULACION["puntos"] = puntos_totales
            except: pass

        # ---------------------------------------------------------
        # CASO 3: MODIFICAR PUNTOS (VISITAR, OMITIR...)
        # ---------------------------------------------------------
        elif accion_id:
            for p in puntos_totales:
                if p["id"] == accion_id:
                    if accion_tipo == "visitar": p["estado"] = "VISITADO"
                    elif accion_tipo == "omitir": p["estado"] = "OMITIDO"
                    elif accion_tipo == "restaurar": p["estado"] = "PENDIENTE"
                    elif accion_tipo == "asignar_zona": p["cluster_manual"] = None if valor_extra == -1 else valor_extra
                    elif accion_tipo == "fijar_inicio": CACHE_SIMULACION["id_inicio"] = accion_id
                    elif accion_tipo == "fijar_fin": CACHE_SIMULACION["id_fin"] = accion_id
                    break

        if accion_tipo == "limpiar_ruta": CACHE_SIMULACION["id_inicio"] = None; CACHE_SIMULACION["id_fin"] = None

    # --- RESPUESTA JSON PARA EL FRONTEND ---
    pts = CACHE_SIMULACION["puntos"]
    if not pts: return {"paradas": [], "rutas_clusters": [], "ruta_global": None, "ruta_vip": None}

    nt = CACHE_SIMULACION["nodos_totales"]
    fmt = CACHE_SIMULACION["full_matrix_time"]
    id_ini, id_fin = CACHE_SIMULACION["id_inicio"], CACHE_SIMULACION["id_fin"]
    
    res_paradas = []
    for p in pts:
        tipo = "NORMAL"
        if p["id"] == id_ini: tipo = "INICIO"
        elif p["id"] == id_fin: tipo = "FIN"
        elif p["rol_base"] == "VIP": tipo = "VIP"
        res_paradas.append({**p, "tipo": tipo})

    idx_ini_n = next((i for i, p in enumerate(pts) if p["id"] == id_ini), None)
    idx_fin_n = next((i for i, p in enumerate(pts) if p["id"] == id_fin), None)

    # 1. RUTA GLOBAL
    ruta_global_obj = None
    indices_globales = [i for i, p in enumerate(pts) if p["estado"] == "PENDIENTE" or i == idx_ini_n or i == idx_fin_n]
    if idx_ini_n is not None and len(indices_globales) > 1:
        sub = fmt[np.ix_(indices_globales, indices_globales)]
        orden_local = optimizar_indices(indices_globales, sub, idx_ini_n, idx_fin_n if idx_fin_n in indices_globales else None)
        km_g, t_g = calcular_metricas(orden_local, nt, G, nombre_ruta="Global")
        full_coords = []
        ruta_nodos_global = [nt[i] for i in orden_local]
        for i in range(len(ruta_nodos_global)-1):
            try:
                path = nx.shortest_path(G, ruta_nodos_global[i], ruta_nodos_global[i+1], weight='travel_time')
                for nid in path: full_coords.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
            except: pass
        ruta_global_obj = {"coords": full_coords, "km": km_g, "tiempo": t_g}

    # 2. RUTA VIP
    ruta_vip_obj = None
    indices_vip = [i for i, p in enumerate(pts) if p.get("rol_base") == "VIP" and p["estado"] == "PENDIENTE"]
    if idx_ini_n is not None and idx_ini_n not in indices_vip: indices_vip.insert(0, idx_ini_n)
    if len(indices_vip) > 1:
        sub_vip = fmt[np.ix_(indices_vip, indices_vip)]
        orden_vip = optimizar_indices(indices_vip, sub_vip, idx_ini_n if idx_ini_n in indices_vip else None, None)
        km_v, t_v = calcular_metricas(orden_vip, nt, G, nombre_ruta="VIP")
        coords_vip = []
        ruta_nodos_vip = [nt[i] for i in orden_vip]
        for i in range(len(ruta_nodos_vip)-1):
            try:
                path = nx.shortest_path(G, ruta_nodos_vip[i], ruta_nodos_vip[i+1], weight='travel_time')
                for nid in path: coords_vip.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
            except: pass
        ruta_vip_obj = {"coords": coords_vip, "km": km_v, "tiempo": t_v}

    # 3. ZONAS (CLUSTERS)
    rutas_clusters = []
    clusters_map = {}
    for i, p in enumerate(pts):
        if p.get("cluster_manual") is not None: 
            clusters_map.setdefault(p["cluster_manual"], []).append(i)
    
    for cid, indices in clusters_map.items():
        grupo = [i for i in indices if pts[i]["estado"] == "PENDIENTE"]
        if idx_ini_n is not None and pts[idx_ini_n].get("cluster_manual") == cid:
            if idx_ini_n not in grupo: grupo.insert(0, idx_ini_n)
        if len(grupo) > 1:
            try:
                sub = fmt[np.ix_(grupo, grupo)]
                start_node = idx_ini_n if (idx_ini_n in grupo) else None
                ruta_indices = optimizar_indices(grupo, sub, start_node, None)
                km_z, t_z = calcular_metricas(ruta_indices, nt, G, nombre_ruta=f"Cluster {cid}")
                coords_z = []
                ruta_nodos_z = [nt[i] for i in ruta_indices]
                for i in range(len(ruta_nodos_z)-1):
                    try:
                        path = nx.shortest_path(G, ruta_nodos_z[i], ruta_nodos_z[i+1], weight='travel_time')
                        for nid in path: coords_z.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
                    except: pass
                rutas_clusters.append({
                    "cluster_id": cid, "coords": coords_z, 
                    "color": COLORES_ZONAS[cid % len(COLORES_ZONAS)], "km": km_z, "tiempo": t_z
                })
            except: pass

    return {
        "paradas": res_paradas,
        "rutas_clusters": rutas_clusters,
        "ruta_global": ruta_global_obj,
        "ruta_vip": ruta_vip_obj
    }

# --- CLUSTER MANUAL (SIN CAMBIOS) ---
class ClusterManualRequest(BaseModel):
    nombre: str
    nodos_ids: List[int]

class ClusterResponse(BaseModel):
    nombre: str
    distancia_km: float
    tiempo_min: str
    path_coords: List[List[float]]
    nodos_secuencia: List[int]

@router.post("/cluster-manual", response_model=ClusterResponse)
def crear_cluster_manual(datos: ClusterManualRequest):
    G = get_grafo()
    if G is None: raise HTTPException(503, "Grafo no cargado")
    nodos = datos.nodos_ids
    if len(nodos) < 2: 
        try:
            nd = G.nodes[nodos[0]]
            c = [[nd['y'], nd['x']]]
        except: c = []
        return {"nombre": datos.nombre, "distancia_km": 0, "tiempo_min": "0m", "path_coords": c, "nodos_secuencia": nodos}
    indices = list(range(len(nodos)))
    km, tiempo_str = calcular_metricas(indices, nodos, G, nombre_ruta=f"Manual {datos.nombre}")
    path_coords = []
    for i in range(len(nodos)-1):
        try:
            path = nx.shortest_path(G, nodos[i], nodos[i+1], weight='travel_time')
            for nid in path: path_coords.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
        except: pass
    return {"nombre": datos.nombre, "distancia_km": km, "tiempo_min": tiempo_str, "path_coords": path_coords, "nodos_secuencia": nodos}