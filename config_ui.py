import streamlit as st
import os
import datetime
import pandas as pd
from database_manager import DatabaseManager
from auth import hash_password, verify_password, is_strong_password
from frota_ui import frota_tab
from locatarios_ui import locatarios_tab
from dotenv import load_dotenv
import extra_streamlit_components as stx

cookie_manager = stx.CookieManager()

# --- Utility Functions ---

def load_env_vars():
    # Still load native .env for baseline DB connections
    load_dotenv()
    db = DatabaseManager()
    db_configs = db.get_all_configs()
    
    # Merge os.environ with the persistent database configs (DB overrides .env)
    merged_env = dict(os.environ)
    merged_env.update(db_configs)
    
    # Also inject them back to os.environ so other modules like asaas_client.py 
    # relying strictly on os.getenv can find them without code changes!
    for k, v in db_configs.items():
        os.environ[k] = str(v)
        
    return merged_env

def save_env_var(key, value):
    db = DatabaseManager()
    db.set_config(key, value)
    os.environ[key] = str(value)

def format_currency(value):
    try:
        val = float(value)
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return value

def init_session_state():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
                
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None
    if "user_permissions" not in st.session_state:
        st.session_state.user_permissions = ""

    if "cookie_sync_attempts" not in st.session_state:
        st.session_state.cookie_sync_attempts = 0

    # Synchronize cookies
    if "cookies_synced" not in st.session_state:
        # We only call get_all() ONCE per script run to avoid StreamlitDuplicateElementKey
        cookies = cookie_manager.get_all(key="cookie_sync")
        
        # extra-streamlit-components returns an empty dict initially
        if len(cookies.keys()) == 0 and st.session_state.cookie_sync_attempts < 2:
            st.session_state.cookie_sync_attempts += 1
            return False # Not yet synced
            
        st.session_state.cookies_synced = True
        st.session_state.cached_cookies = cookies

    # Check for remember me cookie
    if not st.session_state.logged_in:
        # Reuse the cookies dict we got earlier, or get it once if somehow bypassed
        cookies = st.session_state.get("cached_cookies", cookie_manager.get_all(key="cookie_login"))
        rem_user = cookies.get("locamotos_user")
        if rem_user:
            db = DatabaseManager()
            user = db.get_user_by_username(rem_user)
            if user:
                user_id, nome, username_db, email_db, senha_hash, papel, status, permissoes, created_at = user
                if status == "aprovado":
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.session_state.user_name = nome
                    st.session_state.user_role = papel
                    st.session_state.user_permissions = permissoes
    return True

def do_login(username_login, password, lembrar_user):
    db = DatabaseManager()
    user = db.get_user_by_username(username_login)
    if user:
        user_id, nome, username_db, email_db, senha_hash, papel, status, permissoes, created_at = user
        if verify_password(senha_hash, password):
            if status == "aprovado":
                if lembrar_user:
                    st.session_state.cookie_to_set = username_db
                    
                st.session_state.logged_in = True
                st.session_state.user_id = user_id
                st.session_state.user_name = nome
                st.session_state.user_role = papel
                st.session_state.user_permissions = permissoes
                st.rerun()
            elif status == "bloqueado":
                st.error("Conta bloqueada. Contate o administrador.")
            else:
                st.warning("Seu cadastro ainda está pendente de aprovação pelo administrador.")
        else:
            st.error("Senha incorreta.")
    else:
        st.error("Usuário não encontrado.")

def do_logout():
    st.session_state.cookie_to_delete = True
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.user_role = None
    st.session_state.user_permissions = ""
    st.rerun()

# --- Auth Screens ---

def login_register_screen():
    st.title("Locamotos - Acesso Restrito")
    env_vars = load_env_vars()
    
    # Use columns to center the login form on desktop
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.header("Entrar no Sistema")
        with st.form("login_form"):
            # Check local browser session storage if implemented, else empty
            username_login = st.text_input("Usuário")
            pass_login = st.text_input("Senha", type="password")
            lembrar_user = st.checkbox("Lembrar meu usuário")
            
            submitted_login = st.form_submit_button("Entrar")
            if submitted_login:
                if username_login and pass_login:
                    do_login(username_login, pass_login, lembrar_user)
                else:
                    st.error("Preencha todos os campos.")
                    
        st.info("⚠️ Acesso restrito a usuários autorizados. Se você esqueceu sua senha ou precisa de acesso, contate o administrador.")

# --- Dashboard Modules ---

def change_tab_state(tab):
    st.session_state.active_tab = tab

