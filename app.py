import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição Pro", layout="wide")

# --- 2. FUNÇÕES DE SUPORTE ---

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
    """Retorna os dias, a cor e o ícone do status"""
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim_contrato).date()
        med = pd.to_datetime(data_medicao).date()
        
        # Se já concluiu (100%), comparamos a data da medição com o fim do contrato
        data_referencia = med if float(percentual) >= 1 else hoje
        diferenca = (fim - data_referencia).days
        
        if diferenca > 0:
            return f"{diferenca} dias adiantado", "🟢"
        elif diferenca == 0:
            return "No prazo limite", "🟡"
        else:
            return f"{abs(diferenca)} dias atrasado", "🔴"
    except:
        return "Sem dados", "⚪"

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

if escolha == "Dashboard":
    st.title("📊 Painel de Controle")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        total_c = pd.to_numeric(df_c['valor_contrato']).sum()
        total_m = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Contratado", formatar_real(total_c))
        c2.metric("Total Medido", formatar_real(total_m))
        c3.metric("Saldo a Medir", formatar_real(total_c - total_m))
        
        st.divider()
        st.subheader("📋 Resumo por Contrato")
        
        for _, contrato in df_c.iterrows():
            cid = contrato['contract_id']
            itens_ctt = df_i[df_i['contract_id'] == cid] if not df_i.empty else pd.DataFrame()
            ids_itens = itens_ctt['item_id'].tolist() if not itens_ctt.empty else []
            med_ctt = df_m[df_m['item_id'].isin(ids_itens)] if not df_m.empty else pd.DataFrame()
            
            soma_medido = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                col1.markdown(f"**Contrato:** {contrato['ctt']}  \n**Gestor:** {contrato['gestor']}  \n**Fornecedor:** {contrato['fornecedor']}")
                col2.write(f"**Data Inicial:** {formatar_data_br(contrato['data_inicio'])}")
                col3.write(f"**Data Final:** {formatar_data_br(contrato['data_fim'])}")
                col4.write(f"**Saldo Total:** \n{formatar_real(float(contrato['valor_contrato']) - soma_medido)}")
                
                if st.button(f"📄 Detalhar Cronograma {contrato['ctt']}", key=f"btn_{cid}"):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_ctt[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        
                        # Aplicando lógica de status para cada item
                        rel['Status Prazo'] = rel.apply(lambda x: calcular_status_prazo(contrato['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        rel['Dias/Status'] = rel['Status Prazo'].apply(lambda x: f"{x[1]} {x[0]}")
                        
                        rel['Data Medição'] = rel['data_medicao'].apply(formatar_data_br)
                        rel['Valor Unitário'] = rel['vlr_unit'].apply(formatar_real)
                        rel['% Acumulado'] = rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%")
                        rel['Medido R$'] = rel['valor_acumulado'].apply(formatar_real)
                        
                        st.table(rel[['descricao_item', 'Valor Unitário', 'Data Medição', '% Acumulado', 'Medido R$', 'Dias/Status']])
                    else:
                        st.warning("Sem medições para este contrato.")

elif escolha == "Contratos":
    st.title("📄 Gestão de Contratos")
    with st.expander("➕ Cadastrar Novo Contrato"):
        with st.form("f_con"):
            c1, c2 = st.columns(2)
            ctt = c1.text_input("Número CTT")
            forn = c2.text_input("Fornecedor")
            obra = c1.text_input("Obra")
            gest = c2.text_input("Gestor")
            vlr = c1.number_input("Valor Total", min_value=0.0, format="%.2f")
            d1, d2 = st.columns(2)
            dt_i = d1.date_input("Data Inicial", format="DD/MM/YYYY")
            dt_f = d2.date_input("Data Final", format="DD/MM/YYYY")
            if st.form_submit_button("Salvar"):
                salvar_dados("contracts", {
                    "contract_id": str(uuid.uuid4()), "ctt": ctt, "fornecedor": forn, "obra": obra,
                    "gestor": gest, "valor_contrato": vlr, "data_inicio": str(dt_i), "data_fim": str(dt_f), "status": "Ativo"
                })
                st.rerun()
    st.dataframe(carregar_dados("get_contracts"))

elif escolha == "Itens":
    st.title("🏗️ Itens do Contrato")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        sel = st.selectbox("Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
        with st.form("f_item"):
            d = st.text_input("Descrição")
            v = st.number_input("Vlr Unit", min_value=0.0, format="%.2f")
            if st.form_submit_button("Add"):
                salvar_dados("items", {"item_id": str(uuid.uuid4()), "contract_id": id_c, "descricao_item": d, "vlr_unit": v})
                st.rerun()
        df_i = carregar_dados("get_items")
        if not df_i.empty:
            st.dataframe(df_i[df_i['contract_id'] == id_c])

elif escolha == "Lançar Medição":
    st.title("📏 Lançar Medição")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    if not df_c.empty:
        c_mae = st.selectbox("Contrato", df_c['ctt'].tolist())
        id_m = df_c[df_c['ctt'] == c_mae]['contract_id'].values[0]
        i_f = df_i[df_i['contract_id'] == id_m]
        if not i_f.empty:
            i_sel = st.selectbox("Item", i_f['descricao_item'].tolist())
            row = i_f[i_f['descricao_item'] == i_sel].iloc[0]
            with st.form("f_m"):
                p = st.slider("%", 0, 100) / 100
                dt = st.date_input("Data Medição", format="DD/MM/YYYY")
                f = st.selectbox("Fase", ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado"])
                if st.form_submit_button("Lançar"):
                    salvar_dados("measurements", {
                        "measurement_id": str(uuid.uuid4()), "item_id": row['item_id'],
                        "data_medicao": str(dt), "percentual_acumulado": p,
                        "valor_acumulado": p * float(row['vlr_unit']), "fase_workflow": f, "updated_at": str(datetime.now())
                    })
                    st.success("Lançado!")

elif escolha == "Kanban":
    st.title("📋 Kanban")
    df_m = carregar_dados("get_measurements")
    df_i = carregar_dados("get_items")
    if not df_m.empty:
        for f in ["Em execução", "Aguardando aprovação", "Medição lançada", "Aprovado"]:
            st.subheader(f)
            cards = df_m[df_m['fase_workflow'] == f]
            for _, c in cards.iterrows():
                with st.container(border=True):
                    st.write(c['measurement_id']) # Simplificado para exemplo
