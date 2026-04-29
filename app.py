import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(page_title="Dashboard Ministerial", layout="wide")

# Estilo CSS para o Farol (Badges)
st.markdown("""
    <style>
    .farol { padding: 5px 15px; border-radius: 15px; color: white; font-weight: bold; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    # Caminho do seu arquivo principal (suba ele para o GitHub)
    file_path = "Relatório financeiro_2026_BD.xlsx"
    xl = pd.ExcelFile(file_path)
    
    data_dict = {}
    for sheet in xl.sheet_names:
        # Lê a aba pulando as linhas de título do Excel
        df = pd.read_excel(xl, sheet_name=sheet, skiprows=1)
        # Limpa colunas e nomes
        df.columns = [str(c).strip() for c in df.columns]
        if 'Unnamed: 1' in df.columns:
            df = df.rename(columns={'Unnamed: 1': 'Casa de Oração'})
        data_dict[sheet] = df
    return data_dict

try:
    db = load_data()
    
    # --- BARRA LATERAL (Filtros) ---
    st.sidebar.header("Filtros")
    # Pega lista de casas da aba Água como referência
    lista_casas = sorted(db['Água']['Casa de Oração'].dropna().unique())
    casa_sel = st.sidebar.selectbox("Selecione a Casa de Oração", lista_casas)

    st.title(f"Relatório Gerencial: {casa_sel}")

    # --- FUNÇÃO PARA CRIAR CADA CARD DO PDF ---
    def criar_card(titulo, aba_nome, is_gasto=True):
        df = db[aba_nome]
        dados_casa = df[df['Casa de Oração'] == casa_sel].iloc[0]
        
        # Extração de valores (Média 24, 25 e meses de 26)
        m24 = dados_casa.get('Média 2024', 0)
        m25 = dados_casa.get('Média 2025', 0)
        jan26 = dados_casa.get('2026-01-01', 0)
        fev26 = dados_casa.get('2026-02-01', 0)
        
        # Lógica do Farol
        variacao = ((m25 - m24) / m24 * 100) if m24 != 0 else 0
        cor_farol = "good" if (variacao <= 0 if is_gasto else variacao >= 0) else "bad"
        
        col1, col2 = st.columns([3, 1])
        with col1: st.subheader(titulo)
        with col2: st.markdown(f'<span class="farol {cor_farol}">{variacao:.1f}%</span>', unsafe_allow_html=True)
        
        # Gráfico
        fig = go.Figure(data=[
            go.Bar(name='Médias', x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7'),
            go.Bar(name='2026', x=['Jan/26', 'Fev/26'], y=[jan26, fev26], marker_color='#3498db')
        ])
        fig.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # --- GRID DO DASHBOARD ---
    c1, c2 = st.columns(2)
    with c1: criar_card("Água e Esgoto", "Água")
    with c2: criar_card("Manutenção", "Manutenção")

    c3, c4 = st.columns(2)
    with c3: criar_card("Energia Elétrica", "Energia")
    with c4: criar_card("Alimentação", "Alimentação")

    c5, c6 = st.columns(2)
    with c5: criar_card("Coletas Total", "Coletas e Ofertas - Total", is_gasto=False)
    with c6: criar_card("Coletas Per Capta", "Coletas e Ofertas - Per Capta", is_gasto=False)

    # --- SANTA CEIA (LARGURA TOTAL) ---
    st.divider()
    st.subheader("Participantes Santa Ceia")
    df_ceia = db['Santa Ceia']
    ceia_casa = df_ceia[df_ceia['Unnamed: 1'] == casa_sel].iloc[0]
    anos = ['2021', '2022', '2023', '2024', '2025']
    valores_ceia = [ceia_casa[ano] for ano in anos]
    
    fig_ceia = go.Figure(go.Bar(x=anos, y=valores_ceia, marker_color='#2c3e50'))
    fig_ceia.update_layout(height=300, yaxis=dict(range=[min(valores_ceia)*0.9, max(valores_ceia)*1.1]))
    st.plotly_chart(fig_ceia, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}. Certifique-se de que os arquivos estão no repositório.")