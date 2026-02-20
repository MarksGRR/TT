from fastapi import APIRouter, HTTPException, Query
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
# FUNCION AUXILIAR: TRAZADO SUAVE
# =============================================================================
def obtener_coords_suaves(G, lista_nodos):
    coords_suaves = []
    if not lista_nodos: return coords_suaves
    start_node = G.nodes[lista_nodos[0]]
    coords_suaves.append([start_node['y'], start_node['x']])
    for i in range(len(lista_nodos) - 1):
        try:
            edge_data = G.get_edge_data(lista_nodos[i], lista_nodos[i+1])[0]
            if 'geometry' in edge_data:
                for lon, lat in edge_data['geometry'].coords:
                    coords_suaves.append([lat, lon])
            else:
                node_v = G.nodes[lista_nodos[i+1]]
                coords_suaves.append([node_v['y'], node_v['x']])
        except: pass
    return coords_suaves

# =============================================================================
# NUEVO ENDPOINT: RUTA PUNTO A -> PUNTO B (Para Aproximación Real)
# =============================================================================
@router.get("/ruta-camino")
def obtener_ruta_camino(lat_origen: float, lon_origen: float, lat_destino: float, lon_destino: float):
    """
    Calcula la ruta real calle por calle entre dos puntos GPS.
    Usado para la fase de aproximación.
    """
    G = get_grafo()
    if G is None: raise HTTPException(503, "Mapa no cargado")
    
    try:
        # 1. Encontrar los nodos de calle más cercanos al GPS y al Destino
        nodo_a = ox.distance.nearest_nodes(G, lon_origen, lat_origen)
        nodo_b = ox.distance.nearest_nodes(G, lon_destino, lat_destino)
        
        # 2. Calcular la ruta más rápida (Dijkstra)
        ruta_nodos = nx.shortest_path(G, nodo_a, nodo_b, weight='travel_time')
        
        # 3. Obtener la geometría (curvas de las calles)
        coords = obtener_coords_suaves(G, ruta_nodos)
        
        # 4. Calcular distancia y tiempo reales sumando las aristas
        dist_m = 0
        tiempo_s = 0
        for i in range(len(ruta_nodos)-1):
            u, v = ruta_nodos[i], ruta_nodos[i+1]
            # Obtenemos datos de la calle (edge)
            # edge_data puede tener multiples keys si hay varias vias, tomamos la 0
            edges = G.get_edge_data(u, v)
            data = edges[0] # Tomamos la primera conexión
            
            dist_m += data.get('length', 0)
            tiempo_s += data.get('travel_time', 0)
            
        return {
            "coords": coords,
            "distancia_km": round(dist_m / 1000, 2),
            "tiempo_min": round(tiempo_s / 60)
        }
    except Exception as e:
        print(f"⚠️ Error calculando ruta aproximación: {e}")
        # Si falla (ej. no hay camino), devolvemos línea recta básica
        return {"coords": [[lat_origen, lon_origen], [lat_destino, lon_destino]], "distancia_km": 0, "tiempo_min": 0}

