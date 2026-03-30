import requests
from bs4 import BeautifulSoup
import re
import gspread
import time
from google.oauth2.service_account import Credentials

# 🔐 Google Sheets
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "/etc/secrets/credenciales.json",
    scopes=scope
)

client = gspread.authorize(creds)

for intento in range(5):
    try:
        sheet = client.open("PRECIOS ALMACEN").sheet1
        print("✅ Conectado a Google Sheets")
        break
    except Exception as e:
        print(f"⚠️ Error conectando a Sheets (intento {intento+1}): {e}")
        time.sleep(5)
else:
    raise Exception("❌ No se pudo conectar a Google Sheets")

# 📄 Leer datos
data_formulas = sheet.get_all_values(value_render_option='FORMULA')
data_valores = sheet.get_all_values()

# 🔧 Extraer link + SKU
def extraer_link_y_sku(celda):
    celda = str(celda)
    link = None
    sku = celda
    if "HYPERLINK" in celda.upper():
        partes = re.findall(r'"([^"]*)"', celda)
        if len(partes) >= 2:
            link = partes[0].strip()
            sku = partes[1].strip()
    return link, sku

# 🔧 Normalizar precio
def normalizar_precio(texto):
    texto = texto.replace("$", "").replace(".", "").replace(",", ".").strip()
    return round(float(texto))

# 🔎 Obtener precio desde HTML
def obtener_precio(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            print("⚠️ Error HTTP:", response.status_code)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # 🔥 buscar precio final
        precio_span = soup.find("span", {"data-price-type2": "finalPrice"})

        if precio_span:
            precio_texto = precio_span.get("data-price-amount")
            return normalizar_precio(precio_texto)

        print("⚠️ No encontró precio en HTML")
        return None

    except Exception as e:
        print("❌ Error obteniendo precio:", e)
        return None

# 📊 Progreso
inicio = time.time()
total_filas = len(data_formulas)
procesadas = 0

for i, fila in enumerate(data_formulas, start=1):
    procesadas += 1

    porcentaje = (procesadas / total_filas) * 100
    print(f"\n🚀 {procesadas}/{total_filas} ({porcentaje:.1f}%)")

    if len(fila) < 4:
        continue

    marca = str(fila[0]).strip()
    sku_raw = str(fila[3]).strip()

    try:
        costo_actual = str(data_valores[i-1][1])
    except:
        costo_actual = ""

    # 📦 categorías
    if marca.isupper() and not sku_raw:
        print(f"📦 {marca}")
        continue

    if not marca or not sku_raw:
        continue
    if marca.upper() == "MARCA":
        continue
    if sku_raw.upper() == "SKU":
        continue

    link_directo, sku = extraer_link_y_sku(sku_raw)

    if not link_directo:
        print("⚠️ Sin link → salto")
        continue

    print(f"🔎 Fila {i} | {marca} | SKU {sku}")

    precio_final = obtener_precio(link_directo)

    # 🚨 lógica sin stock
    if precio_final is None:
        print("❌ Sin stock / no encontrado")
        sheet.update_cell(i, 2, "Sin stock")
        continue

    print(f"💰 Precio: {precio_final}")

    try:
        costo_actual_num = round(float(costo_actual.replace(".", "").replace(",", ".")))
    except:
        costo_actual_num = None

    if costo_actual_num == precio_final:
        print("⏭️ Sin cambios")
        continue

    try:
        sheet.update_cell(i, 2, precio_final)
        print("✅ Actualizado")
    except Exception as e:
        print("❌ Error actualizando:", e)

print("✅ Proceso terminado")
