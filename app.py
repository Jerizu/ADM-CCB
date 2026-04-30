import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

# Estilos para o Farol e Layout
st.markdown("""
    <style>
    .farol { padding: 4px 10px; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    .stTable { font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

def normalizar_texto(txt):
    if not isinstance(txt, str): return str(txt)
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').upper().strip()

@st.cache_data
def carregar_dados(uploaded_files):
    all_sheets = {}
    for f in uploaded_files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            
            # Normalizar Cabeçalhos (Datas do Excel para jan/26)
            novas_cols = []
            for col in df.columns:
                if isinstance(col, (datetime, pd.Timestamp)):
                    m_map = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
                    novas_cols.append(f"{m_map[col.month]}/{str(col.year)[2:]}")
                else:
                    novas_cols.append(str(col).strip())
            df.columns = novas_cols
            
            # Identificar Localidade
            for col in df.columns[:5]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].astype(str).str.replace(' II', ' 2', regex=False).str.strip()
                    df = df[~df['LOCALIDADE_REF'].isin(['nan', 'None', 'Unnamed: 1', 'nan'])]
                    break
            all_sheets[name] = df
    return all_sheets

# --- LOGICA DO DASHBOARD ---
st.sidebar.title("🛠️ Configurações")
files = st.sidebar.file_uploader("Selecione o Relatório Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    
    lista_casas = sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique() if str(c) != 'nan'])
    casa_sel = st.sidebar.selectbox("Localidade / Filtro", ["Todas as Localidades"] + lista_casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Meses de Análise", options=meses_eixo, value=("jan/26", "fev/26"))

    st.title(f"Relatório Ministerial: {casa_sel}")

    def plotar(titulo, busca_aba, is_gasto=True, especial=None):
        # Localiza a aba correta ignorando acentos
        aba_real = next((k for k in db.keys() if normalizar_texto(busca_aba) in normalizar_texto(k)), None)
        if not aba_real: return

        df = db[aba_real].copy()
        
        # AGREGAÇÃO: Se for 'Todas', faz a MÉDIA de cada coluna entre as localidades
        if casa_sel == "Todas as Localidades":
            dados = df.select_dtypes(include=['number']).mean()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            if linha.empty: return
            dados = linha.iloc[0]

        # --- CASO SANTA CEIA ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            valores_anos = [pd.to_numeric(dados.get(a, 0), errors='coerce') for a in anos]
            fig = go.Figure(data=[go.Bar(x=anos, y=valores_anos, text=[f"{v:.0f}" for v in valores_anos], textposition='auto', marker_color='#2c3e50')])
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"**Dados Históricos ({casa_sel})**")
            st.table(pd.DataFrame([valores_anos], columns=anos, index=[casa_sel]))
            return

        # --- CASO FINANCEIRO / PER CAPTA ---
        m25 = pd.to_numeric(dados.get('Média 2025', 0), errors='coerce')
        m26 = pd.to_numeric(dados.get('Média 2026', 0), errors='coerce')
        
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_selecionados = meses_eixo[idx_i:idx_f]
        valores_mensais = [pd.to_numeric(dados.get(m, 0), errors='coerce') for m in meses_selecionados]

        # Farol de Tendência
        var = ((m26 - m25) / m25 * 100) if m25 else 0
        cor_classe = "good" if (var <= 0 if is_gasto else var >= 0) else "bad"

        st.markdown(f"**{titulo}** <span class='farol {cor_classe}'>{var:+.1f}%</span>", unsafe_allow_html=True)
        
        fig = go.Figure()
        # Colunas de Médias (Sempre presentes)
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7', name='Médias'))
        # Colunas dos Meses
        fig.add_trace(go.Bar(x=meses_selecionados, y=valores_mensais, marker_color='#3498db', name='Meses'))

        # Linhas de Referência para Per Capta
        if especial == "per_capta":
            # Valor fixo ou média da planilha
            v_varzea = round(df['Média 2025'].mean(), 2)
            v_regional = 35.50
            fig.add_hline(y=v_varzea, line_dash="dash", line_color="orange", 
                          annotation_text=f"Média Várzea: {v_varzea}", annotation_position="top right")
            fig.add_hline(y=v_regional, line_dash="dot", line_color="red", 
                          annotation_text=f"Média Regional: {v_regional}", annotation_position="bottom right")

        fig.update_layout(height=280, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- RENDERIZAÇÃO ---
    col1, col2 = st.columns(2)
    with col1: plotar("Água e Esgoto", "Água")
    with col2: plotar("Energia Elétrica", "Energia")

    col3, col4 = st.columns(2)
    with col3: plotar("Manutenção", "Manutenção")
    with col4: plotar("Alimentação", "Alimentação")

    st.divider()
    col_t, col_p = st.columns(2)
    with col_t:
        st.markdown("### Coletas e Ofertas (Total)")
        plotar("Total Mensal", "Total", is_gasto=False)
    with col_p:
        st.markdown("### Coletas Per Capta")
        plotar("Valor Per Capta", "Per Capta", is_gasto=False, especial="per_capta")

    st.divider()
    st.subheader("📊 Participantes Santa Ceia")
    plotar("Evolução", "Santa Ceia", especial="santa_ceia")

else:
    st.warning("⚠️ Aguardando o upload do arquivo: 'Relatório financeiro_2026_BD.xlsx'")
