from playwright.sync_api import sync_playwright
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
    r"C:\Users\Ivann\OneDrive\Escritorio\actualizador_precios\credenciales.json",
    scopes=scope
)

client = gspread.authorize(creds)
sheet = client.open("PRECIOS ALMACEN").sheet1

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

# 📊 PROGRESO
inicio = time.time()
total_filas = len(data_formulas)
procesadas = 0

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir="perfil",
        headless=False
    )

    page = browser.new_page()

    # 🔐 LOGIN MANUAL
    page.goto("https://maxiconsumo.com/")
    print("👉 Logueate y presioná ENTER")
    input()
    page.wait_for_timeout(3000)

    categoria_actual = ""

    for i, fila in enumerate(data_formulas, start=1):

        procesadas += 1

        porcentaje = (procesadas / total_filas) * 100
        tiempo_transcurrido = time.time() - inicio
        tiempo_por_fila = tiempo_transcurrido / procesadas
        tiempo_restante = tiempo_por_fila * (total_filas - procesadas)

        minutos = int(tiempo_restante // 60)
        segundos = int(tiempo_restante % 60)

        print("\n" + "="*50)  # 👈 separador visual
        print(f"🚀 {procesadas}/{total_filas} | {porcentaje:.1f}% | ETA: {minutos}m {segundos}s")

        if len(fila) < 4:
            continue

        marca = str(fila[0]).strip()
        sku_raw = str(fila[3]).strip()

        try:
            costo_actual = str(data_valores[i-1][1])
        except:
            costo_actual = ""

        # 🧠 Categorías
        if marca.isupper() and not sku_raw:
            categoria_actual = marca
            print(f"📦 {categoria_actual}")
            continue

        # 🚫 Filtros
        if not marca or not sku_raw:
            continue
        if marca.upper() == "MARCA":
            continue
        if sku_raw.upper() == "SKU":
            continue

        link_directo, sku = extraer_link_y_sku(sku_raw)

        if not sku:
            continue

        print(f"🔎 Fila {i} | {marca} | SKU {sku}")

        try:
            precio_final = None

            # 🚀 LINK DIRECTO
            if link_directo:
                print("🔗 Usando link directo")
                page.goto(link_directo, wait_until="commit")
                page.wait_for_timeout(2000)

                selector_precio = ".product-info-main .price-wrapper .price"
                precio_elemento = page.locator(selector_precio)

                for intento in range(2):
                    if precio_elemento.count() > 0:
                        precio_texto = precio_elemento.first.inner_text()
                        precio_final = normalizar_precio(precio_texto)
                        break
                    else:
                        page.wait_for_timeout(1500)

            # 🔁 FALLBACK
            if precio_final is None:
                print("🔄 Usando fallback por búsqueda")

                buscador = page.locator('input[placeholder="Explorá nuestros productos"]')
                buscador.fill("")
                buscador.fill(sku)
                buscador.press("Enter")

                page.wait_for_timeout(2000)

                productos = page.locator(f"text=SKU {sku}")

                if productos.count() > 0:
                    contenedor = productos.first.locator("xpath=ancestor::div[contains(@class,'product')]")

                    precio_locator = contenedor.locator(".price")

                    if precio_locator.count() == 0:
                        print("⚠️ Sin precio (disponibilidad crítica)")
                        sheet.update_cell(i, 2, "Sin stock")
                        continue

                    precio_texto = precio_locator.first.inner_text()
                    precio_final = normalizar_precio(precio_texto)
                    

                else:
                    print("❌ No encontrado")
                    sheet.update_cell(i, 2, "Sin stock")
                    continue

            print(f"💰 Precio final: {precio_final}")

            # 🔍 Comparar
            try:
                costo_actual_num = round(float(costo_actual.replace(".", "").replace(",", ".")))
            except:
                costo_actual_num = None

            if costo_actual_num == precio_final:
                print("⏭️ Sin cambios")
                continue

            # ✏️ Actualizar
            sheet.update_cell(i, 2, precio_final)
            print("✅ Actualizado")

        except Exception as e:
            print(f"❌ Error en fila {i}: {e}")
            sheet.update_cell(i, 2, "Sin stock")

    print("\n" + "="*50)
    print("✅ Proceso terminado")
    input("ENTER para cerrar")