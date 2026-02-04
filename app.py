import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- 2. FERRAMENTAS DE PERFORMANCE E TRADUÇÃO ---

@st.cache_data(ttl=60)
def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=15)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    if pd.isna(data_str) or data_str == "": return "-"
    try:
        return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return str(data_str)

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    r = requests.post(URL_DO_APPS_SCRIPT, json=payload)
    st.cache_data.clear() 
    return r

def calcular_status_prazo_texto(data_fim, data_medicao, percentual):
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

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. PÁGINA: DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle e Cronograma")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        t_con = pd.to_numeric(df_c['valor_contrato']).sum()
        t_med = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(t_con))
        m2.metric("Total Medido", formatar_real(t_med))
        m3.metric("Saldo Geral", formatar_real(t_con - t_med))
        
        st.divider()
        gestor_sel = st.selectbox("Filtrar por Gestor", ["Todos"] + sorted(df_c['gestor'].unique().tolist()))
        df_f = df_c if gestor_sel == "Todos" else df_c[df_c['gestor'] == gestor_sel]

        for _, con in df_f.iterrows():
            cid = con['contract_id']
            itens_con = df_i[df_i['contract_id']==cid] if not df_i.empty else pd.DataFrame()
            
            # Proteção: Verifica coluna de data
            if not itens_con.empty and 'data_fim_item' not in itens_con.columns:
                itens_con['data_fim_item'] = con['data_fim']
            
            med_ctt = df_m[df_m['item_id'].isin(itens_con['item_id'].tolist())] if not df_m.empty and not itens_con.empty else pd.DataFrame()
            
            # Lógica do Farol
            atrasado = False
            if not med_ctt.empty:
                rel_check = med_ctt.merge(itens_con[['item_id', 'data_fim_item']], on='item_id')
                for _, r in rel_check.iterrows():
                    d_fim = r['data_fim_item'] if not pd.isna(r['data_fim_item']) else con['data_fim']
                    if (pd.to_datetime(d_fim).date() - datetime.now().date()).days < 0 and float(r['percentual_acumulado']) < 1:
                        atrasado = True; break
            
            farol = "🔴" if atrasado else "🟢"
            v_bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            
            with st.container(border=True):
                st.subheader(f"{farol} {con['ctt']} - {con['fornecedor']}")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(v_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(v_bruto*0.15)}", delta_color="inverse")
                f3.metric("Líquido (85%)", formatar_real(v_bruto*0.85))
                f4.metric("Saldo Contrato", formatar_real(float(con['valor_contrato']) - v_bruto))
                
                if st.button(f"🔍 Detalhar Boletim {con['ctt']}", key=f"btn_det_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_con[['item_id', 'descricao_item', 'vlr_unit', 'data_fim_item']], on='item_id')
                        rel['Data Limite'] = rel['data_fim_item'].fillna(con['data_fim'])
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo_texto(x['Data Limite'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        st.table(pd.DataFrame({
                            'Item': rel['descricao_item'], 'Vlr Unit.': rel['vlr_unit'].apply(formatar_real),
                            '% Acum.': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medido R$': rel['valor_acumulado'].apply(formatar_real),
                            'Prazo': rel['Data Limite'].apply(formatar_data_br), 'Status': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        }))
                    else: st.warning("Sem medições para detalhar.")

# --- 5. PÁGINA: ITENS ---
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        sel_ctt = st.selectbox("Escolha o Contrato", df_c['ctt'].tolist())
        row_ctt = df_c[df_c['ctt'] == sel_ctt].iloc[0]
        with st.expander("➕ Novo Item", expanded=True):
            with st.form("f_item"):
                c1, c2 = st.columns([2,1])
                desc = c1.text_input("Descrição"); v_u = c2.number_input("Vlr Unit", min_value=0.0)
                dt = st.date_input("Prazo", pd.to_datetime(row_ctt['data_fim']).date())
                if st.form_submit_button("Salvar Novo Item"):
                    salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": row_ctt['contract_id'], "descricao_item": desc, "vlr_unit": v_u, "data_fim_item": str(dt)})
                    st.rerun()
        if not df_i.empty:
            st.divider()
            i_f = df_i[df_i['contract_id'] == row_ctt['contract_id']]
            busca = st.text_input("🔍 Pesquisar item por nome...")
            if busca: i_f = i_f[i_f['descricao_item'].str.contains(busca, case=False)]
            for _, item in i_f.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    n_d = c1.text_input("Desc", item['descricao_item'], key=f"d_{item['item_id']}")
                    n_v = c2.number_input("Vlr", value=float(item['vlr_unit']), key=f"v_{item['item_id']}")
                    if c3.button("💾", key=f"s_{item['item_id']}"):
                        salvar_dados("items", {"descricao_item": n_d, "vlr_unit": n_v}, "update", "item_id", item['item_id']); st.rerun()
                    if (item['item_id'] not in df_m['item_id'].values if not df_m.empty else True) and c4.button("🗑️", key=f"del_{item['item_id']}"):
                        salvar_dados("items", {}, "delete", "item_id", item['item_id']); st.rerun()

# --- 6. LANÇAR MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        c_sel = st.selectbox("1. Selecione o Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == c_sel]['contract_id'].values[0]
        i_f = df_i[df_i['contract_id'] == id_c].copy()
        if not i_f.empty:
            b = st.text_input("🔍 Filtrar Itens..."); 
            if b: i_f = i_f[i_f['descricao_item'].str.contains(b, case=False)]
            i_f['display'] = i_f.apply(lambda x: f"{x['descricao_item']} ({formatar_real(x['vlr_unit'])})", axis=1)
            row = i_f[i_f['display'] == st.selectbox("2. Selecione o Item", i_f['display'].tolist())].iloc[0]
            p_a = float(df_m[df_m['item_id'] == row['item_id']].iloc[-1]['percentual_acumulado']) if not df_m.empty and not df_m[df_m['item_id'] == row['item_id']].empty else 0.0
            with st.form("f_m"):
                st.info(f"Progresso Atual: {p_a*100:.2f}%")
                p = st.slider("% Executado", 0, 100, int(p_a * 100)) / 100
                dt = st.date_input("Data da Medição", format="DD/MM/YYYY")
                fase = st.selectbox("Fase do Kanban", ["Em execução", "Medição lançada", "Aprovado", "Faturado"])
                if st.form_submit_button("Registrar Medição"):
                    salvar_dados("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * float(row['vlr_unit']), "fase_workflow": fase, "updated_at": str(datetime.now())})
                    st.rerun()
            if not df_m.empty: 
                st.subheader("📋 Histórico de Lançamentos")
                st.dataframe(df_m[df_m['item_id'].isin(i_f['item_id'])], use_container_width=True, height=250)

# --- 7. KANBAN ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        sel = st.selectbox("Filtrar por Contrato:", ["Todos"] + df_c['ctt'].tolist())
        m_f = df_m if sel == "Todos" else df_m[df_m['item_id'].isin(df_i[df_i['contract_id'] == df_c[df_c['ctt'] == sel]['contract_id'].values[0]]['item_id'])]
        cols = st.columns(4)
        fases = ["Em execução", "Medição lançada", "Aprovado", "Faturado"]
        for i, f in enumerate(fases):
            with cols[i]:
                st.subheader(f)
                if not m_f.empty and 'fase_workflow' in m_f.columns:
                    for _, card in m_f[m_f['fase_workflow'] == f].iterrows():
                        it_row = df_i[df_i['item_id'] == card['item_id']]
                        if not it_row.empty:
                            with st.container(border=True):
                                st.write(f"**{it_row.iloc[0]['descricao_item']}**")
                                st.caption(f"📑 CTT: {df_c[df_c['contract_id'] == it_row.iloc[0]['contract_id']].iloc[0]['ctt']}")
                                st.write(f"{float(card['percentual_acumulado'])*100:.0f}% | {formatar_real(card['valor_acumulado'])}")

# --- 8. CONTRATOS ---
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.form("f_con"):
        c1, c2 = st.columns(2); ctt = c1.text_input("Número CTT"); forn = c2.text_input("Fornecedor")
        gst = c1.text_input("Gestor"); vlr = c2.number_input("Valor Total", min_value=0.0)
        dt_i = st.date_input("Início"); dt_f = st.date_input("Fim")
        if st.form_submit_button("Salvar Contrato"):
            salvar_dados("contracts", {"contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "gestor": gst, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"})
            st.rerun()
