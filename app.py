import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
# COLE SUA URL DO APPS SCRIPT ENTRE AS ASPAS ABAIXO:
URL_DO_APPS_SCRIPT = "SUA_URL_AQUI"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição Pro", layout="wide")

# --- 2. FERRAMENTAS DE FORMATAÇÃO E CÁLCULO ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def formatar_data_br(data_str):
    try:
        dt = pd.to_datetime(data_str)
        return dt.strftime('%d/%m/%Y')
    except:
        return data_str

def calcular_status_prazo(data_fim_contrato, data_medicao, percentual):
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim_contrato).date()
        med = pd.to_datetime(data_medicao).date()
        data_ref = med if float(percentual) >= 1 else hoje
        dif = (fim - data_ref).days
        if dif > 0: return f"{dif} dias adiantado", "🟢"
        elif dif == 0: return "No prazo", "🟡"
        else: return f"{abs(dif)} dias atrasado", "🔴"
    except:
        return "Sem dados", "⚪"

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. PÁGINA: DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle Financeiro")
    
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # TOTAIS GERAIS NO TOPO
        vlr_total_geral = pd.to_numeric(df_c['valor_contrato']).sum()
        vlr_medido_geral = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        st.subheader("Resumo Geral")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(vlr_total_geral))
        m2.metric("Total Medido", formatar_real(vlr_medido_geral))
        m3.metric("Saldo a Medir", formatar_real(vlr_total_geral - vlr_medido_geral))
        
        st.divider()

        # FILTRO POR GESTOR
        gestores = ["Todos"] + sorted(df_c['gestor'].unique().tolist())
        gestor_sel = st.selectbox("🎯 Filtrar Visão por Gestor", gestores)
        
        df_f = df_c.copy()
        if gestor_sel != "Todos":
            df_f = df_f[df_f['gestor'] == gestor_sel]

        for _, contrato in df_f.iterrows():
            cid = contrato['contract_id']
            itens_ctt = df_i[df_i['contract_id'] == cid] if not df_i.empty else pd.DataFrame()
            ids_itens = itens_ctt['item_id'].tolist() if not itens_ctt.empty else []
            med_ctt = df_m[df_m['item_id'].isin(ids_itens)] if not df_m.empty else pd.DataFrame()
            
            vlr_contrato = float(contrato['valor_contrato'])
            v_bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            v_retencao = v_bruto * 0.15
            v_liquido = v_bruto - v_retencao
            v_saldo = vlr_contrato - v_bruto

            with st.container(border=True):
                st.subheader(f"📄 {contrato['ctt']} - {contrato['fornecedor']}")
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Gestor:** {contrato['gestor']}")
                c2.write(f"**Obra:** {contrato['obra']}")
                c3.write(f"**Vlr Total:** {formatar_real(vlr_contrato)}")

                st.markdown("---")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(v_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(v_retencao)}", delta_color="inverse")
                f3.metric("Líquido a Pagar", formatar_real(v_liquido))
                f4.metric("Saldo Contrato", formatar_real(v_saldo))

                if st.button(f"🔍 Abrir Detalhamento ({contrato['ctt']})", key=f"btn_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_ctt[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(contrato['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        rel_view = pd.DataFrame({
                            'Item': rel['descricao_item'],
                            'Vlr Unitário': rel['vlr_unit'].apply(formatar_real),
                            'Medição acumulada %': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medição Acumulada R$': rel['valor_acumulado'].apply(formatar_real),
                            'Saldo a medir': rel.apply(lambda x: formatar_real(float(x['vlr_unit']) - float(x['valor_acumulado'])), axis=1),
                            'Data Inicial': formatar_data_br(contrato['data_inicio']),
                            'Data Final': rel['data_medicao'].apply(formatar_data_br),
                            'Prazo': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        })
                        st.table(rel_view)
                    else:
                        st.warning("Sem medições lançadas.")

