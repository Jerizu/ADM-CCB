import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Dashboard Ministerial", layout="wide")

# Estilos dos Faróis
st.markdown("""
    <style>
    .farol { padding: 5px 15px; border-radius: 15px; color: white; font-weight: bold; float: right; font-size: 14px; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_excel_data(files):
    all_data = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for sheet in xl.sheet_names:
            # Lê a aba. Skiprows=1 para pular títulos decorativos do Excel
            df = pd.read_excel(xl, sheet_name=sheet, skiprows=1)
            # Limpa nomes de colunas (remove espaços e quebras de linha)
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            
            # Tenta encontrar a coluna da Localidade (pode ser 'Localidade', 'Coluna1', 'Unnamed: 1', etc)
            # Procuramos pela coluna que contém nomes conhecidos como 'Cidade Nova II'
            for col in df.columns[:3]: # Geralmente está nas 3 primeiras colunas
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila', na=False, case=False).any():
                    df = df.rename(columns={col: 'CASA_NOMES'})
                    break
            
            all_data[sheet] = df
    return all_data

# --- BARRA LATERAL ---
st.sidebar.title("Configurações")
uploaded_files = st.sidebar.file_uploader("Arraste seus arquivos .xlsx aqui", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = load_excel_data(uploaded_files)
    
    # Encontrar aba de referência para o menu
    ref_sheet = next((k for k in db.keys() if "Água" in k or "Energia" in k), list(db.keys())[0])
    
    if 'CASA_NOMES' in db[ref_sheet].columns:
        lista_casas = sorted(db[ref_sheet]['CASA_NOMES'].dropna().unique())
        casa_sel = st.sidebar.selectbox("Selecione a Localidade", lista_casas)

        # Filtro de Meses (Baseado no seu jan/26)
        meses_lista = ["jan/25", "fev/25", "mar/25", "abr/25", "mai/25", "jun/25", "jul/25", "ago/25", "set/25", "out/25", "nov/25", "dez/25", "jan/26", "fev/26"]
        periodo = st.sidebar.select_slider("Período", options=meses_lista, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def render_card(titulo, chave_busca, is_gasto=True):
            # Busca a aba correta ignorando maiúsculas/minúsculas
            aba_real = next((k for k in db.keys() if chave_busca.upper() in k.upper()), None)
            if not aba_real: return
            
            df = db[aba_real]
            # Filtra a linha da casa selecionada
            row_data = df[df['CASA_NOMES'] == casa_sel]
            if row_data.empty: return
            row = row_data.iloc[0]

            # Médias e Meses
            m24 = pd.to_numeric(row.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(row.get('Média 2025', 0), errors='coerce')
            
            # Pegar meses do slider
            idx_i = meses_lista.index(periodo[0])
            idx_f = meses_lista.index(periodo[1]) + 1
            meses_selecionados = meses_lista[idx_i:idx_f]
            valores_meses = [pd.to_numeric(row.get(m, 0), errors='coerce') for m in meses_selecionados]

            # Farol (Tendência)
            var = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            cor = "good" if (var <= 0 if is_gasto else var >= 0) else "bad"

            c_tit, c_far = st.columns([3, 1])
            c_tit.markdown(f"**{titulo}**")
            c_far.markdown(f'<span class="farol {cor}">{var:+.1f}%</span>', unsafe_allow_html=True)

            # Gráfico
            fig = go.Figure()
            fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name='Médias'))
            fig.add_trace(go.Bar(x=meses_selecionados, y=valores_meses, marker_color='#3498db', name='Meses'))

            # Linhas de Referência (Apenas para Per Capta)
            if "PER CAPTA" in titulo.upper():
                mvp = pd.to_numeric(row.get('Média Várzea Pta', 0), errors='coerce')
                mrj = pd.to_numeric(row.get('Média Regional Jdi', 0), errors='coerce')
                if mvp: fig.add_hline(y=mvp, line_dash="dash", line_color="green", annotation_text="Média Várzea")
                if mrj: fig.add_hline(y=mrj, line_dash="dot", line_color="orange", annotation_text="Média Jundiaí")

            fig.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Dashboard Grid
        cols = st.columns(2)
        with cols[0]: render_card("Água e Esgoto", "Água")
        with cols[1]: render_card("Manutenção", "Manutenção")

        cols2 = st.columns(2)
        with cols2[0]: render_card("Energia Elétrica", "Energia")
        with cols2[1]: render_card("Alimentação", "Alimentação")

        cols3 = st.columns(2)
        with cols3[0]: render_card("Coletas Total", "Total", is_gasto=False)
        with cols3[1]: render_card("Coletas Per Capta", "Per Capta", is_gasto=False)

        # Santa Ceia (Baseado no seu histórico de anos)
        st.divider()
        st.subheader("Histórico Santa Ceia")
        aba_ceia = next((k for k in db.keys() if "SANTA CEIA" in k.upper()), None)
        if aba_ceia:
            row_ceia = db[aba_ceia][db[aba_ceia]['CASA_NOMES'] == casa_sel].iloc[0]
            anos = ['2021', '2022', '2023', '2024', '2025']
            vals = [pd.to_numeric(row_ceia.get(a, 0), errors='coerce') for a in anos]
            fig_c = go.Figure(go.Bar(x=anos, y=vals, marker_color='#2c3e50'))
            fig_c.update_layout(height=300, yaxis=dict(range=[min(vals)*0.95, max(vals)*1.05]))
            st.plotly_chart(fig_c, use_container_width=True)

else:
    st.info("Aguardando upload do arquivo 'Relatório financeiro_2026_BD.xlsx'.")
