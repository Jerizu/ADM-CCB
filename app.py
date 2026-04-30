import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

st.markdown("""
    <style>
    .farol { padding: 4px 10px; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    .legenda-container { display: flex; gap: 20px; justify-content: center; font-size: 13px; margin-top: -10px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

def normalizar(txt):
    if not isinstance(txt, str): return str(txt)
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').upper().strip()

@st.cache_data
def carregar_dados(uploaded_files):
    all_sheets = {}
    for f in uploaded_files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            novas_cols = []
            for col in df.columns:
                if isinstance(col, (datetime, pd.Timestamp)):
                    m_map = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
                    novas_cols.append(f"{m_map[col.month]}/{str(col.year)[2:]}")
                else:
                    novas_cols.append(str(col).strip())
            df.columns = novas_cols
            for col in df.columns[:5]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].astype(str).str.replace(' II', ' 2', regex=False).strip()
                    df = df[~df['LOCALIDADE_REF'].isin(['nan', 'None', 'Unnamed: 1'])]
                    break
            all_sheets[name] = df
    return all_sheets

# --- INTERFACE ---
st.sidebar.title("📊 Painel de Controle")
files = st.sidebar.file_uploader("Upload Relatório", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Filtrar Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Período", options=meses_eixo, value=("jan/26", "fev/26"))

    st.title(f"Relatório Ministerial: {casa_sel}")

    def criar_grafico(titulo, busca_aba, is_gasto=True, especial=None):
        aba_real = next((k for k in db.keys() if normalizar(busca_aba) in normalizar(k)), None)
        if not aba_real: return
        df = db[aba_real].copy()

        # --- LÓGICA SANTA CEIA (SOMA TOTAL E VALORES INTEIROS) ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            if casa_sel == "Todas as Localidades":
                dados_ceia = df[anos].sum()
                st.subheader("Soma Total de Participantes")
            else:
                dados_ceia = df[df['LOCALIDADE_REF'] == casa_sel][anos].iloc[0]
            
            valores = [int(v) for v in dados_ceia]
            fig = go.Figure(go.Bar(x=anos, y=valores, text=valores, textposition='auto', marker_color='#2c3e50'))
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            if casa_sel == "Todas as Localidades":
                st.markdown("**Tabela Detalhada por Localidade (Santa Ceia)**")
                df_tabela = df[['LOCALIDADE_REF'] + anos].copy()
                for a in anos: df_tabela[a] = df_tabela[a].apply(lambda x: f"{int(x)}" if pd.notnull(x) else "0")
                st.dataframe(df_tabela.set_index('LOCALIDADE_REF'), use_container_width=True)
            return

        # --- LÓGICA MÉDIA GERAL PARA OS DEMAIS ---
        if casa_sel == "Todas as Localidades":
            dados = df.select_dtypes(include=['number']).mean()
        else:
            dados = df[df['LOCALIDADE_REF'] == casa_sel].select_dtypes(include=['number']).iloc[0]

        m25, m26 = dados.get('Média 2025', 0), dados.get('Média 2026', 0)
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        valores_mes = [dados.get(m, 0) for m in meses_sel]

        var = ((m26 - m25) / m25 * 100) if m25 else 0
        classe = "good" if (var <= 0 if is_gasto else var >= 0) else "bad"
        st.markdown(f"**{titulo}** <span class='farol {classe}'>{var:+.1f}%</span>", unsafe_allow_html=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7', name='Médias'))
        fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', name='Meses'))

        # --- PER CAPTA: RÓTULOS LIMPOS E LEGENDA ---
        if especial == "per_capta":
            v_varzea, v_reg = 22.28, 35.50
            fig.add_hline(y=v_varzea, line_dash="dash", line_color="orange", annotation_text=f"{v_varzea}", annotation_position="top right")
            fig.add_hline(y=v_reg, line_dash="dot", line_color="red", annotation_text=f"{v_reg}", annotation_position="bottom right")
            
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"""
                <div class="legenda-container">
                    <span><b style="color:orange;">---</b> Média Várzea</span>
                    <span><b style="color:red;">...</b> Média Regional</span>
                </div>
            """, unsafe_allow_html=True)
        else:
            fig.update_layout(height=280, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig, use_container_width=True)

    # LAYOUT
    c1, c2 = st.columns(2)
    with c1: criar_grafico("Água e Esgoto", "Água")
    with c2: criar_grafico("Energia Elétrica", "Energia")
    c3, c4 = st.columns(2)
    with c3: criar_grafico("Manutenção", "Manutenção")
    with c4: criar_grafico("Alimentação", "Alimentação")
    
    st.divider()
    c5, c6 = st.columns(2)
    with c5: criar_grafico("Total Coletas", "Total", is_gasto=False)
    with c6: criar_grafico("Coleta Per Capta", "Per Capta", is_gasto=False, especial="per_capta")
    
    st.divider()
    st.subheader("📊 Histórico Santa Ceia (Total de Participantes)")
    criar_grafico("Evolução Santa Ceia", "Santa Ceia", especial="santa_ceia")
