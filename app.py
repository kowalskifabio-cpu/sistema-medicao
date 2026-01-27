import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
# COLE AQUI O LINK QUE VOCÊ COPIOU NO PASSO 1:
URL_DO_APPS_SCRIPT = "SUA_NOVA_URL_AQUI"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição Pro", layout="wide")

# --- 2. FERRAMENTAS ---
def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    try:
        return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return data_str

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=10)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except: return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição"]
escolha = st.sidebar.selectbox("Navegação", menu)

# --- 4. DASHBOARD (COM TOTAIS E FINANCEIRO) ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # Totais Gerais no Topo
        t_con = pd.to_numeric(df_c['valor_contrato']).sum()
        t_med = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(t_con))
        m2.metric("Total Medido (Bruto)", formatar_real(t_med))
        m3.metric("Saldo a Medir", formatar_real(t_con - t_med))
        
        st.divider()
        gestores = ["Todos"] + sorted(df_c['gestor'].unique().tolist())
        gestor_sel = st.selectbox("Filtrar por Gestor", gestores)
        
        df_f = df_c if gestor_sel == "Todos" else df_c[df_c['gestor'] == gestor_sel]

        for _, con in df_f.iterrows():
            cid = con['contract_id']
            # Filtro financeiro por contrato
            med_ctt = df_m[df_m['item_id'].isin(df_i[df_i['contract_id']==cid]['item_id'])] if not df_m.empty else pd.DataFrame()
            v_bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            v_ret = v_bruto * 0.15 # Retenção de 15% conforme solicitado
            v_liq = v_bruto - v_ret
            
            with st.container(border=True):
                st.subheader(f"📄 {con['ctt']} - {con['fornecedor']}")
                f1, f2, f3 = st.columns(3)
                f1.metric("Bruto Medido", formatar_real(v_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(v_ret)}", delta_color="inverse")
                f3.metric("Líquido a Pagar", formatar_real(v_liq))
                
                if st.button(f"🔍 Ver Detalhes {con['ctt']}", key=f"btn_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        # Tabela detalhada conforme Anexo I
                        st.write(f"**Início:** {formatar_data_br(con['data_inicio'])} | **Fim:** {formatar_data_br(con['data_fim'])}")
                        st.table(med_ctt[['data_medicao', 'fase_workflow', 'percentual_acumulado', 'valor_acumulado']])
                    else:
                        st.info("Nenhuma medição para este contrato.")
    else:
        st.warning("Não foi possível carregar dados. Verifique a URL do seu Apps Script.")

# --- PÁGINAS DE CADASTRO (COM BOTÃO DE SUBMIT CORRIGIDO) ---
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.form("form_con"):
        c1, c2 = st.columns(2)
        ctt = c1.text_input("Número CTT")
        forn = c2.text_input("Fornecedor")
        gest = c1.text_input("Gestor")
        vlr = c2.number_input("Valor Total", min_value=0.0)
        d1, d2 = st.columns(2)
        dt_i = d1.date_input("Início")
        dt_f = d2.date_input("Fim")
        if st.form_submit_button("Salvar Contrato"):
            salvar_dados("contracts", {"contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "gestor": gest, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f)})
            st.success("Salvo!")
            st.rerun()

elif escolha == "Itens":
    st.title("🏗️ Cadastro de Itens")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel = st.selectbox("Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
        with st.form("form_item"):
            desc = st.text_input("Descrição do Item")
            v_u = st.number_input("Valor Unitário", min_value=0.0)
            if st.form_submit_button("Adicionar"):
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_c, "descricao_item": desc, "vlr_unit": v_u})
                st.success("Adicionado!")
                st.rerun()

elif escolha == "Lançar Medição":
    st.title("📏 Lançamento")
    df_i = carregar_dados("get_items")
    if not df_i.empty:
        sel_i = st.selectbox("Item", df_i['descricao_item'].tolist())
        row = df_i[df_i['descricao_item'] == sel_i].iloc[0]
        with st.form("form_med"):
            p = st.slider("%", 0, 100) / 100
            dt = st.date_input("Data")
            if st.form_submit_button("Lançar"):
                salvar_dados("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * float(row['vlr_unit']), "fase_workflow": "Medição lançada", "updated_at": str(datetime.now())})
                st.success("Lançado!")
                st.rerun()
