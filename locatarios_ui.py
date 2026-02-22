import streamlit as st
import pandas as pd
from database_manager import DatabaseManager
import base64

def locatarios_tab():
    st.header("Gestão de Locatários (Pilotos)")
    db = DatabaseManager()

    # Form to Add Locatário
    with st.expander("➕ Cadastrar Novo Locatário (Manual)", expanded=False):
        st.info("Cadastro manual. Futuramente os dados virão da API do ASAAS.")
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

    st.markdown("---")
    
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("Locatários Cadastrados")
    with col_t2:
        if st.button("🔄 Sincronizar com Asaas", use_container_width=True):
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
                             if db.delete_locatario(d_id):
                                 st.success("Piloto excluído com sucesso!")
                                 st.rerun()
                             else:
                                 st.error("Erro ao excluir piloto.")