# PÁGINA: CONTRATOS
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.expander("➕ Novo Contrato", expanded=True):
        with st.form("form_cadastro_contrato"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            gest = c2.text_input("Gestor Responsável")
            vlr = c1.number_input("Valor Total", min_value=0.0, format="%.2f")
            d1, d2 = st.columns(2)
            dt_i = d1.date_input("Início")
            dt_f = d2.date_input("Fim")
            # BOTÃO OBRIGATÓRIO DO FORMULÁRIO
            submetido = st.form_submit_button("Salvar Contrato")
            if submetido:
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, 
                    "obra": obra, "gestor": gest, "valor_contrato": vlr, 
                    "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"
                })
                st.success("Contrato salvo com sucesso!")
                st.rerun()
    st.subheader("Contratos Ativos")
    st.dataframe(carregar_dados("get_contracts"), use_container_width=True)

# PÁGINA: ITENS
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel_ctt = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel_ctt]['contract_id'].values[0]
        with st.form("form_novo_item"):
            desc = st.text_input("Descrição do Item")
            vlr_u = st.number_input("Valor Unitário", min_value=0.0, format="%.2f")
            # BOTÃO OBRIGATÓRIO DO FORMULÁRIO
            add_item = st.form_submit_button("Adicionar Item ao Contrato")
            if add_item:
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_c, "descricao_item": desc, "vlr_unit": vlr_u})
                st.success("Item adicionado!")
                st.rerun()
        st.subheader("Itens Cadastrados")
        df_itens = carregar_dados("get_items")
        if not df_itens.empty:
            st.dataframe(df_itens[df_itens['contract_id'] == id_c], use_container_width=True)

# PÁGINA: LANÇAR MEDIÇÃO
elif escolha == "Lançar Medição":
    st.title("📏 Lançar Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    if not df_c.empty:
        c_nome = st.selectbox("Escolha o Contrato", df_c['ctt'].tolist())
        id_m = df_c[df_c['ctt'] == c_nome]['contract_id'].values[0]
        itens_f = df_i[df_i['contract_id'] == id_m]
        if not itens_f.empty:
            i_nome = st.selectbox("Escolha o Item", itens_f['descricao_item'].tolist())
            row = itens_f[itens_f['descricao_item'] == i_nome].iloc[0]
            with st.form("form_lancar_medicao"):
                p = st.slider("Percentual Concluído (%)", 0, 100) / 100
                dt = st.date_input("Data da Medição")
                f = st.selectbox("Fase", ["Em execução", "Aguardando aprovação", "Aprovado"])
                # BOTÃO OBRIGATÓRIO DO FORMULÁRIO
                btn_lancar = st.form_submit_button("Registrar Medição")
                if btn_lancar:
                    salvar_dados("measurements", {
                        "measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], 
                        "data_medicao": str(dt), "percentual_acumulado": p, 
                        "valor_acumulado": p * float(row['vlr_unit']), "fase_workflow": f, 
                        "updated_at": str(datetime.now())
                    })
                    st.success("Medição registrada!")
                    st.rerun()
        else:
            st.warning("Este contrato não possui itens cadastrados.")

# PÁGINA: KANBAN
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    if not df_m.empty:
        col_fases = st.columns(3)
        fases = ["Em execução", "Aguardando aprovação", "Aprovado"]
        for i, fase in enumerate(fases):
            with col_fases[i]:
                st.header(fase)
                cards = df_m[df_m['fase_workflow'] == fase]
                for _, c in cards.iterrows():
                    with st.container(border=True):
                        it = df_i[df_i['item_id'] == c['item_id']]
                        nm = it['descricao_item'].values[0] if not it.empty else "Item"
                        st.write(f"**{nm}**")
                        st.write(f"Progresso: {float(c['percentual_acumulado'])*100:.0f}%")
                        st.write(formatar_real(c['valor_acumulado']))
