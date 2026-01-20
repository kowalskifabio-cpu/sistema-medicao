import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
# ATENÇÃO: Substitua a URL abaixo pela sua URL do Google Apps Script (Passo 2 item 9)
URL_DO_APPS_SCRIPT = "SUA_URL_DO_GOOGLE_SCRIPT_AQUI"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição", layout="wide")

# --- 2. FUNÇÕES DE SUPORTE (FORMATAÇÃO E DADOS) ---

def formatar_real(valor):
    """Transforma números no formato brasileiro: R$ 4.330,11"""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def carregar_dados(acao):
    """Busca dados da planilha via API do Apps Script"""
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        return pd.DataFrame(r.json())
    except:
        return pd.DataFrame()

def salvar_dados(tabela, dados):
    """Envia novos dados para serem salvos na planilha"""
    payload = {"token": TOKEN, "table": tabela, "data": dados}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. LÓGICA DAS PÁGINAS ---

# PÁGINA: DASHBOARD
if escolha == "Dashboard":
    st.title("📊 Painel de Controle de Medições")
    df_m = carregar_dados("get_measurements")
    df_c = carregar_dados("get_contracts")
    
    col1, col2, col3 = st.columns(3)
    
    if not df_c.empty:
        total_c = pd.to_numeric(df_c['valor_contrato']).sum()
        col1.metric("Total Contratado", formatar_real(total_c))
        
        if not df_m.empty:
            total_m = pd.to_numeric(df_m['valor_acumulado']).sum()
            col2.metric("Total Medido", formatar_real(total_m))
            col3.metric("Saldo a Medir", formatar_real(total_c - total_m))
            
            st.subheader("Resumo das Medições")
            df_m_view = df_m.copy()
            df_m_view['valor_acumulado'] = df_m_view['valor_acumulado'].apply(formatar_real)
            st.dataframe(df_m_view, use_container_width=True)
    else:
        st.info("Cadastre contratos para visualizar o dashboard.")

# PÁGINA: CONTRATOS
elif escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("➕ Cadastrar Novo Contrato"):
        with st.form("form_novo_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT / Código")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            vlr = c2.number_input("Valor Total do Contrato", min_value=0.0, step=0.01, format="%.2f")
            if st.form_submit_button("Salvar Contrato"):
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn,
                    "obra": obra, "valor_contrato": vlr, "status": "Ativo",
                    "data_inicio": str(datetime.now().date())
                })
                st.success("Contrato cadastrado!")
                st.rerun()
    
    st.subheader("Lista de Contratos")
    st.dataframe(carregar_dados("get_contracts"), use_container_width=True)

# PÁGINA: ITENS (COM EDIÇÃO)
elif escolha == "Itens":
    st.title("🏗️ Itens por Contrato")
    df_c = carregar_dados("get_contracts")
    
    if not df_c.empty:
        escolha_ctt = st.selectbox("Selecione o Contrato para Gerenciar Itens", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == escolha_ctt]['contract_id'].values[0]
        
        with st.expander("➕ Adicionar Novo Item a este Contrato"):
            with st.form("form_add_item"):
                desc_i = st.text_input("Descrição do Item")
                vlr_u = st.number_input("Valor Unitário (R$)", min_value=0.0, step=0.01, format="%.2f")
                if st.form_submit_button("Adicionar Item"):
                    salvar_dados("items", {
                        "item_id": str(uuid.uuid4()), "contract_id": id_ctt,
                        "descricao_item": desc_i, "vlr_unit": vlr_u
                    })
                    st.success("Item adicionado!")
                    st.rerun()

        st.subheader("Itens Registrados")
        df_i = carregar_dados("get_items")
        if not df_i.empty:
            itens_filtrados = df_i[df_i['contract_id'] == id_ctt]
            for _, row in itens_filtrados.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    novo_desc = c1.text_input("Descrição", value=row['descricao_item'], key=f"d_{row['item_id']}")
                    novo_vlr = c2.number_input("Valor Unit.", value=float(row['vlr_unit']), key=f"v_{row['item_id']}")
                    if c3.button("💾 Salvar", key=f"b_{row['item_id']}"):
                        payload = {
                            "token": TOKEN, "action": "update", "table": "items",
                            "id_field": "item_id", "id_value": row['item_id'],
                            "data": {"descricao_item": novo_desc, "vlr_unit": novo_vlr}
                        }
                        requests.post(URL_DO_APPS_SCRIPT, json=payload)
                        st.rerun()
    else:
        st.warning("Cadastre um contrato primeiro.")

# PÁGINA: LANÇAR MEDIÇÃO (COM FILTRO MÃE)
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    
    if not df_c.empty:
        # SELEÇÃO MÃE
        lista_ctts = df_c['ctt'].tolist()
        ctt_mae = st.selectbox("Selecione o Contrato (Filtro)", lista_ctts)
        id_mae = df_c[df_c['ctt'] == ctt_mae]['contract_id'].values[0]
        
        if not df_i.empty:
            itens_da_mae = df_i[df_i['contract_id'] == id_mae]
            if not itens_da_mae.empty:
                itens_da_mae['display'] = itens_da_mae.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
                item_sel = st.selectbox("Selecione o Item para Medir", itens_da_mae['display'].tolist())
                row_item = itens_da_mae[itens_da_mae['display'] == item_sel].iloc[0]
                
                with st.form("form_medir"):
                    v_unit = float(row_item['vlr_unit'])
                    perc = st.slider("Percentual Executado (%)", 0, 100, step=1) / 100
                    v_calc = perc * v_unit
                    st.info(f"Valor Calculado: {formatar_real(v_calc)}")
                    
                    fase = st.selectbox("Status da Medição", ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado", "Pago"])
                    obs = st.text_area("Notas Adicionais")
                    
                    if st.form_submit_button("Registrar Medição"):
                        salvar_dados("measurements", {
                            "measurement_id": str(uuid.uuid4()), "item_id": row_item['item_id'],
                            "data_medicao": str(datetime.now().date()), "percentual_acumulado": perc,
                            "valor_acumulado": v_calc, "fase_workflow": fase, 
                            "updated_at": str(datetime.now()), "observacao": obs
                        })
                        st.success("Medição registrada com sucesso!")
            else:
                st.warning("Nenhum item cadastrado para este contrato.")
    else:
        st.error("Cadastre contratos e itens antes de medir.")

# PÁGINA: KANBAN
elif escolha == "Kanban":
    st.title("📋 Quadro de Acompanhamento")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    
    if not df_m.empty and not df_i.empty:
        fases = ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado"]
        cols = st.columns(len(fases))
        for i, f in enumerate(fases):
            with cols[i]:
                st.markdown(f"### {f}")
                cards = df_m[df_m['fase_workflow'] == f]
                for _, card in cards.iterrows():
                    item_info = df_i[df_i['item_id'] == card['item_id']]
                    nome = item_info['descricao_item'].values[0] if not item_info.empty else "Item não encontrado"
                    with st.container(border=True):
                        st.write(f"**{nome}**")
                        st.caption(f"Progresso: {float(card['percentual_acumulado'])*100:.0f}%")
                        st.write(formatar_real(card['valor_acumulado']))
                        # Regra de 3 dias parado
                        dt_up = pd.to_datetime(card['updated_at'])
                        if (datetime.now() - dt_up).days > 3:
                            st.error("🚨 PARADO +3 DIAS")
