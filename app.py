import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- CONFIGURAÇÃO ---
# COLE AQUI O LINK QUE VOCÊ COPIOU NO PASSO 2 ENTRE AS ASPAS:
URL_DO_APPS_SCRIPT = "COLE_AQUI_A_URL_DO_PASSO_2_ITEM_9"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Medição Full-Stack", layout="wide")

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        return pd.DataFrame(r.json())
    except:
        return pd.DataFrame()

def salvar_dados(tabela, dados):
    payload = {"token": TOKEN, "table": tabela, "data": dados}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- MENU ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Menu", menu)

if escolha == "Contratos":
    st.title("Gestão de Contratos")
    with st.form("Cadastrar Contrato"):
        c1, c2 = st.columns(2)
        ctt = c1.text_input("Número CTT")
        fornecedor = c2.text_input("Fornecedor")
        obra = c1.text_input("Obra")
        valor = c2.number_input("Valor do Contrato", min_value=0.0)
        if st.form_submit_button("Salvar Contrato"):
            info = {
                "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": fornecedor,
                "obra": obra, "valor_contrato": valor, "status": "Ativo", "data_inicio": str(datetime.now().date())
            }
            salvar_dados("contracts", info)
            st.success("Contrato cadastrado!")
    
    st.subheader("Contratos Atuais")
    st.dataframe(carregar_dados("get_contracts"))

elif escolha == "Dashboard":
    st.title("Dashboard de Medição")
    df_c = carregar_dados("get_contracts")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        total = pd.to_numeric(df_c['valor_contrato']).sum()
        st.metric("Total Contratado", f"R$ {total:,.2f}")
    
    if not df_m.empty:
        st.write("Histórico de Medições")
        st.dataframe(df_m)
    else:
        st.info("Nenhuma medição encontrada.")

# (As outras páginas podem ser adicionadas conforme você se sentir confortável)
