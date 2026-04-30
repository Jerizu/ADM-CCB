import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

# Estilos CSS para as bolinhas do Farol e Tabelas
st.markdown("""
    <style>
    .dot { height: 15px; width: 15px; border-radius: 50%; display: inline-block; }
    .dot-green { background-color: #27ae60; }
    .dot-red { background-color: #c0392b; }
    .stTable { width: 100%; }
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
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].astype(str).str.replace(' II', ' 2', regex=False).str.strip()
                    df = df[~df['LOCALIDADE_REF'].isin(['nan', 'None', 'Unnamed: 1'])]
                    break
            all_sheets[name] = df
    return all_sheets

files = st.sidebar.file_uploader("Upload Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Período", options=meses_eixo, value=("jan/26", "fev/26"))

    resumo_farol = []

    def criar_grafico(titulo, busca_aba, is_gasto=True, especial=None):
        aba_real = next((k for k in db.keys() if normalizar(busca_aba) in normalizar(k)), None)
        if not aba_real: return
        df = db[aba_real].copy()

        if casa_sel == "Todas as Localidades":
            dados = df.select_dtypes(include=['number']).mean() if especial != "santa_ceia" else df.select_dtypes(include=['number']).sum()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            dados = linha.select_dtypes(include=['number']).iloc[0] if not linha.empty else None
        
        if dados is None: return

        # --- LÓGICA SANTA CEIA ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            y_vals = [int(dados.get(a, 0)) for a in anos]
            v21, v24, v25 = dados.get('2021', 0), dados.get('2024', 0), dados.get('2025', 0)
            
            p21_25 = ((v25 - v21) / v21 * 100) if v21 else 0
            p24_25 = ((v25 - v24) / v24 * 100) if v24 else 0

            fig = go.Figure()
            fig.add_trace(go.Bar(x=anos, y=y_vals, text=y_vals, textposition='auto', marker_color='#2c3e50', name="Participantes"))
            
            # Linha 1: 2021 para 2025 (Tendência Longa)
            fig.add_trace(go.Scatter(x=['2021', '2025'], y=[y_vals[0], y_vals[-1]], mode='lines+text',
                                     line=dict(color='red', width=2, dash='dash'),
                                     text=["", f"Total: {p21_25:+.1f}%"], textposition="top center"))
            
            # Linha 2: 2024 para 2025 (Variação Recente)
            fig.add_trace(go.Scatter(x=['2024', '2025'], y=[y_vals[3], y_vals[4]], mode='lines+text',
                                     line=dict(color='orange', width=3),
                                     text=["", f"Anual: {p24_25:+.1f}%"], textposition="bottom center"))

            fig.update_layout(height=400, showlegend=False, margin=dict(t=50))
            st.plotly_chart(fig, use_container_width=True)
            
            if casa_sel == "Todas as Localidades":
                st.dataframe(df[['LOCALIDADE_REF'] + anos].set_index('LOCALIDADE_REF'), use_container_width=True)
            return

        # --- GRÁFICOS FINANCEIROS E PER CAPTA ---
        m25, m26 = dados.get('Média 2025', 0), dados.get('Média 2026', 0)
        var = ((m26 - m25) / m25 * 100) if m25 else 0
        
        # Lógica das Bolinhas do Farol
        status_pos = (var <= 0 if is_gasto else var >= 0)
        cor_bola = "dot-green" if status_pos else "dot-red"
        bola_html = f'<span class="dot {cor_bola}"></span>'

        # Definição de Médias Várzea e Jundiaí
        m_varzea = f"{df['Média 2025'].mean():.2f}" if 'Média 2025' in df else "-"
        m_jdi = "-" # Padrão vazio conforme solicitado
        
        if especial == "per_capta":
            m_varzea, m_jdi = "22.28", "35.50" # Valores Reais Per Capta

        resumo_farol.append({
            "Indicador": titulo,
            "Farol": bola_html,
            "Var. %": f"{var:+.1f}%",
            "Média Várzea": m_varzea,
            "Média Regional Jdi": m_jdi
        })

        st.markdown(f"**{titulo}**")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7', name='Histórico'))
        
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        fig.add_trace(go.Bar(x=meses_sel, y=[dados.get(m, 0) for m in meses_sel], marker_color='#3498db', name='Atual'))
        
        if especial == "per_capta":
            fig.add_hline(y=float(m_varzea), line_dash="dash", line_color="orange", annotation_text="Várzea")
            fig.add_hline(y=float(m_jdi), line_dash="dot", line_color="red", annotation_text="Regional Jdi")

        fig.update_layout(height=280, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Renderização da Interface
    c1, c2 = st.columns(2)
    with c1: criar_grafico("Água e Esgoto", "Água")
    with c2: criar_grafico("Energia Elétrica", "Energia")
    c3, c4 = st.columns(2)
    with c3: criar_grafico("Manutenção", "Manutenção")
    with c4: criar_grafico("Alimentação", "Alimentação")
    
    st.divider()
    c5, c6 = st.columns(2)
    with c5: criar_grafico("Coletas Total", "Total", is_gasto=False)
    with c6: criar_grafico("Per Capta", "Per Capta", is_gasto=False, especial="per_capta")

    # --- TABELA DE FAROL ---
    st.subheader("🚩 Farol de Performance")
    if resumo_farol:
        df_farol = pd.DataFrame(resumo_farol)
        st.write(df_farol.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Evolução Santa Ceia")
    criar_grafico("Santa Ceia", "Santa Ceia", especial="santa_ceia")

else:
    st.info("Aguardando upload dos arquivos.")
