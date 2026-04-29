import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Dashboard Ministerial CCB", layout="wide")

# Estilos CSS para os Faróis (Trend Badges)
st.markdown("""
    <style>
    .farol { padding: 5px 15px; border-radius: 15px; color: white; font-weight: bold; float: right; font-size: 14px; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

def converter_cabecalho_para_texto(col):
    """Converte datas internas do Excel (Timestamp) para o formato jan/26"""
    if isinstance(col, (datetime, pd.Timestamp)):
        meses = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 
                 7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
        return f"{meses[col.month]}/{str(col.year)[2:]}"
    return str(col).strip().replace('\n', ' ')

@st.cache_data
def carregar_dados(files):
    all_sheets = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            # Pula a primeira linha de título para pegar o cabeçalho real
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            df.columns = [converter_cabecalho_para_texto(c) for c in df.columns]
            
            # Localiza a coluna de cidades (Coluna B)
            for col in df.columns[:3]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'CASA_REF'})
                    break
            all_sheets[name] = df
    return all_sheets

# --- BARRA LATERAL ---
st.sidebar.title("🛠️ Painel Administrativo")
st.sidebar.info("📌 **Instrução:** Envie o arquivo:\n`Relatório financeiro_2026_BD.xlsx`")
uploaded_files = st.sidebar.file_uploader("Selecione o arquivo Excel", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = carregar_dados(uploaded_files)
    
    # Encontrar a lista de casas de oração
    primeira_aba = next((k for k in db.keys() if 'CASA_REF' in db[k].columns), None)
    
    if primeira_aba:
        casas = sorted(db[primeira_aba]['CASA_REF'].dropna().unique())
        casa_sel = st.sidebar.selectbox("Escolha a Casa de Oração", casas)

        # Slider de tempo: cobre 2025 e 2026
        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Selecione o Período", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def criar_card(titulo, busca_aba, is_gasto=True):
            # Busca aba ignorando acentos
            aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper().replace('Á','A').replace('Ç','C')), None)
            if not aba_real: return
            
            df = db[aba_real]
            linha = df[df['CASA_REF'] == casa_sel]
            if linha.empty: return
            row = linha.iloc[0]

            # Dados de Médias
            m24 = pd.to_numeric(row.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(row.get('Média 2025', 0), errors='coerce')
            
            # Dados dos Meses (Slider)
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(row.get(m, 0), errors='coerce') for m in meses_sel]

            # Farol (Tendência) - Correção do SyntaxError
            var = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            is_good = (var <= 0) if is_gasto else (var >= 0)
            cor_classe = "good" if is_good else "bad"

            c_t, c_f = st.columns([3, 1])
            c_t.markdown(f"**{titulo}**")
            c_f.markdown(f'<span class="farol {cor_classe}">{var:+.1f}%</span>', unsafe_allow_html=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name='Médias'))
            fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', name='Meses'))

            # Linhas Médias para Per Capta
            if "PER CAPTA" in titulo.upper():
                mvp = pd.to_numeric(row.get('Média Várzea Pta', 0), errors='coerce')
                mrj = pd.to_numeric(row.get('Média Regional Jdi', 0), errors='coerce')
                if mvp: fig.add_hline(y=mvp, line_dash="dash", line_color="#27ae60", annotation_text="Média Várzea")
                if mrj: fig.add_hline(y=mrj, line_dash="dot", line_color="#e67e22", annotation_text="Média Jundiaí")

            fig.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Grade de Gráficos
        col1, col2 = st.columns(2)
        with col1: criar_card("Água e Esgoto", "Água")
        with col2: criar_card("Manutenção", "Manutenção")

        col3, col4 = st.columns(2)
        with col3: criar_card("Energia Elétrica", "Energia")
        with col4: criar_card("Alimentação", "Alimentação")

        col5, col6 = st.columns(2)
        with col5: criar_card("Coletas Total", "Total", is_gasto=False)
        with col6: criar_card("Coletas Per Capta", "Per Capta", is_gasto=False)

        # Santa Ceia
        st.divider()
        st.subheader("Santa Ceia (Participantes 2021-2025)")
        criar_card("Participantes", "Santa Ceia", is_gasto=False)
else:
    st.info("Aguardando o upload do arquivo: 'Relatório financeiro_2026_BD.xlsx'")
