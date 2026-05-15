import streamlit as st
import pandas as pd
import sqlite3
import matplotlib
import unicodedata

# --- 1. FUNÇÃO DE TRATAMENTO DE TEXTO (Acentos e Busca) ---
def remover_acentos(texto):
    if not texto: return ""
    return "".join(c for c in unicodedata.normalize('NFKD', str(texto).upper()) if not unicodedata.combining(c))

# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Oráculo do Clima", page_icon="🌤️", layout="wide")

st.title("🌤️ Oráculo do Clima - Goiás")
st.markdown("Análise detalhada de extremos térmicos e rankings oficiais do estado.")

# --- 3. CARREGAMENTO DOS DADOS (Com correção de Data ISO8601) ---
@st.cache_data
def carregar_dados():
    try:
        conexao = sqlite3.connect("banco_oraculo.db")
        df = pd.read_sql("SELECT * FROM clima_goias", conexao)
        conexao.close()
        
        # Garante que o Pandas entenda as datas do SQLite sem o erro de '00:00:00'
        df['data'] = pd.to_datetime(df['data'], format='ISO8601', errors='coerce')
        
        # Cria uma coluna invisível para facilitar as buscas sem acento
        df['cidade_norm'] = df['cidade'].apply(remover_acentos)
        
        return df.dropna(subset=['data']).sort_values(by='data').reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar o banco: {e}")
        return pd.DataFrame()

dados_completos = carregar_dados()

if dados_completos.empty:
    st.warning("⚠️ Banco de dados não encontrado ou vazio. Verifique o arquivo .db!")
    st.stop()

# --- 4. ABAS DO APLICATIVO ---
aba1, aba2 = st.tabs(["📊 Análise Mensal Detalhada", "🏆 Hall da Fama (Rankings)"])

# ==========================================
# ABA 1: O "TREM BONITINHO" COM TUDO DENTRO
# ==========================================
with aba1:
    st.header("Análise por Cidade e Mês")
    
    cidades_escolhidas = st.multiselect(
        "Selecione as cidades:", 
        options=sorted(dados_completos['cidade'].unique()),
        default=['GOIANIA']
    )

    if not cidades_escolhidas:
        st.info("💡 Selecione uma cidade para começar.")
    else:
        df_filt = dados_completos[dados_completos['cidade'].isin(cidades_escolhidas)].copy()

        c1, c2 = st.columns(2)
        with c1:
            ano = st.selectbox("Selecione o Ano:", sorted(df_filt['data'].dt.year.unique(), reverse=True))
        with c2:
            mes = st.selectbox("Selecione o Mês:", sorted(df_filt[df_filt['data'].dt.year == ano]['data'].dt.month.unique()))

        df_mes = df_filt[(df_filt['data'].dt.year == ano) & (df_filt['data'].dt.month == mes)].copy()

        # --- MÉTRICAS DE DESTAQUE ---
        st.markdown("### 📊 Indicadores do Mês")
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            d_quentes = len(df_mes[df_mes['temp_max'] >= 35])
            st.metric("Dias de Calor (>=35°C)", f"{d_quentes} dias")
        with m2:
            d_frios = len(df_mes[df_mes['temp_min'] <= 15])
            st.metric("Dias de Frio (<=15°C)", f"{d_frios} dias")
        with m3:
            st.metric("Maior Máxima", f"{df_mes['temp_max'].max():.1f}°C")
        with m4:
            st.metric("Menor Mínima", f"{df_mes['temp_min'].min():.1f}°C")

        # --- GRÁFICO DE LINHA ---
        st.markdown("### 📈 Evolução da Temperatura Máxima")
        st.line_chart(df_mes.pivot(index='data', columns='cidade', values='temp_max'))

        # --- TABELA MENSAL ESTILIZADA ---
        st.markdown("### 📅 Registros Detalhados")
        # Garante que as colunas existam para não dar erro
        colunas_exibir = ['data', 'cidade', 'temp_max', 'temp_min', 'chuva']
        if 'umidade' in df_mes.columns: colunas_exibir.append('umidade')
        
        tabela_view = df_mes[colunas_exibir].copy()
        tabela_view['data'] = tabela_view['data'].dt.strftime('%d/%m/%Y')
        
        # Renomeando para ficar profissional
        nomes_colunas = {'data': 'Data', 'cidade': 'Cidade', 'temp_max': 'Máx (°C)', 'temp_min': 'Mín (°C)', 'chuva': 'Chuva (mm)'}
        if 'umidade' in df_mes.columns: nomes_colunas['umidade'] = 'Umid (%)'
        tabela_view.columns = [nomes_colunas.get(c, c) for c in tabela_view.columns]

        # Função de cores para a tabela
        def colorir_extremos(row):
            estilo = [''] * len(row)
            if row['Máx (°C)'] >= 35: estilo = ['background-color: #631212; color: white'] * len(row)
            elif row['Mín (°C)'] <= 15: estilo = ['background-color: #122b63; color: white'] * len(row)
            return estilo

        st.dataframe(tabela_view.style.apply(colorir_extremos, axis=1).format(precision=1), use_container_width=True, hide_index=True)

