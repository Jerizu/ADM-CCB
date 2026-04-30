import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

st.markdown("""
    <style>
    .farol-badge { padding: 4px 10px; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    .stTable { font-size: 14px; }
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

if "resumo" not in st.session_state:
    st.session_state.resumo = {}

# --- INTERFACE ---
st.sidebar.title("📊 Painel Ministerial")
files = st.sidebar.file_uploader("Upload Relatório Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Filtrar Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Período de Análise", options=meses_eixo, value=("jan/26", "fev/26"))

    st.title(f"Relatório: {casa_sel}")

    def extrair_dados(busca_aba):
        aba_real = next((k for k in db.keys() if normalizar(busca_aba) in normalizar(k)), None)
        if not aba_real: return None, None
        df = db[aba_real].copy()
        if casa_sel == "Todas as Localidades":
            dados = df.select_dtypes(include=['number']).mean()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            dados = linha.select_dtypes(include=['number']).iloc[0] if not linha.empty else None
        return dados, df

    def criar_grafico(titulo, busca_aba, is_gasto=True, especial=None):
        dados, df_ori = extrair_dados(busca_aba)
        if dados is None: return

        # --- LÓGICA SANTA CEIA ---
        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            # Se for todas as localidades, somar
            if casa_sel == "Todas as Localidades":
                v_ceia = df_ori[anos].sum()
            else:
                v_ceia = dados[anos]
            
            y_vals = [int(v_ceia.get(a, 0)) for a in anos]
            
            # Cálculos de Diferença
            diff_21_25 = ((v_ceia['2025'] - v_ceia['2021']) / v_ceia['2021'] * 100) if v_ceia['2021'] else 0
            diff_24_25 = ((v_ceia['2025'] - v_ceia['2024']) / v_ceia['2024'] * 100) if v_ceia['2024'] else 0

            fig = go.Figure(go.Bar(x=anos, y=y_vals, text=y_vals, textposition='auto', marker_color='#2c3e50', name="Participantes"))
            
            # Linha de Diferença 2021-2025
            fig.add_shape(type="line", x0='2021', y0=y_vals[0], x1='2025', y1=y_vals[-1],
                          line=dict(color="Red", width=3, dash="dot"))
            
            fig.update_layout(height=400, title=f"Evolução Santa Ceia (Var. 21-25: {diff_21_25:+.1f}% | Var. 24-25: {diff_24_25:+.1f}%)")
            st.plotly_chart(fig, use_container_width=True)
            
            if casa_sel == "Todas as Localidades":
                st.markdown("**Tabela Detalhada por Localidade**")
                df_detalhe = df_ori[['LOCALIDADE_REF'] + anos].copy()
                st.dataframe(df_detalhe.set_index('LOCALIDADE_REF'), use_container_width=True)
            return

        # --- GRÁFICOS FINANCEIROS ---
        m25, m26 = dados.get('Média 2025', 0), dados.get('Média 2026', 0)
        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        valores_mes = [dados.get(m, 0) for m in meses_sel]

        # Guardar para a tabela de farol no fim
        var_anual = ((m26 - m25) / m25 * 100) if m25 else 0
        
        # Referências Fixas (Exemplo baseado no seu critério)
        ref_varzea = 22.28 if especial == "per_capta" else (df_ori['Média 2025'].mean() if 'Média 2025' in df_ori else 0)
        ref_jdi = 35.50 if especial == "per_capta" else (ref_varzea * 1.1) # Exemplo JDI 10% acima se não houver coluna

        st.session_state.resumo[titulo] = {
            "Comparativo 25/26": f"{var_anual:+.1f}%",
            "Média Várzea": round(ref_varzea, 2),
            "Média Jundiaí": round(ref_jdi, 2),
            "Status": "✅" if (var_anual <= 0 if is_gasto else var_anual >= 0) else "⚠️"
        }

        st.markdown(f"**{titulo}**")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7', name='Médias'))
        fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', name='Meses'))
        
        if especial == "per_capta":
            fig.add_hline(y=ref_varzea, line_dash="dash", line_color="orange", annotation_text="Várzea")
            fig.add_hline(y=ref_jdi, line_dash="dot", line_color="red", annotation_text="Jundiaí")

        fig.update_layout(height=280, barmode='group', showlegend=False, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- GRID DE RENDERIZAÇÃO ---
    st.session_state.resumo = {} # Limpa para recalcular
    
    col1, col2 = st.columns(2)
    with col1: criar_grafico("Água e Esgoto", "Água")
    with col2: criar_grafico("Energia Elétrica", "Energia")
    
    col3, col4 = st.columns(2)
    with col3: criar_grafico("Manutenção", "Manutenção")
    with col4: criar_grafico("Alimentação", "Alimentação")
    
    st.divider()
    col5, col6 = st.columns(2)
    with col5: criar_grafico("Coletas Total", "Total", is_gasto=False)
    with col6: criar_grafico("Per Capta", "Per Capta", is_gasto=False, especial="per_capta")
    
    # --- TABELA DE FAROL (NO FIM DOS GRÁFICOS FINANCEIROS) ---
    st.subheader("🚩 Tabela de Farol Consolidada")
    if st.session_state.resumo:
        df_farol = pd.DataFrame(st.session_state.resumo).T
        st.table(df_farol)

    st.divider()
    st.subheader("📊 Participantes Santa Ceia")
    criar_grafico("Santa Ceia", "Santa Ceia", especial="santa_ceia")

else:
    st.info("Por favor, faça o upload dos arquivos para gerar o relatório.")
