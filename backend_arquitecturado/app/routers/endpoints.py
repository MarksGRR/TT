from fastapi import APIRouter, HTTPException
import random
import numpy as np
import networkx as nx
import osmnx as ox
from app.core.config import LAT_CENTRO, LON_CENTRO
from app.core.mapa import get_grafo
from app.services.logica_rutas import calcular_metricas, optimizar_indices

router = APIRouter()

# --- CACHE EN MEMORIA ---
CACHE_SIMULACION = {
    "puntos": [], "full_matrix_time": None, "nodos_totales": [],
    "id_inicio": None, "id_fin": None     
}

COLORES_ZONAS = ["#00E5FF", "#E040FB", "#C6FF00", "#FF9100", "#FF4081", "#7C4DFF"]

def haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

@router.get("/simulacion-leaflet")
def simulacion_leaflet(
    id_inicio: str = None, id_fin: str = None, 
    accion_id: str = None, accion_tipo: str = None, valor_extra: int = None,
    lat_manual: float = None, lon_manual: float = None,
    reset: bool = False
):
    global CACHE_SIMULACION
    
    # SIEMPRE USAMOS EL GRAFO ESTÁTICO (NEZA/ARAGÓN)
    G = get_grafo() 
    if G is None: raise HTTPException(503, "Cargando grafo...")

    if reset: 
        CACHE_SIMULACION = {
            "puntos": [], "full_matrix_time": None, "nodos_totales": [],
            "id_inicio": None, "id_fin": None
        }

    puntos_totales = CACHE_SIMULACION.get("puntos", [])
    
    if accion_tipo:
        
        # --- A) GENERAR PUNTOS ALEATORIOS EN NEZA (FIJO) ---
        if accion_tipo == "generar_random":
            print(">>> Generando puntos en zona predeterminada (Neza)")
            
            # RANGO FIJO DE NEZA
            mn_lat = LAT_CENTRO - 0.015
            mx_lat = LAT_CENTRO + 0.015
            mn_lon = LON_CENTRO - 0.015
            mx_lon = LON_CENTRO + 0.015

            CANTIDAD = 15
            puntos_totales = []
            lats_t, lons_t = [], []
            
            for i in range(CANTIDAD):
                lats_t.append(random.uniform(mn_lat, mx_lat))
                lons_t.append(random.uniform(mn_lon, mx_lon))
                
            try:
                # Pegar a calles reales (Snap)
                nodos = ox.distance.nearest_nodes(G, lons_t, lats_t)
                
                for i, nid in enumerate(nodos):
                    node_data = G.nodes[nid]
                    rol = "VIP" if random.random() < 0.20 else "NORMAL"
                    puntos_totales.append({
                        "id": f"P-{i+1}", 
                        "lat": node_data['y'], 
                        "lon": node_data['x'], 
                        "estado": "PENDIENTE", 
                        "idx": i, 
                        "rol_base": rol, 
                        "cluster_manual": None
                    })

                # Matriz
                num = len(nodos)
                ft = np.zeros((num, num))
                for i in range(num):
                    for j in range(i+1, num):
                        try:
                            t = nx.shortest_path_length(G, nodos[i], nodos[j], weight='travel_time')
                            ft[i][j]=t; ft[j][i]=t
                        except: ft[i][j]=9e9; ft[j][i]=9e9
                
                CACHE_SIMULACION["puntos"] = puntos_totales
                CACHE_SIMULACION["full_matrix_time"] = ft
                CACHE_SIMULACION["nodos_totales"] = nodos
                
                if puntos_totales:
                    CACHE_SIMULACION["id_inicio"] = puntos_totales[0]["id"]
                    CACHE_SIMULACION["id_fin"] = puntos_totales[-1]["id"]
                    
            except Exception as e:
                print(f"Error generando: {e}")
                CACHE_SIMULACION["puntos"] = []

        # --- B) CREAR MANUAL (SNAP A CALLE) ---
        elif accion_tipo == "crear_manual" and lat_manual and lon_manual:
            try:
                nuevo_nodo = ox.distance.nearest_nodes(G, lon_manual, lat_manual)
                nd = G.nodes[nuevo_nodo]
                nuevo_idx = len(puntos_totales)
                puntos_totales.append({
                    "id": f"P-{nuevo_idx+1}", "lat": nd['y'], "lon": nd['x'], 
                    "estado": "PENDIENTE", "idx": nuevo_idx, "rol_base": "NORMAL", "cluster_manual": None
                })
                CACHE_SIMULACION["nodos_totales"].append(nuevo_nodo)
                
                # Matriz incremental
                old_matrix = CACHE_SIMULACION["full_matrix_time"]
                nodos = CACHE_SIMULACION["nodos_totales"]
                num = len(nodos); ft = np.zeros((num, num))
                if old_matrix is not None:
                    s = old_matrix.shape[0]; ft[:s, :s] = old_matrix
                    target = nodos[num-1]
                    for i in range(s):
                        try:
                            d = nx.shortest_path_length(G, nodos[i], target, weight='travel_time')
                            ft[i][s] = d; ft[s][i] = d
                        except: ft[i][s]=9e9; ft[s][i]=9e9
                CACHE_SIMULACION["full_matrix_time"] = ft
                CACHE_SIMULACION["puntos"] = puntos_totales
            except: pass

        # --- C) AVANZAR ---
        elif accion_tipo == "avanzar_inicio":
            curr = CACHE_SIMULACION["id_inicio"]
            idx = next((i for i, p in enumerate(puntos_totales) if p["id"]==curr), None)
            if idx is not None:
                puntos_totales[idx]["estado"] = "VISITADO"
                # Buscar siguiente pendiente en la zona o global
                zona = puntos_totales[idx].get("cluster_manual")
                cands = [i for i, p in enumerate(puntos_totales) if (p["estado"] == "PENDIENTE" and (zona is None or p.get("cluster_manual") == zona))]
                
                if cands:
                    # Pequeña optimización local
                    sub = CACHE_SIMULACION["full_matrix_time"][np.ix_([idx]+cands, [idx]+cands)]
                    ruta = optimizar_indices([idx]+cands, sub, 0, None)
                    if len(ruta) > 1:
                        next_real_idx = ([idx]+cands)[ruta[1]]
                        CACHE_SIMULACION["id_inicio"] = puntos_totales[next_real_idx]["id"]

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
        elif accion_tipo == "borrar_zona":
            for p in puntos_totales:
                if p.get("cluster_manual") == valor_extra: p["cluster_manual"] = None

    # RESPUESTA
    pts = CACHE_SIMULACION["puntos"]
    if not pts: return {"paradas": [], "rutas_clusters": [], "ruta_global": None, "ruta_vip": None}

    nt = CACHE_SIMULACION["nodos_totales"]
    fmt = CACHE_SIMULACION["full_matrix_time"]
    id_ini = CACHE_SIMULACION["id_inicio"]
    id_fin = CACHE_SIMULACION["id_fin"]
    
    res_paradas = []
    for p in pts:
        tipo = "NORMAL"
        if p["id"] == id_ini: tipo = "INICIO"
        elif p["id"] == id_fin: tipo = "FIN"
        elif p["rol_base"] == "VIP": tipo = "VIP"
        res_paradas.append({**p, "tipo": tipo})

    # RUTA GLOBAL
    indices_globales = [i for i, p in enumerate(pts) if p["estado"] == "PENDIENTE" or i == next((k for k, x in enumerate(pts) if x["id"]==id_ini), -1) or i == next((k for k, x in enumerate(pts) if x["id"]==id_fin), -1)]
    idx_ini_n = next((i for i, p in enumerate(pts) if p["id"] == id_ini), None)
    idx_fin_n = next((i for i, p in enumerate(pts) if p["id"] == id_fin), None)
    
    orden_final = indices_globales
    if idx_ini_n is not None and len(indices_globales) > 1:
         sub = fmt[np.ix_(indices_globales, indices_globales)]
         orden_final = optimizar_indices(indices_globales, sub, idx_ini_n, idx_fin_n if idx_fin_n in indices_globales else None)

    ruta_coords = []
    total_km = 0
    total_min = 0

    if len(orden_final) > 1:
        for k in range(len(orden_final)-1):
            u, v = orden_final[k], orden_final[k+1]
            try:
                # Intentar ruta real con el grafo estático (G)
                path = nx.shortest_path(G, nt[u], nt[v], weight='travel_time')
                for nid in path: ruta_coords.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
                d = nx.shortest_path_length(G, nt[u], nt[v], weight='length')
                total_km += d/1000
                total_min += (d/1000) / 20 * 60
            except:
                # Fallback linea recta
                p1, p2 = pts[u], pts[v]
                ruta_coords.append([p1["lat"], p1["lon"]]); ruta_coords.append([p2["lat"], p2["lon"]])
                d = haversine_dist(p1["lat"], p1["lon"], p2["lat"], p2["lon"])
                total_km += d; total_min += (d / 20 * 60)

    t_fmt = f"{int(total_min//60)}h {int(total_min%60)}m" if total_min > 60 else f"{int(total_min)} min"

    # ZONAS
    rutas_clusters = []
    clusters_map = {}
    for i, p in enumerate(pts):
        if p.get("cluster_manual") is not None: clusters_map.setdefault(p["cluster_manual"], []).append(i)
    
    for cid, indices in clusters_map.items():
        grupo = [i for i in indices if pts[i]["estado"] == "PENDIENTE" or i == idx_ini_n or i == idx_fin_n]
        if len(grupo) > 1:
            try:
                sub = fmt[np.ix_(grupo, grupo)]
                ruta = optimizar_indices(grupo, sub, idx_ini_n if idx_ini_n in grupo else None, idx_fin_n if idx_fin_n in grupo else None)
                coords_z = []
                for k in range(len(ruta)-1):
                    p1, p2 = pts[ruta[k]], pts[ruta[k+1]]
                    coords_z.append([p1["lat"], p1["lon"]]); coords_z.append([p2["lat"], p2["lon"]])
                rutas_clusters.append({"cluster_id": cid, "coords": coords_z, "color": COLORES_ZONAS[cid%len(COLORES_ZONAS)], "km": 0, "tiempo": ""})
            except: pass

    return {
        "paradas": res_paradas,
        "rutas_clusters": rutas_clusters,
        "ruta_global": {"coords": ruta_coords, "km": round(total_km, 2), "tiempo": t_fmt},
        "ruta_vip": None
    }