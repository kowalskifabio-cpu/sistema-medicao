import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
# ATENÇÃO: Substitua a URL abaixo pela sua URL do Google Apps Script
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição", layout="wide")

# --- 2. FUNÇÕES DE SUPORTE ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        return pd.DataFrame(r.json())
    except:
        return pd.DataFrame()

def salvar_dados(tabela, dados):
    payload = {"token": TOKEN, "table": tabela, "data": dados}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. LÓGICA DAS PÁGINAS ---

if escolha == "Dashboard":
    st.title("📊 Painel de Controle")
    df_m = carregar_dados("get_measurements")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        total_c = pd.to_numeric(df_c['valor_contrato']).sum()
        st.metric("Total Contratado", formatar_real(total_c))
        if not df_m.empty:
            st.dataframe(df_m, use_container_width=True)

elif escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("➕ Cadastrar Novo Contrato"):
        with st.form("form_novo_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT / Código")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            # --- NOVO CAMPO ADICIONADO ABAIXO ---
            gestor = c2.text_input("Gestor Responsável") 
            vlr = c2.number_input("Valor Total do Contrato", min_value=0.0, step=0.01, format="%.2f")
            
            if st.form_submit_button("Salvar Contrato"):
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), 
                    "ctt": ctt, 
                    "fornecedor": forn,
                    "obra": obra, 
                    "gestor": gestor, # Enviando o gestor para a planilha
                    "valor_contrato": vlr, 
                    "status": "Ativo",
                    "data_inicio": str(datetime.now().date())
                })
                st.success(f"Contrato salvo! Gestor {gestor} registrado.")
                st.rerun()
    
    st.subheader("Lista de Contratos")
    df_contratos = carregar_dados("get_contracts")
    if not df_contratos.empty:
        # Reorganizando colunas para o Gestor aparecer na frente
        colunas_ordem = ['ctt', 'fornecedor', 'gestor', 'obra', 'valor_contrato', 'status']
        # Só exibe as colunas que existirem na planilha
        cols_existentes = [c for c in colunas_ordem if c in df_contratos.columns]
        st.dataframe(df_contratos[cols_existentes], use_container_width=True)

elif escolha == "Itens":
    st.title("🏗️ Itens por Contrato")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        # Aqui o gestor aparece na seleção para facilitar
        df_c['display'] = df_c['ctt'] + " - " + df_c['fornecedor']
        escolha_ctt = st.selectbox("Selecione o Contrato", df_c['display'].tolist())
        id_ctt = df_c[df_c['display'] == escolha_ctt]['contract_id'].values[0]
        
        with st.expander("➕ Adicionar Novo Item"):
            with st.form("form_add_item"):
                desc_i = st.text_input("Descrição do Item")
                vlr_u = st.number_input("Valor Unitário (R$)", min_value=0.0, format="%.2f")
                if st.form_submit_button("Adicionar"):
                    salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_ctt, "descricao_item": desc_i, "vlr_unit": vlr_u})
                    st.rerun()

        df_i = carregar_dados("get_items")
        if not df_i.empty:
            itens_f = df_i[df_i['contract_id'] == id_ctt]
            st.dataframe(itens_f[['descricao_item', 'vlr_unit']], use_container_width=True)

elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    # (Mantém a lógica de filtro mãe por contrato já criada anteriormente)
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        ctt_mae = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        # ... (resto do código de medição)

elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    # (Mantém a lógica do Kanban já criada anteriormente)
