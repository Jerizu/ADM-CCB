import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Relatório Ministerial CCB", layout="wide")

# Estilos CSS
st.markdown("""
    <style>
    .farol-badge { padding: 4px 10px; border-radius: 8px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    .metric-card { 
        background-color: #f8f9fa; padding: 15px; border-radius: 10px; 
        border-left: 5px solid #ccc; margin-bottom: 10px; text-align: center;
    }
    .legenda-container { display: flex; gap: 20px; justify-content: center; font-size: 13px; margin-top: 5px; }
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

# --- INTERFACE ---
st.sidebar.title("📊 Painel Ministerial")
files = st.sidebar.file_uploader("Upload Relatório Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    casas = ["Todas as Localidades"] + sorted([str(c) for c in db[aba_ref]['LOCALIDADE_REF'].unique()])
    casa_sel = st.sidebar.selectbox("Filtrar Localidade", casas)
    
    meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
    periodo = st.sidebar.select_slider("Selecione o Período", options=meses_eixo, value=("jan/26", "fev/26"))

    st.title(f"Relatório: {casa_sel}")

    # --- DICIONÁRIO PARA O RESUMO DE FARÓIS ---
    resumo_farois = []

    def processar_dados(busca_aba, especial=None):
        aba_real = next((k for k in db.keys() if normalizar(busca_aba) in normalizar(k)), None)
        if not aba_real: return None, None
        df = db[aba_real].copy()

        if casa_sel == "Todas as Localidades":
            if especial == "santa_ceia": dados = df.select_dtypes(include=['number']).sum()
            else: dados = df.select_dtypes(include=['number']).mean()
        else:
            linha = df[df['LOCALIDADE_REF'] == casa_sel]
            dados = linha.select_dtypes(include=['number']).iloc[0] if not linha.empty else None
        return dados, df

    def criar_grafico(titulo, busca_aba, is_gasto=True, especial=None):
        dados, df_completo = processar_dados(busca_aba, especial)
        if dados is None: return

        m25, m26 = dados.get('Média 2025', 0), dados.get('Média 2026', 0)
        var = ((m26 - m25) / m25 * 100) if m25 else 0
        status = (var <= 0 if is_gasto else var >= 0)
        cor = "good" if status else "bad"
        
        # Salva para o painel de resumo
        resumo_farois.append({"metric": titulo, "var": var, "status": status})

        if especial == "santa_ceia":
            anos = ['2021', '2022', '2023', '2024', '2025']
            valores = [int(dados.get(a, 0)) for a in anos]
            fig = go.Figure(go.Bar(x=anos, y=valores, text=valores, textposition='auto', marker_color='#2c3e50'))
            fig.update_layout(height=350, margin=dict(l=10,r=10,t=10,b=10), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            st.table(pd.DataFrame([valores], columns=anos, index=[casa_sel]))
            return

        idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
        meses_sel = meses_eixo[idx_i:idx_f]
        valores_mes = [dados.get(m, 0) for m in meses_sel]

        st.markdown(f"**{titulo}** <span class='farol-badge {cor}'>{var:+.1f}%</span>", unsafe_allow_html=True)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=['Média 25', 'Média 26'], y=[m25, m26], marker_color='#bdc3c7', showlegend=False))
        fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', showlegend=False))

        if especial == "per_capta":
            v_varzea, v_reg = 22.28, 35.50
            # Adicionando traces vazios apenas para a legenda
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='orange', dash='dash'), name='Média Várzea'))
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='red', dash='dot'), name='Média Regional'))
            
            fig.add_hline(y=v_varzea, line_dash="dash", line_color="orange", annotation_text=f"{v_varzea}")
            fig.add_hline(y=v_reg, line_dash="dot", line_color="red", annotation_text=f"{v_reg}")
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

        fig.update_layout(height=300, barmode='group', margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- PAINEL DE RESUMO (FARÓIS) ---
    # Processamos os dados antes para preencher a lista de resumo
    abas_chaves = [("Água", "Água"), ("Energia", "Energia"), ("Manutenção", "Manutenção"), 
                   ("Alimentação", "Alimentação"), ("Total", "Total"), ("Per Capta", "Per Capta")]
    
    st.subheader("📌 Resumo de Performance (Média 26 vs Média 25)")
    cols_f = st.columns(len(abas_chaves))
    
    # Renderização da Grade de Gráficos com alinhamento rigoroso
    c1, c2 = st.columns(2)
    with c1: criar_grafico("Água e Esgoto", "Água")
    with c2: criar_grafico("Energia Elétrica", "Energia")
    
    c3, c4 = st.columns(2)
    with c3: criar_grafico("Manutenção", "Manutenção")
    with c4: criar_grafico("Alimentação", "Alimentação")
    
    st.divider()
    # Alinhamento Total Coletas e Per Capta
    c5, c6 = st.columns(2)
    with c5: criar_grafico("Total Coletas", "Total", is_gasto=False)
    with c6: criar_grafico("Coleta Per Capta", "Per Capta", is_gasto=False, especial="per_capta")
    
    # Renderizar os badges no topo agora que os dados foram calculados
    for i, item in enumerate(resumo_farois[:6]):
        with cols_f[i]:
            bg = "#27ae60" if item['status'] else "#c0392b"
            st.markdown(f"""<div class='metric-card' style='border-left-color:{bg}'>
                        <small>{item['metric']}</small><br><b style='color:{bg}'>{item['var']:+.1f}%</b>
                        </div>""", unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Histórico Santa Ceia")
    criar_grafico("Evolução Santa Ceia", "Santa Ceia", especial="santa_ceia")

else:
    st.info("Aguardando upload do arquivo Excel.")
