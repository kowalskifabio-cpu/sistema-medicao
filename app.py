import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- 2. FERRAMENTAS ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    if pd.isna(data_str) or data_str == "": return "-"
    try: return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return str(data_str)

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=15)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. PÁGINA: ITENS (COM EDIÇÃO E EXCLUSÃO) ---
if escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements") # Carregar medições para validar exclusão
    
    if not df_c.empty:
        sel_ctt = st.selectbox("Escolha o Contrato", df_c['ctt'].tolist())
        row_ctt = df_c[df_c['ctt'] == sel_ctt].iloc[0]
        
        with st.expander("➕ Adicionar Novo Item"):
            with st.form("f_item"):
                c1, c2 = st.columns([2,1])
                desc = c1.text_input("Descrição do Item")
                v_u = c2.number_input("Valor Unitário (R$)", min_value=0.0, format="%.2f")
                dt_fim_default = pd.to_datetime(row_ctt['data_fim']).date()
                dt_item = st.date_input("Prazo do Item", dt_fim_default, format="DD/MM/YYYY")
                
                if st.form_submit_button("Salvar Novo Item"):
                    salvar_dados("items", {
                        "item_id": str(uuid.uuid4()), "contract_id": row_ctt['contract_id'], 
                        "descricao_item": desc, "vlr_unit": v_u, "data_fim_item": str(dt_item)
                    })
                    st.success("Item adicionado!")
                    st.rerun()
        
        st.divider()
        st.subheader(f"Lista de Itens - {sel_ctt}")
        
        if not df_i.empty:
            itens_ctt = df_i[df_i['contract_id'] == row_ctt['contract_id']].copy()
            
            busca = st.text_input("🔍 Pesquisar item...")
            if busca:
                itens_ctt = itens_ctt[itens_ctt['descricao_item'].str.contains(busca, case=False)]

            for index, item in itens_ctt.iterrows():
                # Verifica se o item já tem medição
                tem_medicao = False
                if not df_m.empty:
                    tem_medicao = item['item_id'] in df_m['item_id'].values

                with st.container(border=True):
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                    
                    # Campos de edição
                    nova_desc = col1.text_input("Descrição", value=item['descricao_item'], key=f"desc_{item['item_id']}")
                    novo_vlr = col2.number_input("Valor Unit.", value=float(item['vlr_unit']), key=f"vlr_{item['item_id']}")
                    
                    col3.write(f"**Prazo:**\n{formatar_data_br(item.get('data_fim_item', ''))}")
                    
                    # Botão Salvar Edição
                    if col4.button("💾", key=f"save_{item['item_id']}", help="Salvar alterações"):
                        salvar_dados("items", 
                                     {"descricao_item": nova_desc, "vlr_unit": novo_vlr}, 
                                     acao="update", id_field="item_id", id_value=item['item_id'])
                        st.toast("Item atualizado!")
                        st.rerun()
                    
                    # Botão Excluir (Bloqueado se houver medição)
                    if not tem_medicao:
                        if col5.button("🗑️", key=f"del_{item['item_id']}", help="Excluir item"):
                            salvar_dados("items", {}, acao="delete", id_field="item_id", id_value=item['item_id'])
                            st.warning("Item excluído!")
                            st.rerun()
                    else:
                        col5.write("⚠️ Medido")

# --- AS OUTRAS PÁGINAS CONTINUAM IGUAIS ---
# (Manter os blocos Dashboard, Lançar Medição, Kanban e Contratos do script anterior)
elif escolha == "Dashboard":
    # ... código do dashboard mantido ...
    st.title("📊 Painel de Controle e Cronograma")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    # (Copie o resto do código do dashboard aqui para completar o arquivo)

elif escolha == "Lançar Medição":
    # ... código de medição mantido ...
    st.title("📏 Lançamento de Medição")
    # (Copie o resto do código de medição aqui)

elif escolha == "Kanban":
    # ... código do kanban mantido ...
    st.title("📋 Quadro Kanban")
    # (Copie o resto do código do kanban aqui)

elif escolha == "Contratos":
    # ... código de contratos mantido ...
    st.title("📄 Cadastro de Contratos")
    # (Copie o resto do código de contratos aqui)
