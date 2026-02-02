import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
# COLE SUA URL DO APPS SCRIPT (TERMINADA EM /exec) ENTRE AS ASPAS ABAIXO:
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição Pro", layout="wide")

# --- 2. FUNÇÕES DE SUPORTE (DATA E MOEDA) ---

def formatar_real(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

def formatar_data_br(data_str):
    try:
        return pd.to_datetime(data_str).strftime('%d/%m/%Y')
    except: return data_str

def calcular_status_prazo(data_fim_contrato, data_medicao, percentual):
    """Lógica do Semáforo: Verde (Adiantado), Amarelo (No prazo), Vermelho (Atrasado)"""
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim_contrato).date()
        med = pd.to_datetime(data_medicao).date()
        # Se 100%, usa a data da medição. Se não, usa 'hoje' para ver se já atrasou.
        ref = med if float(percentual) >= 1 else hoje
        dif = (fim - ref).days
        if dif > 0: return f"{dif} dias adiantado", "🟢"
        elif dif == 0: return "No prazo limite", "🟡"
        else: return f"{abs(dif)} dias atrasado", "🔴"
    except: return "Sem dados", "⚪"

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        return pd.DataFrame(r.json()) if r.status_code == 200 else pd.DataFrame()
    except: return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. DASHBOARD FINANCEIRO (MODELO ANEXO I) ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle e Cronograma")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # Totais no Topo
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
            # Cálculos de Retenção e Líquido
            med_ctt = df_m[df_m['item_id'].isin(df_i[df_i['contract_id']==cid]['item_id'])] if not df_m.empty else pd.DataFrame()
            bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            retencao = bruto * 0.15 # Retenção de 15%
            liquido = bruto - retencao
            
            with st.container(border=True):
                st.subheader(f"📄 {con['ctt']} - {con['fornecedor']}")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(retencao)}")
                f3.metric("Líquido a Pagar", formatar_real(liquido))
                f4.metric("Saldo Contrato", formatar_real(float(con['valor_contrato']) - bruto))
                
                if st.button(f"🔍 Detalhar Itens ({con['ctt']})", key=f"btn_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(df_i[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(con['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        
                        # Colunas conforme Anexo I
                        st.table(pd.DataFrame({
                            'Item': rel['descricao_item'],
                            'Valor Unitário': rel['vlr_unit'].apply(formatar_real),
                            'Medição Acumulada %': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medição Acumulada R$': rel['valor_acumulado'].apply(formatar_real),
                            'Data Inicial': formatar_data_br(con['data_inicio']),
                            'Data Final (Real)': rel['data_medicao'].apply(formatar_data_br),
                            'Status Prazo': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        }))
                    else:
                        st.info("Nenhuma medição encontrada.")

# --- PÁGINAS DE CADASTRO (MANTIDAS COM BOTÃO SUBMIT) ---
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.form("f_con"):
        c1, c2 = st.columns(2)
        ctt = c1.text_input("Número CTT")
        forn = c2.text_input("Fornecedor")
        gest = c1.text_input("Gestor")
        vlr = c2.number_input("Valor Total", min_value=0.0)
        d1, d2 = st.columns(2)
        dt_i = d1.date_input("Data Início")
        dt_f = d2.date_input("Data Final")
        if st.form_submit_button("Salvar Contrato"):
            salvar_dados("contracts", {"contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "gestor": gest, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f)})
            st.rerun()

elif escolha == "Itens":
    st.title("🏗️ Gestão de Itens")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel = st.selectbox("Selecione o Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
        with st.form("f_item"):
            desc = st.text_input("Descrição do Item")
            v_u = st.number_input("Valor Unitário", min_value=0.0)
            if st.form_submit_button("Adicionar Item"):
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_c, "descricao_item": desc, "vlr_unit": v_u})
                st.rerun()

elif escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    df_i = carregar_dados("get_items")
    if not df_i.empty:
        sel_i = st.selectbox("Selecione o Item", df_i['descricao_item'].tolist())
        row = df_i[df_i['descricao_item'] == sel_i].iloc[0]
        with st.form("f_med"):
            p = st.slider("Percentual (%)", 0, 100) / 100
            dt = st.date_input("Data da Medição")
            if st.form_submit_button("Registrar"):
                salvar_dados("measurements", {"measurement_id": str(uuid.uuid4()), "item_id": row['item_id'], "data_medicao": str(dt), "percentual_acumulado": p, "valor_acumulado": p * float(row['vlr_unit']), "fase_workflow": "Aprovado", "updated_at": str(datetime.now())})
                st.rerun()
