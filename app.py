import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

st.markdown("""
    <style>
    .dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 5px; }
    .dot-green { background-color: #27ae60; }
    .dot-red { background-color: #c0392b; }
    .stTable { width: 100%; font-size: 14px; }
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

files = st.sidebar.file_uploader("Upload Relatórios Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Selecionar Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Janela de Visualização", options=meses_eixo, value=("jan/26", "fev/26"))

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

        # --- SANTA CEIA ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            y_vals = [int(dados.get(a, 0)) for a in anos]
            v21, v24, v25 = dados.get('2021', 0), dados.get('2024', 0), dados.get('2025', 0)
            
            p21_25 = ((v25 - v21) / v21 * 100) if v21 else 0
            p24_25 = ((v25 - v24) / v24 * 100) if v24 else 0

            fig = go.Figure()
            fig.add_trace(go.Bar(x=anos, y=y_vals, text=y_vals, textposition='auto', marker_color='#2c3e50'))
            
            # Linha 1: 2021 -> 2025 (Tracejada Vermelha)
            fig.add_trace(go.Scatter(x=['2021', '2025'], y=[y_vals[0], y_vals[-1]], mode='lines+text',
                                     line=dict(color='red', width=2, dash='dash'),
                                     text=["", f"{p21_25:+.1f}%"], textposition="top right"))
            
            # Linha 2: 2024 -> 2025 (Sólida Laranja)
            fig.add_trace(go.Scatter(x=['2024', '2025'], y=[y_vals[3], y_vals[4]], mode='lines+text',
                                     line=dict(color='orange', width=3),
                                     text=["", f"{p24_25:+.1f}%"], textposition="bottom center"))

            fig.update_layout(height=400, showlegend=False, title="Variação de Participantes")
            st.plotly_chart(fig, use_container_width=True)
            
            if casa_sel == "Todas as Localidades":
                st.dataframe(df[['LOCALIDADE_REF'] + anos].set_index('LOCALIDADE_REF'), use_container_width=True)
            return

        # --- FINANCEIRO & PER CAPTA ---
        m25, m26 = dados.get('Média 2025', 0), dados.get('Média 2026', 0)
        var = ((m26 - m25) / m25 * 100) if m25 else 0
        
        status_pos = (var <= 0 if is_gasto else var >= 0)
        cor_bola = "dot-green" if status_pos else "dot-red"
        bola_html = f'<span class="dot {cor_bola}"></span>'

        # Referências Farol
        ref_varzea = 22.28 if especial == "per_capta" else (df['Média 2025'].mean() if 'Média 2025' in df else 0)
        ref_jdi = "35.50" if especial == "per_capta" else "-"

        resumo_farol.append({
            "Métrica": titulo,
            "Farol": bola_html,
            "Média 2026": f"{m26:.2f}",
            "Var. 25/26": f"{var:+.1f}%",
            "Média Várzea": f"{ref_varzea:.2f}" if isinstance(ref_varzea, float) else ref_varzea,
            "Média Reg. Jdi": ref_jdi
        })

        st.markdown(f"**{titulo}**")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7'))
        
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        fig.add_trace(go.Bar(x=meses_sel, y=[dados.get(m, 0) for m in meses_sel], marker_color='#3498db'))
        
        if especial == "per_capta":
            fig.add_hline(y=float(ref_varzea), line_dash="dash", line_color="orange", annotation_text="Média Várzea")
            fig.add_hline(y=float(ref_jdi), line_dash="dot", line_color="red", annotation_text="Média Jdi")

        fig.update_layout(height=260, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Layout Grid
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

    # --- TABELA DE FAROL FINAL ---
    st.subheader("🚩 Farol de Performance")
    if resumo_farol:
        df_farol = pd.DataFrame(resumo_farol)
        st.write(df_farol.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Histórico Santa Ceia")
    criar_grafico("Santa Ceia", "Santa Ceia", especial="santa_ceia")

else:
    st.info("Por favor, carregue o arquivo Excel para visualizar o relatório.")
