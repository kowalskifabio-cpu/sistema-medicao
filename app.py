import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- 2. FERRAMENTAS DE SUPORTE ---

def formatar_real(valor):
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=15)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição"]
escolha = st.sidebar.selectbox("Navegação", menu)

# --- PÁGINA: LANÇAR MEDIÇÃO (CORRIGIDA) ---
if escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements") # Buscamos o histórico para saber o valor anterior
    
    if not df_c.empty:
        lista_ctts = df_c['ctt'].tolist()
        ctt_sel = st.selectbox("1. Selecione o Contrato", lista_ctts)
        id_ctt = df_c[df_c['ctt'] == ctt_sel]['contract_id'].values[0]
        
        itens_filtrados = df_i[df_i['contract_id'] == id_ctt]
        
        if not itens_filtrados.empty:
            item_sel = st.selectbox("2. Selecione o Item para Medir", itens_filtrados['descricao_item'].tolist())
            row_i = itens_filtrados[itens_filtrados['descricao_item'] == item_sel].iloc[0]
            item_id_atual = row_i['item_id']

            # --- MÁGICA PARA TRAZER O ÚLTIMO PERCENTUAL ---
            perc_anterior = 0.0
            if not df_m.empty:
                # Procura todas as medições desse item e pega a mais recente (a última da lista)
                med_item = df_m[df_m['item_id'] == item_id_atual]
                if not med_item.empty:
                    # Pegamos o valor da última linha da coluna percentual_acumulado
                    perc_anterior = float(med_item.iloc[-1]['percentual_acumulado'])

            with st.form("form_medicao_inteligente"):
                st.write(f"📊 **Progresso atual registrado:** {perc_anterior*100:.2f}%")
                
                # O slider agora começa no valor que já foi medido antes!
                p = st.slider("Novo Percentual Acumulado (%)", 0, 100, int(perc_anterior * 100)) / 100
                
                v_calc = p * float(row_i['vlr_unit'])
                st.info(f"Valor total acumulado após este lançamento: {formatar_real(v_calc)}")
                
                dt = st.date_input("Data da Medição")
                fase = st.selectbox("Fase", ["Em execução", "Aprovado", "Faturado"])
                
                if st.form_submit_button("Registrar Nova Medição"):
                    if p < perc_anterior:
                        st.error("O novo percentual não pode ser menor que o anterior!")
                    else:
                        salvar_dados("measurements", {
                            "measurement_id": str(uuid.uuid4()), "item_id": item_id_atual, 
                            "data_medicao": str(dt), "percentual_acumulado": p, 
                            "valor_acumulado": v_calc, "fase_workflow": fase, "updated_at": str(datetime.now())
                        })
                        st.success("Medição atualizada com sucesso!")
                        st.rerun()
        else:
            st.warning("Sem itens neste contrato.")
    else:
        st.error("Sem contratos cadastrados.")

# --- MANTENHA AS OUTRAS PÁGINAS (DASHBOARD, CONTRATOS, ITENS) IGUAIS À VERSÃO ANTERIOR ---
elif escolha == "Dashboard":
    st.title("📊 Painel de Controle")
    # (Copie a lógica do Dashboard da resposta anterior aqui)
           
