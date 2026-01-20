import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- CONFIGURAÇÃO ---
# LEMBRE-SE DE COLAR SUA URL ABAIXO ENTRE AS ASPAS
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição", layout="wide")

# Função para converter números para o formato R$ 4.330,11
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

# --- MENU LATERAL ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Navegação", menu)

# --- PÁGINA: DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Indicadores Gerais")
    df_m = carregar_dados("get_measurements")
    df_c = carregar_dados("get_contracts")
    
    col1, col2, col3 = st.columns(3)
    if not df_c.empty:
        total_c = pd.to_numeric(df_c['valor_contrato']).sum()
        col1.metric("Total Contratado", formatar_real(total_c))
    
    if not df_m.empty:
        total_m = pd.to_numeric(df_m['valor_acumulado']).sum()
        col2.metric("Total Medido", formatar_real(total_m))
        if not df_c.empty:
            col3.metric("Saldo a Medir", formatar_real(total_c - total_m))

# --- PÁGINA: CONTRATOS ---
elif escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("Cadastrar Novo Contrato"):
        with st.form("form_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT")
            forn = c2.text_input("Fornecedor")
            vlr = st.number_input("Valor Total (R$)", min_value=0.0, format="%.2f")
            if st.form_submit_button("Salvar"):
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn,
                    "valor_contrato": vlr, "data_inicio": str(datetime.now().date()), "status": "Ativo"
                })
                st.success("Contrato salvo!")
                st.rerun()
    st.dataframe(carregar_dados("get_contracts"))

# --- PÁGINA: ITENS ---
elif escolha == "Itens":
    st.title("🏗️ Itens do Contrato")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        escolha_ctt = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == escolha_ctt]['contract_id'].values[0]
        
        with st.expander("➕ Novo Item"):
            with st.form("n_item"):
                d = st.text_input("Descrição")
                v = st.number_input("Valor Unitário", min_value=0.0, format="%.2f")
                if st.form_submit_button("Adicionar"):
                    salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_ctt, "descricao_item": d, "vlr_unit": v})
                    st.rerun()

        df_i = carregar_dados("get_items")
        if not df_i.empty:
            itens_f = df_i[df_i['contract_id'] == id_ctt]
            for _, row in itens_f.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    n_d = c1.text_input("Descrição", value=row['descricao_item'], key=f"d_{row['item_id']}")
                    n_v = c2.number_input("Valor", value=float(row['vlr_unit']), key=f"v_{row['item_id']}")
                    if c3.button("💾 Salvar", key=f"b_{row['item_id']}"):
                        payload = {"token": TOKEN, "action": "update", "table": "items", "id_field": "item_id", "id_value": row['item_id'], "data": {"descricao_item": n_d, "vlr_unit": n_v}}
                        requests.post(URL_DO_APPS_SCRIPT, json=payload)
                        st.rerun()

# --- PÁGINA: LANÇAR MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_i = carregar_dados("get_items")
    if not df_i.empty:
        df_i['label'] = df_i.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
        item_sel = st.selectbox("Selecione o Item", df_i['label'].tolist())
        row_i = df_i[df_i['label'] == item_sel].iloc[0]
        
        with st.form("f_med"):
            perc = st.slider("Concluído (%)", 0, 100) / 100
            vlr_calc = perc * float(row_i['vlr_unit'])
            st.info(f"Valor a medir: {formatar_real(vlr_calc)}")
            fase = st.selectbox("Fase", ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado"])
            if st.form_submit_button("Lançar"):
                salvar_dados("measurements", {
                    "measurement_id": str(uuid.uuid4()), "item_id": row_i['item_id'],
                    "data_medicao": str(datetime.now().date()), "percentual_acumulado": perc,
                    "valor_acumulado": vlr_calc, "fase_workflow": fase, "updated_at": str(datetime.now())
                })
                st.success("Medição registrada!")

# --- PÁGINA: KANBAN ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    if not df_m.empty:
        fases = ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado"]
        cols = st.columns(len(fases))
        for i, f in enumerate(fases):
            with cols[i]:
                st.subheader(f)
                cards = df_m[df_m['fase_workflow'] == f]
                for _, card in cards.iterrows():
                    nome = df_i[df_i['item_id'] == card['item_id']]['descricao_item'].values[0]
                    with st.container(border=True):
                        st.write(f"**{nome}**")
                        st.write(f"Progresso: {float(card['percentual_acumulado'])*100}%")
                        st.write(formatar_real(card['valor_acumulado']))
                        if (datetime.now() - pd.to_datetime(card['updated_at'])).days > 3:
                            st.error("🚨 PARADO")
