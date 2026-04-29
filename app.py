import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Ministerial CCB", layout="wide")

# Estilos CSS para o "Farol" de variação
st.markdown("""
    <style>
    .farol {
        padding: 4px 10px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
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
            # Pula a primeira linha conforme a estrutura do seu Excel
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            
            # 1. Normalizar nomes das colunas (Tratar Datas do Excel)
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
            for col in df.columns[:5]: # Procura nas primeiras colunas
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    # Correção do AttributeError usando .str.strip()
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].astype(str).str.replace(' II', ' 2').str.strip()
                    break
            
            all_sheets[name] = df
    return all_sheets

# --- INTERFACE LATERAL ---
st.sidebar.title("📊 Gestão Ministerial")
files = st.sidebar.file_uploader("Upload do arquivo Excel", type="xlsx", accept_multiple_files=True)

if files:
    db = carregar_dados(files)
    
    # Tenta achar a aba principal para pegar a lista de casas
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), list(db.keys())[0])
    
    if 'LOCALIDADE_REF' in db[aba_ref].columns:
        casas = ["Todas as Localidades"] + sorted(db[aba_ref]['LOCALIDADE_REF'].unique().tolist())
        casa_sel = st.sidebar.selectbox("Selecione a Localidade", casas)
        
        # Filtro de Meses (Slider)
        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Período para Gráficos Mensais", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório: {casa_sel}")

        def criar_grafico(titulo, busca_aba, is_gasto=True):
            # Encontrar a aba correta ignorando maiúsculas/minúsculas
            aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper()), None)
            if not aba_real: return
            
            df = db[aba_real]
            
            # Filtragem: Soma tudo se for "Todas as Localidades"
            if casa_sel == "Todas as Localidades":
                dados = df.select_dtypes(include=['number']).sum()
            else:
                linha = df[df['LOCALIDADE_REF'] == casa_sel]
                if linha.empty: return
                dados = linha.iloc[0]

            # --- LÓGICA ESPECIAL SANTA CEIA (Evolução Anual) ---
            if "SANTA CEIA" in busca_aba.upper():
                anos = ['2021', '2022', '2023', '2024', '2025']
                valores_anos = [pd.to_numeric(dados.get(a, 0), errors='coerce') for a in anos]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=anos, y=valores_anos, mode='lines+markers+text',
                                         text=[f"{int(v)}" for v in valores_anos], textposition="top center",
                                         line=dict(color='#2c3e50', width=3)))
                fig.update_layout(height=350, title="Evolução de Participantes (Anual)", margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig, use_container_width=True)
                return

            # --- LÓGICA GRÁFICOS FINANCEIROS (Médias vs Meses) ---
            m24 = pd.to_numeric(dados.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(dados.get('Média 2025', 0), errors='coerce')
            
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
