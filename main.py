from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        emergency INTEGER NOT NULL
    )
    """)

    conn.commit()
    conn.close()

init_db()

def insert_data(timestamp, temperature, humidity, emergency):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO measurements (timestamp, temperature, humidity, emergency)
        VALUES (?, ?, ?, ?)
    """, (timestamp, temperature, humidity, emergency))

    conn.commit()
    conn.close()

temperature = 0.0
humidity = 0.0
emergency = 0

@app.route("/")
def home():
    return "IoT API Alvin Running"

@app.route("/data")
def data():
    global temperature, humidity, emergency

    temperature = float(request.args.get("temp", 0))
    humidity = float(request.args.get("hum", 0))
    emergency = int(request.args.get("emergency", 0))

    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": temperature,
        "humidity": humidity,
        "emergency": emergency
    }

    insert_data(
        log_entry["timestamp"],
        log_entry["temperature"],
        log_entry["humidity"],
        log_entry["emergency"]
    )

    print("Données reçues :", log_entry, flush=True)

    return "OK", 200

@app.route("/status")
def status():
    return jsonify({
        "temperature": temperature,
        "humidity": humidity,
        "emergency": emergency
    })

@app.route("/logs")
def get_logs():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT timestamp, temperature, humidity, emergency
        FROM measurements
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    logs = []
    for row in rows:
        logs.append({
            "timestamp": row[0],
            "temperature": row[1],
            "humidity": row[2],
            "emergency": row[3]
        })

    return jsonify(logs)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)