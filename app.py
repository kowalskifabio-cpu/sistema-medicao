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
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    """Envia dados para criar, atualizar ou deletar na planilha"""
    payload = {
        "token": TOKEN, 
        "table": tabela, 
        "data": dados, 
        "action": acao,
        "id_field": id_field,
        "id_value": id_value
    }
    try:
        requests.post(URL_DO_APPS_SCRIPT, json=payload)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. LÓGICA DAS PÁGINAS ---

# PÁGINA: DASHBOARD
if escolha == "Dashboard":
    st.title("📊 Painel de Controle")
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
            st.subheader("Histórico Recente")
            st.dataframe(df_m.tail(10), use_container_width=True)
    else:
        st.info("Cadastre contratos para ver os indicadores.")

# PÁGINA: CONTRATOS
elif escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("➕ Cadastrar Novo Contrato"):
        with st.form("form_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT / Código")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            gestor = c2.text_input("Gestor Responsável")
            vlr = c2.number_input("Valor Total", min_value=0.0, format="%.2f")
            if st.form_submit_button("Salvar Contrato"):
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn,
                    "obra": obra, "gestor": gestor, "valor_contrato": vlr, 
                    "status": "Ativo", "data_inicio": str(datetime.now().date())
                })
                st.success("Contrato salvo!")
                st.rerun()
    
    st.subheader("Lista de Contratos")
    df_contratos = carregar_dados("get_contracts")
    if not df_contratos.empty:
        st.dataframe(df_contratos, use_container_width=True)

# PÁGINA: ITENS (COM EDIÇÃO E EXCLUSÃO)
elif escolha == "Itens":
    st.title("🏗️ Itens por Contrato")
    df_c = carregar_dados("get_contracts")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        escolha_ctt = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == escolha_ctt]['contract_id'].values[0]
        
        with st.expander("➕ Adicionar Novo Item"):
            with st.form("form_item"):
                d = st.text_input("Descrição do Item")
                v = st.number_input("Valor Unitário (R$)", min_value=0.0, format="%.2f")
                if st.form_submit_button("Adicionar"):
                    salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_ctt, "descricao_item": d, "vlr_unit": v})
                    st.rerun()

        st.subheader("Itens Cadastrados")
        df_i = carregar_dados("get_items")
        if not df_i.empty:
            itens_f = df_i[df_i['contract_id'] == id_ctt]
            for _, row in itens_f.iterrows():
                # Verifica se já tem medição para bloquear exclusão
                tem_medicao = False
                if not df_m.empty:
                    tem_medicao = row['item_id'] in df_m['item_id'].values

                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    n_desc = col1.text_input("Descrição", value=row['descricao_item'], key=f"d_{row['item_id']}")
                    n_vlr = col2.number_input("Valor Unit.", value=float(row['vlr_unit']), key=f"v_{row['item_id']}")
                    
                    if col3.button("💾 Salvar", key=f"s_{row['item_id']}"):
                        salvar_dados("items", {"descricao_item": n_desc, "vlr_unit": n_vlr}, acao="update", id_field="item_id", id_value=row['item_id'])
                        st.success("Atualizado!")
                        st.rerun()
                    
                    if not tem_medicao:
                        if col4.button("🗑️ Excluir", key=f"del_{row['item_id']}"):
                            salvar_dados("items", {}, acao="delete", id_field="item_id", id_value=row['item_id'])
                            st.warning("Excluído!")
                            st.rerun()
                    else:
                        col4.write("⚠️ Medido")
    else:
        st.warning("Cadastre um contrato primeiro.")

# PÁGINA: LANÇAR MEDIÇÃO
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    
    if not df_c.empty:
        ctt_mae = st.selectbox("Selecione o Contrato (Filtro)", df_c['ctt'].tolist())
        id_mae = df_c[df_c['ctt'] == ctt_mae]['contract_id'].values[0]
        
        if not df_i.empty:
            itens_f = df_i[df_i['contract_id'] == id_mae]
            if not itens_f.empty:
                itens_f['display'] = itens_f.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
                item_sel = st.selectbox("Selecione o Item", itens_f['display'].tolist())
                row_i = itens_f[itens_f['display'] == item_sel].iloc[0]
                
                with st.form("f_med"):
                    perc = st.slider("Concluído (%)", 0, 100) / 100
                    v_calc = perc * float(row_i['vlr_unit'])
                    st.info(f"Valor a medir: {formatar_real(v_calc)}")
                    fase = st.selectbox("Fase", ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado", "Pago"])
                    if st.form_submit_button("Lançar Medição"):
                        salvar_dados("measurements", {
                            "measurement_id": str(uuid.uuid4()), "item_id": row_i['item_id'],
                            "data_medicao": str(datetime.now().date()), "percentual_acumulado": perc,
                            "valor_acumulado": v_calc, "fase_workflow": fase, "updated_at": str(datetime.now())
                        })
                        st.success("Medição registrada!")
            else:
                st.warning("Este contrato não tem itens.")

# PÁGINA: KANBAN
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    if not df_m.empty and not df_i.empty:
        fases = ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado"]
        cols = st.columns(len(fases))
        for i, f in enumerate(fases):
            with cols[i]:
                st.subheader(f)
                cards = df_m[df_m['fase_workflow'] == f]
                for _, card in cards.iterrows():
                    nome_item = df_i[df_i['item_id'] == card['item_id']]['descricao_item'].values[0]
                    with st.container(border=True):
                        st.write(f"**{nome_item}**")
                        st.write(f"Progresso: {float(card['percentual_acumulado'])*100:.0f}%")
                        st.write(formatar_real(card['valor_acumulado']))
                        if (datetime.now() - pd.to_datetime(card['updated_at'])).days > 3:
                            st.error("🚨 PARADO")
