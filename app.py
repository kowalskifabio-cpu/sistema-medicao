import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- CONFIGURAÇÃO (COLE SUA URL ABAIXO) ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição", layout="wide")

# Funções de Comunicação
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

# --- PÁGINA: CONTRATOS ---
if escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("Cadastrar Novo Contrato"):
        with st.form("form_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            gest = c2.text_input("Gestor")
            vlr = st.number_input("Valor Total (R$)", min_value=0.0)
            if st.form_submit_button("Salvar"):
                id_c = str(uuid.uuid4())
                salvar_dados("contracts", {
                    "contract_id": id_c, "ctt": ctt, "fornecedor": forn,
                    "obra": obra, "gestor": gest, "valor_contrato": vlr,
                    "data_inicio": str(datetime.now().date()), "status": "Ativo"
                })
                st.success("Contrato salvo!")

    df_c = carregar_dados("get_contracts")
    st.dataframe(df_c)

# --- PÁGINA: ITENS (COM FORMATO BRASILEIRO) ---
elif escolha == "Itens":
    st.title("🏗️ Itens do Contrato")
    df_c = carregar_dados("get_contracts")
    
    if not df_c.empty:
        lista_ctts = df_c['ctt'].tolist()
        escolha_ctt = st.selectbox("Selecione o Contrato", lista_ctts)
        id_ctt = df_c[df_c['ctt'] == escolha_ctt]['contract_id'].values[0]

        with st.expander("➕ Cadastrar Novo Item"):
            with st.form("novo_item"):
                desc_n = st.text_input("Descrição do Item")
                # Aqui definimos o padrão brasileiro de entrada (vírgula e ponto)
                vlr_n = st.number_input("Valor Unitário (R$)", min_value=0.0, step=0.01, format="%.2f")
                if st.form_submit_button("Salvar Novo"):
                    salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_ctt, "descricao_item": desc_n, "vlr_unit": vlr_n})
                    st.success("Item criado!")
                    st.rerun()

        st.subheader("Itens Cadastrados")
        df_i = carregar_dados("get_items")
        
        if not df_i.empty:
            itens_filtrados = df_i[df_i['contract_id'] == id_ctt]
            
            for index, row in itens_filtrados.iterrows():
                # TRANSFORMANDO PARA FORMATO BR: Aqui acontece a mágica do R$ 4.330,11
                vlr_float = float(row['vlr_unit'])
                vlr_formatado = f"R$ {vlr_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    # Campo de texto para descrição
                    nova_desc = col1.text_input("Descrição", value=row['descricao_item'], key=f"desc_{row['item_id']}")
                    
                    # No campo de edição, o Streamlit usa o padrão do seu navegador
                    novo_vlr = col2.number_input(f"Valor (Era {vlr_formatado})", value=vlr_float, step=0.01, format="%.2f", key=f"vlr_{row['item_id']}")
                    
                    if col3.button("💾 Salvar", key=f"btn_{row['item_id']}"):
                        payload = {
                            "token": TOKEN, "action": "update", "table": "items",
                            "id_field": "item_id", "id_value": row['item_id'],
                            "data": {"descricao_item": nova_desc, "vlr_unit": novo_vlr}
                        }
                        requests.post(URL_DO_APPS_SCRIPT, json=payload)
                        st.success("Atualizado!")
                        st.rerun()

# --- PÁGINA: LANÇAR MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_i = carregar_dados("get_items")
    if not df_i.empty:
        item_nome = st.selectbox("Selecione o Item", df_i['descricao_item'].tolist())
        row_item = df_i[df_i['descricao_item'] == item_nome].iloc[0]
        
        with st.form("form_med"):
            perc = st.slider("Percentual Concluído (%)", 0, 100) / 100
            fase = st.selectbox("Mudar Fase", ["Planejado", "Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado", "Pago"])
            obs = st.text_area("Observações")
            if st.form_submit_button("Registrar Medição"):
                salvar_dados("measurements", {
                    "measurement_id": str(uuid.uuid4()), "item_id": row_item['item_id'],
                    "data_medicao": str(datetime.now().date()), "percentual_acumulado": perc,
                    "valor_acumulado": perc * float(row_item['vlr_unit']),
                    "fase_workflow": fase, "updated_at": str(datetime.now())
                })
                st.success("Medição registrada!")
    else:
        st.warning("Nenhum item encontrado para medir.")

# --- PÁGINA: KANBAN ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    
    if not df_m.empty:
        fases = ["Planejado", "Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado", "Pago"]
        cols = st.columns(len(fases))
        
        for i, fase in enumerate(fases):
            with cols[i]:
                st.markdown(f"**{fase}**")
                cards = df_m[df_m['fase_workflow'] == fase]
                for _, card in cards.iterrows():
                    # Buscar nome do item
                    nome_item = df_i[df_i['item_id'] == card['item_id']]['descricao_item'].values[0]
                    with st.container(border=True):
                        st.write(f"**{nome_item}**")
                        st.caption(f"Progresso: {float(card['percentual_acumulado'])*100}%")
                        # Regra PARADO (3 dias)
                        dt_up = pd.to_datetime(card['updated_at'])
                        if (datetime.now() - dt_up).days > 3:
                            st.error("🚨 PARADO")

# --- PÁGINA: DASHBOARD ---
elif escolha == "Dashboard":
    st.title("📊 Indicadores Gerais")
    df_m = carregar_dados("get_measurements")
    if not df_m.empty:
        total_medido = pd.to_numeric(df_m['valor_acumulado']).sum()
        st.metric("Total Medido Acumulado", f"R$ {total_medido:,.2f}")
        st.bar_chart(df_m.set_index('data_medicao')['valor_acumulado'])
        
        if st.button("Exportar CSV"):
            df_m.to_csv("medicoes.csv", index=False)
            st.success("Arquivo pronto!")
