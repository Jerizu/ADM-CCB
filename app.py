import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(page_title="Dashboard Administrativo Igreja", layout="wide")

# Estilo dos Faróis (Trend Badges)
st.markdown("""
    <style>
    .farol { padding: 5px 12px; border-radius: 15px; color: white; font-weight: bold; float: right; font-size: 13px; }
    .status-bom { background-color: #27ae60; }
    .status-ruim { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

def extrair_valor_mes(row, mes_ref):
    """ Tenta encontrar o valor do mês independente do formato da coluna (jan/26, 2026-01-01, etc) """
    # Normaliza a busca para minúsculo e remove espaços
    for col in row.index:
        col_str = str(col).lower().strip()
        if mes_ref.lower() in col_str:
            return pd.to_numeric(row[col], errors='coerce')
    return 0

@st.cache_data
def carregar_dados(files):
    all_data = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for sheet in xl.sheet_names:
            # Pula as linhas de título para pegar o cabeçalho real
            df = pd.read_excel(xl, sheet_name=sheet, skiprows=1)
            # Limpa nomes de colunas
            df.columns = [str(c).strip() for c in df.columns]
            # Padroniza a coluna de localidade (Coluna B nos seus arquivos)
            if 'Unnamed: 1' in df.columns:
                df = df.rename(columns={'Unnamed: 1': 'Localidade'})
            all_data[sheet] = df
    return all_data

# --- UI INTERFACE ---
st.sidebar.title("Configuração do Dashboard")
uploaded_files = st.sidebar.file_uploader("Selecione os arquivos Excel", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = carregar_dados(uploaded_files)
    
    # Identificar abas disponíveis
    abas = list(db.keys())
    aba_ref = next((a for a in abas if "ÁGUA" in a.upper() or "ENERGIA" in a.upper()), abas[0])
    
    # Filtro de Localidade
    lista_casas = sorted(db[aba_ref]['Localidade'].dropna().unique())
    # Remove nomes que pareçam cabeçalhos
    lista_casas = [c for c in lista_casas if not any(x in str(c).upper() for x in ["TOTAL", "MÉDIA", "COLUNA"])]
    
    casa_sel = st.sidebar.selectbox("Casa de Oração", lista_casas)
    
    # Seleção de Período (Meses)
    meses_lista = ["jan/26", "fev/26", "mar/26", "abr/26", "mai/26", "jun/26"]
    periodo = st.sidebar.select_slider("Selecione o Período", options=meses_lista, value=("jan/26", "fev/26"))

    st.header(f"Gestão Financeira: {casa_sel}")

    def render_card_pdf(titulo, nome_aba, is_gasto=True):
        # Localiza a aba correta ignorando acentos
        aba_real = next((a for a in abas if nome_aba.upper() in a.upper()), None)
        if not aba_real: return
        
        df = db[aba_real]
        dados_casa = df[df['Localidade'] == casa_sel]
        if dados_casa.empty: return
        
        row = dados_casa.iloc[0]
        
        # 1. Pegar Médias Históricas
        m24 = pd.to_numeric(row.get('Média 2024', 0), errors='coerce')
        m25 = pd.to_numeric(row.get('Média 2025', 0), errors='coerce')
        
        # 2. Pegar Meses do Período Selecionado
        idx_ini = meses_lista.index(periodo[0])
        idx_fim = meses_lista.index(periodo[1]) + 1
        meses_atuais = meses_lista[idx_ini:idx_fim]
        valores_atuais = [extrair_valor_mes(row, m) for m in meses_atuais]

        # 3. Cálculo do Farol (Média 25 vs 24)
        var = ((m25 - m24) / m24 * 100) if m24 != 0 else 0
        is_bom = (var <= 0) if is_gasto else (var >= 0)
        classe = "status-bom" if is_bom else "status-ruim"

        # HTML do Título + Farol
        col_t, col_f = st.columns([3, 1])
        with col_t: st.markdown(f"**{titulo}**")
        with col_f: st.markdown(f'<span class="farol {classe}">{var:+.1f}%</span>', unsafe_allow_html=True)

        # Gráfico
        fig = go.Figure()
        # Médias em Cinza
        fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name="Médias"))
        # Meses em Azul
        fig.add_trace(go.Bar(x=meses_atuais, y=valores_atuais, marker_color='#3498db', name="Realizado"))

        # Linhas de Meta (Apenas para Per Capta)
        if "PER CAPTA" in titulo.upper():
            meta_vpta = pd.to_numeric(row.get('Média Várzea Pta', 0), errors='coerce')
            meta_jdi = pd.to_numeric(row.get('Média Regional Jdi', 0), errors='coerce')
            if meta_vpta: fig.add_hline(y=meta_vpta, line_dash="dash", line_color="green", annotation_text="Meta VPTA")
            if meta_jdi: fig.add_hline(y=meta_jdi, line_dash="dot", line_color="orange", annotation_text="Meta JDI")

        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Grid de 2 colunas como no PDF
    c1, c2 = st.columns(2)
    with c1: render_card_pdf("Água e Esgoto", "Água")
    with c2: render_card_pdf("Manutenção", "Manutenção")

    c3, c4 = st.columns(2)
    with c3: render_card_pdf("Energia Elétrica", "Energia")
    with c4: render_card_pdf("Alimentação", "Alimentação")

    c5, c6 = st.columns(2)
    with c5: render_card_pdf("Coletas Total", "Total", is_gasto=False)
    with c6: render_card_pdf("Coletas Per Capta", "Per Capta", is_gasto=False)

    # Santa Ceia (Histórico)
    st.divider()
    render_card_pdf("Participantes Santa Ceia", "Santa Ceia", is_gasto=False)

else:
    st.info("Aguardando upload do arquivo 'Relatório financeiro_2026_BD.xlsx'...")
