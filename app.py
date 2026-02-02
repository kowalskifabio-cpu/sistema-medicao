import streamlit as st
import pandas as pd
import requests
import uuid
from datetime import datetime

# --- CONFIGURAÇÕES ---
# O segredo da vida do sistema está nestas duas linhas abaixo:
URL_DO_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbzgnCmVZURdpN6LF54lYWyNSeVLvV36FQwB9DMSa2_lEF8Nm-lsvYzv_qmqibe-hcRp/exec"
TOKEN = "CHAVE_SEGURA_123"

st.set_page_config(page_title="Gestão de Medições Pro", layout="wide")

# --- FUNÇÕES DE LIMPEZA E BUSCA ---
@st.cache_data(ttl=10) # Atualiza os dados a cada 10 segundos
def carregar_dados(acao):
    try:
        r = requests.get(URL_DO_APPS_SCRIPT, params={"token": TOKEN, "action": acao}, timeout=20)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def formatar_real(valor):
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "R$ 0,00"

# --- MENU ---
menu = ["Dashboard", "Contratos", "Itens", "Lançar Medição"]
escolha = st.sidebar.selectbox("Navegação", menu)

# --- TELA DE LANÇAMENTO (COM MEMÓRIA) ---
if escolha == "Lançar Medição":
    st.title("📏 Lançamento de Medição")
    
    # Buscamos os dados atualizados
    df_c = carregar_dados("get_contracts")
    df_i = carregar_dados("get_items")
    df_m = carregar_dados("get_measurements")
    
    if not df_c.empty:
        ctt_sel = st.selectbox("1. Selecione o Contrato", df_c['ctt'].tolist())
        id_ctt = df_c[df_c['ctt'] == ctt_sel]['contract_id'].values[0]
        
        itens_f = df_i[df_i['contract_id'] == id_ctt]
        
        if not itens_f.empty:
            item_sel = st.selectbox("2. Selecione o Item", itens_f['descricao_item'].tolist())
            row_i = itens_f[itens_f['descricao_item'] == item_sel].iloc[0]
            
            # BUSCA O ÚLTIMO PERCENTUAL NO HISTÓRICO
            perc_anterior = 0.0
            if not df_m.empty:
                historico = df_m[df_m['item_id'] == row_i['item_id']]
                if not historico.empty:
                    # Pegamos o valor da última medição feita
                    perc_anterior = float(historico.iloc[-1]['percentual_acumulado'])

            with st.form("form_final"):
                st.write(f"📈 **Progresso Anterior:** {perc_anterior*100:.2f}%")
                
                # O slider agora "nasce" no valor anterior
                novo_p = st.slider("Novo Percentual (%)", 0, 100, int(perc_anterior*100)) / 100
                
                v_calc = novo_p * float(row_i['vlr_unit'])
                st.info(f"Valor Acumulado Final: {formatar_real(v_calc)}")
                
                if st.form_submit_button("✅ Registrar Medição"):
                    payload = {
                        "token": TOKEN, "table": "measurements", "data": {
                            "measurement_id": str(uuid.uuid4()), "item_id": row_i['item_id'],
                            "data_medicao": str(datetime.now().date()), "percentual_acumulado": novo_p,
                            "valor_acumulado": v_calc, "fase_workflow": "Aprovado", "updated_at": str(datetime.now())
                        }
                    }
                    requests.post(URL_DO_APPS_SCRIPT, json=payload)
                    st.success("Medição salva! Atualizando...")
                    st.rerun()
        else: st.warning("Adicione itens a este contrato primeiro.")
    else: st.error("Nenhum contrato encontrado. Verifique a URL do Apps Script.")

# --- DASHBOARD DE RECUPERAÇÃO ---
elif escolha == "Dashboard":
    st.title("📊 Resumo de Contratos")
    df_c = carregar_dados("get_contracts")
    if not df_c.empty:
        st.write("### Seus contratos salvos no Google:")
        st.dataframe(df_c[['ctt', 'fornecedor', 'gestor', 'valor_contrato']])
    else:
        st.error("O site não conseguiu ler sua planilha. Verifique a URL na linha 15 do código.")
           
