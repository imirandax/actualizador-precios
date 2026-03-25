from flask import Flask
import subprocess

app = Flask(__name__)

@app.route('/ejecutar')
def ejecutar():
    print("🔥 Ejecutando en servidor nube")

    subprocess.Popen(["python", "script_final.py"])

    return "OK", 200


if __name__ == "__main__":
    app.run()