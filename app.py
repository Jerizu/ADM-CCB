import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Ministerial CCB", layout="wide")

# Estilos CSS para os Faróis de Tendência
st.markdown("""
    <style>
    .farol {
        padding: 4px 10px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
        float: right;
    }
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
            # Lógica: pula a primeira linha para o cabeçalho real
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            
            # 1. Normalizar nomes das colunas (Datas do Excel para jan/26)
            novas_colunas = []
            for col in df.columns:
                if isinstance(col, (datetime, pd.Timestamp)):
                    meses_map = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 
                                 7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
                    novas_colunas.append(f"{meses_map[col.month]}/{str(col.year)[2:]}")
                else:
                    novas_colunas.append(str(col).strip())
            df.columns = novas_colunas
            
            # 2. Identificar e Tratar a coluna de Localidade
            for col in df.columns[:5]: 
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    # Limpeza robusta: converte para string, remove NaNs, padroniza "II" para "2"
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].astype(str).str.replace(' II', ' 2', regex=False).str.strip()
                    # Remove linhas onde a localidade ficou como "nan" ou "None"
                    df = df[~df['LOCALIDADE_REF'].isin(['nan', 'None', 'nan'])]
                    break
            
            all_sheets[name] = df
    return all_sheets

# --- BARRA LATERAL ---
st.sidebar.title("📊 Gestão Ministerial")
uploaded_files = st.sidebar.file_uploader("Upload do arquivo Excel", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = carregar_dados(uploaded_files)
    
    # Busca a aba que contém a coluna de localidades para preencher o filtro
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    
    if 'LOCALIDADE_REF' in db[aba_ref].columns:
        # CORREÇÃO DO TYPEERROR: Garante que os valores são strings e não nulos antes do sorted
        raw_casas = db[aba_ref]['LOCALIDADE_REF'].dropna().unique().tolist()
        casas_limpas = sorted([str(c) for c in raw_casas if str(c).lower() not in ['nan', 'none']])
        
        opcoes_casas = ["Todas as Localidades"] + casas_limpas
        casa_sel = st.sidebar.selectbox("Selecione a Localidade", opcoes_casas)
        
        # Slider de Período (Focado em 2025-2026 conforme seus dados)
        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Período para os Gráficos", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def criar_grafico(titulo, busca_aba, is_gasto=True):
            # Busca aba ignorando acentos e maiúsculas
            aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper().replace('Á','A')), None)
            if not aba_real: return
            
            df = db[aba_real]
            
            # Filtragem dos dados
            if casa_sel == "Todas as Localidades":
                dados = df.select_dtypes(include=['number']).sum()
            else:
                linha = df[df['LOCALIDADE_REF'] == casa_sel]
                if linha.empty: return
                dados = linha.iloc[0]

            # --- CASO ESPECIAL: SANTA CEIA (Evolução Anual) ---
            if "SANTA CEIA" in busca_aba.upper():
                anos = ['2021', '2022', '2023', '2024', '2025']
                valores_anos = [pd.to_numeric(dados.get(a, 0), errors='coerce') for a in anos]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=anos, y=valores_anos, mode='lines+markers+text',
                                         text=[f"{int(v)}" if not pd.isna(v) else "0" for v in valores_anos], 
                                         textposition="top center",
                                         line=dict(color='#2c3e50', width=3)))
                fig.update_layout(height=350, title="Evolução de Participantes (2021-2025)", 
                                  margin=dict(l=20,r=20,t=40,b=20), xaxis_title="Anos")
                st.plotly_chart(fig, use_container_width=True)
                return

            # --- CASO PADRÃO: FINANCEIRO (Mensal) ---
            m24 = pd.to_numeric(dados.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(dados.get('Média 2025', 0), errors='coerce')
            
            # Pega os meses entre o início e fim do slider
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(dados.get(m, 0), errors='coerce') for m in meses_sel]

            # Cálculo do Farol
            var =
