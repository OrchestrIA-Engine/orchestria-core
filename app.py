import streamlit as st
import sys, os, json, time, tempfile
sys.path.insert(0, '.')
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer
from src.agents.documentor import IVRDocumentor

st.set_page_config(page_title='OrchestrIA', layout='wide', page_icon='🎙️',
                   initial_sidebar_state='collapsed')

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stApp"] {
    background: #07080B !important; color: #E8EDF5 !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important; }
[data-testid="stAppViewContainer"] > .main { background: #07080B !important; }
.block-container { padding: 2rem 2.5rem 4rem !important; max-width: 1320px !important; }
#MainMenu, footer, header, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; }
hr { border-color: #1C2030 !important; margin: 1.75rem 0 !important; }

/* HEADER */
.orch-header { display:flex; align-items:center; justify-content:space-between;
    padding:0 0 1.75rem; border-bottom:1px solid #1C2030; margin-bottom:2rem; }
.orch-logo-main { font-family:'Syne',sans-serif; font-size:1.5rem; font-weight:800;
    color:#F0F6FC; letter-spacing:-0.03em; }
.orch-logo-dot { color:#00D4AA; font-size:1.5rem; font-weight:800; }
.orch-logo-badge { font-family:'DM Mono',monospace; font-size:0.68rem; color:#3D4D66;
    background:#0E1118; border:1px solid #1C2030; border-radius:4px;
    padding:2px 8px; margin-left:0.6rem; letter-spacing:0.1em; text-transform:uppercase; }
.orch-tagline { font-family:'DM Mono',monospace; font-size:0.68rem; color:#3D4D66;
    letter-spacing:0.1em; text-transform:uppercase; }

/* RADIO TABS */
.stRadio > div { flex-direction:row !important; gap:0 !important;
    background:#0E1118 !important; border:1px solid #1C2030 !important;
    border-radius:8px !important; padding:3px !important;
    display:inline-flex !important; width:auto !important; }
.stRadio > div > label { background:transparent !important; border:none !important;
    border-radius:5px !important; padding:7px 18px !important;
    font-family:'Plus Jakarta Sans',sans-serif !important; font-size:0.82rem !important;
    font-weight:500 !important; color:#4B5568 !important;
    cursor:pointer !important; transition:all 0.15s !important; white-space:nowrap !important; }
.stRadio > div > label:has(input:checked) { background:#1C2030 !important; color:#E8EDF5 !important; }
.stRadio > div > label > div:first-child { display:none !important; }

/* UPLOAD */
[data-testid="stFileUploader"] { background:#0B0D14 !important;
    border:1px dashed #1C2030 !important; border-radius:10px !important; padding:0.25rem !important; }
[data-testid="stFileUploaderDropzone"] { background:transparent !important;
    border:none !important; padding:1.5rem !important; }
[data-testid="stFileUploaderDropzoneInstructions"] p {
    font-family:'Plus Jakarta Sans',sans-serif !important; color:#4B5568 !important; font-size:0.82rem !important; }

/* TEXTAREA */
.stTextArea textarea { background:#0B0D14 !important; border:1px solid #1C2030 !important;
    border-radius:10px !important; color:#8B9EB8 !important;
    font-family:'DM Mono',monospace !important; font-size:0.76rem !important; line-height:1.65 !important; }
.stTextArea textarea:focus { border-color:#00D4AA40 !important; outline:none !important; }

/* BUTTONS */
.stButton > button { background:#00D4AA !important; color:#07080B !important;
    border:none !important; border-radius:8px !important;
    font-family:'Plus Jakarta Sans',sans-serif !important; font-size:0.85rem !important;
    font-weight:600 !important; padding:0.65rem 1.5rem !important; transition:all 0.15s !important; }
.stButton > button:hover { background:#00BBAA !important; transform:translateY(-1px) !important;
    box-shadow:0 4px 20px #00D4AA25 !important; }
.stDownloadButton > button { background:#0E1118 !important; color:#00D4AA !important;
    border:1px solid #00D4AA40 !important; border-radius:8px !important;
    font-family:'Plus Jakarta Sans',sans-serif !important; font-size:0.82rem !important; }
.stDownloadButton > button:hover { background:#00D4AA12 !important; }

/* METRICS */
div[data-testid="metric-container"] { background:#0B0D14 !important;
    border:1px solid #1C2030 !important; border-radius:10px !important; padding:1rem 1.1rem !important; }
div[data-testid="metric-container"] label { font-family:'DM Mono',monospace !important;
    font-size:0.62rem !important; color:#3D4D66 !important;
    text-transform:uppercase !important; letter-spacing:0.12em !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family:'Syne',sans-serif !important; font-size:1.5rem !important;
    font-weight:700 !important; color:#E8EDF5 !important; }

/* PROGRESS */
.stProgress > div > div { background:#0E1118 !important; border-radius:4px !important; }
.stProgress > div > div > div { background:linear-gradient(90deg,#00D4AA,#00A8FF) !important; border-radius:4px !important; }

/* EXPANDER */
.streamlit-expanderHeader { background:#0B0D14 !important; border:1px solid #1C2030 !important;
    border-radius:8px !important; font-family:'Plus Jakarta Sans',sans-serif !important;
    font-size:0.85rem !important; color:#8B9EB8 !important; padding:0.75rem 1rem !important; }
.streamlit-expanderContent { background:#09090F !important; border:1px solid #1C2030 !important;
    border-top:none !important; border-radius:0 0 8px 8px !important; padding:1.5rem !important; }

/* CUSTOM CLASSES */
.orch-badge { display:inline-flex; align-items:center; gap:6px; padding:3px 10px;
    border-radius:20px; font-family:'DM Mono',monospace; font-size:0.7rem;
    font-weight:500; letter-spacing:0.05em; }
.badge-simple   { background:#00D4AA12; color:#00D4AA; border:1px solid #00D4AA25; }
.badge-moderado { background:#D2992212; color:#D29922; border:1px solid #D2992225; }
.badge-complejo { background:#F0883E12; color:#F0883E; border:1px solid #F0883E25; }
.badge-muy      { background:#F8514912; color:#F85149; border:1px solid #F8514925; }

.orch-chip { display:inline-flex; align-items:center; background:#0E1118;
    border:1px solid #1C2030; border-radius:5px; padding:2px 9px;
    font-family:'DM Mono',monospace; font-size:0.7rem; color:#6B7A94; margin:2px; }
.chip-teal { color:#00D4AA; border-color:#00D4AA20; background:#00D4AA06; }
.chip-blue { color:#00A8FF; border-color:#00A8FF20; background:#00A8FF06; }

.lbl { font-family:'DM Mono',monospace; font-size:0.62rem; color:#3D4D66;
    text-transform:uppercase; letter-spacing:0.15em; margin-bottom:0.85rem; display:block; }

.ph-done  { color:#00D4AA; font-family:'DM Mono',monospace; font-size:0.78rem; display:block; padding:7px 0; border-bottom:1px solid #13161E; }
.ph-active{ color:#00A8FF; font-family:'DM Mono',monospace; font-size:0.78rem; display:block; padding:7px 0; border-bottom:1px solid #13161E; }
.ph-pend  { color:#252D3D; font-family:'DM Mono',monospace; font-size:0.78rem; display:block; padding:7px 0; border-bottom:1px solid #13161E; }

/* FEATURE CARDS (empty state) */
.feat-card { background:#0B0D14; border:1px solid #1C2030; border-radius:10px;
    padding:1.25rem 1.5rem; margin-bottom:0.75rem; }
.feat-icon { font-size:1.1rem; margin-bottom:0.5rem; display:block; }
.feat-title { font-family:'Syne',sans-serif; font-size:0.88rem; font-weight:700;
    color:#E8EDF5; margin-bottom:0.35rem; }
.feat-desc { font-family:'Plus Jakarta Sans',sans-serif; font-size:0.8rem;
    color:#4B5568; line-height:1.55; }

/* GENESYS COMPAT CHIPS */
.compat-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:0.6rem; }
.compat-chip { font-family:'DM Mono',monospace; font-size:0.65rem;
    background:#0E1118; border:1px solid #1C2030; border-radius:4px;
    padding:2px 8px; color:#3D4D66; }
</style>
""")

# ── SESSION STATE ──────────────────────────────────────────────────────────────
for k, v in [('analysis', None), ('flow', None),
              ('batch_results', []), ('batch_flows', {})]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── HELPERS ────────────────────────────────────────────────────────────────────
def parse_content(content, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'yaml'
    if ext == 'json':
        try:
            import yaml; content = yaml.dump(json.loads(content))
        except Exception as e: return None, 'Error JSON: ' + str(e)
    elif ext == 'xml':
        try:
            import xmltodict, yaml; content = yaml.dump(dict(xmltodict.parse(content)))
        except ImportError: return None, 'xmltodict no instalado: pip install xmltodict'
        except Exception as e: return None, 'Error XML: ' + str(e)
    return GenesysYAMLParser().parse(content, flow_name=filename.rsplit('.', 1)[0]), None

def generar_pdf_bytes(flow, analysis):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp: path = tmp.name
    IVRDocumentor().generate_pdf(flow, analysis, path)
    with open(path, 'rb') as f: data = f.read()
    os.unlink(path); return data

def score_color(s):
    return '#00D4AA' if s >= 70 else '#D29922' if s >= 40 else '#F85149'

def score_ring(score):
    color = score_color(score)
    r, size = 52, 124
    circ = 2 * 3.14159 * r
    offset = circ * (1 - score / 100)
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;padding:0.75rem 0 1.25rem;">'
        f'<div style="font-family:\'DM Mono\',monospace;font-size:0.58rem;color:#3D4D66;'
        f'text-transform:uppercase;letter-spacing:0.2em;margin-bottom:0.4rem;">Quality Score</div>'
        f'<div style="position:relative;width:{size}px;height:{size}px;">'
        f'<svg width="{size}" height="{size}" style="transform:rotate(-90deg)">'
        f'<circle cx="{size//2}" cy="{size//2}" r="{r}" fill="none" stroke="#13161E" stroke-width="5"/>'
        f'<circle cx="{size//2}" cy="{size//2}" r="{r}" fill="none" stroke="{color}"'
        f' stroke-width="5" stroke-linecap="round"'
        f' stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"'
        f' style="filter:drop-shadow(0 0 7px {color}55)"/>'
        f'</svg>'
        f'<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;">'
        f'<div style="font-family:\'Syne\',sans-serif;font-size:2.2rem;font-weight:800;'
        f'color:{color};line-height:1;letter-spacing:-0.04em;">{score}</div>'
        f'</div></div>'
        f'<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#3D4D66;margin-top:0.15rem;">/ 100</div>'
        f'</div>'
    )

def migration_badge(ml):
    cls = {'SIMPLE':'badge-simple','MODERADO':'badge-moderado',
           'COMPLEJO':'badge-complejo','MUY COMPLEJO':'badge-muy'}.get(ml,'badge-simple')
    return f'<span class="orch-badge {cls}">● {ml}</span>'

def empty_state_panel():
    return """
<div style="padding:0.25rem 0 0;">
  <div style="font-family:'DM Mono',monospace;font-size:0.58rem;color:#252D3D;
       text-transform:uppercase;letter-spacing:0.15em;margin-bottom:1.25rem;">What you'll get</div>

  <div class="feat-card">
    <span class="feat-icon">◈</span>
    <div class="feat-title">Quality Score + Rubric</div>
    <div class="feat-desc">AI-powered audit across 6 dimensions — structural integrity, operational robustness, CX, API handling, architecture, and edge coverage.</div>
  </div>

  <div class="feat-card">
    <span class="feat-icon">⬡</span>
    <div class="feat-title">Full Flow Inventory</div>
    <div class="feat-desc">Node counts, queue mapping, external API dependencies, dynamic TTS variables, auth services, self-service ratio.</div>
  </div>

  <div class="feat-card">
    <span class="feat-icon">⇢</span>
    <div class="feat-title">Migration Assessment</div>
    <div class="feat-desc">Complexity scoring for Genesys Cloud migration. Risk flags, dependency matrix, estimated effort level.</div>
  </div>

  <div class="feat-card">
    <span class="feat-icon">↓</span>
    <div class="feat-title">Executive PDF Report</div>
    <div class="feat-desc">CIO-ready PDF with findings, action plan, migration roadmap, and technical inventory. Ready to share in minutes.</div>
  </div>

  <div style="margin-top:1.25rem;">
    <div style="font-family:'DM Mono',monospace;font-size:0.58rem;color:#252D3D;
         text-transform:uppercase;letter-spacing:0.15em;margin-bottom:0.6rem;">Genesys compatibility</div>
    <div class="compat-row">
      <span class="compat-chip">Genesys Cloud CX</span>
      <span class="compat-chip">Architect inboundCall</span>
      <span class="compat-chip">YAML · JSON · XML</span>
      <span class="compat-chip">dataQuery / apiCall</span>
      <span class="compat-chip">authenticate</span>
      <span class="compat-chip">TTS Variables</span>
      <span class="compat-chip">Transfer Nodes</span>
    </div>
  </div>
</div>"""

def mostrar_loading(placeholder):
    fases = ['Parsing flow structure','Extracting node inventory',
             'Detecting external dependencies','AI analysis · Genesys Expert',
             'Generating migration assessment']
    hints = ['Scanning for dead ends...','Mapping transfer targets...',
             'Evaluating timeout coverage...','Cross-referencing node graph...',
             'Calculating migration complexity...']
    def render(step, hi):
        rows = ''.join(
            f'<span class="ph-{"done" if i<step else "active" if i==step else "pend"}">'
            f'{"✓" if i<step else "▸" if i==step else "·"} {label}</span>'
            for i, label in enumerate(fases))
        with placeholder.container():
            st.markdown(
                f'<div style="background:#0B0D14;border:1px solid #1C2030;border-radius:10px;'
                f'padding:1.25rem 1.5rem;"><span class="lbl">Analyzing</span>'
                f'{rows}'
                f'<div style="margin-top:0.85rem;font-family:\'DM Mono\',monospace;'
                f'font-size:0.65rem;color:#252D3D;">{hints[hi%len(hints)]}</div></div>',
                unsafe_allow_html=True)
            st.progress((step+1)/len(fases))
    return render

def mostrar_resultado(analysis, flow=None, key_prefix='main'):
    score  = analysis.get('score', 0)
    inv    = analysis.get('inventory', {})
    issues = analysis.get('critical_issues', [])
    imps   = analysis.get('improvements', [])
    summ   = analysis.get('summary', '')

    col_s, col_r = st.columns([1, 2])
    with col_s:
        st.markdown(score_ring(score), unsafe_allow_html=True)
        if flow:
            pk = 'pdf_bytes_' + key_prefix
            if pk not in st.session_state: st.session_state[pk] = None
            if st.button('Generate Report PDF', key='btn_'+key_prefix, use_container_width=True):
                with st.spinner('Building executive report...'):
                    try: st.session_state[pk] = generar_pdf_bytes(flow, analysis)
                    except Exception as e: st.error(str(e))
            if st.session_state.get(pk):
                st.download_button('↓ Download PDF', data=st.session_state[pk],
                    file_name=flow.flow_name+'_orchestria.pdf', mime='application/pdf',
                    key='dl_'+key_prefix, use_container_width=True)

    with col_r:
        st.markdown(
            f'<div style="font-family:\'Plus Jakarta Sans\',sans-serif;font-size:0.9rem;'
            f'color:#7A8BA5;line-height:1.75;padding:0.25rem 0 1rem;">{summ}</div>',
            unsafe_allow_html=True)
        for i in issues: st.error(i)
        for i in imps:   st.success(i)

    if inv:
        st.divider()
        st.markdown('<span class="lbl">Flow Inventory</span>', unsafe_allow_html=True)
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric('Nodes',    inv.get('total_nodes',0))
        c2.metric('Menus',    inv.get('menu_nodes',0))
        c3.metric('Transfers',inv.get('transfer_nodes',0))
        c4.metric('Tasks',    inv.get('task_nodes',0))
        c5.metric('Self-Svc',str(inv.get('self_service_ratio',0))+'%')
        c6.metric('Ext. Deps',inv.get('total_external_deps',0))

    if inv and any([inv.get('data_services'),inv.get('auth_services'),
                    inv.get('dynamic_variables'),inv.get('unique_queues')]):
        st.divider()
        st.markdown('<span class="lbl">External Dependencies</span>', unsafe_allow_html=True)
        chips = ''
        for s in inv.get('data_services',   []): chips += f'<span class="orch-chip chip-teal">⬡ {s}</span>'
        for s in inv.get('auth_services',   []): chips += f'<span class="orch-chip chip-blue">⬡ {s}</span>'
        for v in inv.get('dynamic_variables',[]): chips += f'<span class="orch-chip">'+'{'+v+'}</span>'
        for q in inv.get('unique_queues',   []): chips += f'<span class="orch-chip">⇒ {q}</span>'
        st.markdown('<div style="display:flex;flex-wrap:wrap;gap:0.2rem;">'+chips+'</div>',
                    unsafe_allow_html=True)

    if inv:
        st.divider()
        ml = inv.get('migration_level', 'SIMPLE')
        ms = inv.get('migration_complexity_score', 0)
        breakdown = inv.get('migration_score_breakdown', {})
        flags = inv.get('migration_risk_flags', [])

        # Header del card
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:0.9rem;margin-bottom:1.25rem;">'
            f'<span class="lbl" style="margin:0;">Migration to Cloud</span>'
            f'{migration_badge(ml)}'
            f'<span style="font-family:\'DM Mono\',monospace;font-size:0.7rem;color:#3D4D66;">{ms}/100</span>'
            f'</div>', unsafe_allow_html=True)

        # Breakdown de 5 dimensiones si existe
        if breakdown:
            dim_colors = {
                'D1_grafo':        '#00A8FF',
                'D2_dependencias': '#00D4AA',
                'D3_riesgo':       '#F85149',
                'D4_escala':       '#D29922',
                'D5_testing':      '#A78BFA',
            }
            bars_html = '<div style="display:flex;flex-direction:column;gap:8px;margin-bottom:1.25rem;">'
            for key, dim in breakdown.items():
                label  = dim.get('label', key)
                dscore = dim.get('score', 0)
                dmax   = dim.get('max', 25)
                pct    = round(dscore / dmax * 100) if dmax else 0
                color  = dim_colors.get(key, '#4B5568')
                bars_html += (
                    f'<div style="display:flex;align-items:center;gap:10px;">'
                    f'<div style="font-family:\'DM Mono\',monospace;font-size:0.62rem;'
                    f'color:#4B5568;width:160px;flex-shrink:0;">{label}</div>'
                    f'<div style="flex:1;background:#0E1118;border-radius:3px;height:5px;overflow:hidden;">'
                    f'<div style="width:{pct}%;background:{color};height:100%;border-radius:3px;'
                    f'box-shadow:0 0 6px {color}50;"></div></div>'
                    f'<div style="font-family:\'DM Mono\',monospace;font-size:0.62rem;'
                    f'color:#3D4D66;width:40px;text-align:right;">{dscore}/{dmax}</div>'
                    f'</div>'
                )
            bars_html += '</div>'
            st.markdown(bars_html, unsafe_allow_html=True)

        # Risk flags
        if flags:
            for f_ in flags:
                st.warning(f_)
        else:
            st.success('No migration risks detected')

# ── HEADER ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="orch-header">'
    '<div style="display:flex;align-items:center;">'
    '<span class="orch-logo-main">Orchestr</span>'
    '<span class="orch-logo-dot">IA</span>'
    '<span class="orch-logo-badge">IVR · IA</span>'
    '</div>'
    '<span class="orch-tagline">Genesys Flow Intelligence · YAML · JSON · XML</span>'
    '</div>',
    unsafe_allow_html=True)

modo = st.radio('', ['Individual Flow', 'Portfolio Batch'],
                horizontal=True, label_visibility='collapsed')
st.markdown('<div style="margin-top:1.75rem;"></div>', unsafe_allow_html=True)

YAML_EXAMPLE = '''inboundCall:
  name: "Flujo Banca Retail"
  startUpRef: "./menus/menu_principal"
  defaultLanguage: "es-ES"
  supportedLanguages:
    es-ES:
      textToSpeech: Genesys TTS'''

# ── INDIVIDUAL ──────────────────────────────────────────────────────────────────
if modo == 'Individual Flow':
    col_l, col_r = st.columns([1, 1], gap='large')

    with col_l:
        st.markdown('<span class="lbl">Upload Flow</span>', unsafe_allow_html=True)
        uploaded = st.file_uploader('', type=['yaml','yml','json','xml'],
                                    label_visibility='collapsed')
        st.markdown(
            '<div style="margin:0.6rem 0;text-align:center;font-family:\'DM Mono\','
            'monospace;font-size:0.6rem;color:#1E2535;letter-spacing:0.12em;">— OR PASTE YAML DIRECTLY —</div>',
            unsafe_allow_html=True)
        yaml_input = st.text_area('', height=240, placeholder=YAML_EXAMPLE,
                                   label_visibility='collapsed')
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:0.6rem;">'
            '<span class="compat-chip">✓ inboundCall</span>'
            '<span class="compat-chip">✓ YAML / JSON / XML</span>'
            '<span class="compat-chip">✓ Genesys Cloud</span>'
            '<span class="compat-chip">✓ Architect flows</span>'
            '</div>',
            unsafe_allow_html=True)

    with col_r:
        analizar_clicked = st.button('Analyze Flow →', type='primary', use_container_width=True)

        # Empty state — siempre visible hasta que haya análisis
        if not st.session_state.analysis:
            st.markdown(empty_state_panel(), unsafe_allow_html=True)

        if analizar_clicked:
            content, filename = '', 'flow.yaml'
            if uploaded:
                content, filename = uploaded.read().decode('utf-8'), uploaded.name
            elif yaml_input.strip():
                content = yaml_input.strip()
            else:
                st.error('Upload a file or paste YAML content.')
                st.stop()

            loading_slot = st.empty()
            render = mostrar_loading(loading_slot)

            render(0,0); time.sleep(0.3)
            flow, err = parse_content(content, filename)
            if err:
                loading_slot.empty(); st.error(err); st.stop()
            render(1,1); time.sleep(0.2)
            render(2,2); time.sleep(0.2)
            render(3,3)
            analysis = IVRAnalyzer().analyze(flow)
            render(4,4); time.sleep(0.3)
            loading_slot.empty()

            st.session_state.analysis = analysis
            st.session_state.flow = flow
            st.session_state['pdf_bytes_main'] = None
            st.rerun()

    if st.session_state.analysis and modo == 'Individual Flow':
        st.divider()
        mostrar_resultado(st.session_state.analysis,
                          flow=st.session_state.flow, key_prefix='main')

# ── BATCH ───────────────────────────────────────────────────────────────────────
else:
    col_l, col_r = st.columns([1, 1], gap='large')

    with col_l:
        st.markdown('<span class="lbl">Upload Portfolio · up to 50 flows</span>',
                    unsafe_allow_html=True)
        uploaded_files = st.file_uploader('', type=['yaml','yml','json','xml'],
                                          accept_multiple_files=True,
                                          label_visibility='collapsed')
        if uploaded_files:
            st.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;'
                f'color:#3D4D66;margin-top:0.5rem;">{len(uploaded_files)} file(s) ready</div>',
                unsafe_allow_html=True)
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:0.75rem;">'
            '<span class="compat-chip">✓ Up to 50 flows</span>'
            '<span class="compat-chip">✓ Auto-ranked by score</span>'
            '<span class="compat-chip">✓ PDF per flow</span>'
            '</div>', unsafe_allow_html=True)

    with col_r:
        run_batch = st.button('Analyze Portfolio →', type='primary',
                               disabled=not uploaded_files)
        if not st.session_state.batch_results:
            st.markdown(empty_state_panel(), unsafe_allow_html=True)

    if run_batch and uploaded_files:
        resultados, flows_map = [], {}
        prog = st.progress(0)
        slot = st.empty()
        analyzer = IVRAnalyzer()
        for i, f in enumerate(uploaded_files[:50]):
            slot.markdown(
                f'<div style="font-family:\'DM Mono\',monospace;font-size:0.7rem;'
                f'color:#3D4D66;">Analyzing {i+1}/{len(uploaded_files)} · {f.name}</div>',
                unsafe_allow_html=True)
            flow, err = parse_content(f.read().decode('utf-8'), f.name)
            if err:
                resultados.append({'filename':f.name,'score':0,'error':err})
            else:
                r = analyzer.analyze(flow)
                r['filename'] = f.name
                resultados.append(r)
                flows_map[f.name] = flow
            prog.progress((i+1)/len(uploaded_files))
        slot.empty(); prog.empty()
        st.session_state.batch_results = resultados
        st.session_state.batch_flows   = flows_map
        st.rerun()

    if st.session_state.batch_results:
        results   = st.session_state.batch_results
        flows_map = st.session_state.batch_flows
        ok = sorted([r for r in results if 'error' not in r],
                    key=lambda x: x.get('score',0), reverse=True)
        st.markdown(
            f'<div style="margin:1.75rem 0 1rem;" class="lbl">'
            f'Portfolio · {len(ok)} flows · ranked by quality score</div>',
            unsafe_allow_html=True)
        for idx, r in enumerate(ok):
            s  = r.get('score',0)
            ml = r.get('inventory',{}).get('migration_level','—')
            fname = r['filename'].replace('.yaml','').replace('.yml','')
            dot = '🟢' if s >= 70 else '🟡' if s >= 40 else '🔴'
            with st.expander(f'{dot}  {fname}   ·   {s}/100   ·   {ml}'):
                mostrar_resultado(r, flow=flows_map.get(r['filename']),
                                  key_prefix=f'batch_{idx}')
        for r in [x for x in results if 'error' in x]:
            st.error(f"Error · {r['filename']}: {r['error']}")
