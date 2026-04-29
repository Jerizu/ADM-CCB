import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Dashboard Ministerial v2", layout="wide")

# Estilos CSS para os Faróis
st.markdown("""
    <style>
    .farol { padding: 5px 15px; border-radius: 15px; color: white; font-weight: bold; float: right; font-size: 14px; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

def limpar_nome_coluna(col):
    return str(col).strip().replace('\n', ' ')

@st.cache_data
def carregar_e_limpar(file):
    xl = pd.ExcelFile(file)
    sheets_dict = {}
    for name in xl.sheet_names:
        # Lendo a partir da linha onde geralmente estão os cabeçalhos nos seus arquivos
        df = pd.read_excel(xl, sheet_name=name, skiprows=1)
        df.columns = [limpar_nome_coluna(c) for c in df.columns]
        # Renomeia a coluna B (que vem como Unnamed: 1) para Localidade
        if 'Unnamed: 1' in df.columns:
            df = df.rename(columns={'Unnamed: 1': 'Localidade'})
        elif 'Coluna1' in df.columns:
            df = df.rename(columns={'Coluna1': 'Localidade'})
        sheets_dict[name] = df
    return sheets_dict

# --- BARRA LATERAL ---
st.sidebar.title("Configurações")
files = st.sidebar.file_uploader("Suba 'Relatório financeiro_2026_BD.xlsx'", type="xlsx", accept_multiple_files=True)

if files:
    db = {}
    for f in files:
        db.update(carregar_e_limpar(f))

    # Identificar aba de referência para pegar a lista de Casas de Oração
    ref_key = next((k for k in db.keys() if "Água" in k or "Energia" in k), None)
    
    if ref_key:
        casas = sorted(db[ref_key]['Localidade'].dropna().unique())
        casa_sel = st.sidebar.selectbox("Casa de Oração", casas)
        
        # --- FILTRO DE LINHA DO TEMPO ---
        # Definindo o período baseado nas colunas de data que encontramos nos seus arquivos
        meses_disponiveis = ["jan/25", "fev/25", "mar/25", "abr/25", "mai/25", "jun/25", "jul/25", "ago/25", "set/25", "out/25", "nov/25", "dez/25"]
        periodo = st.sidebar.select_slider("Linha do Tempo (Meses 2025/26)", options=meses_disponiveis, value=("jan/25", "fev/25"))

        st.title(f"Relatório: {casa_sel}")

        def render_grafico(titulo, aba_key, is_gasto=True):
            aba_real = next((k for k in db.keys() if aba_key.upper() in k.upper()), None)
            if not aba_real: return
            
            df = db[aba_real]
            row = df[df['Localidade'] == casa_sel]
            
            if row.empty: return
            row = row.iloc[0]

            # Captura de dados históricos
            m24 = pd.to_numeric(row.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(row.get('Média 2025', 0), errors='coerce')
            
            # Captura de meses selecionados no slider
            idx_inicio = meses_disponiveis.index(periodo[0])
            idx_fim = meses_disponiveis.index(periodo[1]) + 1
            meses_selecionados = meses_disponiveis[idx_inicio:idx_fim]
            
            valores_meses = [pd.to_numeric(row.get(m, 0), errors='coerce') for m in meses_selecionados]

            # Farol
            variacao = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            cor = "good" if (variacao <= 0 if is_gasto else variacao >= 0) else "bad"
            
            c_label, c_farol = st.columns([3,1])
            c_label.markdown(f"**{titulo}**")
            c_farol.markdown(f'<span class="farol {cor}">{variacao:+.1f}%</span>', unsafe_allow_html=True)

            fig = go.Figure()
            # Barras Cinzas (Médias)
            fig.add_trace(go.Bar(x=['Méd. 24', 'Méd. 25'], y=[m24, m25], marker_color='#bdc3c7', name="Médias"))
            # Barras Azuis (Meses)
            fig.add_trace(go.Bar(x=meses_selecionados, y=valores_meses, marker_color='#3498db', name="Meses"))

            # Adição de Linhas Médias para Per Capta
            if "PER CAPTA" in titulo.upper():
                mvp = pd.to_numeric(row.get('Média Várzea Pta', 0), errors='coerce')
                mrj = pd.to_numeric(row.get('Média Regional Jdi', 0), errors='coerce')
                fig.add_hline(y=mvp, line_dash="dash", line_color="green", annotation_text="Média VPTA")
                fig.add_hline(y=mrj, line_dash="dot", line_color="orange", annotation_text="Média JDI")

            fig.update_layout(height=300, margin=dict(l=0,r=0,t=20,b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Layout em Grid
        col1, col2 = st.columns(2)
        with col1: render_grafico("Água e Esgoto", "Água")
        with col2: render_grafico("Manutenção", "Manutenção")

        col3, col4 = st.columns(2)
        with col3: render_grafico("Energia Elétrica", "Energia")
        with col4: render_grafico("Alimentação", "Alimentação")

        col5, col6 = st.columns(2)
        with col5: render_grafico("Coletas Total", "Coletas e Ofertas - Total", is_gasto=False)
        with col6: render_grafico("Coletas Per Capta", "Per Capta", is_gasto=False)

        # Santa Ceia
        st.divider()
        st.subheader("Santa Ceia (Histórico)")
        render_grafico("Participantes", "Santa Ceia", is_gasto=False)

else:
    st.info("Aguardando upload do arquivo 'Relatório financeiro_2026_BD.xlsx' para gerar o dashboard.")
