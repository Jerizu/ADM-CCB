import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

st.markdown("""
    <style>
    .farol { padding: 4px 10px; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def carregar_dados(uploaded_files):
    all_sheets = {}
    for f in uploaded_files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            
            # Normalizar Colunas (Datas)
            novas_colunas = []
            for col in df.columns:
                if isinstance(col, (datetime, pd.Timestamp)):
                    m_map = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
                    novas_colunas.append(f"{m_map[col.month]}/{str(col.year)[2:]}")
                else:
                    novas_colunas.append(str(col).strip())
            df.columns = novas_colunas
            
            # Identificar Localidade
            for col in df.columns[:5]: 
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].astype(str).str.replace(' II', ' 2', regex=False).str.strip()
                    df = df[~df['LOCALIDADE_REF'].isin(['nan', 'None'])]
                    break
            all_sheets[name] = df
    return all_sheets

# --- APP ---
st.sidebar.title("📊 Painel Administrativo")
files = st.sidebar.file_uploader("Upload Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Período", options=meses_eixo, value=("jan/26", "fev/26"))

    st.title(f"Relatório Ministerial: {casa_sel}")

    def criar_grafico(titulo, busca_aba, is_gasto=True, especial=None):
        aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper().replace('Á','A')), None)
        if not aba_real: return
        
        df = db[aba_real]
        
        # Dados da seleção atual
        if casa_sel == "Todas as Localidades":
            dados_atuais = df.select_dtypes(include=['number']).sum()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            if linha.empty: return
            dados_atuais = linha.iloc[0]

        # --- LÓGICA SANTA CEIA ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            valores = [pd.to_numeric(dados_atuais.get(a, 0), errors='coerce') for a in anos]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=anos, y=valores, mode='lines+markers+text', text=valores, textposition="top center", line=dict(width=4, color='#2c3e50')))
            fig.update_layout(height=300, title="Evolução de Participantes", margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("**Tabela de Valores Históricos (Santa Ceia)**")
            st.table(pd.DataFrame([valores], columns=anos, index=[casa_sel]))
            return

        # --- LÓGICA PER CAPTA COM LINHAS MÉDIAS ---
        if especial == "per_capta":
            m24, m25 = dados_atuais.get('Média 2024', 0), dados_atuais.get('Média 2025', 0)
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(dados_atuais.get(m, 0), errors='coerce') for m in meses_sel]

            # Médias Comparativas (Exemplo: Média da Planilha toda)
            media_varzea = df['Média 2025'].mean() 
            media_regional_jdi = 35.50 # Valor fixo ou calculado se houver dados

            fig = go.Figure()
            fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, name=casa_sel, marker_color='#3498db'))
            fig.add_hline(y=media_varzea, line_dash="dash", line_color="orange", annotation_text="Média Várzea Pta")
            fig.add_hline(y=media_regional_jdi, line_dash="dot", line_color="red", annotation_text="Média Regional Jundiaí")
            
            fig.update_layout(height=300, margin=dict(l=10,r=10,t=30,b=10))
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- GRÁFICOS PADRÃO (FINANCEIRO) ---
        m24 = pd.to_numeric(dados_atuais.get('Média 2024', 0), errors='coerce')
        m25 = pd.to_numeric(dados_atuais.get('Média 2025', 0), errors='coerce')
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        valores_mes = [pd.to_numeric(dados_atuais.get(m, 0), errors='coerce') for m in meses_sel]

        var = ((m25 - m24) / m24 * 100) if m24 else 0
        classe = "good" if (var <= 0 if is_gasto else var >= 0) else "bad"

        st.markdown(f"**{titulo}** <span class='farol {classe}'>{var:+.1f}%</span>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7'))
        fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db'))
        fig.update_layout(height=250, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Grid de Visualização
    c1, c2 = st.columns(2)
    with c1: criar_grafico("Água e Esgoto", "Água")
    with c2: criar_grafico("Manutenção", "Manutenção")

    c3, c4 = st.columns(2)
    with c3: criar_grafico("Energia Elétrica", "Energia")
    with c4: criar_grafico("Alimentação", "Alimentação")

    st.divider()
    st.subheader("Evolução Santa Ceia")
    criar_grafico("Participantes", "Santa Ceia", especial="santa_ceia")

    st.divider()
    c5, c6 = st.columns(2)
    with c5:
        st.markdown("**Coletas e Ofertas (Total)**")
        criar_grafico("Total", "Total", is_gasto=False)
    with c6:
        st.markdown("**Coletas Per Capta**")
        criar_grafico("Per Capta", "Per Capta", is_gasto=False, especial="per_capta")

else:
    st.info("Carregue o arquivo Excel para gerar o relatório.")
