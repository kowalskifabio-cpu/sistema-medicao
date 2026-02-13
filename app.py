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
    with st.spinner('Sincronizando com a Nuvem...'):
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
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban", "Relatório"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle e Cronograma")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_m_last = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
        t_con = pd.to_numeric(df_c['valor_contrato'], errors='coerce').fillna(0).sum()
        t_med = df_m_last['valor_acumulado'].apply(safe_float).sum() if not df_m_last.empty else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(t_con))
        m2.metric("Total Medido", formatar_real(t_med))
        m3.metric("Saldo Geral", formatar_real(t_con - t_med))
        st.divider()
        g_sel = st.selectbox("Filtrar por Gestor", ["Todos"] + sorted(df_c['gestor'].unique().tolist()))
        df_f = df_c if g_sel == "Todos" else df_c[df_c['gestor'] == g_sel]
        for _, con in df_f.iterrows():
            cid = con['contract_id']
            itens_con = df_i[df_i['contract_id']==cid] if not df_i.empty else pd.DataFrame()
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'].tolist())] if not df_m_last.empty and not itens_con.empty else pd.DataFrame()
            farol = "🟡" if med_ctt.empty else ("🔴" if any((pd.to_datetime(r['data_fim_item'] if not pd.isna(r['data_fim_item']) else con['data_fim']).date() - datetime.now().date()).days < 0 and safe_float(r['percentual_acumulado']) < 1 for _, r in med_ctt.merge(itens_con[['item_id', 'data_fim_item']], on='item_id').iterrows()) else "🟢")
            v_bruto = med_ctt['valor_acumulado'].apply(safe_float).sum() if not med_ctt.empty else 0
            with st.container(border=True):
                st.markdown(f"#### {farol} {con.get('cliente', 'Cliente')} (CTR: {con.get('ctr', '-')}) | {con['fornecedor']} (CTT: {con['ctt']})")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(v_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(v_bruto*0.15)}", delta_color="inverse")
                f3.metric("Líquido (85%)", formatar_real(v_bruto*0.85))
                f4.metric("Saldo Contrato", formatar_real(safe_float(con['valor_contrato']) - v_bruto))
                if st.button(f"🔍 Detalhes {con['ctt']}", key=f"det_{cid}"):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_con[['item_id', 'descricao_item', 'vlr_unit', 'data_fim_item']], on='item_id')
                        rel['Data Limite'] = rel['data_fim_item'].fillna(con['data_fim'])
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo_texto(x['Data Limite'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        st.table(pd.DataFrame({'Item': rel['descricao_item'], 'Vlr Unit.': rel['vlr_unit'].apply(formatar_real), '% Acum.': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Medido R$': rel['valor_acumulado'].apply(formatar_real), 'Status': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")}))

# --- 5. ITENS (CONFERÊNCIA FINANCEIRA) ---
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c['list_name'] = df_c.apply(lambda x: f"{x.get('cliente', 'Sem Cliente')} / {x['fornecedor']} (CTT: {x['ctt']})", axis=1)
        sel_ctt = st.selectbox("Contrato", df_c['list_name'].tolist())
        row_ctt = df_c[df_c['list_name'] == sel_ctt].iloc[0]
        with st.expander("➕ Novo Item"):
            with st.form("f_item", clear_on_submit=True):
                c1, c2 = st.columns([2,1])
                desc = c1.text_input("Descrição"); v_u = c2.number_input("Vlr Unit", min_value=0.0)
                dt = st.date_input("Prazo", pd.to_datetime(row_ctt['data_fim']).date())
                if st.form_submit_button("Salvar"):
                    if salvar_dados_otimizado("items", {"item_id": str(uuid.uuid4()), "contract_id": row_ctt['contract_id'], "descricao_item": desc, "vlr_unit": v_u, "data_fim_item": str(dt)}):
                        st.rerun()
        if not df_i.empty:
            i_f = df_i[df_i['contract_id'] == row_ctt['contract_id']]
            for _, it in i_f.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    n_d = c1.text_input("Desc", it['descricao_item'], key=f"d_{it['item_id']}")
                    n_v = c2.number_input("Vlr", value=safe_float(it['vlr_unit']), key=f"v_{it['item_id']}")
                    if c3.button("💾", key=f"s_{it['item_id']}"):
                        salvar_dados_otimizado("items", {"descricao_item": n_d, "vlr_unit": n_v}, "update", "item_id", it['item_id']); st.rerun()
                    if (it['item_id'] not in df_m['item_id'].values if not df_m.empty else True) and c4.button("🗑️", key=f"del_{it['item_id']}"):
                        salvar_dados_otimizado("items", {}, "delete", "item_id", it['item_id']); st.rerun()
            st.divider()
            tot = i_f['vlr_unit'].apply(safe_float).sum()
            v_con = safe_float(row_ctt['valor_contrato'])
            with st.container(border=True):
                st.subheader("💰 Resumo de Lançamentos")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Lançado", formatar_real(tot))
                c2.metric("Valor Contrato", formatar_real(v_con))
                diff = v_con - tot
                c3.metric("Saldo a Lançar", formatar_real(diff), delta_color="normal" if diff >= 0 else "inverse")
                if diff < 0: st.error("Atenção: Itens superam o valor total do contrato!")
                st.progress(min(tot / v_con, 1.0) if v_con > 0 else 0)

# --- 6. MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        c_sel = st.selectbox("Contrato", df_c['ctt'].tolist())
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
    st.title("📋 Quadro Kanban")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_m.empty:
        m_f = df_m.sort_values('updated_at').groupby('item_id').tail(1)
        cols = st.columns(4)
        for i, f in enumerate(["Em execução", "Medição lançada", "Aprovado", "Faturado"]):
            with cols[i]:
                st.subheader(f)
                for _, card in m_f[m_f['fase_workflow'] == f].iterrows():
                    it = df_i[df_i['item_id'] == card['item_id']]
                    if not it.empty:
                        with st.container(border=True):
                            st.write(f"**{it.iloc[0]['descricao_item']}**")
                            st.write(f"{safe_float(card['percentual_acumulado'])*100:.0f}% | {formatar_real(card['valor_acumulado'])}")

# --- 8. RELATÓRIO (EXCEL + IMPRESSÃO) ---
elif escolha == "Relatório":
    st.title("📝 Relatório de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        sel_ctt = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        con = df_c[df_c['ctt'] == sel_ctt].iloc[0]
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
                df_ex = pd.DataFrame({'Item': rel_ex['descricao_item'], 'Vlr Unit': rel_ex['vlr_unit'].apply(safe_float), 'Med %': rel_ex['percentual_acumulado'].apply(safe_float), 'Med R$': rel_ex['valor_acumulado'].apply(safe_float)})
                output = io.BytesIO()
                # USANDO MOTOR PADRÃO 'openpyxl' (Lembrar do requirements.txt no Github)
                df_ex.to_excel(output, index=False, sheet_name='Boletim')
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
                rel_view = pd.DataFrame({'Item': rel['descricao_item'], 'VLR UNIT': rel['vlr_unit'].apply(formatar_real), 'Medição %': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Medição R$': rel['valor_acumulado'].apply(formatar_real)})
                st.table(rel_view)
                v_bruto = med_ctt['valor_acumulado'].apply(safe_float).sum()
                v_ret = v_bruto * 0.15
                st.divider()
                st.write(f"**Bruto:** {formatar_real(v_bruto)} | **Retenção (15%):** - {formatar_real(v_ret)}")
                st.markdown(f"### **Líquido Financeiro: {formatar_real(v_bruto - v_ret)}**")

# --- 9. CONTRATOS ---
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.form("f_con", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cl = c1.text_input("Cliente"); ctr = c2.text_input("CTR")
        fo = c1.text_input("Fornecedor"); ctt = c2.text_input("CTT")
        gs = c1.text_input("Gestor"); vl = c2.number_input("Valor Total")
        dt_i = st.date_input("Início"); dt_f = st.date_input("Fim")
        if st.form_submit_button("Salvar"):
            if salvar_dados_otimizado("contracts", {"contract_id": str(uuid.uuid4()), "cliente": cl, "ctr": ctr, "fornecedor": fo, "ctt": ctt, "gestor": gs, "valor_contrato": vl, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"}):
                st.rerun()
