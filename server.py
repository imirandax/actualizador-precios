from flask import Flask
import subprocess

app = Flask(__name__)

proceso_activo = None

@app.route("/")
def home():
    return "Servidor activo"

@app.route("/ejecutar")
def ejecutar():
    print("🔥 Ejecutando en servidor nube")

    resultado = subprocess.run(
        ["python", "script_final.py"],
        capture_output=True,
        text=True
    )

    print("STDOUT:\n", resultado.stdout)
    print("STDERR:\n", resultado.stderr)

    return "OK", 200
