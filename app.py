import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Dashboard Ministerial CCB", layout="wide")

@st.cache_data
def carregar_dados(files):
    all_sheets = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            # Pula a primeira linha para pegar o cabeçalho correto
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            
            # Limpeza de nomes de colunas: converte datas do Excel para 'jan/26'
            novas_colunas = []
            for col in df.columns:
                if isinstance(col, (datetime, pd.Timestamp)):
                    meses = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 
                             7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
                    novas_colunas.append(f"{meses[col.month]}/{str(col.year)[2:]}")
                else:
                    novas_colunas.append(str(col).strip())
            df.columns = novas_colunas
            
            # Identifica coluna de localidade
            for col in df.columns[:3]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].str.replace(' II', ' 2').strip()
                    break
            all_sheets[name] = df
    return all_sheets

# --- BARRA LATERAL ---
st.sidebar.title("📊 Filtros")
uploaded_files = st.sidebar.file_uploader("Arraste o arquivo Excel aqui", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = carregar_dados(uploaded_files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), None)
    
    if aba_ref:
        lista_casas = ["Todas as Localidades"] + sorted(db[aba_ref]['LOCALIDADE_REF'].dropna().unique().tolist())
        casa_sel = st.sidebar.selectbox("Selecione a Localidade", lista_casas)

        # Eixo de meses disponível nos dados
        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Período de Análise", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def criar_grafico(titulo, busca_aba, is_gasto=True):
            # Localiza a aba correta
            aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper()), None)
            if not aba_real: return
            
            df = db[aba_real]
            
            # Filtra por localidade ou soma tudo
            if casa_sel == "Todas as Localidades":
                dados = df.drop(columns=['LOCALIDADE_REF'], errors='ignore').sum(numeric_only=True)
            else:
                linha = df[df['LOCALIDADE_REF'] == casa_sel]
                if linha.empty: return
                dados = linha.iloc[0]

            # Lógica específica para Santa Ceia (Evolução Anual)
            if "SANTA CEIA" in busca_aba.upper():
                anos = ['2021', '2022', '2023', '2024', '2025']
                valores = [pd.to_numeric(dados.get(a, 0), errors='coerce') for a in anos]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=anos, y=valores, mode='lines+markers+text', 
                                         text=[int(v) for v in valores], textposition="top center",
                                         line=dict(color='#2c3e50', width=3), name="Participantes"))
                fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20), title="Evolução Anual Santa Ceia")
                st.plotly_chart(fig, use_container_width=True)
                return

            # Lógica para Gráficos Mensais (Financeiros)
            m24 = pd.to_numeric(dados.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(dados.get('Média 2025', 0), errors='coerce')
            
            # Filtra meses do slider
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(dados.get(m, 0), errors='coerce') for m in meses_sel]

            # Cálculo de Tendência
            var = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            cor_farol = "#27ae60" if (var <= 0 if is_gasto else var >= 0) else "#c0392b"

            col_t, col_f = st.columns([3, 1])
            col_t.markdown(f"**{titulo}**")
            col_f.markdown(f'<span style="background:{cor_farol}; color:white; padding:2px 8px; border-radius:5px;">{var:+.1f}%</span>', unsafe_allow_html=True)

            fig = go.Figure()
            # Barras Cinzas (Médias Históricas)
            fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name='Histórico'))
            # Barras Azuis (Meses selecionados)
            fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', name='Meses'))

            fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, barmode='group')
            st.plotly_chart(fig, use_container_width=True)

        # Organização Visual
        c1, c2 = st.columns(2)
        with c1: criar_grafico("Água e Esgoto", "Água")
        with c2: criar_grafico("Manutenção", "Manutenção")

        c3, c4 = st.columns(2)
        with c3: criar_grafico("Energia Elétrica", "Energia")
        with c4: criar_grafico("Alimentação", "Alimentação")

        st.divider()
        st.subheader("Evolução Santa Ceia")
        criar_grafico("Participantes Santa Ceia", "Santa Ceia", is_gasto=False)

    else:
        st.error("Planilha não reconhecida. Verifique se os nomes das localidades estão na coluna B.")
