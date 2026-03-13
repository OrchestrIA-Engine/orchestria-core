import streamlit as st
import sys, os, json, time, tempfile
sys.path.insert(0, '.')
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer
from src.agents.documentor import IVRDocumentor

st.set_page_config(page_title='OrchestrIA IVR·IA', layout='wide', page_icon='🎙️')

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .phase-done { color: #3FB950; font-weight: 600; }
    .phase-active { color: #388BFD; font-weight: 600; }
    .phase-pending { color: #8B949E; }
    .score-big { font-size: 3rem; font-weight: 800; line-height: 1; }
    .badge-simple { background:#1a4731; color:#3FB950; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:600; }
    .badge-moderado { background:#3a2f00; color:#D29922; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:600; }
    .badge-complejo { background:#3a1f00; color:#F0883E; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:600; }
    .badge-muy { background:#3a1010; color:#F85149; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:600; }
    div[data-testid="metric-container"] { background:#161B22; border:1px solid #30363D; border-radius:8px; padding:12px 16px; }
</style>
""", unsafe_allow_html=True)

st.title('OrchestrIA IVR IA')
st.caption('Analisis inteligente de flujos Genesys · YAML · JSON · XML')
st.divider()

modo = st.radio('Modo', ['Flujo individual', 'Batch (multiples flujos)'],
                horizontal=True, label_visibility='collapsed')
st.divider()

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if 'analysis' not in st.session_state:
    st.session_state.analysis = None
if 'flow' not in st.session_state:
    st.session_state.flow = None
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []
if 'batch_flows' not in st.session_state:
    st.session_state.batch_flows = {}


def parse_content(content, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'yaml'
    if ext == 'json':
        try:
            import yaml
            data = json.loads(content)
            content = yaml.dump(data)
        except Exception as e:
            return None, 'Error parseando JSON: ' + str(e)
    elif ext == 'xml':
        try:
            import xmltodict, yaml
            data = xmltodict.parse(content)
            content = yaml.dump(dict(data))
        except ImportError:
            return None, 'xmltodict no instalado. Ejecuta: pip install xmltodict'
        except Exception as e:
            return None, 'Error parseando XML: ' + str(e)
    parser = GenesysYAMLParser()
    flow_name = filename.rsplit('.', 1)[0]
    return parser.parse(content, flow_name=flow_name), None


def generar_pdf_bytes(flow, analysis):
    doc = IVRDocumentor()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        path = tmp.name
    doc.generate_pdf(flow, analysis, path)
    with open(path, 'rb') as f:
        data = f.read()
    os.unlink(path)
    return data


def mostrar_loading(placeholder):
    fases = [
        'Parseando estructura del flujo',
        'Extrayendo inventario de nodos',
        'Detectando dependencias externas',
        'Analizando con IA · Genesys Expert Mode',
        'Generando Migration Assessment',
    ]
    mensajes = [
        'Detectando dead ends...',
        'Evaluando robustez operativa...',
        'Calculando complejidad de migracion...',
        'Revisando manejo de timeouts...',
        'Identificando referencias rotas...',
        'Analizando self-service ratio...',
    ]
    with placeholder.container():
        st.markdown('#### Analizando flujo...')
        texts = []
        for label in fases:
            slot = st.empty()
            slot.markdown('<span class="phase-pending">' + label + '</span>', unsafe_allow_html=True)
            texts.append(slot)
        st.markdown('---')
        msg_slot = st.empty()
        prog = st.progress(0)

    def update(step, msg_idx):
        for i, label in enumerate(fases):
            if i < step:
                texts[i].markdown('<span class="phase-done">checkmark ' + label + '</span>', unsafe_allow_html=True)
            elif i == step:
                texts[i].markdown('<span class="phase-active">... ' + label + '</span>', unsafe_allow_html=True)
            else:
                texts[i].markdown('<span class="phase-pending">' + label + '</span>', unsafe_allow_html=True)
        msg_slot.caption(mensajes[msg_idx % len(mensajes)])
        prog.progress((step + 1) / len(fases))

    return update


def mostrar_resultado(analysis, flow=None, key_prefix=''):
    score = analysis.get('score', 0)
    summary = analysis.get('summary', '')
    issues = analysis.get('critical_issues', [])
    improvements = analysis.get('improvements', [])
    inv = analysis.get('inventory', {})

    col_score, col_summary = st.columns([1, 3])
    with col_score:
        color = '#3FB950' if score >= 70 else '#D29922' if score >= 40 else '#F85149'
        st.markdown(
            '<div style="text-align:center;padding:24px;background:#161B22;border:1px solid #30363D;border-radius:12px;">'
            '<div style="color:#8B949E;font-size:0.8rem;text-transform:uppercase;letter-spacing:1px;">SCORE DE CALIDAD</div>'
            '<div class="score-big" style="color:' + color + '">' + str(score) + '</div>'
            '<div style="color:#8B949E;font-size:0.9rem;">/ 100</div>'
            '</div>',
            unsafe_allow_html=True
        )

        if flow is not None:
            st.markdown('')
            pdf_key = 'pdf_bytes_' + key_prefix
            if pdf_key not in st.session_state:
                st.session_state[pdf_key] = None

            if st.button('Generar PDF', key='btn_pdf_' + key_prefix, use_container_width=True):
                with st.spinner('Generando informe ejecutivo...'):
                    try:
                        st.session_state[pdf_key] = generar_pdf_bytes(flow, analysis)
                    except Exception as e:
                        st.error('Error: ' + str(e))

            if st.session_state[pdf_key] is not None:
                st.download_button(
                    label='Descargar PDF',
                    data=st.session_state[pdf_key],
                    file_name=(flow.flow_name + '_orchestria.pdf'),
                    mime='application/pdf',
                    key='dl_pdf_' + key_prefix,
                    use_container_width=True
                )

    with col_summary:
        st.markdown('**Resumen ejecutivo**')
        st.write(summary)
        for issue in issues:
            st.error(issue)
        for imp in improvements:
            st.success(imp)

    if inv:
        st.divider()
        st.subheader('Inventario del Flujo')

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Total Nodos', inv.get('total_nodes', 0))
        c2.metric('Menus', inv.get('menu_nodes', 0))
        c3.metric('Transfers', inv.get('transfer_nodes', 0))
        c4.metric('Tareas', inv.get('task_nodes', 0))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric('Exits Autoservicio', inv.get('self_service_exits', 0))
        c6.metric('Transfers a Agente', inv.get('agent_transfers', 0))
        c7.metric('Self-Service Ratio', str(inv.get('self_service_ratio', 0)) + '%')
        c8.metric('Deps. Externas', inv.get('total_external_deps', 0))

        st.divider()
        st.subheader('Dependencias Externas')
        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown('**APIs de Datos**')
            ds = inv.get('data_services', [])
            for s in ds:
                st.code(s)
            if not ds:
                st.caption('Ninguna detectada')
        with d2:
            st.markdown('**Servicios de Auth**')
            auth = inv.get('auth_services', [])
            for s in auth:
                st.code(s)
            if not auth:
                st.caption('Ninguna detectada')
        with d3:
            st.markdown('**Variables Dinamicas TTS**')
            dvars = inv.get('dynamic_variables', [])
            for v in dvars:
                st.code('{' + v + '}')
            if not dvars:
                st.caption('Ninguna detectada')

        queues = inv.get('unique_queues', [])
        if queues:
            st.markdown('**Colas:** ' + '  '.join(['`' + q + '`' for q in queues]))

        st.divider()
        st.subheader('Migration Assessment')
        ml = inv.get('migration_level', 'SIMPLE')
        ms = inv.get('migration_complexity_score', 0)
        badge_class = {
            'SIMPLE': 'badge-simple',
            'MODERADO': 'badge-moderado',
            'COMPLEJO': 'badge-complejo',
            'MUY COMPLEJO': 'badge-muy'
        }.get(ml, 'badge-simple')
        st.markdown(
            '<span class="' + badge_class + '">' + ml + '</span>'
            ' &nbsp; Complejidad de migracion: <strong>' + str(ms) + '/100</strong>',
            unsafe_allow_html=True
        )
        st.markdown('')
        flags = inv.get('migration_risk_flags', [])
        if flags:
            for flag in flags:
                st.warning(flag)
        else:
            st.success('No se detectaron riesgos de migracion')


# ── MODO INDIVIDUAL ───────────────────────────────────────────────────────────
if modo == 'Flujo individual':
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('**Sube tu flujo o pega el YAML directamente**')
        uploaded = st.file_uploader(
            'Arrastra aqui tu archivo',
            type=['yaml', 'yml', 'json', 'xml'],
            label_visibility='collapsed'
        )
        yaml_input = st.text_area(
            'O pega el contenido aqui',
            height=320,
            placeholder='inboundCall:\n  name: "Mi Flujo"\n  ...'
        )

    with col_r:
        analizar = st.button('Analizar Flujo', type='primary', use_container_width=True)

        if analizar:
            content = ''
            filename = 'flujo.yaml'
            if uploaded:
                content = uploaded.read().decode('utf-8')
                filename = uploaded.name
            elif yaml_input.strip():
                content = yaml_input.strip()
            else:
                st.error('Sube un archivo o pega el contenido YAML')
                st.stop()

            loading_slot = st.empty()
            update_fn = mostrar_loading(loading_slot)

            update_fn(0, 0)
            time.sleep(0.4)
            flow, err = parse_content(content, filename)
            if err:
                loading_slot.empty()
                st.error(err)
                st.stop()

            update_fn(1, 1)
            time.sleep(0.3)
            update_fn(2, 2)
            time.sleep(0.3)
            update_fn(3, 3)

            analyzer = IVRAnalyzer()
            analysis = analyzer.analyze(flow)

            update_fn(4, 4)
            time.sleep(0.3)
            loading_slot.empty()

            st.session_state.analysis = analysis
            st.session_state.flow = flow
            st.session_state.pdf_bytes_individual = None

    if st.session_state.analysis is not None and modo == 'Flujo individual':
        mostrar_resultado(
            st.session_state.analysis,
            flow=st.session_state.flow,
            key_prefix='individual'
        )

# ── MODO BATCH ────────────────────────────────────────────────────────────────
else:
    st.markdown('**Arrastra hasta 50 flujos** · Formatos: YAML, JSON, XML')
    uploaded_files = st.file_uploader(
        'Selecciona multiples archivos',
        type=['yaml', 'yml', 'json', 'xml'],
        accept_multiple_files=True,
        label_visibility='collapsed'
    )
    if uploaded_files:
        st.caption(str(len(uploaded_files)) + ' archivo(s) cargado(s)')

    analizar_batch = st.button('Analizar Portfolio', type='primary',
                               disabled=not uploaded_files)

    if analizar_batch and uploaded_files:
        resultados = []
        flows_map = {}
        progress_bar = st.progress(0)
        status_slot = st.empty()
        analyzer = IVRAnalyzer()

        for i, f in enumerate(uploaded_files[:50]):
            status_slot.caption('Analizando ' + str(i + 1) + '/' +
                                str(len(uploaded_files)) + ': ' + f.name)
            content = f.read().decode('utf-8')
            flow, err = parse_content(content, f.name)
            if err:
                resultados.append({'filename': f.name, 'score': 0, 'error': err})
            else:
                analysis = analyzer.analyze(flow)
                analysis['filename'] = f.name
                resultados.append(analysis)
                flows_map[f.name] = flow
            progress_bar.progress((i + 1) / len(uploaded_files))

        status_slot.empty()
        progress_bar.empty()

        st.session_state.batch_results = resultados
        st.session_state.batch_flows = flows_map

    if st.session_state.batch_results:
        st.divider()
        resultados = st.session_state.batch_results
        flows_map = st.session_state.batch_flows
        st.subheader('Resultados del Portfolio · ' + str(len(resultados)) + ' flujos')

        resultados_ok = sorted(
            [r for r in resultados if 'error' not in r],
            key=lambda x: x.get('score', 0),
            reverse=True
        )

        for idx, r in enumerate(resultados_ok):
            score = r.get('score', 0)
            icon = '🟢' if score >= 70 else '🟡' if score >= 40 else '🔴'
            ml = r.get('inventory', {}).get('migration_level', '-')
            label = icon + ' ' + r['filename'] + ' — Score: ' + str(score) + '/100 · Migracion: ' + ml
            with st.expander(label):
                flow_ref = flows_map.get(r['filename'])
                mostrar_resultado(r, flow=flow_ref, key_prefix='batch_' + str(idx))

        for r in [x for x in resultados if 'error' in x]:
            st.error('Error en ' + r['filename'] + ': ' + r['error'])