# ==========================================
# ABA 2: RANKINGS E BUSCA INTELIGENTE
# ==========================================
with aba2:
    st.header("🏆 Hall da Fama Climático de Goiás")
    
    # Cálculos dos Rankings (Agrupando por cidade para pegar os recordes reais)
    idx_calor = dados_completos.groupby('cidade')['temp_max'].idxmax()
    ranking_calor = dados_completos.loc[idx_calor].copy().sort_values(by='temp_max', ascending=False).reset_index(drop=True)
    ranking_calor.index += 1

    idx_frio = dados_completos.groupby('cidade')['temp_min'].idxmin()
    ranking_frio = dados_completos.loc[idx_frio].copy().sort_values(by='temp_min', ascending=True).reset_index(drop=True)
    ranking_frio.index += 1

    # --- CAMPO DE BUSCA COM E SEM ACENTO ---
    st.subheader("🔍 Localizar Cidade")
    busca_raw = st.text_input("Digite o nome da cidade para ver a posição:")
    busca_limpa = remover_acentos(busca_raw)

    if busca_limpa:
        # Busca usando a normalização que fizemos lá no início
        res_c = ranking_calor[ranking_calor['cidade_norm'].str.contains(busca_limpa, na=False)]
        res_f = ranking_frio[ranking_frio['cidade_norm'].str.contains(busca_limpa, na=False)]
        
        if not res_c.empty:
            c1, c2 = st.columns(2)
            cidade_nome = res_c.iloc[0]['cidade']
            with c1:
                st.success(f"🔥 **{cidade_nome}** no Calor:")
                st.write(f"Posição: **#{res_c.index[0]}**")
                st.write(f"Máxima: **{res_c.iloc[0]['temp_max']:.1f}°C** em {res_c.iloc[0]['data'].strftime('%d/%m/%Y')}")
            with c2:
                st.info(f"🧊 **{cidade_nome}** no Frio:")
                st.write(f"Posição: **#{res_f.index[0]}**")
                st.write(f"Mínima: **{res_f.iloc[0]['temp_min']:.1f}°C** em {res_f.iloc[0]['data'].strftime('%d/%m/%Y')}")
        else:
            st.error("Cidade não encontrada no banco de dados.")

    st.markdown("---")

    # --- TABELAS DE RANKING COLORIDAS ---
    # Limpando as datas para a exibição (Removendo o 00:00:00 de vez!)
    view_calor = ranking_calor[['cidade', 'temp_max', 'data']].copy()
    view_calor['data'] = view_calor['data'].dt.strftime('%d/%m/%Y')
    view_calor.columns = ['Cidade', 'Máxima (°C)', 'Data']

    view_frio = ranking_frio[['cidade', 'temp_min', 'data']].copy()
    view_frio['data'] = view_frio['data'].dt.strftime('%d/%m/%Y')
    view_frio.columns = ['Cidade', 'Mínima (°C)', 'Data']

    col_q, col_f = st.columns(2)
    with col_q:
        st.subheader("🔥 Top Calor")
        st.dataframe(
            view_calor.style.background_gradient(cmap='Reds', subset=['Máxima (°C)'])
            .format({'Máxima (°C)': '{:.1f}'}), 
            use_container_width=True
        )

    with col_f:
        st.subheader("🧊 Top Frio")
        st.dataframe(
            view_frio.style.background_gradient(cmap='Blues_r', subset=['Mínima (°C)'])
            .format({'Mínima (°C)': '{:.1f}'}), 
            use_container_width=True
        )