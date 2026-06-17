import streamlit as st
import pandas as pd
import requests
import requests_cache
import urllib3
import time

# 1. Configurações Iniciais
# Desliga os avisos chatos de "InsecureRequest" por conta do SSL (como falamos antes)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configura o cache (cria um arquivo viacep_cache.sqlite na pasta do app)
# expire_after=2592000 significa que o cache dura 30 dias
requests_cache.install_cache('viacep_cache', expire_after=2592000)

# Configuração da página do Streamlit
st.set_page_config(page_title="Enriquecedor de CEP", page_icon="📍")

# 2. Função de Busca
def buscar_cep(cep):
    if pd.isna(cep):
        return pd.Series(["", "", "", "", "Célula Vazia"], index = ['Logradouro', 'Bairro', 'Cidade', 'UF', 'Status_Busca'])
        
    cep_limpo = ''.join(filter(str.isdigit, str(cep)))
    
    if len(cep_limpo) != 8:
        return pd.Series(["", "", "", "", "CEP Inválido"], index = ['Logradouro', 'Bairro', 'Cidade', 'UF', 'Status_Busca'])
        
    url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
    
    try:
        # verify=False ignora o erro de SSL
        response = requests.get(url, verify=False, timeout=5)
        
        if response.status_code == 200:
            dados = response.json()
            if "erro" in dados:
                return pd.Series(["", "", "", "", "Não Encontrado"], index = ['Logradouro', 'Bairro', 'Cidade', 'UF', 'Status_Busca'])
            
            # Se a resposta veio do cache, o requests_cache adiciona a flag 'from_cache'
            origem = "Cache" if getattr(response, 'from_cache', False) else "API"
            
            return pd.Series([
                dados.get('logradouro', ''), 
                dados.get('bairro', ''), 
                dados.get('localidade', ''), 
                dados.get('uf', ''),
                f"Sucesso ({origem})"
            ], index = ['Logradouro', 'Bairro', 'Cidade', 'UF', 'Status_Busca'])
        else:
            return pd.Series(["", "", "", "", f"Erro HTTP {response.status_code}"])
            
    except Exception as e:
        return pd.Series(["", "", "", "", f"Erro: {str(e)}"], index = ['Logradouro', 'Bairro', 'Cidade', 'UF', 'Status_Busca'])

# 3. Interface do Usuário
st.title("📍 Enriquecedor de Endereços via CEP")
st.markdown("Suba um arquivo CSV contendo uma coluna chamada **CEP**. O sistema irá preencher os dados e retornar um novo arquivo. Consultas repetidas são cacheadas automaticamente!")

arquivo_upload = st.file_uploader("Escolha um arquivo CSV", type=["csv"])

if arquivo_upload is not None:
    # Lê o CSV
    df = pd.read_csv(arquivo_upload, dtype=str) # Lê tudo como string para não perder zeros à esquerda
    
    st.write("Visualização das primeiras linhas:")
    st.dataframe(df.head())
    
    # Verifica se a coluna 'CEP' existe (ignorando maiúsculas/minúsculas)
    colunas_upper = [col.upper() for col in df.columns]
    
    if 'CEP' not in colunas_upper:
        st.error("Erro: O arquivo CSV precisa ter uma coluna chamada 'CEP'.")
    else:
        # Encontra o nome exato da coluna original
        col_cep_nome = df.columns[colunas_upper.index('CEP')]
        
        if st.button("Processar Arquivo"):
            st.info("Processando... Por favor, aguarde.")
            
            # Barra de progresso para dar feedback visual aos colegas
            barra_progresso = st.progress(0)
            status_text = st.empty()
            
            # Prepara as novas colunas
            resultados = []
            total_linhas = len(df)
            
            for index, row in df.iterrows():
                cep_atual = row[col_cep_nome]
                resultado = buscar_cep(cep_atual)
                resultados.append(resultado)
                
                # Atualiza a barra
                progresso = (index + 1) / total_linhas
                barra_progresso.progress(progresso)
                status_text.text(f"Processando linha {index + 1} de {total_linhas}...")
                
                # Um sleep minúsculo apenas para requisições que NÃO estão no cache
                # Para não sobrecarregar o ViaCEP (o cache responde na hora)
                if resultado['Status_Busca'] == "Sucesso (API)":
                    time.sleep(0.3)
                    
            # Junta os resultados no DataFrame original
            df_resultados = pd.DataFrame(resultados)
            df_final = pd.concat([df, df_resultados], axis=1)
            
            st.success("Processamento concluído!")
            st.dataframe(df_final.head())
            
            # 4. Botão de Download
            csv_export = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar CSV Processado",
                data=csv_export,
                file_name="ceps_processados.csv",
                mime="text/csv",
            )