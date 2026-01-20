import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- 1. CONFIGURAÇÕES ---
# LEMBRE-SE DE COLAR SUA URL ABAIXO
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Sistema de Medição", layout="wide")

# --- 2. FERRAMENTAS DE FORMATAÇÃO ---
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

# --- 4. DASHBOARD (O QUE VOCÊ PEDIU) ---
if escolha == "Dashboard":
    st.title("📊 Painel de Controle Financeiro")
    
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        # A PARTE LEGAL: OS TRÊS TOTAIS NO TOPO
        total_contratado_geral = pd.to_numeric(df_c['valor_contrato']).sum()
        total_medido_geral = pd.to_numeric(df_m['valor_acumulado']).sum() if not df_m.empty else 0
        saldo_geral = total_contratado_geral - total_medido_geral

        st.subheader("Resumo Geral da Operação")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Contratado", formatar_real(total_contratado_geral))
        m2.metric("Total Medido", formatar_real(total_medido_geral))
        m3.metric("Saldo a Medir", formatar_real(saldo_geral))
        
        st.divider()

        # FILTRO POR GESTOR
        gestores = ["Todos"] + sorted(df_c['gestor'].unique().tolist())
        gestor_sel = st.selectbox("🎯 Filtrar Visão por Gestor", gestores)
        
        df_f = df_c.copy()
        if gestor_sel != "Todos":
            df_f = df_f[df_f['gestor'] == gestor_sel]

        st.write("### Detalhamento por Contrato")

        for _, contrato in df_f.iterrows():
            cid = contrato['contract_id']
            itens_ctt = df_i[df_i['contract_id'] == cid] if not df_i.empty else pd.DataFrame()
            ids_itens = itens_ctt['item_id'].tolist() if not itens_ctt.empty else []
            med_ctt = df_m[df_m['item_id'].isin(ids_itens)] if not df_m.empty else pd.DataFrame()
            
            # Cálculos Financeiros Individuais
            vlr_contrato = float(contrato['valor_contrato'])
            vlr_bruto = pd.to_numeric(med_ctt['valor_acumulado']).sum() if not med_ctt.empty else 0
            vlr_retencao = vlr_bruto * 0.15
            vlr_liquido = vlr_bruto - vlr_retencao
            saldo_contrato = vlr_contrato - vlr_bruto

            # --- CARD DO CONTRATO REORGANIZADO ---
            with st.container(border=True):
                st.markdown(f"#### 📄 {contrato['ctt']} - {contrato['fornecedor']}")
                
                # Info do Contrato
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Gestor:** {contrato['gestor']}")
                c2.write(f"**Obra:** {contrato['obra']}")
                c3.write(f"**Vlr Total Contrato:** {formatar_real(vlr_contrato)}")

                # Quadro Financeiro Expandido
                st.markdown("---")
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Bruto Medido", formatar_real(vlr_bruto))
                f2.metric("Retenção (15%)", f"- {formatar_real(vlr_retencao)}", delta_color="inverse")
                f3.metric("Líquido a Pagar", formatar_real(vlr_liquido))
                f4.metric("Saldo do Contrato", formatar_real(saldo_contrato))

                # Botão na última linha
                if st.button(f"🔍 Abrir Boletim Completo ({contrato['ctt']})", key=f"btn_{cid}", use_container_width=True):
                    if not med_ctt.empty:
                        rel = med_ctt.merge(itens_ctt[['item_id', 'descricao_item', 'vlr_unit']], on='item_id')
                        rel['Status'] = rel.apply(lambda x: calcular_status_prazo(contrato['data_fim'], x['data_medicao'], x['percentual_acumulado']), axis=1)
                        
                        rel_view = pd.DataFrame({
                            'Item': rel['descricao_item'],
                            'Valor Unitário': rel['vlr_unit'].apply(formatar_real),
                            'Medição acumulada %': rel['percentual_acumulado'].apply(lambda x: f"{float(x)*100:.2f}%"),
                            'Medição Acumulada R$': rel['valor_acumulado'].apply(formatar_real),
                            'Saldo a medir': rel.apply(lambda x: formatar_real(float(x['vlr_unit']) - float(x['valor_acumulado'])), axis=1),
                            'Data Inicial': formatar_data_br(contrato['data_inicio']),
                            'Data Final': rel['data_medicao'].apply(formatar_data_br),
                            'Prazo': rel['Status'].apply(lambda x: f"{x[1]} {x[0]}")
                        })
                        st.table(rel_view)
                    else:
                        st.warning("Nenhuma medição lançada.")

# --- OUTRAS PÁGINAS (CONT./ITENS/MED./KANBAN) ---
# (CÓDIGO SEGUE A MESMA LÓGICA DAS VERSÕES ANTERIORES PARA NÃO DAR ERRO)
elif escolha == "Contratos":
    st.title("📄 Cadastro de Contratos")
    with st.expander("➕ Novo Contrato"):
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
        sel = st.selectbox("Escolha o Contrato", df_c['ctt'].tolist())
        id_c = df_c[df_c['ctt'] == sel]['contract_id'].values[0]
        with st.form("f_item"):
            d = st.text_input("Descrição do Item")
            v = st.number_input("Valor Unitário", min_value=0.0, format="%.2f")
            if st.form_submit_button("Adicionar"):
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
                p = st.slider("Percentual (%)", 0, 100) / 100
