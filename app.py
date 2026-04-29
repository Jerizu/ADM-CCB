import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Dashboard Ministerial v3", layout="wide")

# Estilos dos Faróis (Trend Badges)
st.markdown("""
    <style>
    .farol { padding: 5px 15px; border-radius: 15px; color: white; font-weight: bold; float: right; font-size: 14px; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

def formatar_coluna_data(col):
    """Converte colunas de data do Excel para o formato jan/26 ou fev/25"""
    try:
        # Se for um objeto de data do pandas (Timestamp)
        if isinstance(col, pd.Timestamp) or '00:00:00' in str(col):
            dt = pd.to_datetime(col)
            meses = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 
                     7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
            return f"{meses[dt.month]}/{str(dt.year)[2:]}"
    except:
        pass
    return str(col).strip().replace('\n', ' ')

@st.cache_data
def load_and_clean_data(files):
    all_data = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet, skiprows=1)
            # Normaliza os nomes das colunas para jan/26, fev/26 etc.
            df.columns = [formatar_coluna_data(c) for c in df.columns]
            
            # Identifica a coluna da Casa de Oração (Coluna B)
            for col in df.columns[:3]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'CASA_REF'})
                    break
            all_data[sheet] = df
    return all_data

# --- SIDEBAR ---
st.sidebar.title("Painel de Controle")
uploaded_files = st.sidebar.file_uploader("Suba o arquivo Relatório financeiro_2026_BD.xlsx", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = load_and_clean_data(uploaded_files)
    
    # Lista de Casas (usando a primeira aba disponível)
    ref_sheet = list(db.keys())[0]
    if 'CASA_REF' in db[ref_sheet].columns:
        casas = sorted(db[ref_sheet]['CASA_REF'].dropna().unique())
        casa_sel = st.sidebar.selectbox("Selecione a Casa de Oração", casas)

        # Definição dos meses para o Slider (jan/25 até dez/26)
        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Linha do Tempo", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def render_card(titulo, busca, is_gasto=True):
            aba_nome = next((k for k in db.keys() if busca.upper() in k.upper()), None)
            if not aba_nome: return
            
            df = db[aba_nome]
            row_data = df[df['CASA_REF'] == casa_sel]
            if row_data.empty: return
            row = row_data.iloc[0]

            # Médias
            m24 = pd.to_numeric(row.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(row.get('Média 2025', 0), errors='coerce')
            
            # Filtro Dinâmico do Slider
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_selecionados = meses_eixo[idx_i:idx_f]
            valores_meses = [pd.to_numeric(row.get(m, 0), errors='coerce') for m in meses_selecionados]

            # Farol (Comparativo Médias 24 vs 25)
            var = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            cor = "good" if (var <= 0 if is_gasto else var >= 0) else "bad"

            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{titulo}**")
            c2.markdown(f'<span class="farol {cor}">{var:+.1f}%</span>', unsafe_allow_html=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name='Histórico'))
            fig.add_trace(go.Bar(x=meses_selecionados, y=valores_meses, marker_color='#3498db', name='Meses'))

            # Linhas Médias (Per Capta)
            if "PER CAPTA" in titulo.upper():
                vpta = pd.to_numeric(row.get('Média Várzea Pta', 0), errors='coerce')
                regj = pd.to_numeric(row.get('Média Regional Jdi', 0), errors='coerce')
                if vpta: fig.add_hline(y=vpta, line_dash="dash", line_color="#27ae60", annotation_text="Média VPTA")
                if regj: fig.add_hline(y=regj, line_dash="dot", line_color="#e67e22", annotation_text="Média JDI")

            fig.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Dashboard Grid 2x2
        col_a, col_b = st.columns(2)
        with col_a: render_card("Água e Esgoto", "Água")
        with col_b: render_card("Manutenção", "Manutenção")

        col_c, col_d = st.columns(2)
        with col_c: render_card("Energia Elétrica", "Energia")
        with col_d: render_card("Alimentação", "Alimentação")

        col_e, col_f = st.columns(2)
        with col_e: render_card("Coletas Total", "Total", is_gasto=False)
        with col_f: render_card("Coletas Per Capta", "Per Capta", is_gasto=False)

        # Gráfico Santa Ceia (Histórico)
        st.divider()
        st.subheader("Participantes Santa Ceia (2021-2025)")
        aba_ceia = next((k for k in db.keys() if "SANTA CEIA" in k.upper()), None)
        if aba_ceia:
            row_ceia = db[aba_ceia][db[aba_ceia]['CASA_REF'] == casa_sel].iloc[0]
            anos = ['2021', '2022', '2023', '2024', '2025']
            vals = [pd.to_numeric(row_ceia.get(a, 0), errors='coerce') for a in anos]
            fig_ceia = go.Figure(go.Bar(x=anos, y=vals, marker_color='#2c3e50'))
            # Zoom igual ao PDF
            fig_ceia.update_layout(height=350, yaxis=dict(range=[min(vals)*0.95, max(vals)*1.05]))
            st.plotly_chart(fig_ceia, use_container_width=True)

else:
    st.info("Suba o arquivo Excel na barra lateral para gerar o dashboard.")
