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
            
            novas_colunas = []
            for col in df.columns:
                if isinstance(col, (datetime, pd.Timestamp)):
                    m_map = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
                    novas_colunas.append(f"{m_map[col.month]}/{str(col.year)[2:]}")
                else:
                    novas_colunas.append(str(col).strip())
            df.columns = novas_colunas
            
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
        
        if casa_sel == "Todas as Localidades":
            dados_atuais = df.select_dtypes(include=['number']).sum()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            if linha.empty: return
            dados_atuais = linha.iloc[0]

        # --- LÓGICA PER CAPTA COM LINHAS MÉDIAS E RÓTULOS ---
        if especial == "per_capta":
            m25, m26 = pd.to_numeric(dados_atuais.get('Média 2025', 0)), pd.to_numeric(dados_atuais.get('Média 2026', 0))
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(dados_atuais.get(m, 0), errors='coerce') for m in meses_sel]

            val_media_varzea = round(df['Média 2025'].mean(), 2)
            val_media_regional = 35.50 

            fig = go.Figure()
            fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7', name='Médias'))
            fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, name=casa_sel, marker_color='#3498db'))
            
            # Linhas com Rótulos de Valor
            fig.add_hline(y=val_media_varzea, line_dash="dash", line_color="orange", 
                          annotation_text=f"Média Várzea: {val_media_varzea}", annotation_position="top right")
            fig.add_hline(y=val_media_regional, line_dash="dot", line_color="red", 
                          annotation_text=f"Média Regional: {val_media_regional}", annotation_position="bottom right")
            
            fig.update_layout(height=300, margin=dict(l=10,r=10,t=30,b=10), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            return

        # --- LÓGICA SANTA CEIA (BARRAS NO FINAL) ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            valores = [pd.to_numeric(dados_atuais.get(a, 0), errors='coerce') for a in anos]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=anos, y=valores, text=valores, textposition='auto', marker_color='#2c3e50'))
            fig.update_layout(height=350, title="Participantes Santa Ceia (Anual)", margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("**Tabela de Dados: Santa Ceia**")
            st.table(pd.DataFrame([valores], columns=anos, index=[casa_sel]))
            return

        # --- GRÁFICOS PADRÃO (ÁGUA, ENERGIA, ETC) ---
        m25 = pd.to_numeric(dados_atuais.get('Média 2025', 0), errors='coerce')
        m26 = pd.to_numeric(dados_atuais.get('Média 2026', 0), errors='coerce')
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        valores_mes = [pd.to_numeric(dados_atuais.get(m, 0), errors='coerce') for m in meses_sel]

        # Cálculo de variação 26 vs 25
        var = ((m26 - m25) / m25 * 100) if m25 else 0
        classe = "good" if (var <= 0 if is_gasto else var >= 0) else "bad"

        st.markdown(f"**{titulo}** <span class='farol {classe}'>{var:+.1f}%</span>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7'))
        fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db'))
        fig.update_layout(height=280, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- LAYOUT DO RELATÓRIO ---
    col1, col2 = st.columns(2)
    with col1: criar_grafico("Água e Esgoto", "Água")
    with col2: criar_grafico("Energia Elétrica", "Energia")

    col3, col4 = st.columns(2)
    with col3: criar_grafico("Manutenção", "Manutenção")
    with col4: criar_grafico("Alimentação", "Alimentação")

    st.divider()
    
    col5, col6 = st.columns(2)
    with col5:
        st.markdown("### Coletas e Ofertas (Total)")
        criar_grafico("Total Arrecadado", "Total", is_gasto=False)
    with col6:
        st.markdown("### Coletas Per Capta")
        criar_grafico("Valor por Pessoa", "Per Capta", is_gasto=False, especial="per_capta")

    st.divider()
    st.subheader("📊 Histórico de Santa Ceia")
    criar_grafico("Participantes", "Santa Ceia", especial="santa_ceia")

else:
    st.info("Aguardando upload do arquivo Excel para processar o relatório.")
