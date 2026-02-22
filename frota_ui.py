import streamlit as st
import pandas as pd
from database_manager import DatabaseManager
import base64
import datetime

def format_currency(value):
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def frota_tab():
    st.header("Gestão de Frota (Motos)")
    db = DatabaseManager()

    # Form to Add Moto
    with st.expander("➕ Cadastrar Nova Moto", expanded=False):
        with st.form("form_add_moto", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                placa = st.text_input("Placa da Moto *", max_chars=10)
                modelo = st.text_input("Modelo *")
                disponibilidade = st.selectbox("Status", ["Disponível", "Alugada", "Oficina", "Vendida"])
            with col2:
                data_compra = st.date_input("Data da Compra")
                valor_compra = st.number_input("Valor da Moto (R$)", min_value=0.0, format="%.2f")
                locatario = st.text_input("Locatário Atual (Opcional)")
            with col3:
                despesas = st.text_area("Despesas Vinculadas", height=68)
                manutencao = st.text_area("Histórico de Manutenção", height=68)
                
            c_rev, c_oleo = st.columns(2)
            with c_rev:
                 revisao = st.text_area("Próximas Revisões", height=68)
            with c_oleo:
                 troca_oleo = st.text_area("Troca de Óleo", height=68)

            st.write("### Documentos Anexos (PDF, PNG, JPG)")
            col_doc1, col_doc2, col_doc3 = st.columns(3)
            with col_doc1:
                doc_file = st.file_uploader("Documento Geral", type=["pdf", "png", "jpg"], key="doc")
            with col_doc2:
                ipva_file = st.file_uploader("Comprovante IPVA", type=["pdf", "png", "jpg"], key="ipva")
            with col_doc3:
                crlv_file = st.file_uploader("CRLV", type=["pdf", "png", "jpg"], key="crlv")

            submit = st.form_submit_button("Salvar Moto no Banco de Dados")
            if submit:
                if not placa or not modelo:
                    st.error("Placa e Modelo são obrigatórios.")
                else:
                    # Read Files if uploaded
                    df_bytes = doc_file.read() if doc_file else None
                    df_name = doc_file.name if doc_file else None
                    df_type = doc_file.type if doc_file else None

                    if_bytes = ipva_file.read() if ipva_file else None
                    if_name = ipva_file.name if ipva_file else None
                    if_type = ipva_file.type if ipva_file else None

                    cf_bytes = crlv_file.read() if crlv_file else None
                    cf_name = crlv_file.name if crlv_file else None
                    cf_type = crlv_file.type if crlv_file else None

                    success = db.add_moto(
                        placa, modelo, data_compra, valor_compra, despesas, manutencao, revisao, troca_oleo, disponibilidade, locatario,
                        df_bytes, df_name, df_type, if_bytes, if_name, if_type, cf_bytes, cf_name, cf_type
                    )
                    if success:
                        st.success(f"Moto {placa} cadastrada com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao cadastrar. Verifique se a placa já existe.")

    st.markdown("---")
    st.subheader("Motos Cadastradas")
    
    motos_list = db.get_motos_list()
    if not motos_list:
        st.info("Nenhuma moto cadastrada.")
        return
        
    for m in motos_list:
        p_placa, p_modelo, p_disp, p_loc, p_valor = m
        with st.expander(f"🏍️ {p_placa} - {p_modelo} ({p_disp})"):
            details = db.get_moto_details(p_placa)
            if details:
                 (d_placa, d_modelo, d_data, d_valor, d_despesas, d_manut, d_rev, d_oleo, d_disp, d_loc, 
                  d_docn, d_doct, d_ipvan, d_ipvat, d_crlvn, d_crlvt) = details
                 
                 # Criação das Abas
                 aba_dados, aba_manutencao, aba_oleo, aba_valores = st.tabs([
                     "📝 Dados da Moto", 
                     "🔧 Manutenção & Revisão", 
                     "🛢️ Troca de Óleo", 
                     "💰 Valores & Depreciação"
                 ])
                 
                 with aba_dados:
                     c1, c2 = st.columns(2)
                     c1.markdown(f"**Placa:** {d_placa}")
                     c1.markdown(f"**Modelo:** {d_modelo}")
                     c1.markdown(f"**Status:** {d_disp}")
                     c2.markdown(f"**Locatário Atual:** {d_loc or 'Nenhum'}")
                     c2.markdown(f"**Data da Compra:** {d_data}")
                     
                     st.write("### Arquivos")
                     fc1, fc2, fc3 = st.columns(3)
                     
                     def render_file_btn(col, title, prefix, file_name, file_type):
                         if file_name:
                             col.write(f"**{title}**: {file_name}")
                             if col.button(f"Visualizar {title}", key=f"view_{prefix}_{d_placa}"):
                                 file_data = db.get_moto_file(d_placa, prefix)
                                 raw_bytes = file_data[0]
                                 b64 = base64.b64encode(raw_bytes).decode()
                                 if 'pdf' in file_type:
                                     href = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" type="application/pdf"></iframe>'
                                     st.markdown(href, unsafe_allow_html=True)
                                 else:
                                     href = f'<img src="data:{file_type};base64,{b64}" width="100%" />'
                                     st.markdown(href, unsafe_allow_html=True)
                         else:
                             col.write(f"**{title}**: Não anexado")

                     render_file_btn(fc1, "Documento", "doc", d_docn, d_doct)
                     render_file_btn(fc2, "IPVA", "ipva", d_ipvan, d_ipvat)
                     render_file_btn(fc3, "CRLV", "crlv", d_crlvn, d_crlvt)
                 
                 with aba_manutencao:
                     mcol1, mcol2 = st.columns(2)
                     with mcol1:
                         st.markdown("**Anotações de Manutenção:**")
                         st.info(d_manut if d_manut else "Nenhuma anotação")
                     with mcol2:
                         st.markdown("**Datas de Revisão:**")
                         st.warning(d_rev if d_rev else "Nenhuma anotação")
                 
                 with aba_oleo:
                     st.markdown("**Histórico - Troca de Óleo:**")
                     st.info(d_oleo if d_oleo else "Nenhuma anotação de troca de óleo cadastrada.")
                     
                 with aba_valores:
                     vcol1, vcol2 = st.columns(2)
                     
                     # Matemática de Depreciação: 350km/dia = ~10.500km/mes.
                     # Vamos estipular perda de mercado de 1% do valor da moto a cada mẽs de uso severo (aprox 10k km).
                     valor_orig = float(d_valor or 0)
                     data_compra = pd.to_datetime(d_data)
                     hoje = pd.to_datetime(datetime.date.today())
                     
                     dias_uso = (hoje - data_compra).days if pd.notnull(data_compra) else 0
                     meses_uso = max(0, dias_uso // 30)
                     km_estimada = dias_uso * 350
                     
                     # Depreciação de 1% ao mês (desgaste de 10.500 km)
                     taxa_depreciacao = min(0.99, (meses_uso * 0.01)) # Limite máx de perda de 99% pra não ficar negativo
                     valor_depreciado = valor_orig - (valor_orig * taxa_depreciacao)
                     
                     with vcol1:
                         st.markdown("### Valores da Moto")
                         st.markdown(f"**Valor de Compra (Original):** {format_currency(valor_orig)}")
                         st.markdown(f"**Despesas Vinculadas:**\\n{d_despesas if d_despesas else 'Nenhuma'}")
                         
                     with vcol2:
                         st.markdown("### Depreciação Estimada")
                         st.metric("Estimativa de Odômetro", f"{km_estimada:,} km".replace(",", "."))
                         st.metric("Valor Atual de Mercado", format_currency(valor_depreciado), delta=f"-{taxa_depreciacao*100:.0f}% Comercial", delta_color="inverse")
