from flask import Flask
import subprocess
import os

app = Flask(__name__)

proceso_activo = None

@app.route("/")
def home():
    return "Servidor activo"

@app.route("/ejecutar")
def ejecutar():
    global proceso_activo

    print("🔥 Ejecutando en servidor nube")

    # 🔒 evitar doble ejecución
    if proceso_activo and proceso_activo.poll() is None:
        return "⚠️ Ya hay un proceso en ejecución", 200

    proceso_activo = subprocess.Popen(
        ["python", "script_final.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return "OK", 200
