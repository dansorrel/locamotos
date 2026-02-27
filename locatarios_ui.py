import streamlit as st
import pandas as pd
import datetime
from database_manager import DatabaseManager
import base64

def locatarios_tab():
    st.header("Gestão de Locatários (Pilotos)")
    db = DatabaseManager()

    st.markdown("---")
    
    col_t1, col_t2 = st.columns([2, 2])
    with col_t1:
        st.subheader("🏁 Listagem Unificada (Visiun + Asaas)")
    with col_t2:
        if st.button("🔄 Sincronizar Pilotos com ASAAS", use_container_width=True, type="primary"):
            try:
                from asaas_client import AsaasClient
                client = AsaasClient()
                asaas_customers = client.get_customers()
                if asaas_customers:
                    inserted, updated = db.upsert_asaas_customers(asaas_customers)
                    st.success(f"Sincronização concluída! {inserted} clientes importados e {updated} atualizados.")
                else:
                    st.info("Nenhum cliente encontrado no Asaas.")
            except Exception as e:
                st.error(f"Erro na sincronização: {e}")
                
    locatarios_list = db.get_locatarios_list()
    if not locatarios_list:
        st.info("Nenhum locatário cadastrado.")
        return
        
    for l in locatarios_list:
        l_id, l_nome, l_cpf, l_tel, l_placa = l
        assoc_label = f" (🏍️ Moto: {l_placa})" if l_placa else " (Sem moto associada)"
        with st.expander(f"👤 {l_nome} - CPF: {l_cpf} {assoc_label}"):
            details = db.get_locatario_details(l_id)
            if details:
                 (d_id, d_nome, d_cpf, d_endereco, d_telefone, d_email, d_cnh, d_placa, d_cnhn, d_cnht) = details
                 
                 c1, c2 = st.columns(2)
                 c1.markdown(f"**Nome:** {d_nome}")
                 c1.markdown(f"**CPF:** {d_cpf}")
                 c1.markdown(f"**CNH:** {d_cnh or 'Não informada'}")
                 c1.markdown(f"**Email:** {d_email or 'Não informado'}")
                 c2.markdown(f"**Telefone:** {d_telefone or 'Não informado'}")
                 c2.markdown(f"**Moto Associada:** {d_placa or 'Nenhuma'}")
                 c2.markdown(f"**Endereço:**\\n{d_endereco or 'Não informado'}")
                 
                 st.write("---")
                 if d_cnhn:
                     st.write(f"**Arquivo Anexado da CNH**: {d_cnhn}")
                     if st.button(f"Visualizar CNH", key=f"view_cnh_{d_id}"):
                         file_data = db.get_locatario_file(d_id)
                         raw_bytes = file_data[0]
                         b64 = base64.b64encode(raw_bytes).decode()
                         if 'pdf' in d_cnht:
                             href = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" type="application/pdf"></iframe>'
                             st.markdown(href, unsafe_allow_html=True)
                         else:
                             href = f'<img src="data:{d_cnht};base64,{b64}" width="100%" />'
                             st.markdown(href, unsafe_allow_html=True)
                 else:
                     st.write("**Arquivo Anexado da CNH**: Não anexado")
                 
                 st.write("---")
                 
                 # ========== FINANCEIRO DO PILOTO ==========
                 with st.expander("💰 Financeiro do Piloto"):
                     fin_rows = []
                     
                     # 1. Manual transactions from DB
                     all_txs = db.get_transactions()
                     manual_txs = [tx for tx in all_txs if tx[6] == d_cpf and tx[2] in ('entrada', 'entrada_liquida')]
                     
                     for tx in manual_txs:
                         fin_rows.append({
                             "id": tx[0],
                             "origem": "Manual",
                             "valor": float(tx[3]),
                             "valor_liquido": float(tx[3]),
                             "data": str(tx[4]),
                             "status": tx[5],
                             "editavel": True
                         })
                     
                     # 2. ASAAS payments for this pilot
                     try:
                         from asaas_client import AsaasClient
                         ac = AsaasClient()
                         customers = ac.get_customers()
                         
                         # Find ASAAS customer(s) matching this CPF
                         matching_cust_ids = [c["id"] for c in customers if c.get("cpfCnpj", "").replace(".", "").replace("-", "").replace("/", "") == d_cpf.replace(".", "").replace("-", "").replace("/", "")]
                         
                         if matching_cust_ids:
                             h = datetime.date.today()
                             asaas_start = datetime.date(2025, 1, 1).strftime("%Y-%m-%d")
                             asaas_end = (h + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
                             pagamentos = ac.get_all_payments(asaas_start, asaas_end)
                             
                             status_map = {
                                 "RECEIVED": "recebido",
                                 "CONFIRMED": "recebido",
                                 "RECEIVED_IN_CASH": "recebido",
                                 "PENDING": "pendente",
                                 "OVERDUE": "em atraso",
                             }
                             
                             for pg in pagamentos:
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
                     except Exception as e:
                         st.warning(f"Não foi possível buscar dados do ASAAS: {e}")
                     
                     if not fin_rows:
                         st.info("Nenhum registro financeiro encontrado para este piloto.")
                     else:
                         # Summary metrics
                         total_recebido = sum(r["valor"] for r in fin_rows if r["status"] == "recebido")
                         total_pendente = sum(r["valor"] for r in fin_rows if r["status"] == "pendente")
                         total_atraso = sum(r["valor"] for r in fin_rows if r["status"] == "em atraso")
                         
                         m1, m2, m3 = st.columns(3)
                         m1.metric("✅ Recebido", f"R$ {total_recebido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                         m2.metric("⏳ Pendente", f"R$ {total_pendente:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                         m3.metric("🔴 Em Atraso", f"R$ {total_atraso:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                         
                         # Build display table
                         display_rows = []
                         for r in fin_rows:
                             data_fmt = pd.to_datetime(r["data"]).strftime("%d/%m/%Y") if r["data"] else "—"
                             display_rows.append({
                                 "Origem": r["origem"],
                                 "Valor Bruto": f"R$ {r['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                                 "Valor Líquido": f"R$ {r['valor_liquido']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                                 "Data": data_fmt,
                                 "Status": r["status"].upper()
                             })
                         
                         df_fin = pd.DataFrame(display_rows)
                         st.dataframe(df_fin, use_container_width=True, hide_index=True)
                         
                         # Editable manual entries
                         pendentes_manuais = [r for r in fin_rows if r["editavel"] and r["status"] == "pendente" and r["id"]]
                         if pendentes_manuais:
                             st.markdown("#### Marcar como Recebido")
                             for r in pendentes_manuais:
                                 data_fmt = pd.to_datetime(r["data"]).strftime("%d/%m/%Y") if r["data"] else "—"
                                 col_info, col_btn = st.columns([3, 1])
                                 col_info.write(f"**#{r['id']}** — R$ {r['valor']:.2f} — {data_fmt}")
                                 if col_btn.button("✅ Recebido", key=f"mark_recv_{d_id}_{r['id']}"):
                                     db.update_transaction(r["id"], "Manual", r["valor"], r["data"], "recebido", cpf_cliente=d_cpf)
                                     st.success("Status atualizado para Recebido!")
                                     st.rerun()
                 
                 st.write("---")
                 with st.expander("📝 Editar Dados do Piloto"):
                     with st.form(f"form_edit_locatario_{d_id}"):
                         c1, c2 = st.columns(2)
                         with c1:
                             new_nome = st.text_input("Nome Completo", value=d_nome)
                             new_cpf = st.text_input("CPF", value=d_cpf)
                             new_telefone = st.text_input("Telefone", value=d_telefone or "")
                             new_email = st.text_input("E-mail", value=d_email or "")
                         with c2:
                             new_endereco = st.text_area("Endereço", value=d_endereco or "")
                             new_cnh = st.text_input("CNH", value=d_cnh or "")
                             
                             motos_list = db.get_motos_list()
                             placas_disponiveis = ["Nenhuma"] + [m[0] for m in motos_list] if motos_list else ["Nenhuma"]
                             current_placa_idx = placas_disponiveis.index(d_placa) if d_placa in placas_disponiveis else 0
                             new_placa = st.selectbox("Moto Associada Atualmente", placas_disponiveis, index=current_placa_idx)

                         new_cnh_file = st.file_uploader("Nova CNH (Opcional)", type=["pdf", "png", "jpg"], key=f"edit_cnh_{d_id}")
                         
                         cb1, cb2 = st.columns(2)
                         save_btn = cb1.form_submit_button("Salvar Alterações")
                         delete_btn = cb2.form_submit_button("🚨 Excluir Piloto")

                         if save_btn:
                             placa_final = None if new_placa == "Nenhuma" else new_placa
                             cf_bytes = new_cnh_file.read() if new_cnh_file else None
                             cf_name = new_cnh_file.name if new_cnh_file else None
                             cf_type = new_cnh_file.type if new_cnh_file else None
                             
                             if d_placa and d_placa != placa_final:
                                 # Free the old moto
                                 db.sync_moto_association(d_placa, None)

                             if placa_final:
                                 # Bind the new moto
                                 db.sync_moto_association(placa_final, new_nome)

                             success = db.update_locatario(
                                 d_id, new_nome, new_cpf, new_endereco, new_telefone, new_email, new_cnh, placa_final,
                                 cf_bytes, cf_name, cf_type
                             )
                             if success:
                                 st.success(f"Locatário {new_nome} atualizado com sucesso!")
                                 st.rerun()
                             else:
                                 st.error("Erro ao atualizar dados.")
                         
                         if delete_btn:
                             # Before deleting, clear the moto association using sync method
                             if d_placa:
                                 db.sync_moto_association(d_placa, None)

                             if db.delete_locatario(d_id):
                                 st.success("Piloto excluído com sucesso!")
                                 st.rerun()
                             else:
                                 st.error("Erro ao excluir piloto.")

    st.markdown('---')
    # Form to Add Locatário
    with st.expander("👤 Gerenciar Pilotos", expanded=True):
        st.info("Aqui você gerencia os pilotos vinculados à Visiun e sincroniza com os dados de cobrança do Asaas.")
        with st.form("form_add_locatario", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome Completo *")
                cpf = st.text_input("CPF *", placeholder="Apenas números")
                telefone = st.text_input("Telefone / WhatsApp")
                email = st.text_input("E-mail")
            with col2:
                endereco = st.text_area("Endereço Completo")
                cnh = st.text_input("Número da CNH")
                
                # Fetch available motos to associate
                motos_list = db.get_motos_list()
                placas_disponiveis = ["Nenhuma"] + [m[0] for m in motos_list] if motos_list else ["Nenhuma"]
                placa_associada = st.selectbox("Moto Associada Atualmente", placas_disponiveis)

            st.write("### Documento do Piloto (Opcional)")
            cnh_file = st.file_uploader("Upload da CNH (PDF, PNG, JPG)", type=["pdf", "png", "jpg"], key="up_cnh")

            submit = st.form_submit_button("Salvar Locatário no Banco de Dados")
            if submit:
                if not nome or not cnh:
                    st.error("Nome e CNH são campos fortemente recomendados. Nome e CPF são obrigatórios.")
                if not nome or not cpf:
                    st.error("Campos Nome e CPF são obrigatórios.")
                else:
                     # Associar Placa se diferente de Nenhuma
                     placa_final = None if placa_associada == "Nenhuma" else placa_associada
                     
                     # Ler arquivo da CNH
                     cf_bytes = cnh_file.read() if cnh_file else None
                     cf_name = cnh_file.name if cnh_file else None
                     cf_type = cnh_file.type if cnh_file else None

                     success = db.add_locatario(
                         nome, cpf, endereco, telefone, email, cnh, placa_final,
                         cf_bytes, cf_name, cf_type
                     )
                     if success:
                         st.success(f"Locatário {nome} cadastrado com sucesso!")
                         st.rerun()
                     else:
                         st.error("Erro ao cadastrar. Verifique se o CPF já está registrado em outro perfil.")

