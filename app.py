import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- 2. FERRAMENTAS DE TRADUÇÃO E CÁLCULO ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    try:
        return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return data_str

def calcular_status_prazo(data_fim_contrato, data_medicao, percentual):
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim_contrato).date()
        med = pd.to_datetime(data_medicao).date()
        ref = med if float(percentual) >= 1 else hoje
        dif = (fim - ref).days
        if dif > 0: return f"{dif} dias adiantado", "🟢"
        elif dif == 0: return "No prazo limite", "🟡"
        else: return f"{abs(dif)} dias atrasado", "🔴"
    except: return "Sem dados", "⚪"

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

# --- 4. PÁGINA: DASHBOARD (MÉTRICAS TOTAIS + FILTRO + RETENÇÃO) ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle e Cronograma")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # Recuperando a Parte Legal: Totais Gerais no Topo
        t_con_geral = pd.to_numeric(df_c['valor_contrato']).sum()
        t_med_geral = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(t_con_geral))
        m2.metric("Total Medido", formatar_real(t_med_geral))
        m3.metric("Saldo Geral", formatar_real(t_con_geral - t_med_geral))
        
        st.divider()
        gestor_sel = st.selectbox("Filtrar por Gestor", ["Todos"] + sorted(df_c['gestor'].unique().tolist()))
        df_f = df_c if gestor_sel == "Todos" else df_c[df_c['gestor'] == gestor_sel]

        for _, con in df_f.iterrows():
            cid = con['contract_id']
            # Cálculos Financeiros com Retenção de 15%
            itens_ids = df_i[df_i['contract_id']==cid]['item_id'].tolist() if not df_i.empty else []
            med_ctt = df_m[df_m['item_id'].isin(itens_ids)] if not df_m.empty else pd.DataFrame()
            
            bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            retencao = bruto * 0.15 
            liquido = bruto - retencao
            
            with st.container(border=True):
                st.subheader(f"📄 {con['ctt']} - {con['fornecedor']}")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(retencao)}", delta_color="inverse")
                f3.metric("Líquido a Pagar", formatar_real(liquido))
                f4.metric("Saldo Contrato", formatar_real(float(con['valor_contrato']) - bruto))
                
                if st.button(f"🔍 Detalhar Boletim {con['ctt']}", key=f"btn_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(df_i[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(con['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        
                        st.table(pd.DataFrame({
                            'Item': rel['descricao_item'],
                            'Valor Unitário': rel['vlr_unit'].apply(formatar_real),
                            '% Acumulado': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medição R$': rel['valor_acumulado'].apply(formatar_real),
                            'Saldo Item': rel.apply(lambda x: formatar_real(float(x['vlr_unit']) - float(x['valor_acumulado'])), axis=1),
                            'Data Real': rel['data_medicao'].apply(formatar_data_br),
                            'Prazo': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        }))
                    else:
                        st.warning("Nenhuma medição encontrada.")

# --- 5. PÁGINA: LANÇAR MEDIÇÃO (COM MEMÓRIA DO ÚLTIMO PERCENTUAL) ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements") # Buscamos medições para saber o último valor
    
    if not df_c.empty:
        ctt_sel = st.selectbox("1. Selecione o Contrato", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == ctt_sel]['contract_id'].values[0]
        
        itens_filtrados = df_i[df_i['contract_id'] == id_ctt].copy()
        
        if not itens_filtrados.empty:
            itens_filtrados['display'] = itens_filtrados.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
            item_nome = st.selectbox("2. Selecione o Item", itens_filtrados['display'].tolist())
            row_i = itens_filtrados[itens_filtrados['display'] == item_nome].iloc[0]
            
            # --- LÓGICA DE MEMÓRIA DO SLIDER ---
            perc_atual = 0.0
            if not df_m.empty:
                med_historico = df_m[df_m['item_id'] == row_i['item_id']]
                if not med_historico.empty:
                    perc_atual = float(med_historico.iloc[-1]['percentual_acumulado'])

            with st.form("form_medicao_final"):
                st.info(f"📈 Progresso registrado na planilha: {perc_atual*100:.2f}%")
                # O Slider nasce na posição que já foi medida!
                p = st.slider("Ajustar Novo Percentual Acumulado (%)", 0, 100, int(perc_atual * 100)) / 100
                
                v_calc = p * float(row_i['vlr_unit'])
                st.write(f"**Valor total acumulado:** {formatar_real(v_calc)}")
                dt = st.date_input("Data da Medição")
                f = st.selectbox("Status", ["Em execução", "Medição lançada", "Aprovado"])
                
                if st.form_submit_button("Registrar Medição"):
                    salvar_dados("measurements", {
                        "measurement_id": str(uuid.uuid4()), "item_id": row_i['item_id'], 
                        "data_medicao": str(dt), "percentual_acumulado": p, 
                        "valor_acumulado": v_calc, "fase_workflow": f, "updated_at": str(datetime.now())
                    })
                    st.success("Medição registrada!")
                    st.rerun()
        else:
            st.warning("Sem itens para este contrato.")

# --- 6. PÁGINA: KANBAN (A QUE HAVIA SUMIDO) ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban de Medições")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    if not df_m.empty and not df_i.empty:
        fases = ["Em execução", "Medição lançada", "Aprovado", "Faturado"]
        colunas_kanban = st.columns(len(fases))
        for i, fase in enumerate(fases):
            with colunas_kanban[i]:
                st.subheader(fase)
                cards = df_m[df_m['fase_workflow'] == fase]
                for _, card in cards.iterrows():
                    # Busca o nome do item para o card
                    item_info = df_i[df_i['item_id'] == card['item_id']]
                    nome_item = item_info['descricao_item'].values[0] if not item_info.empty else "Item Desconhecido"
                    with st.container(border=True):
                        st.write(f"**{nome_item}**")
                        st.write(f"Progresso: {float(card['percentual_acumulado'])*100:.0f}%")
                        st.write(formatar_real(card['valor_acumulado']))
                        st.caption(f"📅 {formatar_data_br(card['data_medicao'])}")

# --- OUTRAS PÁGINAS ---
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.form("f_con"):
        c1, c2 = st.columns(2)
        ctt = c1.text_input("Número CTT"); forn = c2.text_input("Fornecedor")
        gest = c1.text_input("Gestor"); vlr = c2.number_input("Valor Total", min_value=0.0)
        dt_i = st.date_input("Início"); dt_f = st.date_input("Fim")
        if st.form_submit_button("Salvar"):
            salvar_dados("contracts", {"contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "gestor": gest, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"})
            st.rerun()

elif escolha == "Itens":
    st.title("🏗️ Itens do Contrato")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel = st.selectbox("Escolha o Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
        with st.form("f_item"):
            desc = st.text_input("Descrição"); v_u = st.number_input("Vlr Unitário", min_value=0.0)
            if st.form_submit_button("Adicionar"):
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_c, "descricao_item": desc, "vlr_unit": v_u})
                st.rerun()
           