def dashboard_tab():
    st.header("Dashboard Gerencial")
    
    st.subheader("Módulos Rápidos (Em Tempo Real)")
    
    db = DatabaseManager()
    
    # --- Live Metrics Gathering ---
    hoje = datetime.date.today()
    try:
        from inter_client import InterClient
        # Inter API returns a dict, getting the 'disponivel' key
        balance_data = InterClient().get_balance()
        saldo_inter = float(balance_data.get('disponivel', 0.0))
    except Exception:
        saldo_inter = 0.0

    # Asaas Metrics for Dashboard
    try:
        from asaas_client import AsaasClient
        ac = AsaasClient()
        saldo_asaas = ac.get_balance()
        # Get payments for counts (last 30 days)
        h_asaas = datetime.date.today()
        s_asaas = (h_asaas - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        e_asaas = h_asaas.strftime("%Y-%m-%d")
        pgs_asaas = ac.get_all_payments(s_asaas, e_asaas)
        
        asaas_pagos = len([p for p in pgs_asaas if p.get('status') in ["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"]])
        asaas_vencidos = len([p for p in pgs_asaas if p.get('status') == "OVERDUE"])
        
        # Calculate Future Receivables (up to 1 year)
        e_asaas_future = (h_asaas + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        pgs_asaas_future = ac.get_all_payments(s_asaas, e_asaas_future)
        asaas_pendentes_valor = sum(p.get("value", 0.0) for p in pgs_asaas_future if p.get("status") == "PENDING")
        asaas_pendentes_qtd = sum(1 for p in pgs_asaas_future if p.get("status") == "PENDING")
        
        asaas_count_cust = len(ac.get_customers())
    except Exception:
        saldo_asaas = 0.0
        asaas_pagos = 0
        asaas_vencidos = 0
        asaas_pendentes_valor = 0.0
        asaas_pendentes_qtd = 0
        asaas_count_cust = 0

    # Frota
    try:
        motos_list = db.get_motos_list()
        total_motos = len(motos_list)
        motos_alugadas = sum(1 for m in motos_list if m[2] == "Alugado")
        motos_disp = sum(1 for m in motos_list if m[2] == "Disponível")
    except Exception:
        total_motos = motos_alugadas = motos_disp = 0
        
    # Locatários Ativos
    try:
        locat_list = db.get_locatarios_list() # id, nome, cpf, tel, placa
        locat_ativos = len([l for l in locat_list if l[4]])
    except Exception:
        locat_ativos = 0
        
    all_txs = db.get_transactions()
    
    rec_mes_pend = 0.0
    desp_hoje = 0.0
    desp_mes = 0.0
    visiun_pend = 0.0
    visiun_count = 0
    
    if all_txs:
        df_live = pd.DataFrame(all_txs, columns=["ID", "Origem", "Tipo", "Valor", "Data", "Status", "CPF/ID", "Placa da Moto"])
        df_live["Data"] = pd.to_datetime(df_live["Data"])
        
        # Receitas
        mask_rec_pend = (df_live["Tipo"].isin(["entrada", "entrada_liquida"])) & (df_live["Status"] == "pendente")
        rec_mes_pend = df_live[mask_rec_pend & (df_live["Data"].dt.month == hoje.month) & (df_live["Data"].dt.year == hoje.year)]["Valor"].sum()
        
        # Despesas
        mask_desp_pend = (df_live["Tipo"] == "saida") & (df_live["Status"] == "pendente")
        desp_hoje = df_live[mask_desp_pend & (df_live["Data"].dt.date == hoje)]["Valor"].sum()
        desp_mes = df_live[mask_desp_pend & (df_live["Data"].dt.month == hoje.month) & (df_live["Data"].dt.year == hoje.year)]["Valor"].sum()
        
        # Visiun
        visiun_df = df_live[(df_live["Origem"] == "VISIUN") & (df_live["Status"] == "pendente")]
        visiun_pend = visiun_df["Valor"].sum()
        visiun_count = len(visiun_df)
    
    # 1. Banco Inter
    st.markdown("### 🏦 1. Posição Banco Inter")
    st.success(f"Saldo Online: R$ {format_currency(saldo_inter)}")
    st.button("Ver Extrato Oficial", on_click=change_tab_state, args=("Inter",))
    
    st.write("")

    # 2. ASAAS
    st.markdown("### 🏢 2. Posição ASAAS")
    c1, c2 = st.columns([1,2])
    with c1:
        st.info(f"Saldo Recebível: R$ {format_currency(saldo_asaas)}\n\nA Receber Futuro: R$ {format_currency(asaas_pendentes_valor)}")
    with c2:
        st.write(f"**Métricas (30 dias):** {asaas_pagos} Pagos | {asaas_vencidos} Vencidos | {asaas_pendentes_qtd} Boletos Pendentes\n\n**Clientes Ativos:** {asaas_count_cust}")
    st.button("Acessar Asaas", on_click=change_tab_state, args=("ASAAS",))

    st.write("")

    # 3. Gestão e Financeiro Líquido
    st.markdown("### 📊 3. Resultados e Gestão")
    rc1, rc2, rc3 = st.columns(3)
    
    with rc1:
        st.info(f"🏍️ **Gestão de Frota**\n\nTotal: {total_motos} | Locadas: {motos_alugadas} | Livres: {motos_disp}")
        st.button("Acessar Frota", use_container_width=True, on_click=change_tab_state, args=("Motos",))
        
    with rc2:
        st.info(f"👤 **Locatários (Pilotos)**\n\nClientes Ativos: {locat_ativos}\n\nCobranças Visiun pendentes: {visiun_count}")
        st.button("Acessar Pilotos", use_container_width=True, on_click=change_tab_state, args=("Locatários",))
        
    with rc3:
        resultado_liquido = rec_mes_pend - desp_mes
        if resultado_liquido >= 0:
            res_str = f"R$ {format_currency(resultado_liquido)}"
            color = "normal"
        else:
            res_str = f"-R$ {format_currency(abs(resultado_liquido))}"
            color = "error"
            
        st.info(f"💰 **Balanço Mês - A Vencer**\n\nReceitas: R$ {format_currency(rec_mes_pend)}\nDespesas: R$ {format_currency(desp_mes)}\n\n**Líquido Estimado**: {res_str}")
        st.button("Acessar Receitas e Despesas", use_container_width=True, on_click=change_tab_state, args=("Receitas e Despesas",))

    st.write("")
    
    # 4. Calendário/Evolução
    st.markdown("### 🗓️ 4. Evolução (Receitas vs Despesas)")
    if not all_txs:
        st.info("Nenhuma transação financeira registrada para gráficos adicionais.")
        return
        
    df = pd.DataFrame(all_txs, columns=["ID", "Origem", "Tipo", "Valor", "Data", "Status", "CPF/ID", "Placa da Moto"])
    df["Data"] = pd.to_datetime(df["Data"])
    
    # Calculate metrics
    receitas = df[df["Tipo"].isin(["entrada", "entrada_liquida"])]["Valor"].sum()
    despesas = df[df["Tipo"] == "saida"]["Valor"].sum()
    lucro = receitas - despesas
    
    r1, r2, r3 = st.columns(3)
    r1.metric("Receitas Totais", f"R$ {format_currency(receitas)}")
    r2.metric("Despesas Totais", f"R$ {format_currency(despesas)}")
    r3.metric("Lucro Líquido", f"R$ {format_currency(lucro)}")
    
    st.markdown("---")
    st.subheader("Fluxo de Caixa Mensal")
    
    # Create a monthly summary for the chart
    df['Mes'] = df['Data'].dt.to_period('M').astype(str)
    resumo_mes = df.groupby(['Mes', 'Tipo'])['Valor'].sum().unstack(fill_value=0).reset_index()
    if 'entrada' not in resumo_mes.columns: resumo_mes['entrada'] = 0
    if 'entrada_liquida' not in resumo_mes.columns: resumo_mes['entrada_liquida'] = 0
    if 'saida' not in resumo_mes.columns: resumo_mes['saida'] = 0
    resumo_mes['Receitas'] = resumo_mes['entrada'] + resumo_mes['entrada_liquida']
    resumo_mes['Despesas'] = resumo_mes['saida']
    
    chart_data = pd.DataFrame({
        'Mês': resumo_mes['Mes'],
        'Receitas': resumo_mes['Receitas'],
        'Despesas': resumo_mes['Despesas']
    }).set_index('Mês')
    st.bar_chart(chart_data)
    
    st.write("")
    st.markdown("### 📊 5. DRE — Demonstrativo de Resultados")
    _render_dre(db, embedded=True)

def inter_tab():
    st.header("🏦 Posição Banco Inter")
    st.write("Valores recebidos do ASAAS, despesas pagas e extrato para contador.")
    
    try:
        from inter_client import InterClient
        client = InterClient()
        
        # Try to get balance
        with st.spinner("Puxando dados do Banco Inter..."):
            saldo_info = client.get_balance()
            
            saldo_atual = saldo_info.get("disponivel", 0.0)
            st.metric("Saldo Disponível (Inter)", format_currency(saldo_atual))
            
            # --- Extrato por Período ---
            st.markdown("---")
            st.subheader("📜 Extrato por Período (Recebidos ASAAS / Despesas)")
            
            hoje = datetime.date.today()
            opcoes_periodo = [
                "Mês Atual",
                "Últimos 7 dias",
                "Últimos 30 dias",
                "Últimos 90 dias (Trimestre)",
                "Ano Corrente",
                "Últimos 365 dias (Ano)",
                "Desde 01/01/2025",
                "Busca Personalizada"
            ]
            
            with st.form("inter_form"):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                with c1:
                    periodo_selecionado = st.selectbox("Período Rápido", opcoes_periodo)
                with c2:
                    custom_start = st.date_input("Início (Personalizada)", value=hoje.replace(day=1), format="DD/MM/YYYY")
                with c3:
                    custom_end = st.date_input("Fim (Personalizada)", value=hoje, format="DD/MM/YYYY")
                with c4:
                    st.write("")
                    st.write("")
                    submit_inter = st.form_submit_button("Ir", use_container_width=True)
            
            if periodo_selecionado == "Últimos 7 dias":
                start_date_inter = hoje - datetime.timedelta(days=7)
                end_date_inter = hoje
            elif periodo_selecionado == "Últimos 30 dias":
                start_date_inter = hoje - datetime.timedelta(days=30)
                end_date_inter = hoje
            elif periodo_selecionado == "Últimos 90 dias (Trimestre)":
                start_date_inter = hoje - datetime.timedelta(days=90)
                end_date_inter = hoje
            elif periodo_selecionado == "Ano Corrente":
                start_date_inter = hoje.replace(month=1, day=1)
                end_date_inter = hoje
            elif periodo_selecionado == "Últimos 365 dias (Ano)":
                start_date_inter = hoje - datetime.timedelta(days=365)
                end_date_inter = hoje
            elif periodo_selecionado == "Desde 01/01/2025":
                start_date_inter = datetime.date(2025, 1, 1)
                end_date_inter = hoje
            elif periodo_selecionado == "Busca Personalizada":
                start_date_inter = custom_start
                end_date_inter = custom_end
            else:
                start_date_inter = hoje.replace(day=1) # Mês Atual
                end_date_inter = hoje
            
            if start_date_inter > end_date_inter:
                st.error("A Data Inicial não pode ser maior que a Data Final.")
                extrato = {}
            else:
                extrato = client.get_bank_statement(
                    data_inicio=start_date_inter.strftime("%Y-%m-%d"),
                    data_fim=end_date_inter.strftime("%Y-%m-%d")
                )
            
            transacoes_inter = extrato.get("transacoes", [])
            if transacoes_inter:
                df_inter = pd.DataFrame(transacoes_inter)
                
                # Try to parse dates to sort by newest first
                date_col = None
                if "dataLancamento" in df_inter.columns:
                    date_col = "dataLancamento"
                elif "dataTransacao" in df_inter.columns:
                    date_col = "dataTransacao"
                elif "dataInclusao" in df_inter.columns:
                    date_col = "dataInclusao"
                else:
                    date_columns = [col for col in df_inter.columns if "data" in col.lower() or "date" in col.lower()]
                    if date_columns:
                        date_col = date_columns[0]
                
                if date_col:
                    # Parse to real datetime for sorting, sort descending
                    df_inter["_dt_sort"] = pd.to_datetime(df_inter[date_col], errors="coerce")
                    df_inter = df_inter.sort_values(by="_dt_sort", ascending=False)
                    # Now format the visible date column nicely
                    df_inter[date_col] = df_inter["_dt_sort"].dt.strftime("%d/%m/%Y")
                
                # Build columns to show and rename them
                cols_to_show = {}
                if date_col:
                    cols_to_show[date_col] = "Data"
                
                if "tipoTransacao" in df_inter.columns:
                    cols_to_show["tipoTransacao"] = "Tipo"
                if "valor" in df_inter.columns:
                    cols_to_show["valor"] = "Valor"
                if "descricao" in df_inter.columns:
                    cols_to_show["descricao"] = "Descrição"
                elif "titulo" in df_inter.columns:
                    cols_to_show["titulo"] = "Descrição"
                
                if cols_to_show:
                    df_display = df_inter[list(cols_to_show.keys())].rename(columns=cols_to_show)
                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Valor": st.column_config.NumberColumn(
                                "Valor",
                                format="R$ %.2f"
                            )
                        } if "Valor" in df_display.columns else None
                    )
                else:
                    st.dataframe(df_inter, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma transação encontrada no período.")

            # --- Accountant Export Shortcut ---
            st.markdown("---")
            st.subheader("📁 Dados para Contador")
            dados_contador_tab()

                
    except Exception as e:
        if hasattr(e, "response") and e.response is not None:
            try:
                error_body = e.response.json()
                error_message = error_body.get('message', str(error_body))
                st.error(f"Erro do Banco Inter: {error_message}")
            except Exception:
                st.error(f"Erro ao conectar com a API do Banco Inter: {e}")
        else:
            st.error(f"Erro ao processar os dados do Inter: {e}")

def motos_ui_tab():
    st.header("🏍️ Frota (Motos)")
    st.write("Gestão técnica, manutenção, trocas de óleo e controle de quilometragem.")
    from frota_ui import frota_tab
    frota_tab()

def locatarios_ui_tab():
    st.header("👤 Locatários (Pilotos)")
    st.write("Cadastro de locatários e acompanhamento financeiro individual.")
    
    tab_perfil, tab_financeiro = st.tabs([
        "👤 Perfil e Documentos", 
        "💰 Financeiro Pilotos"
    ])
    
    with tab_perfil:
        from locatarios_ui import locatarios_tab
        locatarios_tab()
        
    with tab_financeiro:
        st.subheader("Cobranças, Receitas e Valores por Piloto")
        
        db_fin = DatabaseManager()
        hoje = datetime.date.today()
        
        # Load locatarios
        locatarios_fin = db_fin.get_locatarios_list()
        if not locatarios_fin:
            st.info("Nenhum locatário cadastrado.")
        else:
            # Load all DB transactions once
            all_db_txs = db_fin.get_transactions()
            
            # Load ASAAS data once
            asaas_payments = []
            asaas_cust_map = {}
            asaas_cust_cpf_map = {}
            try:
                from asaas_client import AsaasClient
                ac = AsaasClient()
                customers = ac.get_customers()
                asaas_cust_map = {c["id"]: c.get("name", "Desconhecido") for c in customers}
                asaas_cust_cpf_map = {c["id"]: c.get("cpfCnpj", "").replace(".", "").replace("-", "").replace("/", "") for c in customers}
                
                asaas_start = datetime.date(2025, 1, 1).strftime("%Y-%m-%d")
                asaas_end = (hoje + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
                with st.spinner("Buscando boletos no ASAAS..."):
                    asaas_payments = ac.get_all_payments(asaas_start, asaas_end)
            except Exception as e:
                st.warning(f"Não foi possível buscar dados do ASAAS: {e}")
            
            # Reverse map: clean CPF -> list of ASAAS customer_ids
            cpf_to_cust_ids = {}
            for cid, cpf in asaas_cust_cpf_map.items():
                if cpf:
                    cpf_to_cust_ids.setdefault(cpf, []).append(cid)
            
            status_map = {
                "RECEIVED": "recebido",
                "CONFIRMED": "recebido",
                "RECEIVED_IN_CASH": "recebido",
                "PENDING": "pendente",
                "OVERDUE": "em atraso",
            }
            
            st.write(f"Exibindo dados financeiros de **{len(locatarios_fin)}** pilotos.")
            
            for loc in locatarios_fin:
                l_id, l_nome, l_cpf, l_tel, l_placa = loc
                cpf_clean = (l_cpf or "").replace(".", "").replace("-", "").replace("/", "").strip()
                
                fin_rows = []
                
                # 1. Manual DB transactions for this pilot
                for tx in all_db_txs:
                    tx_cpf_clean = (tx[6] or "").replace(".", "").replace("-", "").replace("/", "").strip()
                    if tx_cpf_clean and cpf_clean and tx_cpf_clean == cpf_clean:
                        tipo_label = "Receita" if tx[2] in ('entrada', 'entrada_liquida') else "Despesa"
                        tx_status = tx[5] if tx[5] else "recebido"
                        fin_rows.append({
                            "id": tx[0],
                            "origem": f"Manual ({tipo_label})",
                            "valor": float(tx[3]),
                            "valor_liquido": float(tx[3]),
                            "data": str(tx[4]) if tx[4] else "",
                            "status": tx_status,
                            "editavel": True
                        })
                
                # 2. ASAAS payments for this pilot
                matching_cust_ids = cpf_to_cust_ids.get(cpf_clean, [])
                for pg in asaas_payments:
                    if pg.get("customer") in matching_cust_ids:
                        pg_status = pg.get("status", "")
                        if pg_status in status_map:
                            data_pg = pg.get("paymentDate") or pg.get("dueDate") or pg.get("dateCreated", "")
                            fin_rows.append({
                                "id": None,
                                "origem": "ASAAS",
                                "valor": float(pg.get("value", 0)),
                                "valor_liquido": float(pg.get("netValue", pg.get("value", 0))),
                                "data": data_pg,
                                "status": status_map.get(pg_status, pg_status.lower()),
                                "editavel": False
                            })
                
                # Compute totals
                total_recebido = sum(r["valor"] for r in fin_rows if r["status"] == "recebido")
                total_pendente = sum(r["valor"] for r in fin_rows if r["status"] == "pendente")
                total_atraso = sum(r["valor"] for r in fin_rows if r["status"] == "em atraso")
                
                placa_str = f"🏍️ {l_placa}" if l_placa else "Sem moto"
                
                with st.expander(f"👤 {l_nome} — {placa_str} | ✅ R$ {total_recebido:,.2f} | ⏳ R$ {total_pendente:,.2f} | 🔴 R$ {total_atraso:,.2f}"):
                    if not fin_rows:
                        st.info("Nenhum registro financeiro para este piloto.")
                    else:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("✅ Recebido", f"R$ {total_recebido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        m2.metric("⏳ Pendente", f"R$ {total_pendente:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        m3.metric("🔴 Em Atraso", f"R$ {total_atraso:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        
                        # Build display table
                        display_rows = []
                        for r in fin_rows:
                            try:
                                data_fmt = pd.to_datetime(r["data"]).strftime("%d/%m/%Y") if r["data"] else "—"
                            except Exception:
                                data_fmt = r["data"] or "—"
                            display_rows.append({
                                "Origem": r["origem"],
                                "Valor Bruto": f"R$ {r['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                                "Valor Líquido": f"R$ {r['valor_liquido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                                "Data": data_fmt,
                                "Status": r["status"].upper()
                            })
                        
                        df_fin = pd.DataFrame(display_rows)
                        st.dataframe(df_fin, use_container_width=True, hide_index=True)
                        
                        # Mark pending manual entries as received
                        pendentes = [r for r in fin_rows if r["editavel"] and r["status"] == "pendente" and r["id"]]
                        if pendentes:
                            st.markdown("#### Marcar como Recebido")
                            for r in pendentes:
                                try:
                                    data_fmt = pd.to_datetime(r["data"]).strftime("%d/%m/%Y") if r["data"] else "—"
                                except Exception:
                                    data_fmt = "—"
                                ci, cb = st.columns([3, 1])
                                ci.write(f"**#{r['id']}** — R$ {r['valor']:.2f} — {data_fmt}")
                                if cb.button("✅ Recebido", key=f"fin_recv_{l_id}_{r['id']}"):
                                    db_fin.update_transaction(r["id"], "Manual", r["valor"], r["data"], "recebido", cpf_cliente=l_cpf)
                                    st.success("Atualizado para Recebido!")
                                    st.rerun()

def asaas_tab():
    st.header("💳 ASAAS")
    st.write("Boletos, contas a receber, valores a transferir para Inter.")
    st.markdown("---")
    
    try:
        from asaas_client import AsaasClient
        client = AsaasClient()
        
        # Top Metrics (restored)
        saldo = client.get_balance()
        customers = client.get_customers()
        
        # We need to get payments to calculate the future projection
        hoje = datetime.date.today()
        # Look ahead up to 1 year and behind 30 days for open charges
        s_asaas = (hoje - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        e_asaas = (hoje + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        all_pgs = client.get_all_payments(s_asaas, e_asaas)
        
        # Calculate Pending Value Total
        total_futuro_pendente = sum(p.get("value", 0.0) for p in all_pgs if p.get("status") == "PENDING")
        qtd_futuro_pendente = sum(1 for p in all_pgs if p.get("status") == "PENDING")
        
        c_top1, c_top2, c_top3 = st.columns(3)
        c_top1.metric("Saldo Disponível (Asaas)", format_currency(saldo))
        c_top2.metric(f"A Receber ({qtd_futuro_pendente} boletos)", format_currency(total_futuro_pendente))
        c_top3.metric("Total de Clientes", len(customers))
        
        # Sweep Trigger (Simulated for UI)
        st.write("### 🧹 Varredura Automática")
        if saldo > 0:
            st.info(f"R$ {format_currency(saldo)} aguardando transferência para o Banco Inter.")
            if st.button("Executar Varredura Manual (Pix para Inter)"):
                # This would call the logic in webhook_server.py or a dedicated worker
                from webhook_server import trigger_sweep
                success, msg = trigger_sweep()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.write("Saldo zerado. Nada a transferir no momento.")

        st.markdown("---")
        
        # Boletos / Payments List
        st.subheader("📋 Boletos e Cobranças Geradas")
        
        hoje = datetime.date.today()
        opcoes_periodo = ["Últimos 30 dias", "Últimos 90 dias", "Ano Corrente", "Busca Personalizada"]
        
        with st.form("asaas_filter"):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                periodo = st.selectbox("Período de Criação", opcoes_periodo)
            with c2:
                d_inicio = st.date_input("Início", value=hoje - datetime.timedelta(days=30))
            with c3:
                d_fim = st.date_input("Fim", value=hoje)
            with c4:
                st.write("")
                st.write("")
                st_asaas = st.form_submit_button("Filtrar")
        
        if periodo == "Últimos 30 dias":
            start_date = (hoje - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        elif periodo == "Últimos 90 dias":
            start_date = (hoje - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        elif periodo == "Ano Corrente":
            start_date = hoje.replace(month=1, day=1).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        else:
            start_date = d_inicio.strftime("%Y-%m-%d")
            end_date = d_fim.strftime("%Y-%m-%d")

        pagamentos = client.get_all_payments(start_date, end_date)
        
        if pagamentos:
            # Map customer IDs to Names
            customer_map = {c.get("id"): c.get("name", "Desconhecido") for c in customers}
            
            df_pgs = pd.DataFrame(pagamentos)
            
            df_ui = pd.DataFrame({
                "Sacado": df_pgs.get("customer", "").map(lambda c_id: customer_map.get(c_id, "Desconhecido")),
                "Vencimento": pd.to_datetime(df_pgs.get("dueDate", "")).dt.strftime("%d/%m/%Y"),
                "Valor Original": df_pgs.get("value", 0.0),
                "Valor Cobrado": df_pgs.apply(lambda row: 
                    (row.get("value") or 0.0) + 
                    (row.get("interestValue") or 0.0) + 
                    (row.get("fineValue") or 0.0) - 
                    (row.get("discount", {}).get("value", 0.0) if isinstance(row.get("discount"), dict) else 0.0)
                    if row.get("status") in ["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"] else (row.get("value") or 0.0), axis=1),
                "Status": df_pgs.get("status", "")
            })
            
            # Map statuses
            status_map = {
                "PENDING": "🟡 Pendente",
                "RECEIVED": "🟢 Recebido",
                "CONFIRMED": "🟢 Confirmado",
                "OVERDUE": "🔴 Vencido",
                "REFUNDED": "🔄 Estornado",
                "RECEIVED_IN_CASH": "💵 Recebido Físico"
            }
            df_ui["Status"] = df_ui["Status"].map(lambda s: status_map.get(s, s))
            
            # Stats metrics
            p_pagos = len(df_pgs[df_pgs["status"].isin(["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"])])
            p_vencidos = len(df_pgs[df_pgs["status"] == "OVERDUE"])
            p_pendentes = len(df_pgs[df_pgs["status"] == "PENDING"])
            
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Boletos Pagos", p_pagos)
            mc2.metric("Pendentes", p_pendentes)
            mc3.metric("Vencidos", p_vencidos)
            
            def highlight_diff(row):
                # We need to format it to two decimals for comparison to avoid float precision issues
                val_orig = round(row["Valor Original"], 2)
                val_cobr = round(row["Valor Cobrado"], 2)
                is_diff = val_orig != val_cobr
                
                style = []
                for col in row.index:
                    if col == "Valor Cobrado" and is_diff:
                        style.append('color: #FF6B6B; font-weight: bold')
                    else:
                        style.append('')
                return style

            styled_df = df_ui.style.apply(highlight_diff, axis=1)
            
            st.dataframe(
                styled_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Valor Original": st.column_config.NumberColumn("Valor Original", format="R$ %.2f"),
                    "Valor Cobrado": st.column_config.NumberColumn("Valor Cobrado", format="R$ %.2f")
                }
            )
        else:
            st.warning("Nenhuma cobrança encontrada no período selecionado.")

    except Exception as e:
        st.error(f"Erro ao conectar com API do Asaas: {e}")

def receitas_tab():
    st.header("Receitas")
    st.write("Transações de entrada da Frota.")
    
    db = DatabaseManager()
    all_txs = db.get_transactions()
    
    # Filter for receitas ('entrada', 'entrada_liquida')
    # Tx format: id, origem, tipo, valor, data, cpf_cliente, placa_moto
    all_receitas = [tx for tx in all_txs if tx[2] in ('entrada', 'entrada_liquida')]
    
    if not all_receitas:
        st.info("Nenhuma receita registrada ainda.")
        return

    st.subheader("Registrar Receita Manualmente")
    
    try:
        motos = db.get_all_motos()
    except Exception:
        motos = []
        
    with st.form("manual_entry_receitas_form"):
        col_placa, col_data = st.columns(2)
        with col_placa:
            sel_placa = st.selectbox("Moto (Placa) [Opcional]", [""] + motos)
        with col_data:
            sel_data = st.date_input("Data da Receita", format="DD/MM/YYYY")
            
        col_origem, col_valor, col_status = st.columns(3)
        with col_origem:
            sel_origem = st.selectbox("Origem", ["MANUAL", "PIX", "DINHEIRO", "ASAAS"])
        with col_valor:
            sel_valor = st.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f")
        with col_status:
            sel_status = st.selectbox("Status", ["pago", "pendente"], key="status_receita")
            
        submit_btn = st.form_submit_button("Registrar Receita")
        
        if submit_btn:
            db.add_transaction(
                origem=sel_origem,
                tipo="entrada",
                valor=sel_valor,
                data=sel_data.strftime("%Y-%m-%d"),
                status=sel_status,
                placa_moto=sel_placa if sel_placa else None
            )
            st.success(f"Receita de R${sel_valor:.2f} registrada com sucesso!")
            st.rerun()

    st.markdown("---")
    
    if all_receitas:
        df = pd.DataFrame(all_receitas, columns=["ID", "Origem", "Tipo", "Valor", "Data", "Status", "CPF/ID", "Placa da Moto"])
        if not df.empty:
            df["Data"] = pd.to_datetime(df["Data"])
    hoje = datetime.date.today()
    
    opcoes_periodo = [
        "Mês Atual",
        "Últimos 7 dias",
        "Últimos 30 dias",
        "Últimos 90 dias (Trimestre)",
        "Ano Corrente",
        "Últimos 365 dias (Ano)",
        "Desde 01/01/2025",
        "Busca Personalizada"
    ]
    
    with st.form("receitas_form"):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            periodo_selecionado = st.selectbox("Período Rápido", opcoes_periodo)
        with c2:
            custom_start = st.date_input("Início (Personalizada)", value=hoje.replace(day=1), format="DD/MM/YYYY")
        with c3:
            custom_end = st.date_input("Fim (Personalizada)", value=hoje, format="DD/MM/YYYY")
        with c4:
            st.write("")
            st.write("")
            submit_receitas = st.form_submit_button("Ir", use_container_width=True)
        
    if periodo_selecionado == "Últimos 7 dias":
        start_date = hoje - datetime.timedelta(days=7)
        end_date = hoje
    elif periodo_selecionado == "Últimos 30 dias":
        start_date = hoje - datetime.timedelta(days=30)
        end_date = hoje
    elif periodo_selecionado == "Últimos 90 dias (Trimestre)":
        start_date = hoje - datetime.timedelta(days=90)
        end_date = hoje
    elif periodo_selecionado == "Ano Corrente":
        start_date = hoje.replace(month=1, day=1)
        end_date = hoje
    elif periodo_selecionado == "Últimos 365 dias (Ano)":
        start_date = hoje - datetime.timedelta(days=365)
        end_date = hoje
    elif periodo_selecionado == "Desde 01/01/2025":
        start_date = datetime.date(2025, 1, 1)
        end_date = hoje
    elif periodo_selecionado == "Busca Personalizada":
        start_date = custom_start
        end_date = custom_end
    else:
        start_date = hoje.replace(day=1) # Mês Atual
        end_date = hoje
        
    mask = (df["Data"].dt.date >= start_date) & (df["Data"].dt.date <= end_date)
    filtered_df = df.loc[mask].copy()
    
    st.metric("Total de Receitas no Período", format_currency(filtered_df['Valor'].sum(), include_symbol=True))
    
    # filtered_df["Valor"] = filtered_df["Valor"].apply(format_currency) # No longer needed with column_config
    st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Valor": st.column_config.NumberColumn(
                "Valor",
                format="%.2f"
            ),
            "Data": st.column_config.DateColumn(
                "Data",
                format="DD/MM/YYYY"
            )
        }
    )
def _render_dre(db, embedded=False):
    """
    Renders a DRE (Demonstrativo de Resultados do Exercício).
    If embedded=True, renders a compact version for the dashboard.
    """
    hoje = datetime.date.today()
    
    if not embedded:
        st.subheader("📊 DRE — Demonstrativo de Resultados")
    
    # Period selector
    opcoes = ["Mês Atual", "Mês Anterior", "Trimestre Atual", "Ano Corrente", "Desde 01/01/2025", "Busca Personalizada"]
    
    if embedded:
        periodo = st.selectbox("Período do DRE", opcoes, key="dre_dash_per")
    else:
        with st.form("dre_periodo_form"):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                periodo = st.selectbox("Período", opcoes, key="dre_per")
            with c2:
                custom_s = st.date_input("Início", value=hoje.replace(day=1), format="DD/MM/YYYY", key="dre_cs")
            with c3:
                custom_e = st.date_input("Fim", value=hoje, format="DD/MM/YYYY", key="dre_ce")
            with c4:
                st.write("")
                st.write("")
                st.form_submit_button("Gerar", use_container_width=True)
    
    import calendar
    if periodo == "Mês Atual":
        start_date = hoje.replace(day=1)
        end_date = hoje
        periodo_label = hoje.strftime("%B/%Y").capitalize()
    elif periodo == "Mês Anterior":
        first_this = hoje.replace(day=1)
        last_prev = first_this - datetime.timedelta(days=1)
        start_date = last_prev.replace(day=1)
        end_date = last_prev
        periodo_label = last_prev.strftime("%B/%Y").capitalize()
    elif periodo == "Trimestre Atual":
        q = (hoje.month - 1) // 3
        start_date = datetime.date(hoje.year, q * 3 + 1, 1)
        end_date = hoje
        periodo_label = f"Q{q+1}/{hoje.year}"
    elif periodo == "Ano Corrente":
        start_date = datetime.date(hoje.year, 1, 1)
        end_date = hoje
        periodo_label = str(hoje.year)
    elif periodo == "Desde 01/01/2025":
        start_date = datetime.date(2025, 1, 1)
        end_date = hoje
        periodo_label = "2025 até hoje"
    else:
        start_date = custom_s if not embedded else hoje.replace(day=1)
        end_date = custom_e if not embedded else hoje
        periodo_label = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
    
    # 1. Gather Manual DB transactions in period
    all_txs = db.get_transactions()
    
    receitas_manual_bruto = 0.0
    despesas_por_cat = {}  # origin -> total
    
    for tx in all_txs:
        tx_data = tx[4]
        try:
            tx_date = pd.to_datetime(tx_data).date()
        except Exception:
            continue
        if tx_date < start_date or tx_date > end_date:
            continue
        
        valor = float(tx[3])
        tipo = tx[2]
        origem = tx[1] or "Manual"
        
        if tipo in ('entrada', 'entrada_liquida'):
            receitas_manual_bruto += valor
        elif tipo == 'saida':
            # Categorize by origin
            cat = origem if origem else "Outros"
            despesas_por_cat[cat] = despesas_por_cat.get(cat, 0.0) + valor
    
    # 2. Gather ASAAS data
    receitas_asaas_bruto = 0.0
    receitas_asaas_liquido = 0.0
    try:
        from asaas_client import AsaasClient
        ac = AsaasClient()
        asaas_start = start_date.strftime("%Y-%m-%d")
        asaas_end = end_date.strftime("%Y-%m-%d")
        pagamentos = ac.get_all_payments(asaas_start, asaas_end)
        
        for pg in pagamentos:
            pg_status = pg.get("status", "")
            if pg_status in ("RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"):
                pay_date_str = pg.get("paymentDate") or pg.get("dueDate") or ""
                try:
                    pay_date = pd.to_datetime(pay_date_str).date()
                except Exception:
                    continue
                if start_date <= pay_date <= end_date:
                    receitas_asaas_bruto += float(pg.get("value", 0))
                    receitas_asaas_liquido += float(pg.get("netValue", pg.get("value", 0)))
    except Exception:
        pass
    
    # 3. Compute DRE
    receita_bruta = receitas_manual_bruto + receitas_asaas_bruto
    deducoes_asaas = receitas_asaas_bruto - receitas_asaas_liquido
    receita_liquida = receita_bruta - deducoes_asaas
    despesas_total = sum(despesas_por_cat.values())
    resultado_operacional = receita_liquida - despesas_total
    
    # 4. Render
    def fmt(v):
        prefix = "" if v >= 0 else "-"
        return f"{prefix}R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    st.markdown(f"**Período: {periodo_label}**")
    
    # DRE Table
    dre_rows = [
        {"Conta": "RECEITA BRUTA", "Valor": fmt(receita_bruta), "_sort": 1, "_bold": True},
        {"Conta": "  Receitas Manuais (Aluguel, Caução, etc.)", "Valor": fmt(receitas_manual_bruto), "_sort": 2, "_bold": False},
        {"Conta": "  Receitas ASAAS (Boletos Recebidos)", "Valor": fmt(receitas_asaas_bruto), "_sort": 3, "_bold": False},
        {"Conta": "", "Valor": "", "_sort": 4, "_bold": False},
        {"Conta": "(-) DEDUÇÕES / TAXAS", "Valor": fmt(-deducoes_asaas), "_sort": 5, "_bold": True},
        {"Conta": "  Taxas ASAAS (Gateway)", "Valor": fmt(-deducoes_asaas), "_sort": 6, "_bold": False},
        {"Conta": "", "Valor": "", "_sort": 7, "_bold": False},
        {"Conta": "= RECEITA LÍQUIDA", "Valor": fmt(receita_liquida), "_sort": 8, "_bold": True},
        {"Conta": "", "Valor": "", "_sort": 9, "_bold": False},
        {"Conta": "(-) DESPESAS OPERACIONAIS", "Valor": fmt(-despesas_total), "_sort": 10, "_bold": True},
    ]
    
    sort_idx = 11
    for cat, val in sorted(despesas_por_cat.items()):
        dre_rows.append({"Conta": f"  {cat}", "Valor": fmt(-val), "_sort": sort_idx, "_bold": False})
        sort_idx += 1
    
    dre_rows.append({"Conta": "", "Valor": "", "_sort": sort_idx, "_bold": False})
    sort_idx += 1
    dre_rows.append({"Conta": "═══════════════════════════════════", "Valor": "══════════════", "_sort": sort_idx, "_bold": False})
    sort_idx += 1
    dre_rows.append({"Conta": "= RESULTADO OPERACIONAL (LUCRO/PREJUÍZO)", "Valor": fmt(resultado_operacional), "_sort": sort_idx, "_bold": True})
    
    # Display
    df_dre = pd.DataFrame(dre_rows)
    st.dataframe(
        df_dre[["Conta", "Valor"]],
        use_container_width=True,
        hide_index=True,
        height=35 * len(dre_rows) + 38
    )
    
    # Visual summary
    if not embedded:
        c1, c2, c3 = st.columns(3)
        c1.metric("Receita Bruta", fmt(receita_bruta))
        c2.metric("Despesas Totais", fmt(despesas_total))
        
        delta_color = "normal" if resultado_operacional >= 0 else "inverse"
        c3.metric("Resultado", fmt(resultado_operacional), delta=f"{(resultado_operacional/receita_bruta*100):.1f}% margem" if receita_bruta > 0 else "N/A", delta_color=delta_color)

def receitas_despesas_tab():
    st.header("💰 Receitas e Despesas")
    st.write("Registre e acompanhe todas as entradas e saídas financeiras.")
    
    db = DatabaseManager()
    
    tab_receitas, tab_despesas, tab_dre = st.tabs(["📈 Receitas", "📉 Despesas", "📊 DRE"])
    
    # ========== RECEITAS ==========
    with tab_receitas:
        st.subheader("Registrar Receita Manualmente")
        
        try:
            motos = db.get_all_motos()
        except Exception:
            motos = []
        
        try:
            locatarios = db.get_locatarios_list()  # (id, nome, cpf, telefone, placa_associada)
            locatario_options = {l[1]: l for l in locatarios}  # key = nome
            cpf_to_nome = {l[2]: l[1] for l in locatarios}
            cpf_to_placa = {l[2]: (l[4] or "—") for l in locatarios}
        except Exception:
            locatarios = []
            locatario_options = {}
            cpf_to_nome = {}
            cpf_to_placa = {}
            
        with st.form("receita_manual_form"):
            col_cat, col_loc = st.columns(2)
            with col_cat:
                categoria_rec = st.selectbox("Tipo de Receita", [
                    "Aluguel", "Caução", "Multa Contratual", "Outros"
                ])
            with col_loc:
                loc_names = ["(Sem vínculo)"] + list(locatario_options.keys())
                sel_locatario = st.selectbox("Locatário (Cliente)", loc_names)
                
            col_placa_r, col_data_r, col_valor_r = st.columns(3)
            with col_placa_r:
                sel_placa_r = st.selectbox("Moto (Placa) [Opcional]", ["Geral"] + motos, key="placa_receita")
            with col_data_r:
                sel_data_r = st.date_input("Data do Recebimento", format="DD/MM/YYYY", key="data_receita")
            with col_valor_r:
                sel_valor_r = st.number_input("Valor (R$)", min_value=0.01, step=100.0, format="%.2f", key="valor_receita")
            
            col_status_r, col_desc_r = st.columns(2)
            with col_status_r:
                sel_status_r = st.selectbox("Status do Pagamento", ["recebido", "pendente"], key="status_receita")
            with col_desc_r:
                sel_desc_r = st.text_input("Observação (opcional)", key="desc_receita", placeholder="Ex: Aluguel ref. semana 10/03")
            
            submit_rec = st.form_submit_button("Registrar Receita")
            
            if submit_rec:
                cpf_cliente = None
                if sel_locatario != "(Sem vínculo)" and sel_locatario in locatario_options:
                    cpf_cliente = locatario_options[sel_locatario][2]  # CPF
                
                placa_r = sel_placa_r if sel_placa_r != "Geral" else None
                
                db.add_transaction(
                    origem="Manual",
                    tipo="entrada",
                    valor=sel_valor_r,
                    data=sel_data_r.strftime("%Y-%m-%d"),
                    status=sel_status_r,
                    cpf_cliente=cpf_cliente,
                    placa_moto=placa_r
                )
                st.success(f"Receita de {categoria_rec} — R$ {sel_valor_r:.2f} registrada com sucesso!")
                st.rerun()
        
        st.markdown("---")
        st.subheader("Histórico de Receitas")
        
        # 1. Local manual receipts
        all_txs = db.get_transactions()
        all_receitas_local = [tx for tx in all_txs if tx[2] in ('entrada', 'entrada_liquida')]
        
        rows = []
        manual_tx_ids = []  # Track IDs for editing
        for tx in all_receitas_local:
            cliente_nome = cpf_to_nome.get(tx[6], tx[6]) if tx[6] else "—"
            placa = tx[7] or cpf_to_placa.get(tx[6], "—") if tx[6] else (tx[7] or "—")
            tx_status = tx[5] if tx[5] else "recebido"  # Legacy entries may have empty status
            tx_origem = tx[1] if tx[1] else "Manual"
            rows.append({
                "ID": tx[0],
                "Origem": tx_origem if tx_origem == "ASAAS" else "Manual",
                "Cliente": cliente_nome,
                "Valor Bruto": float(tx[3]),
                "Valor Líquido": float(tx[3]),
                "Data": tx[4],
                "Status": tx_status,
                "Placa": placa
            })
            manual_tx_ids.append(tx[0])
        
        # 2. ASAAS paid boletos (automatic)
        asaas_cust_cpf_map = {}  # customer_id -> cpfCnpj
        try:
            from asaas_client import AsaasClient
            ac = AsaasClient()
            
            # Fetch customers for name and CPF mapping
            customers = ac.get_customers()
            cust_map = {c["id"]: c.get("name", c.get("cpfCnpj", "Desconhecido")) for c in customers}
            asaas_cust_cpf_map = {c["id"]: c.get("cpfCnpj", "") for c in customers}
            
            h = datetime.date.today()
            asaas_start = datetime.date(2025, 1, 1).strftime("%Y-%m-%d")
            asaas_end = (h + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
            pagamentos = ac.get_all_payments(asaas_start, asaas_end)
            
            status_map = {
                "RECEIVED": "recebido",
                "CONFIRMED": "recebido",
                "RECEIVED_IN_CASH": "recebido",
                "PENDING": "pendente",
                "OVERDUE": "vencido",
            }
            
            for pg in pagamentos:
                pg_status = pg.get("status", "")
                if pg_status in ("RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH", "PENDING", "OVERDUE"):
                    cliente_nome = cust_map.get(pg.get("customer"), pg.get("customer", "—"))
                    # Cross-reference with locatarios to get plate
                    cust_cpf = asaas_cust_cpf_map.get(pg.get("customer"), "")
                    placa = cpf_to_placa.get(cust_cpf, "—")
                    
                    data_pg = pg.get("paymentDate") or pg.get("dueDate") or pg.get("dateCreated", "")
                    rows.append({
                        "ID": None,
                        "Origem": "ASAAS",
                        "Cliente": cliente_nome,
                        "Valor Bruto": float(pg.get("value", 0)),
                        "Valor Líquido": float(pg.get("netValue", pg.get("value", 0))),
                        "Data": data_pg,
                        "Status": status_map.get(pg_status, pg_status.lower()),
                        "Placa": placa
                    })
        except Exception as e:
            st.warning(f"Não foi possível buscar boletos do ASAAS: {e}")
        
        if not rows:
            st.info("Nenhuma receita registrada ainda.")
        else:
            df_rec = pd.DataFrame(rows)
            df_rec["Data"] = pd.to_datetime(df_rec["Data"], errors="coerce")
            hoje = datetime.date.today()
            
            # Display without the ID column
            _render_financial_history(df_rec.drop(columns=["ID"], errors="ignore"), hoje, "receitas")
        
        # ========== EDITAR ENTRADA MANUAL (compacto) ==========
        if all_receitas_local:
            st.markdown("---")
            # Build options for selectbox
            edit_options = {}
            for tx in all_receitas_local:
                tx_id, tx_orig, tx_tipo, tx_valor, tx_data, tx_status, tx_cpf, tx_placa = tx
                cliente_nome = cpf_to_nome.get(tx_cpf, tx_cpf) if tx_cpf else "Sem vínculo"
                data_fmt = pd.to_datetime(tx_data).strftime("%d/%m/%Y") if tx_data else "—"
                status_label = tx_status if tx_status else "recebido"
                label = f"#{tx_id} — {cliente_nome} — R$ {float(tx_valor):.2f} — {data_fmt} — {status_label}"
                edit_options[label] = tx
            
            selected_label = st.selectbox("✏️ Editar entrada manual:", ["(Nenhuma)"] + list(edit_options.keys()), key="sel_edit_receita")
            
            if selected_label != "(Nenhuma)" and selected_label in edit_options:
                tx = edit_options[selected_label]
                tx_id, tx_orig, tx_tipo, tx_valor, tx_data, tx_status, tx_cpf, tx_placa = tx
                
                with st.form(f"edit_tx_{tx_id}"):
                    e_c1, e_c2, e_c3, e_c4 = st.columns(4)
                    with e_c1:
                        edit_valor = st.number_input("Valor", value=float(tx_valor), min_value=0.01, step=10.0, format="%.2f", key=f"ev_{tx_id}")
                    with e_c2:
                        edit_data = st.date_input("Data", value=pd.to_datetime(tx_data).date() if tx_data else datetime.date.today(), format="DD/MM/YYYY", key=f"ed_{tx_id}")
                    with e_c3:
                        edit_status = st.selectbox("Status", ["recebido", "pendente"], index=["recebido", "pendente"].index(tx_status) if tx_status in ["recebido", "pendente"] else 0, key=f"es_{tx_id}")
                    with e_c4:
                        loc_edit_names = ["(Sem vínculo)"] + list(locatario_options.keys())
                        current_loc_idx = 0
                        if tx_cpf and tx_cpf in cpf_to_nome:
                            try:
                                current_loc_idx = loc_edit_names.index(cpf_to_nome[tx_cpf])
                            except ValueError:
                                current_loc_idx = 0
                        edit_loc = st.selectbox("Locatário", loc_edit_names, index=current_loc_idx, key=f"el_{tx_id}")
                    
                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.form_submit_button("💾 Salvar", use_container_width=True):
                            new_cpf = None
                            if edit_loc != "(Sem vínculo)" and edit_loc in locatario_options:
                                new_cpf = locatario_options[edit_loc][2]
                            db.update_transaction(
                                tx_id, "Manual", edit_valor,
                                edit_data.strftime("%Y-%m-%d"), edit_status,
                                cpf_cliente=new_cpf, placa_moto=tx_placa
                            )
                            st.success("Atualizado!")
                            st.rerun()
                    with btn_c2:
                        if st.form_submit_button("🗑️ Excluir", use_container_width=True):
                            db.delete_transaction(tx_id)
                            st.success("Excluído!")
                            st.rerun()

    
    # ========== DESPESAS ==========
    with tab_despesas:
        st.subheader("Registrar Despesa Manualmente")
        
        try:
            motos_d = db.get_all_motos()
        except Exception:
            motos_d = []
            
        with st.form("manual_entry_form"):
            col_cat, col_placa, col_data = st.columns(3)
            with col_cat:
                categoria = st.selectbox("Categoria", [
                    "Royalties", "Contador", "Taxa de aluguel de espaço", "Cooperloc", 
                    "Fundo de marketing", "Taxa de publicidade", "Licenciamento", 
                    "IPVA", "Seguros", "Pró-labore"
                ])
            with col_placa:
                sel_placa = st.selectbox("Moto (Placa) [Opcional]", ["Geral/Administrativo"] + motos_d)
            with col_data:
                sel_data = st.date_input("Data da Despesa", format="DD/MM/YYYY")
                
            col_origem, col_valor, col_status = st.columns(3)
            with col_origem:
                sel_origem = st.selectbox("Conta de Origem", ["Inter", "ASAAS", "Outros"])
            with col_valor:
                sel_valor = st.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f")
            with col_status:
                sel_status = st.selectbox("Status", ["pago", "pendente"], key="status_despesa")
                
            submit_btn = st.form_submit_button("Registrar Despesa")
            
            if submit_btn:
                db.add_transaction(
                    origem=sel_origem,
                    tipo="saida",
                    valor=sel_valor,
                    data=sel_data.strftime("%Y-%m-%d"),
                    status=sel_status,
                    placa_moto=sel_placa if sel_placa != "Geral/Administrativo" else None
                )
                st.success(f"Despesa de {categoria} registrada com sucesso!")
                st.rerun()
                    
        st.markdown("---")
        st.subheader("Histórico de Despesas")

        all_txs_d = db.get_transactions()
        all_despesas = [tx for tx in all_txs_d if tx[2] == 'saida']
        
        if not all_despesas:
            st.info("Nenhuma despesa registrada ainda.")
        else:
            df = pd.DataFrame(all_despesas, columns=["ID", "Origem", "Tipo", "Valor", "Data", "Status", "CPF/ID", "Placa da Moto"])
            df["Data"] = pd.to_datetime(df["Data"])
            hoje = datetime.date.today()
            
            _render_financial_history(df, hoje, "despesas")

    # ========== DRE ==========
    with tab_dre:
        _render_dre(db, embedded=False)

def _render_financial_history(df, hoje, prefix):
    """Shared period filter + table renderer for both Receitas and Despesas."""
    opcoes_periodo = [
        "Mês Atual",
        "Últimos 7 dias",
        "Últimos 30 dias",
        "Últimos 90 dias (Trimestre)",
        "Ano Corrente",
        "Últimos 365 dias (Ano)",
        "Desde 01/01/2025",
        "Busca Personalizada"
    ]
    
    with st.form(f"{prefix}_filter_form"):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1:
            periodo_selecionado = st.selectbox("Período Rápido", opcoes_periodo, key=f"periodo_{prefix}")
        with c2:
            custom_start = st.date_input("Início (Personalizada)", value=hoje.replace(day=1), format="DD/MM/YYYY", key=f"cs_{prefix}")
        with c3:
            custom_end = st.date_input("Fim (Personalizada)", value=hoje, format="DD/MM/YYYY", key=f"ce_{prefix}")
        with c4:
            st.write("")
            st.write("")
            st.form_submit_button("Ir", use_container_width=True)
        
    if periodo_selecionado == "Últimos 7 dias":
        start_date = hoje - datetime.timedelta(days=7)
        end_date = hoje
    elif periodo_selecionado == "Últimos 30 dias":
        start_date = hoje - datetime.timedelta(days=30)
        end_date = hoje
    elif periodo_selecionado == "Últimos 90 dias (Trimestre)":
        start_date = hoje - datetime.timedelta(days=90)
        end_date = hoje
    elif periodo_selecionado == "Ano Corrente":
        start_date = hoje.replace(month=1, day=1)
        end_date = hoje
    elif periodo_selecionado == "Últimos 365 dias (Ano)":
        start_date = hoje - datetime.timedelta(days=365)
        end_date = hoje
    elif periodo_selecionado == "Desde 01/01/2025":
        start_date = datetime.date(2025, 1, 1)
        end_date = hoje
    elif periodo_selecionado == "Busca Personalizada":
        start_date = custom_start
        end_date = custom_end
    else:
        start_date = hoje.replace(day=1)
        end_date = hoje
        
    mask = (df["Data"].dt.date >= start_date) & (df["Data"].dt.date <= end_date)
    filtered_df = df.loc[mask].copy()
    
    # Determine which value column to use for the total
    if "Valor Bruto" in filtered_df.columns:
        valor_col = "Valor Bruto"
    else:
        valor_col = "Valor"
    
    label = "Total de Receitas (Bruto)" if prefix == "receitas" else "Total de Despesas"
    st.metric(f"{label} no Período", format_currency(filtered_df[valor_col].sum()))
    
    if prefix == "receitas" and "Valor Líquido" in filtered_df.columns:
        st.metric("Total Líquido no Período", format_currency(filtered_df["Valor Líquido"].sum()))
    
    show_df = filtered_df.copy()
    show_df["Data"] = show_df["Data"].dt.strftime("%d/%m/%Y")
    
    # Format currency columns
    for col in ["Valor", "Valor Bruto", "Valor Líquido"]:
        if col in show_df.columns:
            show_df[col] = show_df[col].apply(format_currency)
    
    st.dataframe(
        show_df, 
        use_container_width=True, 
        hide_index=True
    )

def config_ui_tab():
    import os
    st.header("Configurações")
    
    CERTS_DIR = "certs"
    
    st.write("Estas chaves ficam salvas apenas localmente na sua máquina em um arquivo `.env`.")
    env_vars = load_env_vars()

    # SMTP Config
    st.subheader("Configurações de E-mail (SMTP)")
    has_smtp = "✅ Configurado" if "SMTP_SERVER" in env_vars else "❌ Pendente"
    st.write(f"Status Atual: **{has_smtp}**")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        smtp_server = st.text_input("Servidor SMTP", value=env_vars.get("SMTP_SERVER", "smtp.gmail.com"))
        smtp_port = st.text_input("Porta SMTP", value=env_vars.get("SMTP_PORT", "587"))
    with col_s2:
        smtp_user = st.text_input("Usuário SMTP (E-mail)", value=env_vars.get("SMTP_USER", ""))
        smtp_pass = st.text_input("Senha SMTP", type="password", value=env_vars.get("SMTP_PASSWORD", ""))
        
    if st.button("Salvar Servidor de E-mail"):
        if smtp_server and smtp_port and smtp_user and smtp_pass:
            save_env_var("SMTP_SERVER", smtp_server)
            save_env_var("SMTP_PORT", smtp_port)
            save_env_var("SMTP_USER", smtp_user)
            save_env_var("SMTP_PASSWORD", smtp_pass)
            st.success("Configurações SMTP salvas com sucesso em `.env`!")
            st.rerun()
        else:
            st.error("Preencha todos os campos do SMTP.")

    # Contador Config
    st.markdown("---")
    st.subheader("Contador")
    contador_email = st.text_input("Email do Contador", value=env_vars.get("EMAIL_CONTADOR", ""))
    if st.button("Salvar Email do Contador"):
        if contador_email:
            save_env_var("EMAIL_CONTADOR", contador_email)
            st.success("Email salvo com sucesso em `.env`!")

    # ASAAS config
    st.markdown("---")
    st.subheader("ASAAS")
    has_asaas = "✅ Configurado" if "ASAAS_API_KEY" in env_vars else "❌ Pendente"
    st.write(f"Status Atual: **{has_asaas}**")
    asaas_key = st.text_input("Chave de API ASAAS", type="password", value=env_vars.get("ASAAS_API_KEY", ""))
    if st.button("Salvar ASAAS", key="btn_asaas"):
        if asaas_key:
            save_env_var("ASAAS_API_KEY", asaas_key)
            st.success("Chave ASAAS salva com sucesso!")
            st.rerun()

    # Visiun config
    st.markdown("---")
    st.subheader("Visiun")
    has_visiun = "✅ Configurado" if "VISIUN_API_KEY" in env_vars else "❌ Pendente"
    st.write(f"Status Atual: **{has_visiun}**")
    visiun_key = st.text_input("Chave de API Visiun", type="password", value=env_vars.get("VISIUN_API_KEY", ""))
    if st.button("Salvar Visiun", key="btn_visiun"):
        if visiun_key:
            save_env_var("VISIUN_API_KEY", visiun_key)
            st.success("Chave Visiun salva com sucesso!")
            st.rerun()


    # Banco Inter API Config
    st.markdown("---")
    st.subheader("Banco Inter (API & Certificado)")
    has_inter_api = "✅ Configurado" if "INTER_CLIENT_ID" in env_vars else "❌ Pendente"
    has_inter_cert = "✅ Configurado" if "INTER_CERT" in env_vars else "❌ Pendente"
    st.write(f"Status API: **{has_inter_api}** | Status Certificado: **{has_inter_cert}**")
    
    col1, col2 = st.columns(2)
    with col1:
        inter_client_id = st.text_input("Client ID", value=env_vars.get("INTER_CLIENT_ID", ""))
    with col2:
        inter_client_secret = st.text_input("Client Secret", type="password", value=env_vars.get("INTER_CLIENT_SECRET", ""))
        
    if st.button("Salvar Credenciais da API (Inter)"):
        if inter_client_id and inter_client_secret:
            save_env_var("INTER_CLIENT_ID", inter_client_id)
            save_env_var("INTER_CLIENT_SECRET", inter_client_secret)
            st.success("Credenciais do Banco Inter salvas com sucesso!")
            st.rerun()

    # Reordered section: Certificates right below API
    st.write("### Certificados (mTLS)")
    os.makedirs(CERTS_DIR, exist_ok=True)
    uploaded_crt = st.file_uploader("Upload Novo Certificado (.crt)", type=["crt"], key="up_crt")
    uploaded_key = st.file_uploader("Upload Nova Chave Privada (.key)", type=["key"], key="up_key")

    if st.button("Salvar Arquivos de Certificado", key="btn_inter_certs"):
        if uploaded_crt and uploaded_key:
            crt_path = os.path.join(CERTS_DIR, uploaded_crt.name)
            key_path = os.path.join(CERTS_DIR, uploaded_key.name)
            
            with open(crt_path, "wb") as f_crt:
                f_crt.write(uploaded_crt.getbuffer())
            with open(key_path, "wb") as f_key:
                f_key.write(uploaded_key.getbuffer())
            
            save_env_var("INTER_CERT", crt_path)
            save_env_var("INTER_KEY", key_path)
            st.success(f"Certificados salvos com sucesso!")
            st.rerun()
        else:
            st.error("Envie ambos os arquivos (.crt e .key)")

    # Inter Pix Key Config
    st.markdown("---")
    st.subheader("Chave Pix de Destino (Para Varredura Asaas)")
    has_pix = "✅ Configurado" if "INTER_PIX_KEY" in env_vars else "❌ Pendente"
    st.write(f"Status da Chave: **{has_pix}**")
    
    col_pk1, col_pk2 = st.columns(2)
    with col_pk1:
        pix_key = st.text_input("Sua Chave Pix (Banco Inter)", value=env_vars.get("INTER_PIX_KEY", ""))
    with col_pk2:
        pix_type = st.selectbox("Tipo da Chave", ["CPF", "CNPJ", "EMAIL", "PHONE", "EVP"], 
                               index=["CPF", "CNPJ", "EMAIL", "PHONE", "EVP"].index(env_vars.get("INTER_PIX_KEY_TYPE", "CNPJ")) if "INTER_PIX_KEY_TYPE" in env_vars else 1)
                               
    if st.button("Salvar Chave Pix de Recebimento"):
        if pix_key and pix_type:
                save_env_var("INTER_PIX_KEY", pix_key)
                save_env_var("INTER_PIX_KEY_TYPE", pix_type)
                st.success("Chave Pix salva com sucesso!")
                st.rerun()



def dados_contador_tab():
    st.header("Dados para Contador")
    st.write("Exporte OFX e CSV de todas as transações, e gerencie o envio para o email configurado.")
    
    env_vars = load_env_vars()
    contador_email = env_vars.get("EMAIL_CONTADOR", "")
    
    if not contador_email:
        st.warning("O email do contador não está configurado. Vá na aba 'Configurações de API' para adicionar.")
    else:
        st.info(f"Email configurado: **{contador_email}**")
        
    db = DatabaseManager()
    
    st.markdown("---")
    st.subheader("Envio Manual / Download")
    
    # Let the user pick a month to export
    hoje = datetime.date.today()
    mes_atual = hoje.replace(day=1)
    mes_anterior = (mes_atual - datetime.timedelta(days=1)).replace(day=1)
    
    opcoes_meses = [
        mes_atual.strftime("%m/%Y"),
        mes_anterior.strftime("%m/%Y")
    ]
    
    mes_selecionado = st.selectbox("Selecione o Mês Base", opcoes_meses)
    
    if st.button("Gerar Arquivos e Enviar Agora"):
        if not contador_email:
            st.error("Configure o email do contador primeiro.")
        else:
            with st.spinner("Conectando ao Banco Inter e gerando relatórios..."):
                from exports import generate_csv_summary
                from mailer import send_accountant_email
                from inter_client import InterClient
                import calendar
                
                # Setup date range
                month_str, year_str = mes_selecionado.split('/')
                last_day = calendar.monthrange(int(year_str), int(month_str))[1]
                data_inicio = f"{year_str}-{month_str}-01"
                data_fim = f"{year_str}-{month_str}-{last_day:02d}"
                
                # 1. Fetch from Banco Inter
                pdf_b64 = None
                ofx_b64 = None
                inter_error = None
                try:
                    client = InterClient()
                    pdf_b64 = client.get_extrato_export(data_inicio, data_fim, "PDF")
                    ofx_b64 = client.get_extrato_export(data_inicio, data_fim, "OFX")
                except Exception as e:
                    inter_error = str(e)
                    
                if inter_error:
                    st.error(f"Erro ao baixar extratos do Banco Inter: {inter_error}")
                else:
                    # 2. Generate Client Payment CSV for NF issuance
                    clientes_csv_bytes = None
                    try:
                        import io, csv
                        all_txs = db.get_transactions()
                        # Filter: type entrada/entrada_liquida, recebido, in the selected month
                        receitas_mes = []
                        for tx in all_txs:
                            tx_id, tx_orig, tx_tipo, tx_valor, tx_data, tx_status, tx_cpf, tx_placa = tx
                            if tx_tipo in ("entrada", "entrada_liquida") and tx_status in ("recebido", "pago"):
                                tx_date = pd.to_datetime(tx_data)
                                if tx_date.month == int(month_str) and tx_date.year == int(year_str) and tx_cpf:
                                    receitas_mes.append(tx)
                        
                        if receitas_mes:
                            # Group by CPF
                            cpf_totals = {}
                            for tx in receitas_mes:
                                cpf = tx[6]
                                valor = float(tx[3])
                                if cpf not in cpf_totals:
                                    cpf_totals[cpf] = {"total": 0.0, "qtd": 0}
                                cpf_totals[cpf]["total"] += valor
                                cpf_totals[cpf]["qtd"] += 1
                            
                            # Enrich with locatário data
                            locatarios = db.get_locatarios_list()
                            cpf_to_name = {l[2]: l[1] for l in locatarios}
                            cpf_to_tel = {l[2]: l[3] for l in locatarios}
                            
                            output = io.StringIO()
                            writer = csv.writer(output)
                            writer.writerow(["Nome", "CPF", "Telefone", "Qtd Recebimentos", "Total Recebido (R$)"])
                            for cpf, info in cpf_totals.items():
                                nome = cpf_to_name.get(cpf, "Não cadastrado")
                                tel = cpf_to_tel.get(cpf, "")
                                writer.writerow([nome, cpf, tel, info["qtd"], f"{info['total']:.2f}"])
                            
                            clientes_csv_bytes = output.getvalue().encode("utf-8")
                            st.success(f"CSV de clientes gerado: {len(cpf_totals)} clientes com recebimentos no mês.")
                    except Exception as e:
                        st.warning(f"Não foi possível gerar o CSV de clientes: {e}")
                    
                    # 3. Send Email
                    success, msg = send_accountant_email(
                        contador_email, mes_selecionado, 
                        ofx_b64=ofx_b64, pdf_b64=pdf_b64,
                        clientes_csv_bytes=clientes_csv_bytes
                    )
                    
                    if success:
                        db.record_accountant_export(mes_selecionado, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sucesso", st.session_state.user_name)
                        st.success(f"Extratos oficiais enviados com sucesso para {contador_email}! ({msg})")
                    else:
                        db.record_accountant_export(mes_selecionado, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "falha", st.session_state.user_name)
                        st.error(msg)
                        
    st.markdown("---")
    st.subheader("Histórico de Envios Automatizados")
    
    historico = db.get_accountant_exports()
    if historico:
        # DB schema assumes columns: ID, Mês Referência, Data do Envio, Status, Enviado Por
        df_hist = pd.DataFrame(historico, columns=["ID", "Mês Referência", "Data do Envio", "Status", "Enviado Por"])
        df_hist["Data do Envio"] = pd.to_datetime(df_hist["Data do Envio"]).dt.strftime("%d/%m/%Y %H:%M:%S")
        st.dataframe(df_hist, hide_index=True)
    else:
        st.write("Nenhum envio registrado.")

# --- Main App ---

def auto_send_accountant_export():
    env_vars = load_env_vars()
    contador_email = env_vars.get("EMAIL_CONTADOR", "")
    
    if not contador_email:
        return
        
    hoje = datetime.date.today()
    if hoje.day >= 5:
        mes_anterior = (hoje.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
        db = DatabaseManager()
        
        if not db.has_sent_export_for_month(mes_anterior):
            from exports import generate_csv_summary
            from mailer import send_accountant_email
            from inter_client import InterClient
            import calendar
            
            year_str, month_str = mes_anterior.split('-')
            last_day = calendar.monthrange(int(year_str), int(month_str))[1]
            data_inicio = f"{mes_anterior}-01"
            data_fim = f"{mes_anterior}-{last_day:02d}"
            
            try:
                client = InterClient()
                pdf_b64 = client.get_extrato_export(data_inicio, data_fim, "PDF")
                ofx_b64 = client.get_extrato_export(data_inicio, data_fim, "OFX")
                
                success, msg = send_accountant_email(contador_email, mes_anterior, ofx_b64=ofx_b64, pdf_b64=pdf_b64)
                if success:
                    db.record_accountant_export(mes_anterior, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sucesso", "Robô Automático")
                    st.toast(f"✅ Relatório oficial do mês {mes_anterior} enviado automaticamente para o contador.")
                else:
                    db.record_accountant_export(mes_anterior, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "falha", "Robô Automático")
                    st.toast(f"❌ Falha no envio automático para o contador: {msg}")
            except Exception as e:
                st.toast(f"❌ Falha na integração com Banco Inter no envio automático: {str(e)}")

def main():
    st.set_page_config(page_title="Locamotos", page_icon="🏍️", layout="wide")
    
    # --- Dark Mode Premium Theme ---
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* === BASE === */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
        color: #E2E8F0 !important;
        color-scheme: dark !important;
    }
    .stApp {
        background: linear-gradient(145deg, #0D0F12 0%, #111318 50%, #0D0F12 100%) !important;
        color: #E2E8F0 !important;
    }
    /* Force all generic containers dark */
    .main .block-container, .stMainBlockContainer, [data-testid="stAppViewBlockContainer"] {
        color: #E2E8F0 !important;
    }
    /* Force ALL text elements */
    .stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown li, .stMarkdown div,
    .stText, div[data-testid="stText"], .element-container {
        color: #CBD5E1 !important;
    }
    /* Force strong/bold white */
    .stMarkdown strong, .stMarkdown b {
        color: #F1F5F9 !important;
    }

    /* === TYPOGRAPHY === */
    h1, h2, h3, h4, h5, h6 {
        font-weight: 600 !important;
        letter-spacing: -0.02em;
        color: #F1F5F9 !important;
    }
    h1 { color: #FFFFFF !important; }
    p, span, label, .stMarkdown {
        color: #CBD5E1 !important;
    }

    /* === SIDEBAR === */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #131620 0%, #0F1117 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
    }
    [data-testid="stSidebar"] * {
        color: #CBD5E1 !important;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        color: #00D4AA !important;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
        color: #FFFFFF !important;
    }
    /* Sidebar radio selected */
    [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"] {
        color: #00D4AA !important;
        font-weight: 600 !important;
    }

    /* === HEADER === */
    header[data-testid="stHeader"] {
        background-color: rgba(13, 15, 18, 0.8) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
    }

    /* === BUTTONS === */
    .stButton > button {
        background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%) !important;
        color: #0D0F12 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.4rem !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 8px rgba(0, 212, 170, 0.15) !important;
        letter-spacing: 0.01em !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #00E5B8 0%, #00CCA3 100%) !important;
        box-shadow: 0 4px 16px rgba(0, 212, 170, 0.3) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:active {
        transform: translateY(0px) !important;
        box-shadow: 0 2px 4px rgba(0, 212, 170, 0.2) !important;
    }
    /* Form submit buttons */
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%) !important;
        color: #0D0F12 !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
    }

    /* === METRICS === */
    [data-testid="stMetricValue"] {
        font-weight: 700 !important;
        color: #FFFFFF !important;
        font-size: 1.8rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
    }
    [data-testid="stMetricDelta"] > div {
        color: #00D4AA !important;
    }

    /* === CARDS / CONTAINERS === */
    [data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(22, 26, 33, 0.6) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(8px) !important;
    }

    /* === ALERTS / INFO / SUCCESS / WARNING / ERROR === */
    .stAlert {
        border-radius: 10px !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
    /* Force all alert text light */
    .stAlert *, .stAlert p, .stAlert span, .stAlert div,
    [data-testid="stAlert"] *, [data-testid="stAlert"] p,
    [data-testid="stAlert"] span, [data-testid="stAlert"] div {
        color: #CBD5E1 !important;
    }
    div[data-testid="stAlert"]:has(div[role="alert"]) {
        background-color: rgba(22, 26, 33, 0.8) !important;
        border: 1px solid rgba(0, 212, 170, 0.15) !important;
    }
    /* Success alerts */
    div[data-testid="stAlert"][data-baseweb="notification"]:has([kind="positive"]),
    .element-container .stSuccess {
        background-color: rgba(0, 212, 170, 0.08) !important;
        border: 1px solid rgba(0, 212, 170, 0.2) !important;
    }
    /* Warning alerts */  
    div[data-testid="stAlert"][data-baseweb="notification"]:has([kind="warning"]),
    .element-container .stWarning {
        background-color: rgba(250, 204, 21, 0.08) !important;
        border: 1px solid rgba(250, 204, 21, 0.2) !important;
    }
    /* Error alerts */
    div[data-testid="stAlert"][data-baseweb="notification"]:has([kind="negative"]),
    .element-container .stError {
        background-color: rgba(239, 68, 68, 0.08) !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
    }

    /* === DATAFRAMES / TABLES === */
    [data-testid="stDataFrame"] {
        border-radius: 10px !important;
        overflow: hidden !important;
    }
    [data-testid="stDataFrame"] > div {
        background-color: #161A21 !important;
        border-radius: 10px !important;
    }
    /* Table header */
    [data-testid="stDataFrame"] thead th {
        background-color: #1E2330 !important;
        color: #94A3B8 !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.05em !important;
    }
    /* Table rows */
    [data-testid="stDataFrame"] tbody td {
        color: #CBD5E1 !important;
        border-bottom: 1px solid rgba(255,255,255,0.04) !important;
    }
    [data-testid="stDataFrame"] tbody tr:hover td {
        background-color: rgba(0, 212, 170, 0.04) !important;
    }

    /* === INPUTS === */
    .stTextInput input, .stNumberInput input {
        background-color: #161A21 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
        color: #E2E8F0 !important;
        transition: border-color 0.2s ease !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #00D4AA !important;
        box-shadow: 0 0 0 2px rgba(0, 212, 170, 0.15) !important;
    }
    /* Select boxes */
    .stSelectbox > div > div {
        background-color: #161A21 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
        color: #E2E8F0 !important;
    }
    .stSelectbox [data-baseweb="select"] span {
        color: #E2E8F0 !important;
    }
    /* Date input */
    .stDateInput > div > div {
        background-color: #161A21 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
    }
    .stDateInput input {
        color: #E2E8F0 !important;
    }
    /* Checkbox */
    .stCheckbox label span {
        color: #CBD5E1 !important;
    }

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent !important;
        border-bottom: 1px solid rgba(255,255,255,0.06) !important;
        gap: 0 !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #64748B !important;
        font-weight: 500 !important;
        border-bottom: 2px solid transparent !important;
        padding: 0.75rem 1.2rem !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #E2E8F0 !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #00D4AA !important;
        border-bottom: 2px solid #00D4AA !important;
        font-weight: 600 !important;
    }

    /* === EXPANDERS === */
    .streamlit-expanderHeader {
        background-color: rgba(22, 26, 33, 0.6) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 10px !important;
        color: #E2E8F0 !important;
    }
    .streamlit-expanderContent {
        background-color: rgba(22, 26, 33, 0.4) !important;
        border: 1px solid rgba(255,255,255,0.04) !important;
        border-top: none !important;
    }

    /* === FORMS === */
    [data-testid="stForm"] {
        background-color: rgba(22, 26, 33, 0.5) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
    }

    /* === DIVIDERS === */
    hr {
        border-color: rgba(255,255,255,0.06) !important;
    }

    /* === FILE UPLOADER === */
    [data-testid="stFileUploader"] {
        background-color: rgba(22, 26, 33, 0.4) !important;
        border: 1px dashed rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(0, 212, 170, 0.3) !important;
    }

    /* === CHARTS === */
    [data-testid="stVegaLiteChart"] {
        background-color: rgba(22, 26, 33, 0.4) !important;
        border-radius: 12px !important;
        padding: 0.5rem !important;
    }

    /* === TOAST === */
    [data-testid="stToast"] {
        background-color: #1E2330 !important;
        color: #E2E8F0 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
    }

    /* === SCROLLBAR === */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.1);
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255,255,255,0.2);
    }

    /* === POPOVER / DROPDOWN MENUS === */
    [data-baseweb="popover"] {
        background-color: #1E2330 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
    }
    [data-baseweb="menu"] {
        background-color: #1E2330 !important;
    }
    [data-baseweb="menu"] li {
        color: #CBD5E1 !important;
    }
    [data-baseweb="menu"] li:hover {
        background-color: rgba(0, 212, 170, 0.1) !important;
    }
    
    /* === SPINNER === */
    .stSpinner > div {
        border-top-color: #00D4AA !important;
    }

    /* === LINKS === */
    a {
        color: #00D4AA !important;
    }
    a:hover {
        color: #00E5B8 !important;
    }

    /* === RADIO BUTTONS (Main Content) === */
    .stRadio [role="radiogroup"] label {
        color: #CBD5E1 !important;
        transition: color 0.2s ease !important;
    }
    .stRadio [role="radiogroup"] label:hover {
        color: #00D4AA !important;
    }

    /* === NUMBER INPUT BUTTONS === */
    .stNumberInput button {
        background-color: #1E2330 !important;
        color: #CBD5E1 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
    }
    .stNumberInput button:hover {
        background-color: rgba(0, 212, 170, 0.15) !important;
        color: #00D4AA !important;
    }

    /* === MULTISELECT === */
    .stMultiSelect > div > div {
        background-color: #161A21 !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
    }
    .stMultiSelect [data-baseweb="tag"] {
        background-color: rgba(0, 212, 170, 0.15) !important;
        color: #00D4AA !important;
        border-radius: 6px !important;
    }

    /* === LOADING MESSAGE === */
    .stMarkdown div[style*="text-align: center"] {
        color: #94A3B8 !important;
    }

    </style>
    """, unsafe_allow_html=True)
    
    if not init_session_state():
        st.markdown("<div style='text-align: center; margin-top: 20%;'>Carregando sessão de segurança...</div>", unsafe_allow_html=True)
        st.stop()
        
    # Process pending cookie operations securely before rendering anything
    if "cookie_to_set" in st.session_state:
        exp_date = datetime.datetime.now() + datetime.timedelta(days=5)
        cookie_manager.set("locamotos_user", st.session_state.cookie_to_set, expires_at=exp_date)
        del st.session_state.cookie_to_set
        
    if "cookie_to_delete" in st.session_state:
        cookie_manager.delete("locamotos_user")
        del st.session_state.cookie_to_delete
    
    
    if not st.session_state.logged_in:
        login_register_screen()
    else:
        # Check auto send
        if st.session_state.user_role == "admin":
            auto_send_accountant_export()
            
        # Sidebar Navigation
        st.sidebar.title("Locamotos")
        st.sidebar.write(f"Olá, **{st.session_state.user_name}**")
        
        # Determine accessible tabs
        available_tabs = [
            "Dashboard",
            "ASAAS",
            "Inter",
            "Motos",
            "Locatários",
            "Receitas e Despesas"
        ]
        
        # Restrict Configurações only to dansorrel (Daniel Sorrentino)
        if st.session_state.user_name == "Daniel Sorrentino" or st.session_state.user_id == 1:
            available_tabs.append("Configurações")
        
        # DEV OVERRIDE REMOVED
        
        if "active_tab" not in st.session_state:
            st.session_state.active_tab = "Dashboard"
            
        if st.session_state.active_tab not in available_tabs:
            st.session_state.active_tab = "Dashboard"

        selection = st.sidebar.radio("Navegação", available_tabs, key="active_tab")
        
        if st.sidebar.button("Sair (Log Out)"):
            do_logout()
            
        # Router
        if selection == "Dashboard":
            dashboard_tab()
        elif selection == "ASAAS":
            asaas_tab()
        elif selection == "Inter":
            inter_tab()
        elif selection == "Motos":
            motos_ui_tab()
        elif selection == "Locatários":
            locatarios_ui_tab()
        elif selection == "Receitas e Despesas":
            receitas_despesas_tab()
        elif selection == "Configurações":
            config_ui_tab()

if __name__ == "__main__":
    main()
