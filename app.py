import streamlit as st
import pandas as pd
import requests
import uuid
import io
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- BANCO DE DADOS DE USUÁRIOS (BASEADO NO ANEXO) ---
USUARIOS = {
    "FABIO COSTA": "Fstatus@2",
    "LUIZ FERNANDO": "Lfstatus@2",
    "AURÉLIO": "Astatus@2",
    "DENISON EDUARDO DE LIMA": "DELstatus",
    "GILBERTO": "Gstatus@2",
    "PAULO ARRUDA": "Pastatus@2",
    "ADM": "Dstatus@2"
}

# --- SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None

def login():
    st.title("🔐 Acesso Gestão de Medições")
    with st.form("form_login"):
        user = st.selectbox("Selecione o Gestor", list(USUARIOS.keys()))
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if USUARIOS.get(user) == senha:
                st.session_state.logado = True
                st.session_state.usuario = user
                st.rerun()
            else:
                st.error("Senha incorreta!")
    st.stop()

if not st.session_state.logado:
    login()

# --- CSS PARA ALINHAMENTO E IMPRESSÃO ---
st.markdown("""
    <style>
    td { text-align: right !important; }
    td:first-child { text-align: left !important; }
    @media print {
        .stSidebar, .stHeader, .stButton, .no-print { display: none !important; }
        .main { padding: 0px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FERRAMENTAS DE PERFORMANCE E PROTEÇÃO ---

@st.cache_data(ttl=300)
def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=10)
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

def safe_float(valor):
    try:
        if pd.isna(valor) or valor == "": return 0.0
        return float(valor)
    except: return 0.0

def formatar_real(valor):
    v = safe_float(valor)
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_data_br(data_str):
    if pd.isna(data_str) or data_str == "": return "-"
    try: return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return str(data_str)

def salvar_dados_otimizado(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    with st.spinner('Sincronizando...'):
        try:
            r = requests.post(URL_DO_APPS_SCRIPT, json=payload, timeout=15)
            st.cache_data.clear() 
            return True
        except: return False

def calcular_status_prazo_texto(data_fim, data_medicao, percentual):
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim).date()
        med = pd.to_datetime(data_medicao).date()
        p = safe_float(percentual)
        ref = med if p >= 1 else hoje
        dif = (fim - ref).days
        if dif > 0: return f"{dif} dias adiantado", "🟢"
        elif dif == 0: return "No prazo limite", "🟡"
        else: return f"{abs(dif)} dias atrasado", "🔴"
    except: return "Sem dados", "⚪"

# --- 3. MENU LATERAL ---
with st.sidebar:
    st.write(f"👤 Usuário: **{st.session_state.usuario}**")
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
    st.title("Navegação")
    menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban", "Relatório", "📁 CTRs Concluídas"]
    escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle (Ativos)")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
        # FILTRO DE SEGURANÇA POR GESTOR
        if st.session_state.usuario != "ADM":
            df_c = df_c[df_c['gestor'] == st.session_state.usuario]
        
    if not df_c.empty:
        df_m_last = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
        
        t_con = pd.to_numeric(df_c['valor_contrato'], errors='coerce').fillna(0).sum()
        t_med = df_m_last[df_m_last['item_id'].isin(df_i[df_i['contract_id'].isin(df_c['contract_id'])]['item_id'])]['valor_acumulado'].apply(safe_float).sum() if not df_m_last.empty else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(t_con))
        m2.metric("Total Medido", formatar_real(t_med))
        m3.metric("Saldo Geral", formatar_real(t_con - t_med))
        st.divider()
        
        # Filtro de gestor para ADM, para Gestor é fixo
        if st.session_state.usuario == "ADM":
            gestor_sel = st.selectbox("Filtrar por Gestor", ["Todos"] + sorted(df_c['gestor'].unique().tolist()))
            df_f = df_c if gestor_sel == "Todos" else df_c[df_c['gestor'] == gestor_sel]
        else:
            df_f = df_c

        for _, con in df_f.iterrows():
            cid = con['contract_id']
            itens_con = df_i[df_i['contract_id']==cid] if not df_i.empty else pd.DataFrame()
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'].tolist())] if not df_m_last.empty and not itens_con.empty else pd.DataFrame()
            
            if med_ctt.empty: farol = "🟡"
            else:
                atrasado = False
                col_fim = 'data_fim_item' if 'data_fim_item' in itens_con.columns else None
                rel_check = med_ctt.merge(itens_con[['item_id', col_fim]] if col_fim else itens_con[['item_id']], on='item_id')
                for _, r in rel_check.iterrows():
                    d_fim = r.get('data_fim_item', con['data_fim'])
                    if (pd.to_datetime(d_fim).date() - datetime.now().date()).days < 0 and safe_float(r['percentual_acumulado']) < 1:
                        atrasado = True; break
                farol = "🔴" if atrasado else "🟢"
            
            v_bruto = med_ctt['valor_acumulado'].apply(safe_float).sum() if not med_ctt.empty else 0
            with st.container(border=True):
                st.markdown(f"#### {farol} {con.get('cliente', 'Cliente')} (CTR: {con.get('ctr', '-')}) | {con['fornecedor']} (CTT: {con['ctt']})")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(v_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(v_bruto*0.15)}", delta_color="inverse")
                f3.metric("Líquido (85%)", formatar_real(v_bruto*0.85))
                f4.metric("Saldo Contrato", formatar_real(safe_float(con['valor_contrato']) - v_bruto))
                
                c1, c2 = st.columns([4,1])
                if c1.button(f"🔍 Detalhar Boletim {con['ctt']}", key=f"btn_det_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_con[['item_id', 'descricao_item', 'vlr_unit', col_fim] if col_fim else ['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Data Limite'] = rel[col_fim] if col_fim else con['data_fim']
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo_texto(x['Data Limite'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        st.table(pd.DataFrame({'Item': rel['descricao_item'], 'Vlr Unit.': rel['vlr_unit'].apply(formatar_real), '% Acum.': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Medido R$': rel['valor_acumulado'].apply(formatar_real), 'Status': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")}))
                
                if c2.button("✅ Concluir", key=f"btn_done_{cid}", help="Arquivar esta CTR como concluída", use_container_width=True):
                    if salvar_dados_otimizado("contracts", {"status": "Concluído"}, "update", "contract_id", cid):
                        st.rerun()

# --- 5. ITENS ---
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
        # FILTRO DE SEGURANÇA
        if st.session_state.usuario != "ADM":
            df_c = df_c[df_c['gestor'] == st.session_state.usuario]
        
        df_c['list_name'] = df_c.apply(lambda x: f"{x.get('cliente', 'Sem Cliente')} / {x['fornecedor']} (CTT: {x['ctt']})", axis=1)
        if not df_c.empty:
            sel_ctt = st.selectbox("Contrato", df_c['list_name'].tolist())
            row_ctt = df_c[df_c['list_name'] == sel_ctt].iloc[0]
            with st.expander("➕ Novo Item"):
                with st.form("f_item", clear_on_submit=True):
                    c1, c2 = st.columns([2,1])
                    desc = c1.text_input("Descrição"); v_u = c2.number_input("Vlr Unit", min_value=0.0)
                    dt = st.date_input("Prazo", pd.to_datetime(row_ctt['data_fim']).date())
                    if st.form_submit_button("Salvar Item"):
                        if salvar_dados_otimizado("items", {"item_id": str(uuid.uuid4()), "contract_id": row_ctt['contract_id'], "descricao_item": desc, "vlr_unit": v_u, "data_fim_item": str(dt)}):
                            st.rerun()
            if not df_i.empty:
                i_f = df_i[df_i['contract_id'] == row_ctt['contract_id']]
                for _, item in i_f.iterrows():
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                        n_d = c1.text_input("Desc", item['descricao_item'], key=f"d_{item['item_id']}")
                        n_v = c2.number_input("Vlr", value=safe_float(item['vlr_unit']), key=f"v_{item['item_id']}")
                        if c3.button("💾", key=f"s_{item['item_id']}"):
                            salvar_dados_otimizado("items", {"descricao_item": n_d, "vlr_unit": n_v}, "update", "item_id", item['item_id']); st.rerun()
                        if (item['item_id'] not in df_m['item_id'].values if not df_m.empty else True) and c4.button("🗑️", key=f"del_{item['item_id']}"):
                            salvar_dados_otimizado("items", {}, "delete", "item_id", item['item_id']); st.rerun()
                st.divider()
                tot_l = i_f['vlr_unit'].apply(safe_float).sum()
                v_con = safe_float(row_ctt['valor_contrato'])
                with st.container(border=True):
                    st.subheader("💰 Resumo Financeiro")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Total Lançado", formatar_real(tot_l))
                    c2.metric("Valor Contrato", formatar_real(v_con))
                    diff = v_con - tot_l
                    c3.metric("Saldo a Lançar", formatar_real(diff), delta_color="normal" if diff >= 0 else "inverse")
                    st.progress(min(tot_l / v_con, 1.0) if v_con > 0 else 0)

# --- 6. MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
        # FILTRO DE SEGURANÇA
        if st.session_state.usuario != "ADM":
            df_c = df_c[df_c['gestor'] == st.session_state.usuario]
        
        if not df_c.empty:
            c_sel = st.selectbox("Selecione Contrato", df_c['ctt'].tolist())
            id_c = df_c[df_c['ctt'] == c_sel]['contract_id'].values[0]
            i_f = df_i[df_i['contract_id'] == id_c].copy()
            if not i_f.empty:
                i_sel = st.selectbox("Item", i_f['descricao_item'].tolist())
                row = i_f[i_f['descricao_item'] == i_sel].iloc[0]
                p_a = safe_float(df_m[df_m['item_id'] == row['item_id']].sort_values('updated_at').iloc[-1]['percentual_acumulado']) if not df_m.empty and not df_m[df_m['item_id'] == row['item_id']].empty else 0.0
                with st.form("f_m", clear_on_submit=True):
                    p = st.slider("%", 0, 100, int(p_a * 100)) / 100
                    dt = st.date_input("Data", format="DD/MM/YYYY")
                    fase = st.selectbox("Fase", ["Em execução", "Medição lançada", "Aprovado", "Faturado"])
                    if st.form_submit_button("Registrar"):
                        if salvar_dados_otimizado("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * safe_float(row['vlr_unit']), "fase_workflow": fase, "updated_at": str(datetime.now())}):
                            st.rerun()

# --- 7. KANBAN ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban (Ativos)")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
        # FILTRO DE SEGURANÇA
        if st.session_state.usuario != "ADM":
            df_c = df_c[df_c['gestor'] == st.session_state.usuario]
            
        sel = st.selectbox("Filtrar por Contrato:", ["Todos"] + df_c['ctt'].tolist())
        m_f = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            m_f = df_m.sort_values('updated_at').groupby('item_id').tail(1)
            if sel != "Todos" and not df_c.empty:
                cid = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
                m_f = m_f[m_f['item_id'].isin(df_i[df_i['contract_id'] == cid]['item_id'])]
            else:
                m_f = m_f[m_f['item_id'].isin(df_i[df_i['contract_id'].isin(df_c['contract_id'])]['item_id'])]

        cols = st.columns(4)
        for i, f in enumerate(["Em execução", "Medição lançada", "Aprovado", "Faturado"]):
            with cols[i]:
                st.subheader(f)
                if not m_f.empty and 'fase_workflow' in m_f.columns:
                    for _, card in m_f[m_f['fase_workflow'] == f].iterrows():
                        it = df_i[df_i['item_id'] == card['item_id']]
                        if not it.empty and it.iloc[0]['contract_id'] in df_c['contract_id'].values:
                            with st.container(border=True):
                                st.write(f"**{it.iloc[0]['descricao_item']}**")
                                st.caption(f"📑 CTT: {df_c[df_c['contract_id'] == it.iloc[0]['contract_id']].iloc[0]['ctt']}")
                                st.write(f"{safe_float(card['percentual_acumulado'])*100:.0f}% | {formatar_real(card['valor_acumulado'])}")

# --- 8. RELATÓRIO ---
elif escolha == "Relatório":
    st.title("📝 Relatório de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_at = df_c[df_c['status'] == 'Ativo']
        # FILTRO DE SEGURANÇA
        if st.session_state.usuario != "ADM":
            df_at = df_at[df_at['gestor'] == st.session_state.usuario]
            
        if not df_at.empty:
            sel_ctt = st.selectbox("Selecione o Contrato para Gerar Relatório", df_at['ctt'].tolist())
            con = df_at[df_at['ctt'] == sel_ctt].iloc[0]
            df_m_last = pd.DataFrame()
            if not df_m.empty:
                df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
                df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
            itens_con = df_i[df_i['contract_id'] == con['contract_id']]
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'])] if not df_m_last.empty else pd.DataFrame()

            c1, c2 = st.columns(2)
            with c1:
                if st.button("🖨️ Imprimir Boletim", use_container_width=True):
                    st.components.v1.html("<script>window.print();</script>", height=0)
            with c2:
                if not med_ctt.empty:
                    rel_ex = itens_con.merge(med_ctt, on='item_id', how='left')
                    v_bruto = rel_ex['valor_acumulado'].apply(safe_float).sum()
                    v_ret = v_bruto * 0.15; v_liq = v_bruto - v_ret
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_header = pd.DataFrame([["BOLETIM DE MEDIÇÃO", ""], ["CTR / Obra:", f"{con.get('ctr', '-')} - {con.get('cliente', 'Cliente')}"], ["CTT / Fornecedor:", f"{con['ctt']} - {con['fornecedor']}"], ["Gestor:", con.get('gestor', '-')], ["Data de Emissão:", datetime.now().strftime('%d/%m/%Y')], ["", ""]])
                        df_header.to_excel(writer, index=False, header=False, sheet_name='Boletim')
                        df_items_ex = pd.DataFrame({'Item': rel_ex['descricao_item'], 'Vlr Unit (R$)': rel_ex['vlr_unit'].apply(safe_float), 'Medição (%)': rel_ex['percentual_acumulado'].apply(safe_float), 'Medição (R$)': rel_ex['valor_acumulado'].apply(safe_float)})
                        df_items_ex.to_excel(writer, index=False, startrow=len(df_header), sheet_name='Boletim')
                        df_footer = pd.DataFrame([["", ""], ["RESUMO FINANCEIRO", ""], ["Total Bruto Medido:", formatar_real(v_bruto)], ["Retenção (15%):", f"- {formatar_real(v_ret)}"], ["Total Líquido:", formatar_real(v_liq)]])
                        df_footer.to_excel(writer, index=False, header=False, startrow=len(df_header) + len(df_items_ex) + 1, sheet_name='Boletim')
                    st.download_button(label="📥 Exportar para Excel", data=output.getvalue(), file_name=f"Boletim_{con['ctt']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

            with st.container(border=True):
                st.markdown(f"### ANEXO I - Boletim de Medição")
                c1, c2 = st.columns(2)
                c1.write(f"**CTT:** {con['ctt']} - {con['fornecedor']}")
                c1.write(f"**Obra:** {con.get('ctr', '-')} - {con.get('cliente', 'Cliente')}")
                c2.write(f"**Gestor:** {con.get('gestor', '-')}")
                c2.write(f"**Fim:** {formatar_data_br(con.get('data_fim', ''))}")
                st.divider()
                if not med_ctt.empty:
                    rel = itens_con.merge(med_ctt, on='item_id', how='left')
                    rel_view = pd.DataFrame({'Item': rel['descricao_item'], 'VLR UNIT': rel['vlr_unit'].apply(formatar_real), 'Med %': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Med R$': rel['valor_acumulado'].apply(formatar_real)})
                    st.table(rel_view)
                    v_bruto_view = med_ctt['valor_acumulado'].apply(safe_float).sum(); v_ret_view = v_bruto_view * 0.15
                    st.divider()
                    st.write(f"**Bruto:** {formatar_real(v_bruto_view)} | **Retenção (15%):** - {formatar_real(v_ret_view)}")
                    st.markdown(f"### **Líquido Financeiro: {formatar_real(v_bruto_view - v_ret_view)}**")

# --- 9. CTRs CONCLUÍDAS ---
elif escolha == "📁 CTRs Concluídas":
    st.title("📂 Histórico de CTRs Concluídas")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_done = df_c[df_c['status'] == 'Concluído']
        # FILTRO DE SEGURANÇA
        if st.session_state.usuario != "ADM":
            df_done = df_done[df_done['gestor'] == st.session_state.usuario]
            
        if df_done.empty:
            st.info("Nenhuma CTR concluída no histórico.")
        else:
            sel_hist = st.selectbox("Selecione a CTR para visualizar o fechamento", df_done['ctt'].tolist())
            con = df_done[df_done['ctt'] == sel_hist].iloc[0]
            
            df_m_last = pd.DataFrame()
            if not df_m.empty:
                df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
                df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
            
            itens_con = df_i[df_i['contract_id'] == con['contract_id']]
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'])] if not df_m_last.empty else pd.DataFrame()
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🖨️ Imprimir Fechamento", use_container_width=True):
                    st.components.v1.html("<script>window.print();</script>", height=0)
            with c2:
                if not med_ctt.empty:
                    rel_ex = itens_con.merge(med_ctt, on='item_id', how='left')
                    v_bruto = rel_ex['valor_acumulado'].apply(safe_float).sum()
                    v_ret = v_bruto * 0.15; v_liq = v_bruto - v_ret
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_header = pd.DataFrame([["FECHAMENTO DE CTR CONCLUÍDA", ""], ["CTR / Obra:", f"{con.get('ctr', '-')} - {con.get('cliente', 'Cliente')}"], ["CTT / Fornecedor:", f"{con['ctt']} - {con['fornecedor']}"], ["Gestor:", con.get('gestor', '-')], ["Data de Conclusão:", formatar_data_br(datetime.now())], ["", ""]])
                        df_header.to_excel(writer, index=False, header=False, sheet_name='Boletim')
                        df_items_ex = pd.DataFrame({'Item': rel_ex['descricao_item'], 'Vlr Unit (R$)': rel_ex['vlr_unit'].apply(safe_float), 'Medição Final (%)': rel_ex['percentual_acumulado'].apply(safe_float), 'Medição Final (R$)': rel_ex['valor_acumulado'].apply(safe_float)})
                        df_items_ex.to_excel(writer, index=False, startrow=len(df_header), sheet_name='Boletim')
                        df_footer = pd.DataFrame([["", ""], ["RESUMO FINANCEIRO FINAL", ""], ["Total Bruto:", formatar_real(v_bruto)], ["Retenção (15%):", f"- {formatar_real(v_ret)}"], ["Total Líquido Pago:", formatar_real(v_liq)]])
                        df_footer.to_excel(writer, index=False, header=False, startrow=len(df_header) + len(df_items_ex) + 1, sheet_name='Boletim')
                    st.download_button(label="📥 Exportar Excel de Fechamento", data=output.getvalue(), file_name=f"Fechamento_{con['ctt']}.xlsx", use_container_width=True)

            with st.container(border=True):
                st.subheader(f"🏁 Dados de Conclusão - {con['fornecedor']}")
                st.write(f"**Status Final:** Concluído | **Cliente:** {con.get('cliente', 'Cliente')}")
                if not med_ctt.empty:
                    rel = itens_con.merge(med_ctt, on='item_id', how='left')
                    st.table(pd.DataFrame({'Item': rel['descricao_item'], 'VLR UNIT': rel['vlr_unit'].apply(formatar_real), 'Med % Final': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Med R$ Final': rel['valor_acumulado'].apply(formatar_real)}))
                    st.info(f"Valor Líquido Final no momento do arquivamento: {formatar_real(v_bruto - v_ret)}")

# --- 10. CONTRATOS ---
elif escolha == "Contratos":
    if st.session_state.usuario != "ADM":
        st.warning("⚠️ Apenas o Administrador pode cadastrar novos contratos.")
    else:
        st.title("📄 Cadastro de Contratos")
        with st.form("f_con", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cl = c1.text_input("Cliente"); ctr = c2.text_input("CTR")
            fo = c1.text_input("Fornecedor"); ctt = c2.text_input("CTT")
            gs = st.selectbox("Gestor Responsável", [k for k in USUARIOS.keys() if k != "ADM"])
            vl = c2.number_input("Valor Total")
            dt_i = st.date_input("Início"); dt_f = st.date_input("Fim")
            if st.form_submit_button("Salvar"):
                if salvar_dados_otimizado("contracts", {"contract_id": str(uuid.uuid4()), "cliente": cl, "ctr": ctr, "fornecedor": fo, "ctt": ctt, "gestor": gs, "valor_contrato": vl, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"}):
                    st.rerun()
