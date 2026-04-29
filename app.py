import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configuração da página para ocupar a tela toda
st.set_page_config(page_title="Dashboard Ministerial - Igreja", layout="wide")

# Estilo para os "Faróis" (Indicadores de tendência)
st.markdown("""
    <style>
    .farol { padding: 8px 15px; border-radius: 20px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .melhora { background-color: #27ae60; } /* Verde */
    .piora { background-color: #c0392b; }   /* Vermelho */
    .card-header { font-size: 18px; font-weight: bold; color: #2c3e50; text-align: center; border-bottom: 1px solid #eee; padding-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

def processar_excel(file):
    xl = pd.ExcelFile(file)
    data = {}
    for sheet in xl.sheet_names:
        # Pula as linhas de título para pegar o cabeçalho real (geralmente linha 2 ou 3)
        df = pd.read_excel(xl, sheet_name=sheet, skiprows=1)
        df.columns = [str(c).strip() for c in df.columns]
        # Identifica a coluna da localidade (Coluna B no seu arquivo)
        if 'Unnamed: 1' in df.columns:
            df = df.rename(columns={'Unnamed: 1': 'Localidade'})
        data[sheet] = df
    return data

# --- BARRA LATERAL ---
st.sidebar.title("Configurações")
uploaded_files = st.sidebar.file_uploader("Upload das Planilhas (.xlsx)", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    # Consolidação de múltiplos arquivos enviados
    db = {}
    for f in uploaded_files:
        db.update(processar_excel(f))

    # Filtro de Localidade (Cidades)
    # Tenta pegar as localidades de uma aba padrão como 'Água'
    aba_referencia = next((s for s in db.keys() if 'Água' in s or 'Agua' in s), None)
    
    if aba_referencia:
        lista_casas = sorted(db[aba_referencia]['Localidade'].dropna().unique())
        casa_sel = st.sidebar.selectbox("Selecione a Casa de Oração", lista_casas)

        st.title(f"Relatório Gerencial: {casa_sel}")

        # --- FUNÇÃO PARA GERAR OS GRÁFICOS DO PDF ---
        def render_card(titulo, chave_aba, is_gasto=True):
            try:
                # Localiza a aba correta ignorando acentos
                aba_real = next((s for s in db.keys() if chave_aba.upper() in s.upper()), None)
                if not aba_real: return
                
                df = db[aba_real]
                dados = df[df['Localidade'] == casa_sel].iloc[0]

                # Dados para o gráfico (Padrão do seu arquivo BD)
                m24 = float(dados.get('Média 2024', 0))
                m25 = float(dados.get('Média 2025', 0))
                v1 = float(dados.get('2026-01-01', dados.get('jan/25', 0)))
                v2 = float(dados.get('2026-02-01', dados.get('fev/25', 0)))

                # Cálculo do Farol
                var = ((m25 - m24) / m24 * 100) if m24 != 0 else 0
                # Para gasto: variação negativa é melhora (verde). Para coleta: variação positiva é melhora.
                is_good = (var <= 0) if is_gasto else (var >= 0)
                classe_farol = "melhora" if is_good else "piora"

                col_t, col_f = st.columns([3, 1])
                with col_t: st.markdown(f'<div class="card-header">{titulo}</div>', unsafe_allow_html=True)
                with col_f: st.markdown(f'<span class="farol {classe_farol}">{var:+.1f}%</span>', unsafe_allow_html=True)

                fig = go.Figure(data=[
                    go.Bar(name='Médias', x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7'),
                    go.Bar(name='Meses', x=['Jan', 'Fev'], y=[v1, v2], marker_color='#3498db')
                ])
                fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, yaxis=dict(gridcolor='#eee'))
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.warning(f"Dados não encontrados para {titulo}")

        # --- GRID DO DASHBOARD ---
        c1, c2 = st.columns(2)
        with c1: render_card("Água e Esgoto", "Água")
        with c2: render_card("Manutenção", "Manutenção")

        c3, c4 = st.columns(2)
        with c3: render_card("Energia Elétrica", "Energia")
        with c4: render_card("Alimentação", "Alimentação")

        c5, c6 = st.columns(2)
        with c5: render_card("Coletas Total", "Total", is_gasto=False)
        with c6: render_card("Coletas Per Capta", "Per Capta", is_gasto=False)

        # --- SANTA CEIA (RODAPÉ) ---
        st.divider()
        render_card("Participantes Santa Ceia", "Santa Ceia", is_gasto=False)

    else:
        st.info("Por favor, faça o upload do arquivo 'Relatório financeiro_2026_BD.xlsx' para iniciar.")
else:
    st.warning("Aguardando upload dos arquivos locais para gerar o relatório.")
