import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES INICIAIS ---
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

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
    try:
        hoje = datetime.now().date()
        fim = pd.to_datetime(data_fim_contrato).date()
        med = pd.to_datetime(data_medicao).date()
        data_ref = med if float(percentual) >= 1 else hoje
        dif = (fim - data_ref).days
        if dif > 0: return f"{dif} dias adiantado", "🟢"
        elif dif == 0: return "No prazo", "🟡"
        else: return f"{abs(dif)} dias atrasado", "🔴"
    except: return "Sem dados", "⚪"

def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao})
        return pd.DataFrame(r.json())
    except: return pd.DataFrame()

def salvar_dados(tabela, dados, acao="create", id_field=None, id_value=None):
    payload = {"token": TOKEN, "table": tabela, "data": dados, "action": acao, "id_field": id_field, "id_value": id_value}
    requests.post(URL_DO_APPS_SCRIPT, json=payload)

# --- 3. MENU LATERAL ---
st.sidebar.title("Navegação")
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Ir para:", menu)

# --- 4. LÓGICA DAS PÁGINAS ---

if escolha == "Dashboard":
    st.title("📊 Painel de Controle e Financeiro")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # --- FILTROS NO DASHBOARD ---
        col_f1, col_f2 = st.columns(2)
        gestores = ["Todos"] + sorted(df_c['gestor'].unique().tolist())
        gestor_sel = col_f1.selectbox("Filtrar por Gestor", gestores)
        
        status_prazo_filtro = col_f2.selectbox("Filtrar por Status", ["Todos", "🟢 Adiantado", "🔴 Atrasado"])

        # Filtragem do DataFrame principal
        df_filtrado = df_c.copy()
        if gestor_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado['gestor'] == gestor_sel]

        # Métricas Gerais
        total_contratado = pd.to_numeric(df_filtrado['valor_contrato']).sum()
        total_medido = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado (Filtrado)", formatar_real(total_contratado))
        m2.metric("Total Medido Geral", formatar_real(total_medido))
        m3.metric("Saldo Geral", formatar_real(total_contratado - total_medido))
        
        st.divider()
        st.subheader("📋 Resumo Financeiro por Contrato (com Retenção 15%)")
        
        for _, contrato in df_filtrado.iterrows():
            cid = contrato['contract_id']
            itens_ctt = df_i[df_i['contract_id'] == cid] if not df_i.empty else pd.DataFrame()
            ids_itens = itens_ctt['item_id'].tolist() if not itens_ctt.empty else []
            med_ctt = df_m[df_m['item_id'].isin(ids_itens)] if not df_m.empty else pd.DataFrame()
            
            vlr_bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            vlr_retencao = vlr_bruto * 0.15
            vlr_liquido = vlr_bruto - vlr_retencao
            saldo_total = float(contrato['valor_contrato']) - vlr_bruto
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.markdown(f"**Contrato:** {contrato['ctt']} | **Gestor:** {contrato['gestor']}  \n**Obra:** {contrato['obra']}")
                
                # Quadro Financeiro conforme Anexo
                with c2:
                    f_col1, f_col2 = st.columns(2)
                    f_col1.write(f"**Bruto Medido:** {formatar_real(vlr_bruto)}")
                    f_col1.write(f"**Retenção (15%):** -{formatar_real(vlr_retencao)}")
                    f_col2.write(f"**Líquido a Pagar:** \n### {formatar_real(vlr_liquido)}")
                
                if c3.button(f"📄 Boletim Detalhado", key=f"btn_{cid}"):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_ctt[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(contrato['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        rel['Status Visual'] = rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        
                        # Formatação de colunas
                        rel['Item'] = rel['descricao_item']
                        rel['Vlr Unit'] = rel['vlr_unit'].apply(formatar_real)
                        rel['% Medido'] = rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%")
                        rel['Medido R$'] = rel['valor_acumulado'].apply(formatar_real)
                        rel['Saldo Item'] = rel.apply(lambda x: formatar_real(float(x['vlr_unit']) - float(x['valor_acumulado'])), axis=1)
                        
                        st.table(rel[['Item', 'Vlr Unit', 'Data Medição', '% Medido', 'Medido R$', 'Saldo Item', 'Status Visual']])
                        st.caption(f"Cronograma: Início {formatar_data_br(contrato['data_inicio'])} | Fim Contratual {formatar_data_br(contrato['data_fim'])}")
                    else:
                        st.warning("Sem medições lançadas.")

# (Manter as outras páginas: Contratos, Itens, Medição e Kanban iguais à versão anterior)
