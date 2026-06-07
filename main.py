from flask import Flask, request, jsonify
import mysql.connector                               #bibliothèque pour gerer les table sql
import os                                            #bibliotheque pour les variables externe
from datetime import datetime                        #bibliothèque pour gerer les dates
import pandas as pd                                  #bibliothèque pour gerer les tableurs
from sklearn.ensemble import IsolationForest         #bibliothèque IA  machine learning
from google.generativeai import genai                #bibliothèque IA generative

app=Flask(__name__)
# connection à mysql sur lenvironnement railway

db_config={
    "user":os.getenv("MYSQLUSER"),
    "host":os.getenv("MYSQLHOST"),
    "database":os.getenv("MYSQLDATABASE"),
    "password":os.getenv("MYSQLPASSWORD"),
    "port":int(os.getenv("MYSQLPORT",3306))
}
def db_connect():
    return mysql.connector.connect(**db_config)
#initialisation de la DB

def init_db():
    try:
        conn=db_connect()
        cursor=conn.cursor()
        cursor.execute("""
           CREATE TABLEIF NOT EXIST Door_events(
              id INT AUTO_INCREMENT PRIMARY KEY,
              timestamp DATETIME,
              device_id VARCHAR(25),
              door_state INT)
        """ )
        conn.commit()
        cursor.close()
        conn.close()
        print("table door_event OK")
    except exception as e:
        print("erreur DB",e,flush=True)
init_db()

#creation des routes

@app.route("/")
def home():
    return "API WORKING GOOD"

#route pour recuperer les data à pico w, la stocker dans la DB et retourner les valeur du device_id et de l'etat de la porte
@app.route("/Door_data")
def data():
    try:
        device_id=request.args.get("device_id","porte_001")
        door_state=request.args.get("door_state")
        timestamp=datetime.now()
        if door_state None:
        return jsonify({
            "status":"error",
            "message":"door_state manquant"
        }),400
        if door_state not in [0,1]:
            return jsonify({
                "status":"error",
                "message":"door_state doit etre en 0 et 1"
            }),400
        conn=db_connect()
        cursor=conn.cursor()
        cursor.execute("""
           INSERT INTO door_event (timestamp,device_id,door_state)
           VALUES (%s,%s,"%s)"""(timestamp,device_id,door_state))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({
            "status":"sucess",
            "device_id":device_id,
            "door_state":door_state})
    except Exception as e:
        return jsonify({
            "state":"error",
            "message":str(e)
        }),500
            
        
        #historique
@app.route("/Door_logs")
def logs():
    try:
        conn=db_connect()
        cursor=conn.cursor()
        cursor.execute("""
           SELECT * 
           FROM door_event 
           ORDER BY timestamp DESC
           LIMIT 100
        
        """)
        data=cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "status":"error",
            "message":str(e)
        }),500

#annalyse des anormaly grace à l'IA

@app.route("/annalyse")
def annalyse():
    try:
        conn=db_connect()
        query="""
           SELECT *
           FROM door_event 
           ORDER BY timestamp
        """
        df=pd.to_sql(query, conn)
        conn.close()
        
        if len(df)<5:
            return jsonify({
                "state":"error",
                "message":"pas assee de donnees pour isolatioforest"
            })
        df["timestamp"]=pd.to_datetime(df["datetime"])
        df["hour"]=df["timestamp"].dt.hour
        df["minute"]=df["timestamp"].dt.minute

        features=df[["door_state","hour","minute"]]

        model=IsolationForest(
                   contamination=1.5
                   random_state=42
                   )
        df["anomaly"]=model.fit_predict(features)
    result=[]
    for _, row in interrows():
        resultat.append({
            "id":int(row["id"]),
            "timestamp":str(row["timestamp"]),
            "device_id":row["device_id"],
            "door_state":int(row["door_state"]),
            "door_label":"OUVERTE" if row["door_state"]==1 else "FERMEE",
            "status":"ANORMALIE" if row["anormaly"]==-1 else "NORMAL"
        })
    return jsonify(resultat)
except Exception as e:
   return jsonify({
       "status":"error",
       "message":str(e)
   }),500

#rapport gemini
@app.route("/rapport")
def rapport():
    try:
        api_key=os.getenv("GEMINY_API_KEY")
        if not api_key:
            return jsonify({
                "state":"error",
                "message":"gemini_api_key  manquante"
            }),500
        start_date=request.args.get("start_date")
        end_date=request.args.get("end_date")
        conn=db_connect()
        if start_date and end_date:
            query="""
                SELECT *
                FROM door_event
                WHERE DATE(timestamp) BETWEEN %s AND %s
                ORDER BY timestamp ASC
            """
            df=pd.read_sql(query,conn,params=(start_date, end_date))
        else:
            query="""
                SELECT *
                FROM door_event
                ORDER BY timestamp ASC
            """
            df=pd.read_sql(query,conn)

        if len(df)<5:
            return jsonify({
                "status":"error",
                "message":"pas assez de donnee pour isolationForest"
                )}
        df["timestamp"]=pd.to_datetime["timestamp"]
        df["hour"]=df["timestamp"].dt.hour
        df["minute"]=df{"timestamp"].dt.minute
        feature=df["door_state","hour","minute"]
        model=IsolationForest(
            contamination=0.15,
            random_state=42
        )
            
        df["anormaly"]=model.fit_predict(feature)
        anomalies=df[df["anormaly"]==-1]
        if anomalies.empty:
            return jsonify({
                "state":"success",
                "message":"aucune Anormalie d'ouverture detectée sur la periode selectionnee."
            })
        anormaly_text=""
        for _, row in anormalies.interows():
            anormaly_text+=f"""
Horodatage:{row['timestamp']}
Appareil:{row['device_id']}
Etat porte: {"OUVERTE" if row['door_state']==1 else "FERMEE"}
"""
            periode_text=(
                f"periode analysee: du {start_date} au {end_date}"
                if start_date and end_date
                else "periode analysee: toutes les donnees disponibles"
            )
            prompt=f"""
Tu es un assistant industriel specialise en IOT , securite de site, supervision de porte, detection d'anormalie et maintenance intelligente.
{periode_text}
voici les anomlies detectees par IsolationForest:
{anormaly_text}
Redige un rapport court en francais avec cette structure:
1.Resume de la situation
2.Interpretation possible
3.Recommandation technique

le rapport dois etre professionnel, clair et facile à comprendre
"""
            model_gemini=genai.GenerativeModel("gemini-2.5-flash")
            reponse=model.gimini.generate_content(prompt)
            return jsonify({
                "status":"success",
                "start_date":start_date,
                "end_date":end_date,
                "report":reponse.text
            })
    except Exception as e:
        return jsonify({
            "status":"error",
            "message":str(e)
        })


#lancement local

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))

        
        
            
        
        
        
                 
                       
    

