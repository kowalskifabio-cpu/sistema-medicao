import streamlit as st
import pandas as pd
from supabase import create_client
import uuid
import io
import pdfplumber
import re
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MAPA_TABELAS = {
    "contracts": "medicao_contracts",
    "items": "medicao_items",
    "measurements": "medicao_measurements"
}

MAPA_ACOES = {
    "get_contracts": "medicao_contracts",
    "get_items": "medicao_items",
    "get_measurements": "medicao_measurements"
}

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- FUNÇÃO DE LEITURA DE PDF (Extração Inteligente) ---
def extrair_dados_ctt(pdf_file):
    dados = {"itens": []}
    with pdfplumber.open(pdf_file) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += page.extract_text() + "\n"
        
        ctt_match = re.search(r'Número:\s*"?(\d+)', texto_completo)
        cliente_match = re.search(r'STATUS\s+MARCENARIA', texto_completo)
        fornecedor_match = re.search(r'Nome:\s*\n\n(.*?)\n\nCONTRATADO', texto_completo, re.DOTALL)
        
        if ctt_match: dados["ctt"] = ctt_match.group(1)
        if cliente_match: dados["cliente"] = "STATUS MARCENARIA"
        if fornecedor_match: dados["fornecedor"] = fornecedor_match.group(1).strip()
        
        item_regex = r"ITEM\s+\d+[- ]+(.*?)\s*-\s*R\$\s*([\d.,]+)"
        itens_encontrados = re.findall(item_regex, texto_completo)
        
        valor_total = 0.0
        for desc, valor in itens_encontrados:
            v_float = float(valor.replace('.', '').replace(',', '.'))
            dados["itens"].append({"desc": desc.strip(), "valor": v_float})
            valor_total += v_float
        dados["valor_total"] = valor_total
    return dados

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
        tabela = MAPA_ACOES.get(acao)

        if not tabela:
            st.error(f"Ação não mapeada: {acao}")
            return pd.DataFrame()

        res = supabase.table(tabela).select("*").execute()
        return pd.DataFrame(res.data or [])

    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
        return pd.DataFrame()

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
    tabela_supabase = MAPA_TABELAS.get(tabela)

    if not tabela_supabase:
        st.error(f"Tabela não mapeada: {tabela}")
        return False

    with st.spinner("Sincronizando com Supabase..."):
        try:
            if acao == "create":
                supabase.table(tabela_supabase).insert(dados).execute()

            elif acao == "update":
                if not id_field or id_value is None:
                    st.error("Update sem campo de ID.")
                    return False

                supabase.table(tabela_supabase).update(dados).eq(id_field, id_value).execute()

            elif acao == "delete":
                if not id_field or id_value is None:
                    st.error("Delete sem campo de ID.")
                    return False

                supabase.table(tabela_supabase).delete().eq(id_field, id_value).execute()

            else:
                st.error(f"Ação desconhecida: {acao}")
                return False

            st.cache_data.clear()
            return True

        except Exception as e:
            st.error(f"Erro ao salvar no Supabase: {e}")
            return False

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
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban", "Relatório", "📁 CTRs Concluídas"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. DASHBOARD ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle (Ativos)")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
    if not df_c.empty:
        df_m_last = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
        t_con = pd.to_numeric(df_c['valor_contrato'], errors='coerce').fillna(0).sum()

        t_med = 0
        
        if (
            not df_m_last.empty and
            not df_i.empty and
            'contract_id' in df_i.columns and
            'item_id' in df_i.columns and
            'item_id' in df_m_last.columns
        ):
            itens_validos = df_i[
                df_i['contract_id'].isin(df_c['contract_id'])
            ]['item_id']
        
            t_med = (
                df_m_last[
                    df_m_last['item_id'].isin(itens_validos)
                ]['valor_acumulado']
                .apply(safe_float)
                .sum()
            )
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(t_con))
        m2.metric("Total Medido", formatar_real(t_med))
        m3.metric("Saldo Geral", formatar_real(t_con - t_med))
        st.divider()
        gestores = (
            df_c["gestor"]
            .fillna("Sem gestor")
            .astype(str)
            .str.strip()
        )
        
        gestores = sorted([g for g in gestores.unique().tolist() if g != ""])
        
        gestor_sel = st.selectbox(
            "Filtrar por Gestor",
            ["Todos"] + gestores
        )
        
        if gestor_sel == "Sem gestor":
            df_f = df_c[df_c["gestor"].isna() | (df_c["gestor"].astype(str).str.strip() == "")]
        elif gestor_sel == "Todos":
            df_f = df_c
        else:
            df_f = df_c[df_c["gestor"].astype(str).str.strip() == gestor_sel]
        df_f = df_c if gestor_sel == "Todos" else df_c[df_c['gestor'] == gestor_sel]
        for _, con in df_f.iterrows():
            cid = con['contract_id']
            itens_con = df_i[df_i['contract_id']==cid] if not df_i.empty else pd.DataFrame()
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'].tolist())] if not df_m_last.empty and not itens_con.empty else pd.DataFrame()
            farol = "🟡" if med_ctt.empty else ("🔴" if any((pd.to_datetime(r.get('data_fim_item', con['data_fim'])).date() - datetime.now().date()).days < 0 and safe_float(r['percentual_acumulado']) < 1 for _, r in med_ctt.merge(itens_con, on='item_id').iterrows()) else "🟢")
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
                        rel = med_ctt.merge(itens_con, on='item_id')
                        st.table(pd.DataFrame({'Item': rel['descricao_item'], 'Vlr Unit.': rel['vlr_unit'].apply(formatar_real), '% Acum.': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Medido R$': rel['valor_acumulado'].apply(formatar_real)}))
                if c2.button("✅ Concluir", key=f"btn_done_{cid}", use_container_width=True):
                    if salvar_dados_otimizado("contracts", {"status": "Concluído"}, "update", "contract_id", cid): st.rerun()

# --- 5. ITENS ---
elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
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
                        if salvar_dados_otimizado("items", {"item_id": str(uuid.uuid4()), "contract_id": row_ctt['contract_id'], "descricao_item": desc, "vlr_unit": v_u, "data_fim_item": str(dt)}): st.rerun()
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

# --- 6. MEDIÇÃO ---
elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
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
                        if salvar_dados_otimizado("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * safe_float(row['vlr_unit']), "fase_workflow": fase, "updated_at": str(datetime.now())}): st.rerun()

# --- 7. KANBAN ---
elif escolha == "Kanban":
    st.title("📋 Quadro Kanban (Ativos)")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_c = df_c[df_c['status'] == 'Ativo']
        sel = st.selectbox("Filtrar por Contrato:", ["Todos"] + df_c['ctt'].tolist())
        m_f = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            m_f = df_m.sort_values('updated_at').groupby('item_id').tail(1)
            if sel != "Todos":
                cid = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
                m_f = m_f[m_f['item_id'].isin(df_i[df_i['contract_id'] == cid]['item_id'])]
        cols = st.columns(4)
        for i, f in enumerate(["Em execução", "Medição lançada", "Aprovado", "Faturado"]):
            with cols[i]:
                st.subheader(f)
                if not m_f.empty:
                    for _, card in m_f[m_f['fase_workflow'] == f].iterrows():
                        it = df_i[df_i['item_id'] == card['item_id']]
                        if not it.empty:
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
        sel_ctt = st.selectbox("Selecione o Contrato", df_at['ctt'].tolist())
        con = df_at[df_at['ctt'] == sel_ctt].iloc[0]
        df_m_last = pd.DataFrame()
        if not df_m.empty:
            df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
            df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
        itens_con = df_i[df_i['contract_id'] == con['contract_id']]
        med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'])] if not df_m_last.empty else pd.DataFrame()
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🖨️ Imprimir", use_container_width=True): st.components.v1.html("<script>window.print();</script>", height=0)
        with c2:
            if not med_ctt.empty:
                rel_ex = itens_con.merge(med_ctt, on='item_id', how='left')
                v_bruto = rel_ex['valor_acumulado'].apply(safe_float).sum(); v_ret = v_bruto * 0.15; v_liq = v_bruto - v_ret
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_header = pd.DataFrame([["BOLETIM", ""], ["Obra:", f"{con.get('ctr', '-')} - {con.get('cliente', 'Cliente')}"], ["Data:", datetime.now().strftime('%d/%m/%Y')]])
                    df_header.to_excel(writer, index=False, header=False, sheet_name='Boletim')
                    df_items_ex = pd.DataFrame({'Item': rel_ex['descricao_item'], 'Vlr Unit': rel_ex['vlr_unit'].apply(safe_float), 'Med %': rel_ex['percentual_acumulado'].apply(safe_float), 'Med R$': rel_ex['valor_acumulado'].apply(safe_float)})
                    df_items_ex.to_excel(writer, index=False, startrow=len(df_header), sheet_name='Boletim')
                st.download_button(label="📥 Excel", data=output.getvalue(), file_name=f"Boletim_{con['ctt']}.xlsx", use_container_width=True)

# --- 9. CTRs CONCLUÍDAS (FUNÇÃO DE REABERTURA) ---
elif escolha == "📁 CTRs Concluídas":
    st.title("📂 Histórico de CTRs Concluídas")
    df_c = carregar_dados("get_contracts"); df_i = carregar_dados("get_items"); df_m = carregar_dados("get_measurements")
    if not df_c.empty:
        df_done = df_c[df_c['status'] == 'Concluído']
        if df_done.empty: st.info("Nenhuma CTR concluída.")
        else:
            sel_hist = st.selectbox("Selecione para visualizar ou REABRIR", df_done['ctt'].tolist())
            con = df_done[df_done['ctt'] == sel_hist].iloc[0]
            cid = con['contract_id']
            
            # BLOCO DE REABERTURA
            st.warning("⚠️ Deseja reativar esta CTR para novos lançamentos?")
            if st.button("🔄 Reabrir Contrato (Voltar para Ativos)", use_container_width=True):
                if salvar_dados_otimizado("contracts", {"status": "Ativo"}, "update", "contract_id", cid):
                    st.success(f"Contrato {con['ctt']} reativado!")
                    st.rerun()
            st.divider()

            df_m_last = pd.DataFrame()
            if not df_m.empty:
                df_m['updated_at'] = pd.to_datetime(df_m['updated_at'], errors='coerce')
                df_m_last = df_m.sort_values('updated_at').groupby('item_id').tail(1)
            itens_con = df_i[df_i['contract_id'] == con['contract_id']]
            med_ctt = df_m_last[df_m_last['item_id'].isin(itens_con['item_id'])] if not df_m_last.empty else pd.DataFrame()
            if not med_ctt.empty:
                rel = itens_con.merge(med_ctt, on='item_id', how='left')
                st.table(pd.DataFrame({'Item': rel['descricao_item'], 'Med % Final': rel['percentual_acumulado'].apply(lambda x: f"{safe_float(x)*100:.2f}%"), 'Med R$ Final': rel['valor_acumulado'].apply(formatar_real)}))

# --- 10. CONTRATOS (IMPORTAÇÃO PDF) ---
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.expander("📥 Importar Dados de PDF (Padrão CTT)"):
        uploaded_file = st.file_uploader("Arraste o PDF aqui", type="pdf")
        if uploaded_file and st.button("Ler PDF"):
            st.session_state['pdf_data'] = extrair_dados_ctt(uploaded_file)
            st.success("Dados extraídos!")
    
    pdf_info = st.session_state.get('pdf_data', {})
    with st.form("f_con", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cl = c1.text_input("Cliente", value=pdf_info.get("cliente", ""))
        ctr = c2.text_input("CTR", value=pdf_info.get("ctt", ""))
        fo = c1.text_input("Fornecedor", value=pdf_info.get("fornecedor", ""))
        ctt = c2.text_input("CTT", value=pdf_info.get("ctt", ""))
        gs = c1.text_input("Gestor")
        vl = c2.number_input("Valor Total", value=safe_float(pdf_info.get("valor_total", 0.0)))
        dt_i = st.date_input("Início"); dt_f = st.date_input("Fim")
        if st.form_submit_button("Salvar Contrato e Itens"):
            new_cid = str(uuid.uuid4())
            if salvar_dados_otimizado("contracts", {"contract_id": new_cid, "cliente": cl, "ctr": ctr, "fornecedor": fo, "ctt": ctt, "gestor": gs, "valor_contrato": vl, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"}):
                for item in pdf_info.get("itens", []):
                    salvar_dados_otimizado("items", {"item_id": str(uuid.uuid4()), "contract_id": new_cid, "descricao_item": item["desc"], "vlr_unit": item["valor"], "data_fim_item": str(dt_f)})
                if 'pdf_data' in st.session_state: del st.session_state['pdf_data']
                st.rerun()
