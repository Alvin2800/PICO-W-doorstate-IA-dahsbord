from flask import Flask, request, jsonify
import mysql.connector
import os
from datetime import datetime
import pandas as pd
from sklearn.ensemble import IsolationForest
import google.generativeai as genai

app = Flask(__name__)

# =========================
# CONNEXION MYSQL RAILWAY
# =========================

db_config = {
    "host": os.getenv("MYSQLHOST"),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "database": os.getenv("MYSQLDATABASE"),
    "port": int(os.getenv("MYSQLPORT", 3306))
}


def db_connect():
    return mysql.connector.connect(**db_config)


# =========================
# INITIALISATION DB
# =========================

def init_db():
    try:
        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS door_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME,
                device_id VARCHAR(50),
                door_state INT
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()

        print("Table door_events OK", flush=True)

    except Exception as e:
        print("Erreur DB :", e, flush=True)


init_db()


# =========================
# ACCUEIL
# =========================

@app.route("/")
def home():
    return "DOOR MONITORING API WORKING"


# =========================
# TEST DB
# =========================

@app.route("/test-db")
def test_db():
    try:
        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Connexion MySQL OK",
            "result": result[0]
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================
# RECEPTION DONNEES PICO W
# =========================

@app.route("/door-data")
@app.route("/Door_data")
def door_data():
    try:
        device_id = request.args.get("device_id", "porte_001")
        door_state = request.args.get("door_state")

        if door_state is None:
            return jsonify({
                "status": "error",
                "message": "door_state manquant"
            }), 400

        door_state = int(door_state)

        if door_state not in [0, 1]:
            return jsonify({
                "status": "error",
                "message": "door_state doit etre 0 ou 1"
            }), 400

        conn = db_connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO door_events (timestamp, device_id, door_state)
            VALUES (%s, %s, %s)
        """, (datetime.now(), device_id, door_state))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "device_id": device_id,
            "door_state": door_state
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================
# HISTORIQUE
# =========================

@app.route("/door-logs")
@app.route("/Door_logs")
def door_logs():
    try:
        conn = db_connect()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM door_events
            ORDER BY timestamp DESC
            LIMIT 100
        """)

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================
# ANALYSE ISOLATION FOREST
# =========================

@app.route("/door-analyze")
@app.route("/annalyse")
def door_analyze():
    try:
        conn = db_connect()

        query = """
            SELECT *
            FROM door_events
            ORDER BY timestamp ASC
        """

        df = pd.read_sql(query, conn)
        conn.close()

        if len(df) < 5:
            return jsonify({
                "status": "error",
                "message": "Pas assez de donnees pour lancer IsolationForest"
            }), 400

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        df["minute"] = df["timestamp"].dt.minute

        features = df[["door_state", "hour", "minute"]]

        model = IsolationForest(
            contamination=0.15,
            random_state=42
        )

        df["anomaly"] = model.fit_predict(features)

        results = []

        for _, row in df.iterrows():
            results.append({
                "id": int(row["id"]),
                "timestamp": str(row["timestamp"]),
                "device_id": row["device_id"],
                "door_state": int(row["door_state"]),
                "door_label": "OUVERTE" if int(row["door_state"]) == 1 else "FERMEE",
                "status": "ANOMALIE" if int(row["anomaly"]) == -1 else "NORMAL"
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================
# RAPPORT IA GEMINI
# =========================

@app.route("/door-report")
@app.route("/rapport")
def door_report():
    try:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "GEMINI_API_KEY manquante"
            }), 500

        genai.configure(api_key=api_key)

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        conn = db_connect()

        if start_date and end_date:
            query = """
                SELECT *
                FROM door_events
                WHERE DATE(timestamp) BETWEEN %s AND %s
                ORDER BY timestamp ASC
            """
            df = pd.read_sql(query, conn, params=(start_date, end_date))
        else:
            query = """
                SELECT *
                FROM door_events
                ORDER BY timestamp ASC
            """
            df = pd.read_sql(query, conn)

        conn.close()

        if len(df) < 5:
            return jsonify({
                "status": "error",
                "message": "Pas assez de donnees pour generer un rapport IA"
            }), 400

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        df["minute"] = df["timestamp"].dt.minute

        features = df[["door_state", "hour", "minute"]]

        model = IsolationForest(
            contamination=0.15,
            random_state=42
        )

        df["anomaly"] = model.fit_predict(features)

        anomalies = df[df["anomaly"] == -1]

        if anomalies.empty:
            return jsonify({
                "status": "success",
                "report": "Aucune anomalie d'ouverture de porte detectee sur la periode selectionnee."
            })

        anomaly_text = ""

        for _, row in anomalies.iterrows():
            anomaly_text += f"""
Horodatage: {row['timestamp']}
Appareil: {row['device_id']}
Etat porte: {"OUVERTE" if int(row['door_state']) == 1 else "FERMEE"}
Statut IA: ANOMALIE
---
"""

        periode_text = (
            f"Periode analysee: du {start_date} au {end_date}"
            if start_date and end_date
            else "Periode analysee: toutes les donnees disponibles"
        )

        prompt = f"""
Tu es un assistant industriel specialise en IoT, securite de site,
supervision de porte, detection d'anomalies et maintenance intelligente.

{periode_text}

Voici les anomalies detectees par IsolationForest:

{anomaly_text}

Redige un rapport court en francais avec cette structure:

1. Resume de la situation
2. Interpretation possible
3. Recommandation technique

Le rapport doit etre professionnel, clair et facile a comprendre.
"""

        model_gemini = genai.GenerativeModel("gemini-2.5-flash")
        response = model_gemini.generate_content(prompt)

        return jsonify({
            "status": "success",
            "start_date": start_date,
            "end_date": end_date,
            "report": response.text
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =========================
# LANCEMENT LOCAL / RAILWAY
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000))
    )

        
        
            
        
        
        
                 
                       
    

