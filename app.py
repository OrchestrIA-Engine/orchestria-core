import streamlit as st
import sys, os, tempfile
sys.path.insert(0, '.')
from src.parsers.genesys_yaml_parser import GenesysYAMLParser
from src.agents.analyzer import IVRAnalyzer
from src.agents.documentor import IVRDocumentor

st.set_page_config(page_title='OrchestrIA', layout='wide')
st.title('OrchestrIA IVR IA')
st.divider()

api_key = os.environ.get('ANTHROPIC_API_KEY', '')
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
            analyzer = IVRAnalyzer(api_key=api_key)
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
            documentor = IVRDocumentor(api_key=api_key)
            pdf_path = tempfile.mktemp(suffix='.pdf')
            documentor.generate_pdf(flow, analysis, pdf_path)
            with open(pdf_path, 'rb') as f:
                st.download_button('Descargar PDF', f.read(), file_name='informe.pdf', mime='application/pdf')
