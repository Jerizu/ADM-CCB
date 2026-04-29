import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import tempfile

# --- CONFIGURAÇÃO E ESTILOS ---
st.set_page_config(page_title="Dashboard Ministerial CCB", layout="wide")

st.markdown("""
    <style>
    .farol { padding: 2px 10px; border-radius: 10px; color: white; font-weight: bold; font-size: 14px; float: right; }
    .good { background-color: #27ae60; }
    .bad { background-color: #c0392b; }
    .stPlotlyChart { border: 1px solid #f0f2f6; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def normalizar_nome(nome):
    if pd.isna(nome): return nome
    return str(nome).replace(' II', ' 2').strip()

@st.cache_data
def carregar_dados(files):
    all_sheets = {}
    for f in files:
        xl = pd.ExcelFile(f)
        for name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=name, skiprows=1)
            # Normaliza colunas e nomes de localidade
            for col in df.columns[:3]:
                if df[col].astype(str).str.contains('Cidade Nova|Jd.|Vila|Mursa', na=False, case=False).any():
                    df = df.rename(columns={col: 'LOCALIDADE_REF'})
                    df['LOCALIDADE_REF'] = df['LOCALIDADE_REF'].apply(normalizar_nome)
                    break
            all_sheets[name] = df
    return all_sheets

def gerar_pdf(casa_sel, figuras_base64):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Relatório Ministerial: {casa_sel}", ln=True, align='C')
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    
    # Adiciona as imagens dos gráficos (Streamlit/Plotly -> PDF requer salvar temporariamente)
    # Nota: Para uma implementação completa de exportação de imagem no servidor, 
    # recomenda-se usar o componente 'kaleido'.
    pdf.set_font("Arial", "I", 12)
    pdf.ln(10)
    pdf.cell(0, 10, "Consulte o dashboard online para interatividade completa.", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- BARRA LATERAL ---
st.sidebar.title("📊 Painel de Controle")
uploaded_files = st.sidebar.file_uploader("Upload: Relatório financeiro_2026_BD.xlsx", type="xlsx", accept_multiple_files=True)

if uploaded_files:
    db = carregar_dados(uploaded_files)
    aba_ref = next((k for k in db.keys() if 'LOCALIDADE_REF' in db[k].columns), None)
    
    if aba_ref:
        # Opção de ver todas ou uma específica
        opcoes_casas = ["Todas as Localidades"] + sorted(db[aba_ref]['LOCALIDADE_REF'].dropna().unique().tolist())
        casa_sel = st.sidebar.selectbox("Selecione a Localidade", opcoes_casas)

        meses_eixo = [f"{m}/{y}" for y in ['25', '26'] for m in ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']]
        periodo = st.sidebar.select_slider("Filtrar Período", options=meses_eixo, value=("jan/26", "fev/26"))

        st.title(f"Relatório Ministerial: {casa_sel}")

        def processar_dados(busca_aba):
            aba_real = next((k for k in db.keys() if busca_aba.upper() in k.upper().replace('Á','A')), None)
            if not aba_real: return None
            
            df = db[aba_real].copy()
            
            if casa_sel == "Todas as Localidades":
                # Soma os valores de todas as casas para o consolidado
                res = df.select_dtypes(include=['number']).sum()
                return res
            else:
                row = df[df['LOCALIDADE_REF'] == casa_sel]
                return row.iloc[0] if not row.empty else None

        def criar_grafico(titulo, busca_aba, is_gasto=True):
            data = processar_dados(busca_aba)
            if data is None: return
            
            m24 = pd.to_numeric(data.get('Média 2024', 0), errors='coerce')
            m25 = pd.to_numeric(data.get('Média 2025', 0), errors='coerce')
            
            idx_i, idx_f = meses_eixo.index(periodo[0]), meses_eixo.index(periodo[1]) + 1
            meses_sel = meses_eixo[idx_i:idx_f]
            valores_mes = [pd.to_numeric(data.get(m, 0), errors='coerce') for m in meses_sel]

            var = ((m25 - m24) / m24 * 100) if m24 and m24 != 0 else 0
            is_good = (var <= 0) if is_gasto else (var >= 0)
            classe = "good" if is_good else "bad"

            c_tit, c_far = st.columns([3, 1])
            c_tit.markdown(f"**{titulo}**")
            c_far.markdown(f'<span class="farol {classe}">{var:+.1f}%</span>', unsafe_allow_html=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=['Média 24', 'Média 25'], y=[m24, m25], marker_color='#bdc3c7', name='Médias'))
            fig.add_trace(go.Bar(x=meses_sel, y=valores_mes, marker_color='#3498db', name='Atual'))
            
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Layout em Grid similar ao PDF enviado
        col1, col2 = st.columns(2)
        with col1: criar_grafico("Água e Esgoto", "Água")
        with col2: criar_grafico("Manutenção", "Manutenção")

        col3, col4 = st.columns(2)
        with col3: criar_grafico("Energia Elétrica", "Energia")
        with col4: criar_grafico("Alimentação", "Alimentação")

        st.divider()
        col5, col6 = st.columns(2)
        with col5: criar_grafico("Coletas Total", "Coletas e Ofertas - Total", is_gasto=False)
        with col6: criar_grafico("Coletas Per Capta", "Per Capta", is_gasto=False)

        # Botão para salvar PDF (Simulação de geração de relatório)
        st.sidebar.divider()
        if st.sidebar.button("📄 Gerar PDF do Relatório"):
            pdf_data = gerar_pdf(casa_sel, [])
            st.sidebar.download_button(label="Clique para Baixar PDF", 
                                       data=pdf_data, 
                                       file_name=f"Relatorio_{casa_sel}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                       mime="application/pdf")

    else:
        st.error("Coluna 'Localidade' não encontrada.")
else:
    st.info("Por favor, faça o upload do arquivo para visualizar o dashboard.")
