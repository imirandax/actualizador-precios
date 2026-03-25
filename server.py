from flask import Flask
import subprocess
import os

app = Flask(__name__)

@app.route('/ejecutar')
def ejecutar():
    print("🔥 Ejecutando en servidor nube")
    subprocess.Popen(["python", "script_final.py"])
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
