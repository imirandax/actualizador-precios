from playwright.sync_api import sync_playwright
import re
import gspread
import time
import os
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
    raise Exception("❌ No se pudo conectar a Google Sheets después de varios intentos")

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

# 🔐 Login automático
def hacer_login(page):
    print("🔐 Iniciando login automático...")

    page.goto(
        "https://maxiconsumo.com/sucursal_merlo/customer/account/login/",
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(3000)

    page.fill('input[name="login[username]"]', os.environ["MC_EMAIL"])
    page.fill('input[name="login[password]"]', os.environ["MC_PASSWORD"])

    page.wait_for_timeout(3000)

    page.locator('button.action.login.primary').click(
        force=True,
        no_wait_after=True
    )

    page.wait_for_timeout(5000)

    print("✅ Login ejecutado en MERLO")

# 📊 Progreso
inicio = time.time()
total_filas = len(data_formulas)
procesadas = 0

with sync_playwright() as p:
    browser = p.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--single-process",
        "--no-zygote"
    ]
)
    context = browser.new_context(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
    page = context.new_page()

    hacer_login(page)

    categoria_actual = ""

    for i, fila in enumerate(data_formulas, start=1):
        procesadas += 1
        porcentaje = (procesadas / total_filas) * 100
        tiempo_transcurrido = time.time() - inicio
        tiempo_por_fila = tiempo_transcurrido / procesadas
        tiempo_restante = tiempo_por_fila * (total_filas - procesadas)
        minutos = int(tiempo_restante // 60)
        segundos = int(tiempo_restante % 60)

        print(f"\n{'='*50}")
        print(f"🚀 {procesadas}/{total_filas} | {porcentaje:.1f}% | ETA: {minutos}m {segundos}s")

        if len(fila) < 4:
            continue

        marca = str(fila[0]).strip()
        sku_raw = str(fila[3]).strip()

        try:
            costo_actual = str(data_valores[i-1][1])
        except:
            costo_actual = ""

        if marca.isupper() and not sku_raw:
            categoria_actual = marca
            print(f"📦 {categoria_actual}")
            continue

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

            if link_directo:
                print("🔗 Usando link directo")
                page.goto(link_directo, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
                precio_final = None

                bloques = page.locator(".product-info-main")

                for intento in range(5):
                    try:
                        textos = bloques.first.inner_text()

                        if "Precio unitario por bulto cerrado" in textos:
                            lineas = textos.split("\n")

                            for idx, linea in enumerate(lineas):
                                if "Precio unitario por bulto cerrado" in linea:
                                    precio_texto = lineas[idx + 1]
                                    precio_final = normalizar_precio(precio_texto)
                                    break

                        if precio_final:
                           break

                    except:
                        pass

                    page.wait_for_timeout(1500)

            if precio_final is None:
                print("🔄 Usando fallback por búsqueda")
                buscador = page.locator('input[placeholder="Explorá nuestros productos"]')
                buscador.click(force=True, no_wait_after=True)
                buscador.fill(sku)
                page.wait_for_timeout(500)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)
                productos = page.locator(f"text=SKU {sku}")
                if productos.count() > 0:
                    contenedor = productos.first.locator("xpath=ancestor::div[contains(@class,'product')]")
                    precio_locator = contenedor.locator(".price")
                    if precio_locator.count() == 0:
                        print("⚠️ Sin precio")
                        sheet.update_cell(i, 2, "Sin stock")
                        continue
                    precio_texto = precio_locator.first.inner_text()
                    precio_final = normalizar_precio(precio_texto)
                else:
                    print("❌ No encontrado")
                    sheet.update_cell(i, 2, "Sin stock")
                    continue

            print(f"💰 Precio final: {precio_final}")

            try:
                costo_actual_num = round(float(costo_actual.replace(".", "").replace(",", ".")))
            except:
                costo_actual_num = None

            if costo_actual_num == precio_final:
                print("⏭️ Sin cambios")
                continue

            sheet.update_cell(i, 2, precio_final)
            print("✅ Actualizado")

        except Exception as e:
            print(f"❌ Error en fila {i}: {e}")
            sheet.update_cell(i, 2, "Sin stock")

    print(f"\n{'='*50}")
    print("✅ Proceso terminado")

    browser.close()
