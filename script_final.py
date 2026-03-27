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

# 🔁 Conexión con retry
for intento in range(3):
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

# 🔐 Login automático
def hacer_login(page):
    print("🔐 Iniciando login automático...")

    page.goto(
        "https://maxiconsumo.com/sucursal_merlo/customer/account/login/",
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_selector('input[name="login[username]"]', timeout=10000)

    page.fill('input[name="login[username]"]', os.environ["MC_EMAIL"])
    page.fill('input[name="login[password]"]', os.environ["MC_PASSWORD"])

    page.locator('button.action.login.primary').click(
        force=True,
        no_wait_after=True
    )

    page.wait_for_timeout(5000)

    if "login" in page.url.lower():
        raise Exception("❌ Login falló")

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

    try:
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
        )

        # 🚀 BLOQUEAR RECURSOS PESADOS
        context.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in ["image", "media", "font"]
            else route.continue_()
        ))

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

                # LINK DIRECTO
                if link_directo:
                    print("🔗 Usando link directo")

                    for intento_link in range(2):
                        try:
                            page.goto(link_directo, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_selector(".product-info-main", timeout=10000)
                            break
                        except:
                            print("⚠️ Reintentando carga...")
                            page.wait_for_timeout(3000)
                    else:
                        link_directo = None

                    if link_directo:
                        bloques = page.locator(".product-info-main")

                        for intento in range(3):
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

                            page.wait_for_timeout(800)
                            
                # FALLBACK
                if precio_final is None:
                    print("🔄 Usando fallback")

                    page.goto(
                        f"https://maxiconsumo.com/sucursal_merlo/catalogsearch/result/?q={sku}",
                        wait_until="domcontentloaded",
                        timeout=90000
                    )

                    page.wait_for_selector("body", timeout=10000)

                    productos = page.locator(f"text={sku}")

                    print(f"DEBUG: buscando SKU {sku}")
                    print(f"DEBUG count: {productos.count()}")

                    if productos.count() > 0:
                        contenedor = productos.first.locator(
                            "xpath=ancestor::*[contains(@class,'product')]"
                        )

                        precio_locator = contenedor.locator(".price")

                        if precio_locator.count() > 0:
                            precio_texto = precio_locator.first.inner_text()
                            precio_final = normalizar_precio(precio_texto)
                        else:
                            print("⚠️ Sin precio")
                            sheet.update_cell(i, 2, "Sin stock")
                            time.sleep(0.2)
                            continue
                    else:
                        print("❌ No encontrado")
                        sheet.update_cell(i, 2, "Sin stock")
                        time.sleep(0.2)
                        continue

                print(f"💰 Precio final: {precio_final}")

                try:
                    costo_actual_num = round(float(costo_actual.replace(".", "").replace(",", ".")))
                except:
                    costo_actual_num = None

                if costo_actual_num == precio_final:
                    print("⏭️ Sin cambios")
                    time.sleep(0.2)
                    continue

                sheet.update_cell(i, 2, precio_final)
                print("✅ Actualizado")

                time.sleep(0.2)

            except Exception as e:
                print(f"❌ Error en fila {i}: {e}")
                sheet.update_cell(i, 2, "Sin stock")
                time.sleep(0.2)

        print("✅ Proceso terminado")

    finally:
        browser.close()
        print("🔒 Browser cerrado")
