import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(page_title="Dashboard Ministerial CCB", layout="wide")

# Estilos CSS para os Badges de Tendência (Faróis)
st.markdown("""
    <style>
    .farol { padding: 5px 15px; border-radius: 15px; color: white; font-weight: bold; float: right; font-size: 14px; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

def formatar_data_coluna(col):
    """Converte datas do Excel (Timestamp) para o formato jan/26 ou jan/25"""
    try:
        if isinstance(col, (pd.Timestamp, datetime.date)):
            meses = {1:'jan', 2:'fev', 3:'mar', 4:'abr', 5:'mai', 6:'jun', 
                     7:'jul', 8:'ago', 9:'set', 10:'out', 11:'nov', 12:'dez'}
            return f"{meses[col.month]}/{str(col.year)[2:]}"
    except:
        pass
    return str(col).strip().replace('\n', ' ')

@st.cache_data
def carregar_dados(files):
    all_sheets = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            # Lógica de leitura: pula 1 linha para pegar o cabeçalho real
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            # Limpa e formata cabeçalhos
            df.columns = [formatar_data_coluna(c) for c in df.columns]
            
            # Identifica a coluna da Casa de Oração (Coluna B - Unnamed: 1 ou Coluna1)
            for col in df.columns[:3]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    break
            all_sheets[name] = df
    return all_sheets

# --- BARRA LATERAL ---
st.sidebar.title("🛠️ Administração")
# Instrução específica solicitada
st.sidebar.info("📌 **Atenção:** Envie o arquivo com o nome: \n`Relatório financeiro_2026_BD.xlsx`")
uploaded_files = st.sidebar.file_uploader("Selecione o arquivo Excel", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = carregar_dados(uploaded_files)
    
    # Busca a lista de casas (usando a primeira aba que encontrar com a coluna de referência)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), None)
    
    if aba_ref:
        casas = sorted(db[aba_ref]['LOCALIDADE_REF'].dropna().unique())
        casa_sel = st.sidebar.selectbox("Selecione a Localidade", casas)

        # Slider de tempo (jan/25 até dez/26)
        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Filtrar Período", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def criar_grafico(titulo, busca_aba, is_gasto=True):
            # Procura a aba correta ignorando maiúsculas e acentos
            aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper().replace('Á','A').replace('Ç','C')), None)
            if not aba_real: return
            
            df = db[aba_real]
            row = df[df['LOCALIDADE_REF'] == casa_sel]
            if row.empty: return
            row = row.iloc[0]

            # Captura de Médias
            m24 = pd.to_numeric(row.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(row.get('Média 2025', 0), errors='coerce')
            
            # Captura de Meses (Slider)
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(row.get(m, 0), errors='coerce') for m in meses_sel]

            # Lógica do Farol de Tendência
            var = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            is_good = (var <= 0) if is_gasto else (var >= 0)
            classe = "good" if is_good else "bad"

            c_tit, c_far = st.columns([3, 1])
            c_tit.markdown(f"**{titulo}**")
            c_far.markdown(f'<span class="farol {classe}">{var:+.1f}%</span>', unsafe_allow_html=True)

            fig = go.Figure()
            # Barras de Histórico
            fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name='Médias'))
            # Barras do Período Atual
            fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', name='Meses'))

            # Linhas Médias Específicas para PER CAPTA
            if "PER CAPTA" in titulo.upper():
                mvp = pd.to_numeric(row.get('Média Várzea Pta', 0), errors='coerce')
                mrj = pd.to_numeric(row.get('Média Regional Jdi', 0), errors='coerce')
                if not pd.isna(mvp):
                    fig.add_hline(y=mvp, line_dash="dash", line_color="#27ae60", annotation_text="Média Várzea Pta")
                if not pd.isna(mrj):
                    fig.add_hline(y=mrj, line_dash="dot", line_color="#e67e22", annotation_text="Média Regional Jdi")

            fig.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Organização em Grid (Idêntico ao PDF)
        col1, col2 = st.columns(2)
        with col1: criar_grafico("Água e Esgoto", "Água")
        with col2: criar_grafico("Manutenção", "Manutenção")

        col3, col4 = st.columns(2)
        with col3: criar_grafico("Energia Elétrica", "Energia")
        with col4: criar_grafico("Alimentação", "Alimentação")

        col5, col6 = st.columns(2)
        with col5: criar_grafico("Coletas Total", "Coletas e Ofertas - Total", is_gasto=False)
        with col6: criar_grafico("Coletas Per Capta", "Per Capta", is_gasto=False)

        # Santa Ceia (Rodapé)
        st.divider()
        st.subheader("Histórico Participantes Santa Ceia")
        criar_grafico("Participantes", "Santa Ceia", is_gasto=False)

    else:
        st.error("Erro: Não foi possível encontrar a coluna de Localidades no arquivo enviado.")
else:
    st.warning("Aguardando o upload do arquivo: 'Relatório financeiro_2026_BD.xlsx'")
