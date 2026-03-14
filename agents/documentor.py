import sys
sys.path.insert(0, '.')
from src.llm.anthropic_adapter import AnthropicAdapter
from src.llm.base import Message, LLMConfig
from src.models.ivr.flow_model import IVRFlow
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm
from datetime import datetime
import os, json, re

PROMPT = """Eres consultor senior de contact center con experiencia en Genesys Engage y Cloud.
Genera contenido ejecutivo para un informe de auditoria de flujo IVR.
El tono debe ser profesional, orientado a decision de negocio, no tecnico.
Responde UNICAMENTE con JSON valido sin markdown ni texto adicional:
{
  "executive_summary": "2-3 frases orientadas a impacto de negocio",
  "findings": ["hallazgo critico 1 con impacto", "hallazgo 2", "hallazgo 3"],
  "action_plan": ["accion concreta 1 con responsable sugerido", "accion 2", "accion 3"],
  "impact": "impacto esperado en KPIs del contact center si se implementan las mejoras",
  "migration_recommendation": "recomendacion especifica sobre la migracion a Cloud"
}"""


class IVRDocumentor:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.adapter = AnthropicAdapter(api_key=api_key)
        self.config = LLMConfig(model='claude-sonnet-4-6', max_tokens=1500)

    def generate_report_content(self, flow: IVRFlow, analysis: dict) -> dict:
        inv = analysis.get('inventory', {})
        context = (
            'FLUJO: ' + flow.flow_name +
            ' | SCORE: ' + str(analysis.get('score')) + '/100' +
            ' | NODOS: ' + str(inv.get('total_nodes', 0)) +
            ' | SELF-SERVICE RATIO: ' + str(inv.get('self_service_ratio', 0)) + '%' +
            ' | DEPS EXTERNAS: ' + str(inv.get('total_external_deps', 0)) +
            ' | COMPLEJIDAD MIGRACION: ' + str(inv.get('migration_level', 'N/A')) +
            ' | RESUMEN: ' + str(analysis.get('summary', '')) +
            ' | PROBLEMAS CRITICOS: ' + str(analysis.get('critical_issues', [])) +
            ' | MEJORAS: ' + str(analysis.get('improvements', [])) +
            ' | RIESGOS MIGRACION: ' + str(inv.get('migration_risk_flags', []))
        )
        response = self.adapter.complete(
            [Message(role='user', content=PROMPT + '\n\nDATOS:\n' + context)],
            self.config
        )
        raw = response.content.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        try:
            return json.loads(raw)
        except Exception:
            return {
                'executive_summary': analysis.get('summary', ''),
                'findings': analysis.get('critical_issues', []),
                'action_plan': analysis.get('improvements', []),
                'impact': analysis.get('recommendation', ''),
                'migration_recommendation': ''
            }

    def generate_pdf(self, flow: IVRFlow, analysis: dict, output_path: str) -> str:
        content = self.generate_report_content(flow, analysis)
        inv = analysis.get('inventory', {})
        score = analysis.get('score', 0)

        # Colores
        navy = HexColor('#1E3A5F')
        accent = HexColor('#E63946')
        green = HexColor('#2D6A4F')
        orange = HexColor('#F4A261')
        red = HexColor('#E63946')
        light_bg = HexColor('#F8FAFC')
        border = HexColor('#E2E8F0')
        text_secondary = HexColor('#64748B')
        white = HexColor('#FFFFFF')

        score_color = green if score >= 70 else orange if score >= 40 else red

        # Estilos
        brand_style = ParagraphStyle('Brand', fontSize=10, textColor=accent,
                                     fontName='Helvetica-Bold', spaceAfter=4)
        title_style = ParagraphStyle('Title', fontSize=20, textColor=navy,
                                     spaceAfter=6, fontName='Helvetica-Bold')
        subtitle_style = ParagraphStyle('Subtitle', fontSize=11, textColor=text_secondary,
                                        spaceAfter=16)
        h2_style = ParagraphStyle('H2', fontSize=13, textColor=navy, spaceAfter=8,
                                  spaceBefore=20, fontName='Helvetica-Bold')
        h3_style = ParagraphStyle('H3', fontSize=11, textColor=navy, spaceAfter=6,
                                  spaceBefore=12, fontName='Helvetica-Bold')
        body_style = ParagraphStyle('Body', fontSize=10, spaceAfter=5, leading=16,
                                    textColor=HexColor('#1E293B'))
        caption_style = ParagraphStyle('Caption', fontSize=9, textColor=text_secondary,
                                       spaceAfter=4)
        footer_style = ParagraphStyle('Footer', fontSize=8, textColor=text_secondary,
                                      alignment=1)

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        story = []

        # ── CABECERA ─────────────────────────────────────────────────────────
        story.append(Paragraph('OrchestrIA · IVR·IA', brand_style))
        story.append(Paragraph('Informe de Auditoría de Flujo IVR', title_style))
        story.append(Paragraph(flow.flow_name + ' · ' +
                                datetime.now().strftime('%d/%m/%Y'), subtitle_style))
        story.append(HRFlowable(width='100%', thickness=1, color=border, spaceAfter=16))

        # ── TABLA DE MÉTRICAS PRINCIPALES ────────────────────────────────────
        ml = inv.get('migration_level', 'N/A')
        ml_color = {
            'SIMPLE': HexColor('#D1FAE5'),
            'MODERADO': HexColor('#FEF3C7'),
            'COMPLEJO': HexColor('#FFEDD5'),
            'MUY COMPLEJO': HexColor('#FEE2E2'),
        }.get(ml, light_bg)

        metrics_data = [
            ['Métrica', 'Valor', 'Métrica', 'Valor'],
            ['Score de Calidad', str(score) + '/100',
             'Total Nodos', str(inv.get('total_nodes', 0))],
            ['Self-Service Ratio', str(inv.get('self_service_ratio', 0)) + '%',
             'Transfers a Agente', str(inv.get('agent_transfers', 0))],
            ['Deps. Externas', str(inv.get('total_external_deps', 0)),
             'Complejidad Migración', ml],
            ['APIs de Datos', str(len(inv.get('data_services', []))),
             'Servicios de Auth', str(len(inv.get('auth_services', [])))],
        ]

        metrics_table = Table(metrics_data, colWidths=[4.5*cm, 3*cm, 4.5*cm, 3*cm])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), light_bg),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTNAME', (3, 1), (3, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, border),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [light_bg, white]),
        ]))
        story.append(metrics_table)

        # ── RESUMEN EJECUTIVO ─────────────────────────────────────────────────
        story.append(Paragraph('Resumen Ejecutivo', h2_style))
        story.append(Paragraph(content.get('executive_summary', ''), body_style))

        # ── INVENTARIO TÉCNICO ───────────────────────────────────────────────
        story.append(Paragraph('Inventario del Flujo', h2_style))

        inv_data = [['Componente', 'Detalle']]
        if inv.get('data_services'):
            inv_data.append(['APIs de Datos', ', '.join(inv['data_services'])])
        if inv.get('auth_services'):
            inv_data.append(['Servicios de Auth', ', '.join(inv['auth_services'])])
        if inv.get('unique_queues'):
            inv_data.append(['Colas de Destino', ', '.join(inv['unique_queues'])])
        if inv.get('dynamic_variables'):
            inv_data.append(['Variables Dinámicas TTS',
                             ', '.join(['{' + v + '}' for v in inv['dynamic_variables']])])
        inv_data.append(['Nodos Menú / Transfer / Tarea',
                         str(inv.get('menu_nodes', 0)) + ' / ' +
                         str(inv.get('transfer_nodes', 0)) + ' / ' +
                         str(inv.get('task_nodes', 0))])

        if len(inv_data) > 1:
            inv_table = Table(inv_data, colWidths=[5*cm, 10*cm])
            inv_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), navy),
                ('TEXTCOLOR', (0, 0), (-1, 0), white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('PADDING', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, border),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [light_bg, white]),
            ]))
            story.append(inv_table)

        # ── HALLAZGOS ─────────────────────────────────────────────────────────
        story.append(Paragraph('Hallazgos Principales', h2_style))
        for i, finding in enumerate(content.get('findings', []), 1):
            story.append(Paragraph(str(i) + '. ' + finding, body_style))

        # ── PLAN DE ACCIÓN ────────────────────────────────────────────────────
        story.append(Paragraph('Plan de Acción', h2_style))
        for i, action in enumerate(content.get('action_plan', []), 1):
            story.append(Paragraph('Paso ' + str(i) + ': ' + action, body_style))

        # ── MIGRATION ASSESSMENT ──────────────────────────────────────────────
        story.append(Paragraph('Migration Assessment · Genesys Cloud', h2_style))
        story.append(Paragraph(
            'Nivel de complejidad: ' + ml + ' (' +
            str(inv.get('migration_complexity_score', 0)) + '/100)',
            h3_style
        ))
        if content.get('migration_recommendation'):
            story.append(Paragraph(content['migration_recommendation'], body_style))

        flags = inv.get('migration_risk_flags', [])
        if flags:
            story.append(Paragraph('Riesgos identificados:', h3_style))
            for flag in flags:
                story.append(Paragraph('• ' + flag, body_style))

        # ── IMPACTO ESPERADO ──────────────────────────────────────────────────
        story.append(Paragraph('Impacto Esperado', h2_style))
        story.append(Paragraph(content.get('impact', ''), body_style))

        # ── FOOTER ────────────────────────────────────────────────────────────
        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=border, spaceAfter=8))
        story.append(Paragraph(
            'Informe generado por OrchestrIA IVR·IA · ' +
            datetime.now().strftime('%d/%m/%Y %H:%M') +
            ' · Confidencial',
            footer_style
        ))

        doc.build(story)
        return output_path