import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- 2. FERRAMENTAS DE TRADUÇÃO ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    if pd.isna(data_str) or data_str == "": return "-"
    try:
        return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return str(data_str)

def calcular_status_prazo(data_fim, data_medicao, percentual):
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim).date()
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

# --- 4. DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle e Cronograma")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
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
            itens_con = df_i[df_i['contract_id']==cid] if not df_i.empty else pd.DataFrame()
            med_ctt = df_m[df_m['item_id'].isin(itens_con['item_id'].tolist())] if not df_m.empty and not itens_con.empty else pd.DataFrame()
            
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
                        # Proteção para coluna de data no merge
                        if 'data_fim_item' not in itens_con.columns: itens_con['data_fim_item'] = con['data_fim']
                        
                        rel = med_ctt.merge(itens_con[['item_id', 'descricao_item', 'vlr_unit', 'data_fim_item']], on='item_id')
                        rel['Data Limite'] = rel['data_fim_item'].fillna(con['data_fim'])
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(x['Data Limite'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        
                        rel_view = pd.DataFrame({
                            'Item': rel['descricao_item'],
                            'Valor Unitário': rel['vlr_unit'].apply(formatar_real),
                            '% Acumulado': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medição R$': rel['valor_acumulado'].apply(formatar_real),
                            'Prazo do Item': rel['Data Limite'].apply(formatar_data_br),
                            'Status Prazo': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        })
                        st.table(rel_view)
                    else: st.warning("Nenhuma medição encontrada.")

# --- 5. PÁGINA: ITENS (CORREÇÃO DO ERRO) ---
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel_ctt = st.selectbox("Escolha o Contrato", df_c['ctt'].tolist())
        row_ctt = df_c[df_c['ctt'] == sel_ctt].iloc[0]
        
        with st.form("f_item"):
            c1, c2 = st.columns([2,1])
            desc = c1.text_input("Descrição do Item")
            v_u = c2.number_input("Valor Unitário (R$)", min_value=0.0, format="%.2f")
            dt_fim_default = pd.to_datetime(row_ctt['data_fim']).date()
            dt_item = st.date_input("Data Fim do Item", dt_fim_default, format="DD/MM/YYYY")
            if st.form_submit_button("Adicionar Item"):
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": row_ctt['contract_id'], "descricao_item": desc, "vlr_unit": v_u, "data_fim_item": str(dt_item)})
                st.rerun()
        
        st.divider()
        df_i = carregar_dados("get_items")
        if not df_i.empty:
            itens_ctt = df_i[df_i['contract_id'] == row_ctt['contract_id']].copy()
            
            # PROTEÇÃO CONTRA O ERRO KEYERROR
            if 'data_fim_item' not in itens_ctt.columns:
                itens_ctt['data_fim_item'] = "-"
            
            busca = st.text_input("🔍 Pesquisar item...")
            if busca:
                itens_ctt = itens_ctt[itens_ctt['descricao_item'].str.contains(busca, case=False)]
            
            itens_ctt['vlr_unit'] = itens_ctt['vlr_unit'].apply(formatar_real)
            itens_ctt['data_fim_item'] = itens_ctt['data_fim_item'].apply(formatar_data_br)
            st.dataframe(itens_ctt[['descricao_item', 'vlr_unit', 'data_fim_item']], use_container_width=True)

# --- 6. LANÇAR MEDIÇÃO (MANTIDO) ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        ctt_sel = st.selectbox("Contrato", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == ctt_sel]['contract_id'].values[0]
        itens_f = df_i[df_i['contract_id'] == id_ctt].copy() if not df_i.empty else pd.DataFrame()
        if not itens_f.empty:
            busca_l = st.text_input("🔍 Filtrar...")
            if busca_l: itens_f = itens_f[itens_f['descricao_item'].str.contains(busca_l, case=False)]
            itens_f['display'] = itens_f.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
            item_nome = st.selectbox("Item", itens_f['display'].tolist())
            row_i = itens_f[itens_f['display'] == item_nome].iloc[0]
            perc_atual = 0.0
            if not df_m.empty:
                med_h = df_m[df_m['item_id'] == row_i['item_id']]
                if not med_h.empty: perc_atual = float(med_h.iloc[-1]['percentual_acumulado'])
            with st.form("form_med"):
                p = st.slider("%", 0, 100, int(perc_atual * 100)) / 100
                dt = st.date_input("Data", format="DD/MM/YYYY")
                if st.form_submit_button("Registrar"):
                    salvar_dados("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row_i['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * float(row_i['vlr_unit']), "fase_workflow": "Medição lançada", "updated_at": str(datetime.now())})
                    st.rerun()

# --- 7. KANBAN E CONTRATOS (MANTIDOS) ---
elif escolha == "Kanban":
    st.title("📋 Kanban")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    if not df_m.empty and not df_i.empty:
        fases = ["Em execução", "Medição lançada", "Aprovado", "Faturado"]
        cols = st.columns(len(fases))
        for i, f in enumerate(fases):
            with cols[i]:
                st.subheader(f)
                cards = df_m[df_m['fase_workflow'] == f]
                for _, card in cards.iterrows():
                    it = df_i[df_i['item_id'] == card['item_id']]
                    nm = it['descricao_item'].values[0] if not it.empty else "Item"
                    with st.container(border=True):
                        st.write(f"**{nm}**")
                        st.write(f"{float(card['percentual_acumulado'])*100:.0f}% | {formatar_real(card['valor_acumulado'])}")

elif escolha == "Contratos":
    st.title("📄 Contratos")
    with st.form("f_con"):
        c1, c2 = st.columns(2)
        ctt = c1.text_input("Número CTT"); forn = c2.text_input("Fornecedor")
        gest = c1.text_input("Gestor"); vlr = c2.number_input("Valor", min_value=0.0)
        dt_i = st.date_input("Início", format="DD/MM/YYYY"); dt_f = st.date_input("Fim", format="DD/MM/YYYY")
        if st.form_submit_button("Salvar"):
            salvar_dados("contracts", {"contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "gestor": gest, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"})
            st.rerun()
           
