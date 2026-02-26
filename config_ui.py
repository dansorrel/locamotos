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

    # Check for remember me cookie
    if not st.session_state.logged_in:
        cookies = cookie_manager.get_all()
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

def do_login(username_login, password, lembrar_user):
    db = DatabaseManager()
    user = db.get_user_by_username(username_login)
    if user:
        user_id, nome, username_db, email_db, senha_hash, papel, status, permissoes, created_at = user
        if verify_password(senha_hash, password):
            if status == "aprovado":
                if lembrar_user:
                    # Expire in 5 days
                    exp_date = datetime.datetime.now() + datetime.timedelta(days=5)
                    cookie_manager.set("locamotos_user", username_db, expires_at=exp_date)
                    
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
    cookie_manager.delete("locamotos_user")
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
        asaas_count_cust = len(ac.get_customers())
    except Exception:
        saldo_asaas = 0.0
        asaas_pagos = 0
        asaas_vencidos = 0
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
        st.info(f"Saldo Recebível: R$ {format_currency(saldo_asaas)}")
    with c2:
        st.write(f"**Métricas (30 dias):** {asaas_pagos} Recebimentos | {asaas_vencidos} Vencidos | Clientes Ativos: {asaas_count_cust}")
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
        st.button("Acessar Despesas", use_container_width=True, on_click=change_tab_state, args=("Despesas",))

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
                
                # Dynamically find any date columns to ensure we catch whatever the API returns
                date_columns = [col for col in df_inter.columns if "data" in col.lower() or "date" in col.lower()]
                for dc in date_columns:
                    try:
                        df_inter[dc] = pd.to_datetime(df_inter[dc]).dt.strftime("%d/%m/%Y")
                    except:
                        pass
                
                # Build columns to show, prioritizing the first found date column
                cols_to_show = []
                # First try the specific ones asked by user, otherwise fallback to any date column
                if "dataLancamento" in df_inter.columns:
                    cols_to_show.append("dataLancamento")
                elif "dataTransacao" in df_inter.columns:
                    cols_to_show.append("dataTransacao")
                elif "dataInclusao" in df_inter.columns:
                    cols_to_show.append("dataInclusao")
                elif date_columns:
                    cols_to_show.append(date_columns[0])
                    
                # Add the rest of the standard columns
                for c in ["tipoTransacao", "valor", "descricao"]:
                    if c in df_inter.columns:
                        cols_to_show.append(c)
                if cols_to_show:
                    if "valor" in cols_to_show:
                        st.dataframe(
                            df_inter[cols_to_show],
                            use_container_width=True,
                            column_config={
                                "valor": st.column_config.NumberColumn(
                                    "Valor",
                                    format="R$ %.2f"
                                )
                            }
                        )
                    else:
                        st.dataframe(
                            df_inter[cols_to_show],
                            use_container_width=True
                        )
                else:
                    st.dataframe(
                        df_inter,
                        use_container_width=True,
                        column_config={
                            "valor": st.column_config.NumberColumn(
                                "Valor",
                                format="R$ %.2f"
                            )
                        } if "valor" in df_inter.columns else None
                    )
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
        st.subheader("Cobranças e Valores a Receber (Asaas)")
        
        hoje = datetime.date.today()
        opcoes_periodo = [
            "Desde 01/01/2025",
            "Mês Atual",
            "Ano Corrente",
            "Últimos 30 dias",
            "Últimos 90 dias",
            "Busca Personalizada"
        ]
        
        with st.form("visiun_fin_filter"):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                periodo = st.selectbox("Período de Criação", opcoes_periodo)
            with c2:
                d_inicio = st.date_input("Início", value=datetime.date(2025, 1, 1))
            with c3:
                d_fim = st.date_input("Fim", value=hoje)
            with c4:
                st.write("")
                st.write("")
                st_visiun_fin = st.form_submit_button("Filtrar")
                
        if periodo == "Desde 01/01/2025":
            start_date = "2025-01-01"
            end_date = hoje.strftime("%Y-%m-%d")
        elif periodo == "Mês Atual":
            start_date = hoje.replace(day=1).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        elif periodo == "Ano Corrente":
            start_date = hoje.replace(month=1, day=1).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        elif periodo == "Últimos 30 dias":
            start_date = (hoje - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        elif periodo == "Últimos 90 dias":
            start_date = (hoje - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
            end_date = hoje.strftime("%Y-%m-%d")
        else:
            start_date = d_inicio.strftime("%Y-%m-%d")
            end_date = d_fim.strftime("%Y-%m-%d")

        try:
            from asaas_client import AsaasClient
            client = AsaasClient()
            customers = client.get_customers()
            customer_map = {c.get("id"): c.get("name", "Desconhecido") for c in customers}
            
            with st.spinner("Buscando boletos no ASAAS..."):
                pagamentos = client.get_all_payments(start_date, end_date)
            
            if pagamentos:
                df_pgs = pd.DataFrame(pagamentos)
                
                df_pgs["Valor Cobrado"] = df_pgs.apply(lambda row: 
                    (row.get("value") or 0.0) + 
                    (row.get("interestValue") or 0.0) + 
                    (row.get("fineValue") or 0.0) - 
                    (row.get("discount", {}).get("value", 0.0) if isinstance(row.get("discount"), dict) else 0.0)
                    if row.get("status") in ["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"] else (row.get("value") or 0.0), axis=1)
                
                df_pgs["Sacado"] = df_pgs.get("customer", "").map(lambda c_id: customer_map.get(c_id, "Desconhecido"))
                
                def format_date_safe(date_str):
                    if not date_str: return ""
                    return pd.to_datetime(date_str).strftime("%d/%m/%Y")
                    
                df_pgs["Vencimento"] = df_pgs.get("dueDate", "").apply(format_date_safe)
                if "paymentDate" in df_pgs.columns:
                    df_pgs["Pagamento"] = df_pgs.get("paymentDate", "").apply(format_date_safe)
                else:
                    df_pgs["Pagamento"] = ""
                
                status_map = {
                    "PENDING": "🟡 Pendente",
                    "RECEIVED": "🟢 Recebido",
                    "CONFIRMED": "🟢 Confirmado",
                    "OVERDUE": "🔴 Vencido",
                    "REFUNDED": "🔄 Estornado",
                    "RECEIVED_IN_CASH": "💵 Recebido Físico"
                }
                df_pgs["Status"] = df_pgs.get("status", "").map(lambda s: status_map.get(s, s))
                
                grouped = df_pgs.groupby("Sacado")
                
                st.write(f"Encontrados registros para **{len(grouped)}** pilotos no período.")
                
                for sacado, group in sorted(grouped):
                    pagos_mask = group.get("status", "").isin(["RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"])
                    pagos_df = group[pagos_mask]
                    pendentes_df = group[~pagos_mask & (group.get("status", "") != "REFUNDED")]
                    
                    total_pago = pagos_df["Valor Cobrado"].sum()
                    total_pendente = pendentes_df["Valor Cobrado"].sum()
                    
                    with st.expander(f"👤 {sacado} | Pago: R$ {total_pago:,.2f} | A Receber: R$ {total_pendente:,.2f}"):
                        pc1, pc2 = st.columns(2)
                        
                        with pc1:
                            st.markdown("##### ✅ Pagos")
                            if not pagos_df.empty:
                                show_pagos = pagos_df[["Pagamento", "Vencimento", "Valor Cobrado", "Status"]].copy()
                                st.dataframe(
                                    show_pagos, 
                                    hide_index=True, 
                                    use_container_width=True,
                                    column_config={"Valor Cobrado": st.column_config.NumberColumn("Valor Cobrado", format="R$ %.2f")}
                                )
                            else:
                                st.info("Nenhum boleto pago no período.")
                                
                        with pc2:
                            st.markdown("##### ⏳ A Receber / Vencidos")
                            if not pendentes_df.empty:
                                show_pendentes = pendentes_df[["Vencimento", "Valor Cobrado", "Status"]].copy()
                                show_pendentes = show_pendentes.sort_values(by="Vencimento")
                                st.dataframe(
                                    show_pendentes, 
                                    hide_index=True, 
                                    use_container_width=True,
                                    column_config={"Valor Cobrado": st.column_config.NumberColumn("Valor Cobrado", format="R$ %.2f")}
                                )
                            else:
                                st.info("Nenhum boleto pendente no período.")
            else:
                st.info("Nenhum boleto gerado no Asaas neste período.")
                
        except Exception as e:
            st.error(f"Erro ao carregar os dados financeiros do Asaas: {e}")

def asaas_tab():
    st.header("💳 ASAAS")
    st.write("Boletos, contas a receber, valores a transferir para Inter.")
    st.markdown("---")
    
    try:
        from asaas_client import AsaasClient
        client = AsaasClient()
        
        # Top Metrics
        saldo = client.get_balance()
        customers = client.get_customers()
        
        c_top1, c_top2 = st.columns(2)
        c_top1.metric("Saldo Disponível (Asaas)", format_currency(saldo))
        c_top2.metric("Total de Clientes (Asaas)", len(customers))
        
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
                        style.append('color: red; font-weight: bold')
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

def despesas_tab():
    st.header("📉 Despesas")
    st.write("Royalties, contador, taxa de aluguel de espaço, cooperloc, fundo de marketing, taxa de publicidade, licenciamento, IPVA, seguros, pró-labore.")
    
    db = DatabaseManager()
    
    st.subheader("Registrar Despesa Manualmente")
    
    try:
        motos = db.get_all_motos()
    except Exception:
        motos = []
        
    with st.form("manual_entry_form"):
        col_cat, col_placa, col_data = st.columns(3)
        with col_cat:
            categoria = st.selectbox("Categoria", [
                "Royalties", "Contador", "Taxa de aluguel de espaço", "Cooperloc", 
                "Fundo de marketing", "Taxa de publicidade", "Licenciamento", 
                "IPVA", "Seguros", "Pró-labore"
            ])
        with col_placa:
            sel_placa = st.selectbox("Moto (Placa) [Opcional]", ["Geral/Administrativo"] + motos)
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
                # Note: We might want to store the category in the database too.
                # For now, adding it to description or similar if we have it.
            )
            st.success(f"Despesa de {categoria} registrada com sucesso!")
            st.rerun()
                
    st.markdown("---")
    st.subheader("Histórico de Despesas")

    all_txs = db.get_transactions()
    all_despesas = [tx for tx in all_txs if tx[2] == 'saida']
    
    if not all_despesas:
        st.info("Nenhuma despesa registrada ainda.")
        return

    if all_despesas:
        df = pd.DataFrame(all_despesas, columns=["ID", "Origem", "Tipo", "Valor", "Data", "Status", "CPF/ID", "Placa da Moto"])
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
    
    with st.form("despesas_form"):
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
            submit_despesas = st.form_submit_button("Ir", use_container_width=True)
        
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
    
    st.metric("Total de Despesas no Período", format_currency(filtered_df['Valor'].sum()))
    
    filtered_df["Valor"] = filtered_df["Valor"].apply(format_currency)
    st.dataframe(
        filtered_df.style.set_properties(subset=['Valor'], **{'text-align': 'right', 'padding-right': '15px'}), 
        use_container_width=True, 
        hide_index=True
    )

def config_ui_tab():
    st.header("Configurações")
    
    tab_sistema, tab_usuarios = st.tabs(["Sistema (APIs e E-mail)", "Gestão de Usuários"])
    
    with tab_sistema:
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

    with tab_usuarios:
        st.write("Crie novos acessos, defina quais abas cada usuário pode ver e altere senhas.")
        
        db = DatabaseManager()
        
        with st.expander("✨ Criar Novo Usuário"):
            with st.form("admin_create_user_form"):
                new_nome = st.text_input("Nome Completo")
                new_user = st.text_input("Usuário (Login)")
                new_email = st.text_input("E-mail (Opcional)")
                new_pass = st.text_input("Senha", type="password")
                
                todas_abas = [
                    "Dashboard",
                    "ASAAS",
                    "Inter",
                    "Visiun",
                    "Despesas",
                    "Configurações"
                ]
                
                new_perms = st.multiselect("Abas Permitidas", todas_abas, default=["Dashboard", "Receitas", "Despesas"])
                new_papel = st.selectbox("Papel Geral (Legado)", ["user", "viewer", "admin"])
                
                submitted_new = st.form_submit_button("Criar Usuário")
                if submitted_new:
                    if new_nome and new_user and new_pass:
                        is_valid, msg = is_strong_password(new_pass)
                        if not is_valid:
                            st.error(msg)
                        else:
                            perms_str = ",".join(new_perms)
                            hashed = hash_password(new_pass)
                            sucesso = db.create_user(new_nome, new_user, new_email, hashed, new_papel, "aprovado", permissoes=perms_str)
                            if sucesso:
                                st.success(f"Usuário {new_user} criado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Nome de usuário já existe.")
                    else:
                        st.error("Nome, Usuário e Senha são obrigatórios.")
                        
        st.markdown("---")
        st.subheader("Usuários Existentes")
        
        users = db.get_all_users()
        if users:
            for user in users:
                uid, nome, username_db, email_db, papel, status, permissoes_db, created_at = user
                
                # Default permissions if null or empty
                if not permissoes_db:
                    if papel == 'admin':
                        current_perms = ["Dashboard", "Frota", "Locatários", "Posição Inter", "Posição Asaas", "Posição Visiun", "Receitas", "Despesas", "Configurações", "Dados para Contador"]
                    else:
                        current_perms = ["Receitas", "Despesas", "Dashboard"]
                else:
                    current_perms = [p.strip() for p in permissoes_db.split(",") if p.strip()]
                    
                with st.expander(f"👤 {nome} ({username_db}) - Status: {status.upper()}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_nome = st.text_input("Nome Completo", value=nome, key=f"n_{uid}")
                        opts_status = ["aprovado", "pendente", "bloqueado"]
                        new_status = st.selectbox("Status", opts_status, index=opts_status.index(status), key=f"s_{uid}")
                        new_papel = st.selectbox("Papel (Legado)", ["admin", "user", "viewer"], index=["admin", "user", "viewer"].index(papel), key=f"r_{uid}")
                        
                        st.write("Recalcular Senha")
                        new_password = st.text_input("Nova Senha (deixe em branco para manter)", type="password", key=f"p_{uid}")
                        
                    with col2:
                        todas_abas = [
                            "Dashboard",
                            "ASAAS",
                            "Inter",
                            "Visiun",
                            "Despesas",
                            "Configurações"
                        ]
                        
                        st.write("**Acesso aos Módulos (Selecione Individualmente):**")
                        # Create a layout for checkboxes (e.g., 2 per row)
                        new_perms = []
                        valid_current_perms = [p for p in current_perms if p in todas_abas]
                        
                        # Loop through all available tabs to create an individual checkbox for each
                        for idx, tab_name in enumerate(todas_abas):
                            is_checked = tab_name in valid_current_perms
                            # Use a unique key combining user_id and tab index
                            if st.checkbox(tab_name, value=is_checked, key=f"chk_{uid}_{idx}"):
                                new_perms.append(tab_name)
                    
                    if st.button("Salvar Alterações do Usuário", key=f"save_{uid}"):
                        perms_str = ",".join(new_perms)
                        db.update_user_access(uid, new_nome, new_status, new_papel, perms_str)
                        
                        if new_password:
                            is_valid, msg = is_strong_password(new_password)
                            if not is_valid:
                                st.error(msg)
                            else:
                                db.update_user_password(uid, hash_password(new_password))
                                st.success("Permissões e senha atualizadas com sucesso!")
                                st.rerun()
                        else:
                            st.success("Permissões atualizadas com sucesso!")
                            st.rerun()
        else:
            st.info("Nenhum usuário encontrado.")

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
                    # 3. Send Email
                    success, msg = send_accountant_email(contador_email, mes_selecionado, ofx_b64=ofx_b64, pdf_b64=pdf_b64)
                    
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
    init_session_state()
    
    
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
        # GRANT ALL PERMISSIONS TO ALL USERS
        available_tabs = [
            "Dashboard",
            "ASAAS",
            "Inter",
            "Motos",
            "Locatários",
            "Despesas",
            "Configurações"
        ]
        
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
        elif selection == "Despesas":
            despesas_tab()
        elif selection == "Configurações":
            config_ui_tab()

if __name__ == "__main__":
    main()
