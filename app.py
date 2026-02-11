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
        m2.metric("Total Medido (Atual)", formatar_real(t_med))
        m3.metric("Saldo Geral", formatar_real(t_con - t_med))
        st.divider()
        gestor_sel = st.selectbox("Filtrar por Gestor", ["Todos"] + sorted(df_c['gestor'].unique().tolist()))
        df_f = df_c if gestor_sel == "Todos" else df_c[df_c['gestor'] == gestor_sel]
        for _, con in df_f.iterrows():
            cid = con['contract_id']
            itens_con = df_i[df_i['contract_id']==cid] if not df_i.empty else pd.DataFrame()
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'].tolist())] if not df_m_last.empty and not itens_con.empty else pd.DataFrame()
            if med_ctt.empty: farol = "🟡"
            else:
                atrasado = False
                if 'data_fim_item' not in itens_con.columns: itens_con['data_fim_item'] = con['data_fim']
                rel_check = med_ctt.merge(itens_con[['item_id', 'data_fim_item']], on='item_id')
                for _, r in rel_check.iterrows():
                    d_fim = r['data_fim_item'] if not pd.isna(r['data_fim_item']) else con['data_fim']
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
                if st.button(f"🔍 Detalhar Boletim {con['ctt']}", key=f"btn_det_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_con[['item_id', 'descricao_item', 'vlr_unit', 'data_fim_item']], on='item_id')
                        rel['Data Limite'] = rel['data_fim_item'].fillna(con['data_fim'])
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo_texto(x['Data Limite'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        st.table(pd.DataFrame({'Item': rel['descricao_item'], 'Vlr Unit.': rel['vlr_unit'].apply(formatar_real), '% Acum.': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Medido R$': rel['valor_acumulado'].apply(formatar_real), 'Status': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")}))

# --- 5. ITENS ---
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c['list_name'] = df_c.apply(lambda x: f"{x.get('cliente', 'Sem Cliente')} / {x['fornecedor']} (CTT: {x['ctt']})", axis=1)
        sel_ctt = st.selectbox("Escolha o Contrato", df_c['list_name'].tolist())
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
            busca = st.text_input("🔍 Pesquisar...")
            if busca: i_f = i_f[i_f['descricao_item'].str.contains(busca, case=False)]
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
            total_lancado = i_f['vlr_unit'].apply(safe_float).sum()
            valor_contrato = safe_float(row_ctt['valor_contrato'])
            percentual_preechido = (total_lancado / valor_contrato * 100) if valor_contrato > 0 else 0
            with st.container(border=True):
                st.subheader("💰 Resumo Financeiro de Lançamentos")
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Lançado (Itens)", formatar_real(total_lancado))
                c2.metric("Valor Total Contrato", formatar_real(valor_contrato))
                delta = valor_contrato - total_lancado
                if delta < 0:
                    c3.metric("Diferença", formatar_real(delta), delta_color="inverse")
                    st.error(f"Atenção: Os itens superam o contrato em {formatar_real(abs(delta))}!")
                else:
                    c3.metric("Saldo a Lançar", formatar_real(delta))
                st.progress(min(percentual_preechido / 100, 1.0))
                st.caption(f"Você já lançou {percentual_preechido:.2f}% do valor total.")

# --- 6. MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        c_sel = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == c_sel]['contract_id'].values[0]
        i_f = df_i[df_i['contract_id'] == id_c].copy()
        if not i_f.empty:
            i_sel = st.selectbox("Item", i_f['descricao_item'].tolist())
            row = i_f[i_f['descricao_item'] == i_sel].iloc[0]
            p_a = safe_float(df_m[df_m['item_id'] == row['item_id']].sort_values('updated_at').iloc[-1]['percentual_acumulado']) if not df_m.empty and not df_m[df_m['item_id'] == row['item_id']].empty else 0.0
            with st.form("f_m", clear_on_submit=True):
                st.info(f"Progresso Atual: {p_a*100:.2f}%")
                p = st.slider("%", 0, 100, int(p_a * 100)) / 100
                dt = st.date_input("Data", format="DD/MM/YYYY")
                fase = st.selectbox("Fase do Kanban", ["Em execução", "Medição lançada", "Aprovado", "Faturado"])
                if st.form_submit_button("Registrar Medição"):
                    if salvar_dados_otimizado("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * safe_float(row['vlr_unit']), "fase_workflow": f"{fase}", "updated_at": str(datetime.now())}):
                        st.rerun()
            if not df_m.empty: st.dataframe(df_m[df_m['item_id'].isin(i_f['item_id'])].sort_values('updated_at', ascending=False), use_container_width=True, height=200)

# --- 7. KANBAN ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        sel = st.selectbox("Filtrar Contrato:", ["Todos"] + df_c['ctt'].tolist())
        m_f = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            m_f = df_m.sort_values('updated_at').groupby('item_id').tail(1)
            if sel != "Todos":
                m_f = m_f[m_f['item_id'].isin(df_i[df_i['contract_id'] == df_c[df_c['ctt'] == sel]['contract_id'].values[0]]['item_id'])]
        cols = st.columns(4)
        for i, f in enumerate(["Em execução", "Medição lançada", "Aprovado", "Faturado"]):
            with cols[i]:
                st.subheader(f)
                if not m_f.empty and 'fase_workflow' in m_f.columns:
                    for _, card in m_f[m_f['fase_workflow'] == f].iterrows():
                        it_row = df_i[df_i['item_id'] == card['item_id']]
                        if not it_row.empty:
                            with st.container(border=True):
                                st.write(f"**{it_row.iloc[0]['descricao_item']}**")
                                st.caption(f"📑 CTT: {df_c[df_c['contract_id'] == it_row.iloc[0]['contract_id']].iloc[0]['ctt']}")
                                st.write(f"{safe_float(card['percentual_acumulado'])*100:.0f}% | {formatar_real(card['valor_acumulado'])}")

# --- 8. RELATÓRIO (COM EXPORTAÇÃO EXCEL) ---
elif escolha == "Relatório":
    st.title("📝 Relatório de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        sel_ctt = st.selectbox("Selecione o Contrato para Gerar Relatório", df_c['ctt'].tolist())
        con = df_c[df_c['ctt'] == sel_ctt].iloc[0]
        df_m_last = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
        itens_con = df_i[df_i['contract_id'] == con['contract_id']]
        med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'])] if not df_m_last.empty else pd.DataFrame()

        # Botões de Ação
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🖨️ Imprimir Boletim", use_container_width=True):
                st.components.v1.html("<script>window.print();</script>", height=0)
        
        with c2:
            if not med_ctt.empty:
                rel_excel = itens_con.merge(med_ctt, on='item_id', how='left')
                df_export = pd.DataFrame({
                    'Item': rel_excel['descricao_item'],
                    'Valor Unitário': rel_excel['vlr_unit'].apply(safe_float),
                    'Medição (%)': rel_excel['percentual_acumulado'].apply(safe_float),
                    'Medição (R$)': rel_excel['valor_acumulado'].apply(safe_float)
                })
                
                # Gerar Excel em memória
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Boletim')
                processed_data = output.getvalue()
                
                st.download_button(
                    label="📥 Exportar para Excel",
                    data=processed_data,
                    file_name=f"Boletim_{con['ctt']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        with st.container(border=True):
            st.markdown(f"### ANEXO I - Boletim de Medição")
            c1, c2 = st.columns(2)
            c1.write(f"**CTT:** {con['ctt']} - {con['fornecedor']}")
            c1.write(f"**Valor do Contrato:** {formatar_real(con['valor_contrato'])}")
            c1.write(f"**Obra:** {con.get('ctr', '-')} - {con.get('cliente', 'Cliente')}")
            c2.write(f"**Gestor:** {con.get('gestor', '-')}")
            c2.write(f"**Início:** {formatar_data_br(con.get('data_inicio', ''))}")
            c2.write(f"**Fim:** {formatar_data_br(con.get('data_fim', ''))}")
            st.divider()
            if not med_ctt.empty:
                rel = itens_con.merge(med_ctt, on='item_id', how='left')
                rel_view = pd.DataFrame({'Item': rel['descricao_item'], 'VLR UNIT': rel['vlr_unit'].apply(formatar_real), 'Medição %': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Medição R$': rel['valor_acumulado'].apply(formatar_real)})
                st.table(rel_view)
                v_bruto = med_ctt['valor_acumulado'].apply(safe_float).sum()
                v_retencao = v_bruto * 0.15
                v_liquido = v_bruto - v_retencao
                st.divider()
                st.write(f"**Acumulado Bruto:** {formatar_real(v_bruto)}")
                st.write(f"**Retenção (-15%):** - {formatar_real(v_retencao)}")
                st.markdown(f"### **Medição Financeira Líquida (-15%): {formatar_real(v_liquido)}**")
            else: st.warning("Nenhuma medição registrada para este contrato.")

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
