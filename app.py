import os
import math
import urllib.request
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Questa funzione permette al tuo sito Aruba di dialogare in sicurezza con Render
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET')
    return response

def quota_in_pressione_hpa(altitudine_metri):
    return 1013.25 * (1 - 0.0000065 * altitudine_metri)**5.256

def mappa_pressione_livello_meteo(pressione_hpa):
    livelli_standard = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30, 20, 10]
    return min(livelli_standard, key=lambda x: abs(x - pressione_hpa))

def ottieni_meteo_in_quota(lat, lon, pressione_target_hpa):
    livello = mappa_pressione_livello_meteo(pressione_target_hpa)
    url = f"https://open-meteo.com{lat}&longitude={lon}&hourly=temperature_{livello}hPa,relative_humidity_{livello}hPa&forecast_days=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            dati = json.loads(response.read().decode())
            temp = dati["hourly"][f"temperature_{livello}hPa"][0]
            umi = dati["hourly"][f"relative_humidity_{livello}hPa"][0]
            return temp, umi
    except:
        return -52.0, 60.0

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
    
    # Traffico simulato ad alta quota sopra la posizione dell'utente
    voli = [
        {"callsign": "ITA102", "offset_lat": 0.05, "offset_lon": -0.05, "quota": 11000},
        {"callsign": "RYR456", "offset_lat": -0.08, "offset_lon": 0.09, "quota": 9800},
        {"callsign": "UAE05A", "offset_lat": 0.12, "offset_lon": 0.02, "quota": 11500},
        {"callsign": "DLH231", "offset_lat": -0.03, "offset_lon": -0.11, "quota": 8500}
    ]
    
    risultati = []
    for v in voli:
        v_lat = lat + v["offset_lat"]
        v_lon = lon + v["offset_lon"]
        pressione = quota_in_pressione_hpa(v["quota"])
        temp, umi = ottieni_meteo_in_quota(v_lat, v_lon, pressione)
        verdetto, _ = analizza_scia(v["quota"], temp, umi)
        
        risultati.append({
            "callsign": v["callsign"],
            "lat": v_lat,
            "lon": v_lon,
            "quota": v["quota"],
            "temp": round(temp, 1),
            "umi": int(umi),
            "scia": verdetto
        })
    return jsonify(risultati)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
