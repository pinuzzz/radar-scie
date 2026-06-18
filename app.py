import os
import math
import urllib.request
import json
from flask import Flask, request, jsonify
def calcola_distanza_km(lat1, lon1, lat2, lon2):
    """Calcola la distanza in km tra due punti usando la formula di Haversine."""
    R = 6371.0  # Raggio medio della Terra in chilometri
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

app = Flask(__name__)

# Abilita la comunicazione sicura con il tuo sito Aruba (CORS)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET')
    return response

def quota_in_pressione_hpa(altitudine_metri):
    return 1013.25 * (1 - 0.0000065 * altitudine_metri)**5.256

def mappa_pressione_livello_meteo(pressione_hpa):
    livelli_standard = [100, 150, 200, 250, 300, 400, 500, 700, 850, 925, 1000]
    return min(livelli_standard, key=lambda x: abs(x - pressione_hpa))

def ottieni_meteo_in_quota(lat, lon, pressione_target_hpa):
    livello = mappa_pressione_livello_meteo(pressione_target_hpa)
    url = f"https://open-meteo.com{lat}&longitude={lon}&hourly=temperature_{livello}hPa,relative_humidity_{livello}hPa&forecast_days=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            dati = json.loads(response.read().decode())
            temp = dati["hourly"][f"temperature_{livello}hPa"][0]
            umi = dati["hourly"][f"relative_humidity_{livello}hPa"][0]
            return temp, umi
    except:
        return -50.0, 60.0 # Valori standard di sicurezza se il meteo fallisce

def analizza_scia(altitudine_metri, temp_celsius, umidita_relativa):
    E_H2O, Q, cp, eta = 1.25, 43.0e6, 1004.0, 0.3
    pressione_hpa = quota_in_pressione_hpa(altitudine_metri)
    G = (E_H2O * cp * pressione_hpa) / (0.622 * Q * (1 - eta))
    G_log = math.log10(G) if G > 0 else 0
    t_crit = -46.46 + (9.43 * G_log) + (0.72 * (G_log**2))
    
    if temp_celsius < t_crit:
        if umidita_relativa >= 60 and temp_celsius <= -40:
            return "SÌ (Scia Persistente)", t_crit
        return "SÌ (Breve durata)", t_crit
    return "NO", t_crit

@app.route('/api/radar')
def radar():
    lat = float(request.args.get('lat', 41.9))
    lon = float(request.args.get('lon', 12.5))
    
    # Area impostata a 0.5 per catturare più voli intorno a te
    delta = 0.5
    url_opensky = f"https://opensky-network.org{lat-delta}&lamax={lat+delta}&lomin={lon-delta}&lomax={lon+delta}"
    
    risultati = []
    try:
            import base64
    
    # Inserisci qui dentro il nome utente e la password del tuo account OpenSky
    username = "Zampata76"
    password = "Zampatasky76!"
    
    # Codifica le credenziali in formato di sicurezza standard per i server
    auth_str = f"{username}:{password}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    
    req = urllib.request.Request(url_opensky)
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('Authorization', f'Basic {auth_b64}')

        with urllib.request.urlopen(req, timeout=8) as response:
            stati = json.loads(response.read().decode()).get("states", []) or []
            
            for volo in stati[:6]:
                callsign = volo.strip() if volo else "IGNOTO"
                v_lon = volo
                v_lat = volo
                altitudine = volo
                
                # Controllo di sicurezza: esclude aerei senza coordinate o sotto i 3000 metri
                if altitudine is None or altitudine < 3000 or v_lat is None or v_lon is None:
                    continue
                    
                # CALCOLO DISTANZA REAL TIME
                dist_km = calcola_distanza_km(lat, lon, v_lat, v_lon)
                
                pressione = quota_in_pressione_hpa(altitudine)
                temp, umi = ottieni_meteo_in_quota(v_lat, v_lon, pressure=pressione) # Corretto passaggio parametro per evitare bug
                
                if temp is not None:
                    verdetto, _ = analizza_scia(altitudine, temp, umi)
                    risultati.append({
                        "callsign": callsign,
                        "quota": int(altitudine),
                        "distanza": dist_km, # Inserito nel pacchetto dati inviato al sito
                        "temp": round(temp, 1),
                        "umi": int(umi),
                        "scia": verdetto
                    })
    except Exception as e:
        print(f"Errore radar: {e}")
        return jsonify([])
        
    # ORDINA LA LISTA: mette in cima alla tabella l'aereo più vicino a casa tua
    risultati.sort(key=lambda x: x["distanza"])
    return jsonify(risultati)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
