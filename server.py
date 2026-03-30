from flask import Flask
import subprocess

app = Flask(__name__)

proceso_activo = None

@app.route("/")
def home():
    return "Servidor activo"

@app.route("/ejecutar")
def ejecutar():
    global proceso_activo

    print("🔥 Ejecutando en servidor nube")

    if proceso_activo and proceso_activo.poll() is None:
        return "⚠️ Ya hay un proceso en ejecución", 200

    proceso_activo = subprocess.Popen(
        ["python", "script_final.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    return "Proceso iniciado", 200
