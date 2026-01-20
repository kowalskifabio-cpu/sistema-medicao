import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
# SUBSTITUA PELA SUA URL DO GOOGLE APPS SCRIPT
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição Pro", layout="wide")

# --- 2. FUNÇÕES DE TRADUÇÃO (MOEDA E DATA BR) ---

def formatar_real(valor):
    """Exemplo: 4330.11 -> R$ 4.330,11"""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def formatar_data_br(data_str):
    """Exemplo: 2026-01-20 -> 20/01/2026"""
    try:
        # Se vier do Google Sheets como texto de data ISO
        dt = pd.to_datetime(data_str)
        return dt.strftime('%d/%m/%Y')
    except:
        return data_str

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        return pd.DataFrame(r.json())
    except:
        return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. LÓGICA DAS PÁGINAS ---

# PÁGINA: DASHBOARD (COM RELATÓRIO POR CONTRATO)
if escolha == "Dashboard":
    st.title("📊 Painel de Controle de Medições")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # Resumo Geral no Topo
        total_contratado = pd.to_numeric(df_c['valor_contrato']).sum()
        total_medido = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Contratado", formatar_real(total_contratado))
        c2.metric("Total Medido", formatar_real(total_medido))
        c3.metric("Saldo a Medir", formatar_real(total_contratado - total_medido))
        
        st.divider()
        st.subheader("📋 Resumo por Contrato")
        
        for _, contrato in df_c.iterrows():
            cid = contrato['contract_id']
            # Filtros de segurança
            itens_ctt = df_i[df_i['contract_id'] == cid] if not df_i.empty else pd.DataFrame()
            ids_itens = itens_ctt['item_id'].tolist() if not itens_ctt.empty else []
            med_ctt = df_m[df_m['item_id'].isin(ids_itens)] if not df_m.empty else pd.DataFrame()
            
            soma_medido = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            vlr_total = float(contrato['valor_contrato'])
            
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                col1.markdown(f"**Contrato:** {contrato['ctt']}  \n**Gestor:** {contrato['gestor']}  \n**Fornecedor:** {contrato['fornecedor']}")
                col2.write(f"**Valor do Contrato** \n{formatar_real(vlr_total)}")
                col3.write(f"**Total Medido** \n{formatar_real(soma_medido)}")
                col4.write(f"**Saldo a Medir** \n{formatar_real(vlr_total - soma_medido)}")
                
                if st.button(f"📄 Gerar Detalhamento {contrato['ctt']}", key=f"btn_{cid}"):
                    st.info(f"Relatório do Contrato {contrato['ctt']}")
                    if not med_ctt.empty:
                        # Unindo dados para o relatório
                        rel = med_ctt.merge(itens_ctt[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Data'] = rel['data_medicao'].apply(formatar_data_br)
                        rel['Valor Unitário'] = rel['vlr_unit'].apply(formatar_real)
                        rel['% Acumulado'] = rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%")
                        rel['Medição Acumulada R$'] = rel['valor_acumulado'].apply(formatar_real)
                        
                        # Cálculo de Saldo por Item
                        rel['Saldo a Medir'] = rel.apply(lambda x: formatar_real(float(x['vlr_unit']) - float(x['valor_acumulado'])), axis=1)
                        
                        st.table(rel[['descricao_item', 'Valor Unitário', 'Data', '% Acumulado', 'Medição Acumulada R$', 'Saldo a Medir']])
                        st.caption(f"Período: {formatar_data_br(contrato['data_inicio'])} até {formatar_data_br(med_ctt['data_medicao'].max())}")
                    else:
                        st.warning("Nenhuma medição encontrada para este contrato.")

# PÁGINA: CONTRATOS (COM DATAS BR)
elif escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("➕ Cadastrar Novo Contrato"):
        with st.form("f_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT / Código")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            gest = c2.text_input("Gestor Responsável")
            vlr = c1.number_input("Valor Total", min_value=0.0, format="%.2f")
            
            d1, d2 = st.columns(2)
            dt_i = d1.date_input("Data Inicial", format="DD/MM/YYYY")
            dt_f = d2.date_input("Data Final (Prazo)", format="DD/MM/YYYY")
            
            if st.form_submit_button("Salvar Contrato"):
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn,
                    "obra": obra, "gestor": gest, "valor_contrato": vlr, 
                    "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"
                })
                st.success("Contrato salvo!")
                st.rerun()
    
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        df_c_exibicao = df_c.copy()
        df_c_exibicao['data_inicio'] = df_c_exibicao['data_inicio'].apply(formatar_data_br)
        df_c_exibicao['data_fim'] = df_c_exibicao['data_fim'].apply(formatar_data_br)
        df_c_exibicao['valor_contrato'] = df_c_exibicao['valor_contrato'].apply(formatar_real)
        st.dataframe(df_c_exibicao[['ctt', 'fornecedor', 'gestor', 'data_inicio', 'data_fim', 'valor_contrato']], use_container_width=True)

