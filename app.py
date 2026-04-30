import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

# CSS para replicar o design da foto (Tabela e Badges)
st.markdown("""
    <style>
    .farol-badge { padding: 4px 10px; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .status-ok { color: #27ae60; font-weight: bold; }
    .status-alerta { color: #c0392b; font-weight: bold; }
    table { width: 100%; border-collapse: collapse; }
    th { background-color: #f8f9fa; color: #2c3e50; text-align: left; padding: 10px; border-bottom: 2px solid #dee2e6; }
    td { padding: 10px; border-bottom: 1px solid #dee2e6; }
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

if files := st.sidebar.file_uploader("Upload Excel", type="xlsx", accept_multiple_files=True):
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Período", options=meses_eixo, value=("jan/26", "fev/26"))

    resumo_dados = []

    def processar_grafico(titulo, busca_aba, is_gasto=True, especial=None):
        aba_real = next((k for k in db.keys() if normalizar(busca_aba) in normalizar(k)), None)
        if not aba_real: return
        df = db[aba_real].copy()

        if casa_sel == "Todas as Localidades":
            dados = df.select_dtypes(include=['number']).mean() if especial != "santa_ceia" else df.select_dtypes(include=['number']).sum()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            dados = linha.select_dtypes(include=['number']).iloc[0] if not linha.empty else None
        
        if dados is None: return

        # --- LÓGICA ESPECÍFICA SANTA CEIA ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            y_vals = [int(dados.get(a, 0)) for a in anos]
            
            diff_21_25 = ((dados['2025'] - dados['2021']) / dados['2021'] * 100) if dados['2021'] else 0
            diff_24_25 = ((dados['2025'] - dados['2024']) / dados['2024'] * 100) if dados['2024'] else 0

            fig = go.Figure()
            fig.add_trace(go.Bar(x=anos, y=y_vals, text=y_vals, textposition='auto', marker_color='#2c3e50'))
            
            # Linha Reta de Tendência (Design da Foto)
            fig.add_trace(go.Scatter(x=['2021', '2025'], y=[y_vals[0], y_vals[-1]], 
                                     mode='lines+text', line=dict(color='red', width=2, dash='dash'),
                                     text=[f"", f"{diff_21_25:+.1f}%"], textposition="top right"))

            fig.update_layout(height=400, title=f"Evolução Participantes (Var. 24 vs 25: {diff_24_25:+.1f}%)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
            if casa_sel == "Todas as Localidades":
                st.write("**Valores por Localidade (Santa Ceia)**")
                st.dataframe(df[['LOCALIDADE_REF'] + anos].set_index('LOCALIDADE_REF'), use_container_width=True)
            return

        # --- DEMAIS GRÁFICOS ---
        m25, m26 = dados.get('Média 2025', 0), dados.get('Média 2026', 0)
        var = ((m26 - m25) / m25 * 100) if m25 else 0
        
        # Referências para a Tabela de Farol
        ref_v = 22.28 if especial == "per_capta" else (df['Média 2025'].mean() if 'Média 2025' in df else 0)
        ref_j = 35.50 if especial == "per_capta" else (ref_v * 1.15) # Simulação Regional
        
        resumo_dados.append({
            "Métrica": titulo,
            "Var. 25/26": f"{var:+.1f}%",
            "Média Várzea": f"{ref_v:.2f}",
            "Média Regional (Jdi)": f"{ref_j:.2f}",
            "Status": "✅" if (var <= 0 if is_gasto else var >= 0) else "⚠️"
        })

        st.markdown(f"**{titulo}**")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7'))
        
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        fig.add_trace(go.Bar(x=meses_sel, y=[dados.get(m, 0) for m in meses_sel], marker_color='#3498db'))
        
        fig.update_layout(height=250, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Grid de Gráficos
    c1, c2 = st.columns(2)
    with c1: processar_grafico("Água e Esgoto", "Água")
    with c2: processar_grafico("Energia Elétrica", "Energia")
    c3, c4 = st.columns(2)
    with c3: processar_grafico("Manutenção", "Manutenção")
    with c4: processar_grafico("Alimentação", "Alimentação")
    
    st.divider()
    c5, c6 = st.columns(2)
    with c5: processar_grafico("Coletas Total", "Total", is_gasto=False)
    with c6: processar_grafico("Per Capta", "Per Capta", is_gasto=False, especial="per_capta")

    # --- TABELA DE FAROL (DESIGN DA FOTO) ---
    st.subheader("🚩 Farol de Indicadores")
    if resumo_dados:
        st.table(pd.DataFrame(resumo_dados))

    st.divider()
    st.subheader("📊 Santa Ceia")
    processar_grafico("Santa Ceia", "Santa Ceia", especial="santa_ceia")

else:
    st.info("Aguardando upload do arquivo Excel...")
