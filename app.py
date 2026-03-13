import streamlit as st
import sys, os
sys.path.insert(0, '.')
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer

st.set_page_config(page_title='OrchestrIA', layout='wide')
st.title('OrchestrIA IVR IA')
st.divider()

col1, col2 = st.columns(2)

with col1:
    flow_name = st.text_input('Nombre del flujo', value='Mi Flujo IVR')
    yaml_input = st.text_area('YAML de Genesys', height=400)

with col2:
    analizar = st.button('Analizar Flujo', type='primary', use_container_width=True)
    if analizar:
        if not yaml_input.strip():
            st.error('Pega un YAML valido')
        else:
            parser = GenesysYAMLParser()
            flow = parser.parse(yaml_input, flow_name=flow_name)
            analyzer = IVRAnalyzer()
            analysis = analyzer.analyze(flow)

            score = analysis.get('score', 0)
            if score >= 70:
                st.success('Score: ' + str(score) + '/100')
            elif score >= 40:
                st.warning('Score: ' + str(score) + '/100')
            else:
                st.error('Score: ' + str(score) + '/100')

            st.write(analysis.get('summary', ''))

            for issue in analysis.get('critical_issues', []):
                st.error(issue)

            for imp in analysis.get('improvements', []):
                st.success(imp)

            inv = analysis.get('inventory', {})
            if inv:
                st.divider()
                st.subheader('Inventario del Flujo')

                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric('Total Nodos', inv.get('total_nodes', 0))
                col_b.metric('Menus', inv.get('menu_nodes', 0))
                col_c.metric('Transfers', inv.get('transfer_nodes', 0))
                col_d.metric('Tareas', inv.get('task_nodes', 0))

                col_e, col_f, col_g, col_h = st.columns(4)
                col_e.metric('Exits Autoservicio', inv.get('self_service_exits', 0))
                col_f.metric('Transfers a Agente', inv.get('agent_transfers', 0))
                col_g.metric('Self-Service Ratio', str(inv.get('self_service_ratio', 0)) + '%')
                col_h.metric('Deps. Externas', inv.get('total_external_deps', 0))

                st.divider()
                st.subheader('Dependencias Externas')

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.markdown('**APIs de Datos**')
                    ds = inv.get('data_services', [])
                    if ds:
                        for s in ds:
                            st.code(s)
                    else:
                        st.caption('Ninguna detectada')

                with c2:
                    st.markdown('**Servicios de Auth**')
                    auth = inv.get('auth_services', [])
                    if auth:
                        for s in auth:
                            st.code(s)
                    else:
                        st.caption('Ninguna detectada')

                with c3:
                    st.markdown('**Variables Dinamicas TTS**')
                    dvars = inv.get('dynamic_variables', [])
                    if dvars:
                        for v in dvars:
                            st.code('{' + v + '}')
                    else:
                        st.caption('Ninguna detectada')

                queues = inv.get('unique_queues', [])
                if queues:
                    st.markdown('**Colas:** ' + ', '.join(['`' + q + '`' for q in queues]))

                st.divider()
                st.subheader('Migration Assessment')

                ml = inv.get('migration_level', 'SIMPLE')
                ms = inv.get('migration_complexity_score', 0)
                st.markdown('### Complejidad: **' + ml + '** (' + str(ms) + '/100)')

                flags = inv.get('migration_risk_flags', [])
                if flags:
                    for flag in flags:
                        st.warning(flag)
                else:
                    st.success('No se detectaron riesgos de migracion')