# PÁGINA: ITENS (COM FILTRO MÃE)
elif escolha == "Itens":
    st.title("🏗️ Itens por Contrato")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        ctt_sel = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == ctt_sel]['contract_id'].values[0]
        
        with st.expander("➕ Novo Item"):
            with st.form("f_item"):
                desc = st.text_input("Descrição do Item")
                vlr_u = st.number_input("Valor Unitário", min_value=0.0, format="%.2f")
                if st.form_submit_button("Adicionar"):
                    salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_ctt, "descricao_item": desc, "vlr_unit": vlr_u})
                    st.rerun()
        
        df_i = carregar_dados("get_items")
        if not df_i.empty:
            itens_f = df_i[df_i['contract_id'] == id_ctt].copy()
            itens_f['vlr_unit'] = itens_f['vlr_unit'].apply(formatar_real)
            st.dataframe(itens_f[['descricao_item', 'vlr_unit']], use_container_width=True)

# PÁGINA: LANÇAR MEDIÇÃO
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    if not df_c.empty and not df_i.empty:
        ctt_mae = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_mae = df_c[df_c['ctt'] == ctt_mae]['contract_id'].values[0]
        
        itens_f = df_i[df_i['contract_id'] == id_mae].copy()
        if not itens_f.empty:
            itens_f['label'] = itens_f.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
            item_sel = st.selectbox("Selecione o Item", itens_f['label'].tolist())
            row_i = itens_f[itens_f['label'] == item_sel].iloc[0]
            
            with st.form("f_med"):
                perc = st.slider("Concluído (%)", 0, 100) / 100
                vlr_calc = perc * float(row_i['vlr_unit'])
                st.info(f"Valor a medir: {formatar_real(vlr_calc)}")
                dt_med = st.date_input("Data da Medição", format="DD/MM/YYYY")
                fase = st.selectbox("Status", ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado", "Faturado", "Pago"])
                if st.form_submit_button("Lançar"):
                    salvar_dados("measurements", {
                        "measurement_id": str(uuid.uuid4()), "item_id": row_i['item_id'],
                        "data_medicao": str(dt_med), "percentual_acumulado": perc,
                        "valor_acumulado": vlr_calc, "fase_workflow": fase, "updated_at": str(datetime.now())
                    })
                    st.success("Medição registrada!")

# PÁGINA: KANBAN
elif escolha == "Kanban":
    st.title("📋 Kanban de Medições")
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
                    nome = df_i[df_i['item_id'] == card['item_id']]['descricao_item'].values[0]
                    with st.container(border=True):
                        st.write(f"**{nome}**")
                        st.write(f"Progresso: {float(card['percentual_acumulado'])*100:.0f}%")
                        st.write(formatar_real(card['valor_acumulado']))
                        st.caption(f"Medição: {formatar_data_br(card['data_medicao'])}")
