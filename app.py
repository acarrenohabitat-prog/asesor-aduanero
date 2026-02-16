import streamlit as st
from google import genai
from fpdf import FPDF
from PIL import Image
import sqlite3
import pandas as pd

# 1. CONFIGURACIÓN
st.set_page_config(page_title="IA Aduanera Auto-Detect", layout="wide")

try:
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(f"⚠️ Error de Llave: {e}")
    st.stop()

# 2. FUNCIÓN PARA DETECTAR MODELOS REALES
@st.cache_data # Guardamos la lista para no preguntar a cada rato
def obtener_modelos_disponibles():
    try:
        # Preguntamos a Google qué modelos tienes activos
        lista_modelos = client.models.list()
        # Filtramos solo los "Gemini"
        nombres = [m.name for m in lista_modelos if "gemini" in m.name]
        return nombres
    except Exception as e:
        return ["gemini-1.5-flash", "gemini-2.0-flash-lite"] # Respaldo por si falla

# 3. FUNCIÓN DE IA DINÁMICA
def llamar_ia(prompt, modelo_seleccionado, imagen=None):
    try:
        # Si el nombre viene con "models/", a veces hay que dejarlo, a veces quitarlo.
        # La lista automática suele traer el nombre correcto.
        if imagen:
            response = client.models.generate_content(
                model=modelo_seleccionado,
                contents=[imagen, prompt]
            )
        else:
            response = client.models.generate_content(
                model=modelo_seleccionado,
                contents=prompt
            )
        return response.text
    except Exception as e:
        return f"❌ Error con {modelo_seleccionado}: {str(e)}"

# 4. BASE DE DATOS Y PDF
def iniciar_db():
    conn = sqlite3.connect("data_comercio.db")
    conn.execute("CREATE TABLE IF NOT EXISTS historial (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP, tipo TEXT, resultado TEXT)")
    conn.close()

def guardar(tipo, texto):
    conn = sqlite3.connect("data_comercio.db")
    conn.execute("INSERT INTO historial (tipo, resultado) VALUES (?, ?)", (tipo, texto))
    conn.commit()
    conn.close()

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "REPORTE ADUANERO", 0, 1, "C")

def generar_pdf(titulo, contenido):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, titulo, ln=1)
    pdf.set_font("Arial", size=10)
    texto_seguro = contenido.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 6, texto_seguro)
    return pdf.output(dest="S").encode("latin-1")

# 5. INTERFAZ VISUAL
iniciar_db()

# --- BARRA LATERAL INTELIGENTE ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2040/2040946.png", width=50)
    st.title("Panel de Control")
    st.success("✅ Conexión Activa")
    
    st.write("🔍 Buscando tus modelos...")
    mis_modelos = obtener_modelos_disponibles()
    
    # ¡AQUÍ ESTÁ LA MAGIA! El menú se llena solo con TU lista real
    modelo_activo = st.selectbox(
        "🧠 Seleccionar Cerebro IA:",
        mis_modelos
    )
    st.info(f"Usando: {modelo_activo}")
    st.caption("Si sale error 429, espera 30 seg y prueba otro.")

st.title("🚢 SISTEMA ADUANERO INTELIGENTE")

tabs = st.tabs(["💰 Calculadora", "🌎 Viabilidad", "🧐 Auditor DIAN", "🌿 Auditor ANLA", "📂 Historial"])

# --- TAB 0: CALCULADORA ---
with tabs[0]:
    st.header("🏢 Liquidación de Tributos")
    col1, col2 = st.columns(2)
    with col1:
        fob = st.number_input("Valor FOB (USD)", value=1000.0)
        flete = st.number_input("Flete (USD)", value=150.0)
        seguro = st.number_input("Seguro (USD)", value=25.0)
        trm = st.number_input("TRM Actual", value=4000.0)
        arancel_pct = st.number_input("Arancel (%)", value=10)
        iva_pct = st.selectbox("IVA (%)", [19, 5, 0])

    cif_usd = fob + flete + seguro
    total_cop = (cif_usd * trm) * (1 + arancel_pct/100) * (1 + iva_pct/100)

    with col2:
        st.subheader("📊 Resultado")
        st.metric("Total a Pagar (COP)", f"${total_cop:,.0f}")
        if st.button("💾 Guardar Cálculo"):
            guardar("Calculadora", f"Total: {total_cop:,.0f}")
            st.success("Guardado")

# --- TAB 1: VIABILIDAD ---
with tabs[1]:
    st.header("Análisis de Viabilidad")
    prod = st.text_area("Producto:", placeholder="Ej: Relojes inteligentes de Taiwán...")
    if st.button("Analizar Mercado"):
        with st.spinner(f"Analizando con {modelo_activo}..."):
            res = llamar_ia(f"Experto aduanero: Viabilidad de importar {prod}", modelo_activo)
            
            if "❌" in res:
                st.error(res)
                if "429" in res:
                    st.warning("⏳ Límite de velocidad. Espera 1 minuto y vuelve a intentar.")
                elif "404" in res:
                     st.warning("🔧 Ese modelo no respondió. Prueba otro de la lista.")
            else:
                st.markdown(res)
                guardar("Viabilidad", res)
                st.download_button("Descargar PDF", generar_pdf("VIABILIDAD", res), "viabilidad.pdf")

# --- OTRAS TABS ---
with tabs[2]:
    st.header("Auditor DIAN")
    f = st.file_uploader("Doc", key="dian")
    if f and st.button("Auditar Doc"):
        img = Image.open(f)
        res = llamar_ia("Audita este documento:", modelo_activo, img)
        st.write(res)

with tabs[3]:
    st.header("Auditor ANLA")
    f = st.file_uploader("Doc", key="anla")
    if f and st.button("Verificar ANLA"):
        img = Image.open(f)
        res = llamar_ia("¿Requiere ANLA?", modelo_activo, img)
        st.write(res)

with tabs[4]:
    st.header("Historial")
    conn = sqlite3.connect("data_comercio.db")
    st.dataframe(pd.read_sql_query("SELECT * FROM historial ORDER BY fecha DESC", conn), width=1200)
    conn.close()