# =============================================================================
# 1. ENDPOINT SIMULACIÓN
# =============================================================================
@router.get("/simulacion-leaflet")
def simulacion_leaflet(
    id_inicio: str = None, id_fin: str = None, 
    accion_id: str = None, accion_tipo: str = None, valor_extra: int = None,
    lat_manual: float = None, lon_manual: float = None,
    zona_generacion: str = "neza", 
    reset: bool = False
):
    global CACHE_SIMULACION
    
    if reset: 
        CACHE_SIMULACION = {
            "puntos": [], "full_matrix_time": None, "nodos_totales": [],
            "id_inicio": None, "id_fin": None
        }
        print(">>> 🧹 CACHÉ REINICIADA")

    G = get_grafo()
    if G is None: raise HTTPException(503, "Cargando grafo (Espere un momento)...")

    puntos_totales = CACHE_SIMULACION.get("puntos", [])
    
    if accion_tipo:
        
        # --- GENERAR ALEATORIO ---
        if accion_tipo == "generar_random":
            print(f"\n>>> 🎲 GENERANDO EN: '{zona_generacion}'")
            
            clave_zona = zona_generacion.lower()
            if clave_zona not in COORDS_ZONAS: clave_zona = "neza"
            
            centro = COORDS_ZONAS[clave_zona]
            c_lat, c_lon = centro["lat"], centro["lon"]
            
            offset_local = 0.012 if clave_zona == "polanco" else OFFSET_ALEATORIO
            mn_lat, mx_lat = c_lat - offset_local, c_lat + offset_local
            mn_lon, mx_lon = c_lon - offset_local, c_lon + offset_local
            
            cantidad_puntos = random.randint(10, 40)
            
            lats_t, lons_t = [], []
            for _ in range(cantidad_puntos):
                lats_t.append(random.uniform(mn_lat, mx_lat))
                lons_t.append(random.uniform(mn_lon, mx_lon))
            
            try:
                nodos_raw = ox.distance.nearest_nodes(G, lons_t, lats_t)
                nodos = [int(n) for n in nodos_raw]
                
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
                if puntos_totales:
                    CACHE_SIMULACION["id_inicio"] = puntos_totales[0]["id"]
                    CACHE_SIMULACION["id_fin"] = puntos_totales[-1]["id"]
            except Exception as e: print(f"!!! ERROR: {e}")

        # --- CREAR MANUAL ---
        elif accion_tipo == "crear_manual" and lat_manual and lon_manual:
            try:
                nuevo_nodo = int(ox.distance.nearest_nodes(G, lon_manual, lat_manual))
                nd = G.nodes[nuevo_nodo]
                if isinstance(CACHE_SIMULACION["nodos_totales"], np.ndarray):
                    CACHE_SIMULACION["nodos_totales"] = CACHE_SIMULACION["nodos_totales"].tolist()
                CACHE_SIMULACION["nodos_totales"].append(nuevo_nodo)
                
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
                    "id": f"P-{len(puntos_totales)+1}", 
                    "lat": lat_manual, "lon": lon_manual, "lat_nodo": nd['y'], "lon_nodo": nd['x'],
                    "estado": "PENDIENTE", "idx": s-1, "rol_base": "NORMAL", "cluster_manual": None
                })
                CACHE_SIMULACION["puntos"] = puntos_totales
            except: pass

        # --- ACCIONES SOBRE PUNTOS ---
        elif accion_id:
            for p in puntos_totales:
                if p["id"] == accion_id:
                    if accion_tipo == "visitar": 
                        p["estado"] = "VISITADO"
                        CACHE_SIMULACION["id_inicio"] = accion_id 

                    elif accion_tipo == "omitir": p["estado"] = "OMITIDO"
                    elif accion_tipo == "restaurar": p["estado"] = "PENDIENTE"
                    elif accion_tipo == "asignar_zona": p["cluster_manual"] = None if valor_extra == -1 else valor_extra
                    elif accion_tipo == "fijar_inicio": CACHE_SIMULACION["id_inicio"] = accion_id
                    elif accion_tipo == "fijar_fin": CACHE_SIMULACION["id_fin"] = accion_id
                    elif accion_tipo == "desfijar_inicio": 
                        if CACHE_SIMULACION["id_inicio"] == accion_id: CACHE_SIMULACION["id_inicio"] = None
                    elif accion_tipo == "desfijar_fin": 
                        if CACHE_SIMULACION["id_fin"] == accion_id: CACHE_SIMULACION["id_fin"] = None
                    elif accion_tipo == "eliminar_punto":
                        if CACHE_SIMULACION["id_inicio"] == accion_id: CACHE_SIMULACION["id_inicio"] = None
                        if CACHE_SIMULACION["id_fin"] == accion_id: CACHE_SIMULACION["id_fin"] = None
                        p["estado"] = "ELIMINADO"
                    elif accion_tipo == "toggle_vip":
                        p["rol_base"] = "NORMAL" if p.get("rol_base") == "VIP" else "VIP"
                    elif accion_tipo == "avanzar_inicio":
                        p["estado"] = "VISITADO"
                    break

    # --- RESPUESTA ---
    pts = CACHE_SIMULACION["puntos"]
    if not pts: return {"paradas": [], "rutas_clusters": [], "ruta_global": None, "ruta_vip": None}

    nt = CACHE_SIMULACION["nodos_totales"]
    fmt = CACHE_SIMULACION["full_matrix_time"]
    id_ini, id_fin = CACHE_SIMULACION["id_inicio"], CACHE_SIMULACION["id_fin"]
    
    res_paradas = []
    puntos_activos = [p for p in pts if p["estado"] != "ELIMINADO"]

    for p in puntos_activos:
        tipo = "NORMAL"
        if p["id"] == id_ini and p["id"] == id_fin: tipo = "INICIO_FIN"
        elif p["id"] == id_ini: tipo = "INICIO"
        elif p["id"] == id_fin: tipo = "FIN"
        elif p["rol_base"] == "VIP": tipo = "VIP"
        res_paradas.append({**p, "tipo": tipo})

    idx_ini_n = next((i for i, p in enumerate(pts) if p["id"] == id_ini), None)
    idx_fin_n = next((i for i, p in enumerate(pts) if p["id"] == id_fin), None)

    # RUTA GLOBAL
    ruta_global_obj = None
    indices = [i for i, p in enumerate(pts) if (p["estado"] == "PENDIENTE" or i == idx_ini_n or i == idx_fin_n) and p["estado"] != "ELIMINADO"]
    if idx_ini_n is not None and len(indices) > 1:
        try:
            sub = fmt[np.ix_(indices, indices)]
            orden = optimizar_indices(indices, sub, idx_ini_n, idx_fin_n if idx_fin_n in indices else None)
            km, t = calcular_metricas(orden, nt, G, "Global")
            coords = []
            ruta_n = [nt[i] for i in orden]
            for i in range(len(ruta_n)-1):
                try:
                    path = nx.shortest_path(G, ruta_n[i], ruta_n[i+1], weight='travel_time')
                    coords.extend(obtener_coords_suaves(G, path))
                except: pass
            ruta_global_obj = {"coords": coords, "km": km, "tiempo": t}
        except: pass

    # RUTA VIP
    ruta_vip_obj = None
    idx_vip = [i for i, p in enumerate(pts) if p.get("rol_base")=="VIP" and p["estado"]=="PENDIENTE" and p["estado"] != "ELIMINADO"]
    if idx_ini_n is not None and idx_ini_n not in idx_vip: idx_vip.insert(0, idx_ini_n)
    if len(idx_vip) > 1:
        try:
            sub = fmt[np.ix_(idx_vip, idx_vip)]
            orden = optimizar_indices(idx_vip, sub, idx_ini_n if idx_ini_n in idx_vip else None, None)
            km, t = calcular_metricas(orden, nt, G, "VIP")
            coords = []
            ruta_n = [nt[i] for i in orden]
            for i in range(len(ruta_n)-1):
                try:
                    path = nx.shortest_path(G, ruta_n[i], ruta_n[i+1], weight='travel_time')
                    coords.extend(obtener_coords_suaves(G, path))
                except: pass
            ruta_vip_obj = {"coords": coords, "km": km, "tiempo": t}
        except: pass

    # ZONAS
    rutas_clusters = []
    clusters = {}
    for i, p in enumerate(pts):
        if p["estado"] != "ELIMINADO" and p.get("cluster_manual") is not None:
            clusters.setdefault(p["cluster_manual"], []).append(i)
    
    for cid, idxs in clusters.items():
        grupo = [i for i in idxs if pts[i]["estado"]=="PENDIENTE"]
        if idx_ini_n is not None and pts[idx_ini_n].get("cluster_manual")==cid:
            if idx_ini_n not in grupo: grupo.insert(0, idx_ini_n)
        if len(grupo) > 1:
            try:
                sub = fmt[np.ix_(grupo, grupo)]
                start = idx_ini_n if idx_ini_n in grupo else None
                orden = optimizar_indices(grupo, sub, start, None)
                km, t = calcular_metricas(orden, nt, G, f"Cluster {cid}")
                coords = []
                ruta_n = [nt[i] for i in orden]
                for i in range(len(ruta_n)-1):
                    try:
                        path = nx.shortest_path(G, ruta_n[i], ruta_n[i+1], weight='travel_time')
                        coords.extend(obtener_coords_suaves(G, path))
                    except: pass
                rutas_clusters.append({"cluster_id": cid, "coords": coords, "color": COLORES_ZONAS[cid%len(COLORES_ZONAS)], "km": km, "tiempo": t})
            except: pass

    return {"paradas": res_paradas, "rutas_clusters": rutas_clusters, "ruta_global": ruta_global_obj, "ruta_vip": ruta_vip_obj}

# CLUSTER MANUAL
class ClusterManualRequest(BaseModel):
    nombre: str; nodos_ids: List[int]
class ClusterResponse(BaseModel):
    nombre: str; distancia_km: float; tiempo_min: str; path_coords: List[List[float]]; nodos_secuencia: List[int]
@router.post("/cluster-manual", response_model=ClusterResponse)
def crear_cluster_manual(datos: ClusterManualRequest):
    G = get_grafo()
    if G is None: raise HTTPException(503, "Grafo no cargado")
    nodos = datos.nodos_ids
    if len(nodos) < 2: return {"nombre": datos.nombre, "distancia_km": 0, "tiempo_min": "0m", "path_coords": [], "nodos_secuencia": nodos}
    indices = list(range(len(nodos)))
    km, tiempo_str = calcular_metricas(indices, nodos, G, f"Manual {datos.nombre}")
    path_coords = []
    for i in range(len(nodos)-1):
        try:
            path = nx.shortest_path(G, nodos[i], nodos[i+1], weight='travel_time')
            path_coords.extend(obtener_coords_suaves(G, path))
        except: pass
    return {"nombre": datos.nombre, "distancia_km": km, "tiempo_min": tiempo_str, "path_coords": path_coords, "nodos_secuencia": nodos}