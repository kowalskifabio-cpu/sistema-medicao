import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
URL_DO_APPS_SCRIPT = "SUA_URL_AQUI"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição", layout="wide")

# --- 2. FERRAMENTAS ---
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

# --- 3. MENU ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição", "Kanban"]
escolha = st.sidebar.selectbox("Navegação", menu)

# --- 4. DASHBOARD REESTRUTURADO ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle Financeiro")
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # Filtros de Topo
        col_f1, col_f2 = st.columns(2)
        gestores = ["Todos"] + sorted(df_c['gestor'].unique().tolist())
        gestor_sel = col_f1.selectbox("Filtrar por Gestor", gestores)
        
        df_f = df_c.copy()
        if gestor_sel != "Todos":
            df_f = df_f[df_f['gestor'] == gestor_sel]

        st.divider()

        for _, contrato in df_f.iterrows():
            cid = contrato['contract_id']
            itens_ctt = df_i[df_i['contract_id'] == cid] if not df_i.empty else pd.DataFrame()
            ids_itens = itens_ctt['item_id'].tolist() if not itens_ctt.empty else []
            med_ctt = df_m[df_m['item_id'].isin(ids_itens)] if not df_m.empty else pd.DataFrame()
            
            # Cálculos Financeiros conforme Anexo I
            vlr_contrato = float(contrato['valor_contrato'])
            vlr_bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            vlr_retencao = vlr_bruto * 0.15
            vlr_liquido = vlr_bruto - vlr_retencao
            saldo_a_medir = vlr_contrato - vlr_bruto

            # --- NOVO DESIGN DO CARD ---
            with st.container(border=True):
                # Linha 1: Cabeçalho
                st.subheader(f"📄 Contrato: {contrato['ctt']} - {contrato['fornecedor']}")
                
                # Linha 2: Informações Gerais
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Gestor:** {contrato['gestor']}")
                c2.write(f"**Obra:** {contrato['obra']}")
                c3.write(f"**Vlr Total Contrato:** {formatar_real(vlr_contrato)}")

                # Linha 3: Bloco Financeiro (Expandido para baixo)
                st.markdown("#### Resumo Financeiro")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(vlr_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(vlr_retencao)}", delta_color="inverse")
                f3.metric("Líquido a Pagar", formatar_real(vlr_liquido))
                f4.metric("Saldo a Medir", formatar_real(saldo_a_medir))

                # Linha 4: Botão Sozinho na base
                if st.button(f"🔍 Abrir Boletim de Medição Completo ({contrato['ctt']})", key=f"btn_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_ctt[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(contrato['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        
                        # Colunas solicitadas no Anexo
                        rel_view = pd.DataFrame({
                            'Item': rel['descricao_item'],
                            'Valor Unitário': rel['vlr_unit'].apply(formatar_real),
                            'Medição acumulada %': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medição Acumulada R$': rel['valor_acumulado'].apply(formatar_real),
                            'Saldo a medir': rel.apply(lambda x: formatar_real(float(x['vlr_unit']) - float(x['valor_acumulado'])), axis=1),
                            'Data Inicial': formatar_data_br(contrato['data_inicio']),
                            'Data Final (Real)': rel['data_medicao'].apply(formatar_data_br),
                            'Prazo': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        })
                        st.table(rel_view)
                    else:
                        st.warning("Nenhuma medição para detalhar.")

# (Manter as outras páginas Contratos, Itens, Medição e Kanban conforme código anterior)
