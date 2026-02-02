import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
# COLE SUA URL DO APPS SCRIPT ENTRE AS ASPAS ABAIXO:
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- 2. FERRAMENTAS DE SUPORTE ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    try:
        return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return data_str

def carregar_dados(acao):
    """Busca dados e garante que o Streamlit espere a resposta do Google"""
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=20)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição"]
escolha = st.sidebar.selectbox("Navegação", menu)

# --- 4. PÁGINA: LANÇAR MEDIÇÃO (COM BUSCA DE PERCENTUAL ANTERIOR) ---
if escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    
    # Carregamos tudo antes de mostrar a tela
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        lista_ctts = df_c['ctt'].tolist()
        ctt_sel = st.selectbox("1. Selecione o Contrato", lista_ctts)
        id_ctt = df_c[df_c['ctt'] == ctt_sel]['contract_id'].values[0]
        
        itens_filtrados = df_i[df_i['contract_id'] == id_ctt]
        
        if not itens_filtrados.empty:
            item_sel = st.selectbox("2. Selecione o Item para Medir", itens_filtrados['descricao_item'].tolist())
            row_i = itens_filtrados[itens_filtrados['descricao_item'] == item_sel].iloc[0]
            item_id_atual = row_i['item_id']

            # --- BUSCA DO PERCENTUAL ANTERIOR ---
            perc_anterior = 0.0
            if not df_m.empty:
                # Procura a última medição desse item específico
                med_historico = df_m[df_m['item_id'] == item_id_atual]
                if not med_historico.empty:
                    # Pegamos o valor da última linha registrada
                    perc_anterior = float(med_historico.iloc[-1]['percentual_acumulado'])

            with st.form("f_med_inteligente"):
                st.write(f"📈 **Progresso Atual:** {perc_anterior*100:.2f}%")
                
                # O slider inicia onde a última medição parou
                p = st.slider("Ajustar Novo Percentual Acumulado (%)", 0, 100, int(perc_anterior * 100)) / 100
                
                v_calc = p * float(row_i['vlr_unit'])
                st.info(f"Novo valor acumulado: {formatar_real(v_calc)}")
                
                dt = st.date_input("Data desta Medição")
                fase = st.selectbox("Status", ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado"])
                
                # BOTÃO DE SALVAR (OBRIGATÓRIO DENTRO DO FORM)
                if st.form_submit_button("✅ Registrar Medição"):
                    if p < perc_anterior:
                        st.warning("Atenção: Você está tentando lançar um percentual menor que o já medido.")
                    
                    salvar_dados("measurements", {
                        "measurement_id": str(uuid.uuid4()), 
                        "item_id": item_id_atual, 
                        "data_medicao": str(dt), 
                        "percentual_acumulado": p, 
                        "valor_acumulado": v_calc, 
                        "fase_workflow": fase, 
                        "updated_at": str(datetime.now())
                    })
                    st.success("Medição registrada com sucesso!")
                    st.rerun()
        else:
            st.warning("Nenhum item cadastrado para este contrato.")
    else:
        st.error("Nenhum contrato encontrado. Verifique sua planilha ou a URL do Apps Script.")

# --- MANTEMOS O DASHBOARD PARA NÃO DAR ERRO ---
elif escolha == "Dashboard":
    st.title("📊 Dashboard")
    df_c = carregar_dados("get_contracts")
    df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        t_con = pd.to_numeric(df_c['valor_contrato']).sum()
        t_med = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        c1, c2 = st.columns(2)
        c1.metric("Total Contratado", formatar_real(t_con))
        c2.metric("Total Medido", formatar_real(t_med))
        st.divider()
        st.dataframe(df_c)

# --- PÁGINAS DE SUPORTE ---
elif escolha == "Contratos":
    st.title("📄 Contratos")
    with st.form("f_con"):
        c1, c2 = st.columns(2)
        ctt = c1.text_input("Número CTT")
        forn = c2.text_input("Fornecedor")
        gest = c1.text_input("Gestor")
        vlr = c2.number_input("Valor", min_value=0.0)
        dt_i = st.date_input("Início")
        dt_f = st.date_input("Fim")
        if st.form_submit_button("Salvar"):
            salvar_dados("contracts", {"contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "gestor": gest, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f)})
            st.rerun()

elif escolha == "Itens":
    st.title("🏗️ Itens")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel = st.selectbox("Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
        with st.form("f_item"):
            d = st.text_input("Descrição")
            v = st.number_input("Valor Unitário", min_value=0.0)
            if st.form_submit_button("Adicionar"):
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_c, "descricao_item": d, "vlr_unit": v})
                st.rerun()
