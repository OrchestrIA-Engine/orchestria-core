import sys
sys.path.insert(0, '.')
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig
from src.models.ivr.flow_model import IVRFlow
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from datetime import datetime
import os, json, re

PROMPT = 'Eres consultor senior de contact center. Genera contenido para informe ejecutivo basado en este analisis IVR. Responde UNICAMENTE con JSON valido sin markdown: {"executive_summary": "texto", "findings": ["f1","f2"], "action_plan": ["p1","p2"], "impact": "texto"}'

class IVRDocumentor:
    def __init__(self, api_key: str):
        self.adapter = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(model='claude-sonnet-4-6', max_tokens=1500)

    def generate_report_content(self, flow: IVRFlow, analysis: dict) -> dict:
        context = 'FLUJO: ' + flow.flow_name + ' SCORE: ' + str(analysis.get('score')) + '/100 RESUMEN: ' + str(analysis.get('summary')) + ' PROBLEMAS: ' + str(analysis.get('critical_issues')) + ' MEJORAS: ' + str(analysis.get('improvements'))
        response = self.adapter.complete([Message(role='user', content=PROMPT + ' ' + context)], self.config)
        raw = response.content.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match: raw = match.group(0)
        try: return json.loads(raw)
        except: return {'executive_summary': analysis.get('summary',''), 'findings': analysis.get('critical_issues',[]), 'action_plan': analysis.get('improvements',[]), 'impact': analysis.get('recommendation','')}

    def generate_pdf(self, flow: IVRFlow, analysis: dict, output_path: str) -> str:
        content = self.generate_report_content(flow, analysis)
        doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        navy = HexColor('#1E3A5F')
        accent = HexColor('#E63946')
        title_style = ParagraphStyle('Title', fontSize=22, textColor=navy, spaceAfter=16, fontName='Helvetica-Bold')
        h2_style = ParagraphStyle('H2', fontSize=13, textColor=navy, spaceAfter=8, spaceBefore=18, fontName='Helvetica-Bold')
        body_style = ParagraphStyle('Body', fontSize=10, spaceAfter=6, leading=15)
        brand_style = ParagraphStyle('Brand', fontSize=11, textColor=accent, fontName='Helvetica-Bold', spaceAfter=4)
        story = []
        story.append(Paragraph('OrchestrIA - IVR.IA', brand_style))
        story.append(Paragraph('Analisis de Flujo: ' + flow.flow_name, title_style))
        story.append(Paragraph('Generado el ' + datetime.now().strftime('%d/%m/%Y a las %H:%M'), body_style))
        story.append(Spacer(1, 0.4*cm))
        score = analysis.get('score', 0)
        table_data = [['Metrica','Valor'],['Score de Calidad', str(score)+'/100'],['Total Nodos', str(flow.total_nodes)],['Errores', str(len(flow.errors))],['Proveedor', flow.provider]]
        t = Table(table_data, colWidths=[8*cm, 8*cm])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('TEXTCOLOR',(0,0),(-1,0),HexColor('#FFFFFF')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('BACKGROUND',(0,1),(-1,-1),HexColor('#F8FAFC')),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),10),('PADDING',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),0.5,HexColor('#E2E8F0'))]))
        story.append(t)
        story.append(Paragraph('Resumen Ejecutivo', h2_style))
        story.append(Paragraph(content.get('executive_summary',''), body_style))
        story.append(Paragraph('Hallazgos Principales', h2_style))
        for i,f in enumerate(content.get('findings',[]),1): story.append(Paragraph(str(i)+'. '+f, body_style))
        story.append(Paragraph('Plan de Accion', h2_style))
        for i,a in enumerate(content.get('action_plan',[]),1): story.append(Paragraph('Paso '+str(i)+': '+a, body_style))
        story.append(Paragraph('Impacto Esperado', h2_style))
        story.append(Paragraph(content.get('impact',''), body_style))
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph('Informe generado por OrchestrIA', ParagraphStyle('Footer', fontSize=8, textColor=HexColor('#94A3B8'), alignment=1)))
        doc.build(story)
        return output_path