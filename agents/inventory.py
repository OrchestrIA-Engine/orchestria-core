"""
FlowInventoryExtractor v2
Extrae métricas estructurales de un IVRFlow y calcula el Migration Complexity Score
mediante un modelo ponderado en 5 dimensiones — no lineal-aditivo.

Dimensiones (basadas en metodología de integradores Genesys certificados):
  D1 · Complejidad técnica del grafo    25 pts
  D2 · Dependencias externas            25 pts
  D3 · Riesgo de negocio                20 pts
  D4 · Volumen y escala                 15 pts
  D5 · Esfuerzo de testing              15 pts
  ─────────────────────────────────────────
  Total                                100 pts

Niveles:
  SIMPLE       0–20   (~1–2 días · flujo básico sin integraciones)
  MODERADO    21–45   (~3–5 días · integraciones simples o flujo mediano)
  COMPLEJO    46–70   (~8–15 días · múltiples APIs + auth + lógica avanzada)
  MUY COMPLEJO 71–100 (~20–40 días · arquitectura compleja + integraciones críticas)
  Fuente: metodología Cyara/TTEC Digital/PS Genesys. No son datos oficiales Genesys.
"""

import re
from src.models.ivr.flow_model import IVRFlow, NodeType


class FlowInventoryExtractor:

    def extract(self, flow: IVRFlow) -> dict:
        nodes = flow.nodes

        # ── CONTEOS BASE ───────────────────────────────────────────────────────
        total_nodes    = len(nodes)
        menu_nodes     = sum(1 for n in nodes.values() if n.type == NodeType.MENU)
        transfer_nodes = sum(1 for n in nodes.values() if n.type == NodeType.TRANSFER)
        task_nodes     = sum(1 for n in nodes.values() if n.type in (NodeType.SET_VARIABLE, NodeType.LOOP, NodeType.SWITCH))
        exit_nodes     = sum(1 for n in nodes.values() if n.type == NodeType.EXIT)

        # ── COLAS ─────────────────────────────────────────────────────────────
        unique_queues = set()
        for n in nodes.values():
            if n.type == NodeType.TRANSFER:
                if n.transfer_target:
                    unique_queues.add(n.transfer_target)
                rc = n.raw_config or {}
                if rc.get('queue'):
                    unique_queues.add(rc['queue'])
        unique_queues = sorted(unique_queues)

        # ── APIS Y AUTH ────────────────────────────────────────────────────────
        data_services  = set()
        auth_services  = set()
        api_calls      = set()

        for n in nodes.values():
            rc = n.raw_config or {}
            t  = n.type

            # Top-level fields
            if rc.get('dataQuery'):    data_services.add(rc['dataQuery'])
            if rc.get('authenticate'): auth_services.add(rc['authenticate'])
            if rc.get('apiCall'):      api_calls.add(rc['apiCall'])
            if t == NodeType.API_CALL:
                api_calls.add(rc.get('name') or n.id)

            # Genesys actions list: [{type: authenticate, service: "x"}, ...]
            for action in (rc.get('actions') or []):
                if not isinstance(action, dict): continue
                atype   = action.get('type', '')
                service = action.get('service') or action.get('name') or action.get('endpoint', '')
                if not service: continue
                if atype == 'authenticate':
                    auth_services.add(service)
                elif atype in ('dataQuery', 'getData', 'dataAction'):
                    data_services.add(service)
                elif atype in ('apiCall', 'callApi', 'api'):
                    api_calls.add(service)

            # Recursive scan for nested actions
            self._extract_services_recursive(rc, data_services, auth_services, api_calls)

        data_services = sorted(data_services)
        auth_services = sorted(auth_services)
        api_calls     = sorted(api_calls)
        total_ext_deps = len(data_services) + len(auth_services) + len(api_calls)

        # ── VARIABLES DINÁMICAS TTS ────────────────────────────────────────────
        dynamic_variables = set()
        for n in nodes.values():
            rc = n.raw_config or {}
            for val in self._iter_strings(rc):
                for match in re.findall(r'\{(\w+)\}', val):
                    dynamic_variables.add(match)
        dynamic_variables = sorted(dynamic_variables)

        # ── TIPOS ESPECIALES ───────────────────────────────────────────────────
        voicemail_nodes  = [n.id for n in nodes.values()
                            if (n.raw_config or {}).get('recordMessage')]
        dtmf_input_nodes = [n.id for n in nodes.values()
                            if (n.raw_config or {}).get('choices')
                            or (n.raw_config or {}).get('maxDigits')]
        speech_input     = any((n.raw_config or {}).get('speechInput')
                               for n in nodes.values())
        recording_nodes  = [n.id for n in nodes.values()
                            if (n.raw_config or {}).get('record')
                            or (n.raw_config or {}).get('recording')]
        schedule_nodes   = [n.id for n in nodes.values()
                            if (n.raw_config or {}).get('schedule')
                            or n.type == NodeType.CONDITION
                            and 'schedule' in str(n.raw_config).lower()]

        # ── ANÁLISIS DE GRAFO ──────────────────────────────────────────────────
        # Construir mapa de conexiones
        adjacency = {nid: set() for nid in nodes}
        for n in nodes.values():
            for target in (n.next_nodes or []):
                if target in nodes:
                    adjacency[n.id].add(target)

        # Profundidad máxima del árbol (BFS desde entry)
        entry_id   = flow.entry_node_id
        flow_depth = self._compute_depth(entry_id, adjacency, nodes)

        # Dead ends — nodos sin conexiones salientes y que no son EXIT
        dead_ends = [
            nid for nid, n in nodes.items()
            if not adjacency.get(nid)
            and n.type not in (NodeType.EXIT, NodeType.TRANSFER)
        ]

        # Transfers sin timeout / fallback
        missing_fallbacks = []
        for n in nodes.values():
            if n.type == NodeType.TRANSFER:
                rc = n.raw_config or {}
                if not rc.get('timeout') and not rc.get('fallback'):
                    missing_fallbacks.append(n.id)

        # Menus sin noInput / noMatch
        menus_without_handlers = []
        for n in nodes.values():
            if n.type == NodeType.MENU:
                rc = n.raw_config or {}
                has_ni = rc.get('noInput') or rc.get('noInputAction') or rc.get('noInputTarget')
                has_nm = rc.get('noMatch') or rc.get('noMatchAction') or rc.get('noMatchTarget')
                has_to = rc.get('timeout') or rc.get('timeoutAction')
                if not (has_ni or has_nm or has_to):
                    menus_without_handlers.append(n.id)

        # Inter-flow calls (llamadas a otros flujos)
        inter_flow_calls = []
        for n in nodes.values():
            rc = n.raw_config or {}
            if rc.get('transferToFlow') or rc.get('subFlow') or rc.get('externalFlow'):
                inter_flow_calls.append(n.id)

        # Ratio autoservicio
        agent_transfers    = len(unique_queues)
        self_service_exits = exit_nodes
        total_exits        = self_service_exits + agent_transfers
        self_service_ratio = round(
            self_service_exits / total_exits * 100 if total_exits > 0 else 0, 1)

        # Idiomas
        language_count = max(1, len(getattr(flow, 'supported_languages', None) or []))

        # DTMF + speech = doble testing
        dual_input = speech_input and bool(dtmf_input_nodes)

        # ── MIGRATION COMPLEXITY SCORE v2 ──────────────────────────────────────
        score_breakdown, mcs, level, risk_flags = self._compute_migration_score(
            total_nodes        = total_nodes,
            flow_depth         = flow_depth,
            dead_ends          = dead_ends,
            inter_flow_calls   = inter_flow_calls,
            data_services      = data_services,
            auth_services      = auth_services,
            api_calls          = api_calls,
            unique_queues      = unique_queues,
            recording_nodes    = recording_nodes,
            schedule_nodes     = schedule_nodes,
            missing_fallbacks  = missing_fallbacks,
            language_count     = language_count,
            dynamic_variables  = dynamic_variables,
            dual_input         = dual_input,
            speech_input       = speech_input,
            voicemail_nodes    = voicemail_nodes,
            menus_without_handlers = menus_without_handlers,
            entry_id           = entry_id,
        )

        return {
            # Conteos
            'total_nodes':         total_nodes,
            'menu_nodes':          menu_nodes,
            'transfer_nodes':      transfer_nodes,
            'task_nodes':          task_nodes,
            'exit_nodes':          exit_nodes,
            # Dependencias
            'data_services':       data_services,
            'auth_services':       auth_services,
            'api_calls':           api_calls,
            'total_external_deps': total_ext_deps,
            'unique_queues':       unique_queues,
            # Variables y TTS
            'dynamic_variables':   dynamic_variables,
            # Tipos especiales
            'voicemail_nodes':     voicemail_nodes,
            'dtmf_input_nodes':    dtmf_input_nodes,
            'recording_nodes':     recording_nodes,
            'schedule_nodes':      schedule_nodes,
            'speech_input':        speech_input,
            # Grafo
            'flow_depth':          flow_depth,
            'dead_ends':           dead_ends,
            'inter_flow_calls':    inter_flow_calls,
            'missing_fallbacks':   missing_fallbacks,
            'menus_without_handlers': menus_without_handlers,
            # Ratios
            'agent_transfers':     agent_transfers,
            'self_service_exits':  self_service_exits,
            'self_service_ratio':  self_service_ratio,
            'language_count':      language_count,
            # Migration
            'migration_complexity_score': mcs,
            'migration_level':            level,
            'migration_risk_flags':       risk_flags,
            'migration_score_breakdown':  score_breakdown,
        }

    # ── MODELO DE SCORING v2 ───────────────────────────────────────────────────
    def _compute_migration_score(self, **kw) -> tuple:
        """
        Modelo ponderado en 5 dimensiones.
        Cada dimensión produce un score parcial 0–max_pts.
        El resultado final se normaliza a 0–100.
        """
        breakdown = {}
        flags = []

        # ── D1: Complejidad técnica del grafo (25 pts) ─────────────────────────
        d1 = 0
        nodes      = kw['total_nodes']
        depth      = kw['flow_depth']
        dead       = len(kw['dead_ends'])
        inter      = len(kw['inter_flow_calls'])
        no_entry   = not kw['entry_id']

        # Tamaño del flujo
        if nodes > 30:   d1 += 10
        elif nodes > 15: d1 += 6
        elif nodes > 7:  d1 += 3

        # Profundidad del árbol
        if depth > 10:   d1 += 8
        elif depth > 6:  d1 += 5
        elif depth > 3:  d1 += 2

        # Dead ends — flujo roto = riesgo alto
        if dead > 3:     d1 += 7
        elif dead > 0:   d1 += 4
        if dead > 0:
            flags.append(f'{dead} dead end(s) detectado(s) — el flujo tiene nodos sin salida')

        # Inter-flow calls
        if inter > 2:    d1 += 5
        elif inter > 0:  d1 += 3
        if inter > 0:
            flags.append(f'{inter} llamada(s) a flujos externos — dependencias entre flows')

        # Sin entry node
        if no_entry:
            d1 += 5
            flags.append('Sin entry node definido — punto de entrada no claro')

        d1 = min(d1, 25)
        breakdown['D1_grafo'] = {'score': d1, 'max': 25, 'label': 'Complejidad del grafo'}

        # ── D2: Dependencias externas (25 pts) ────────────────────────────────
        d2 = 0
        apis   = len(kw['data_services']) + len(kw['api_calls'])
        auth   = len(kw['auth_services'])
        queues = len(kw['unique_queues'])

        # APIs de datos
        if apis > 4:     d2 += 12
        elif apis > 2:   d2 += 8
        elif apis > 0:   d2 += 5
        if apis > 0:
            flags.append(f'{apis} integración(es) de datos — requieren reconexión en Cloud')

        # Auth — cada servicio requiere validación OAuth/SAML + certificados en Cloud
        if auth > 3:     d2 += 12
        elif auth > 1:   d2 += 8
        elif auth > 0:   d2 += 5
        if auth > 0:
            flags.append(f'{auth} servicio(s) de auth — validar compatibilidad con Genesys Cloud Auth')

        # Colas
        if queues > 8:   d2 += 5
        elif queues > 4: d2 += 3
        elif queues > 1: d2 += 1

        d2 = min(d2, 25)
        breakdown['D2_dependencias'] = {'score': d2, 'max': 25, 'label': 'Dependencias externas'}

        # ── D3: Riesgo de negocio (20 pts) ────────────────────────────────────
        d3 = 0
        recordings  = len(kw['recording_nodes'])
        schedules   = len(kw['schedule_nodes'])
        fallbacks   = len(kw['missing_fallbacks'])
        menus_bad   = len(kw['menus_without_handlers'])

        # Grabación — GDPR / compliance
        if recordings > 0:
            d3 += 8
            flags.append(f'{recordings} nodo(s) de grabación — revisar cumplimiento GDPR en Cloud')

        # Horarios complejos
        if schedules > 2:   d3 += 6
        elif schedules > 0: d3 += 3
        if schedules > 0:
            flags.append(f'{schedules} nodo(s) de horario — validar schedule management en Cloud')

        # Transfers sin fallback
        if fallbacks > 3:   d3 += 6
        elif fallbacks > 0: d3 += 3
        if fallbacks > 0:
            flags.append(f'{fallbacks} transfer(s) sin timeout/fallback — riesgo de experiencia de cliente')

        # Menús sin handlers de error
        if menus_bad > 3:   d3 += 4
        elif menus_bad > 0: d3 += 2

        d3 = min(d3, 20)
        breakdown['D3_riesgo'] = {'score': d3, 'max': 20, 'label': 'Riesgo de negocio'}

        # ── D4: Volumen y escala (15 pts) ─────────────────────────────────────
        d4 = 0
        langs = kw['language_count']
        qcount = len(kw['unique_queues'])
        vm    = len(kw['voicemail_nodes'])

        # Multi-idioma
        if langs > 3:    d4 += 7
        elif langs > 1:  d4 += 4
        if langs > 1:
            flags.append(f'{langs} idiomas — TTS providers y localizaciones a verificar en Cloud')

        # Número de colas — cada cola requiere config en Cloud (queue routing, skills, IVR DN)
        if qcount > 10:  d4 += 7
        elif qcount > 5: d4 += 5
        elif qcount > 2: d4 += 3
        elif qcount > 0: d4 += 1

        # Voicemail
        if vm > 0:
            d4 += 3
            flags.append(f'{vm} nodo(s) de voicemail — verificar configuración de buzón en Cloud')

        d4 = min(d4, 15)
        breakdown['D4_escala'] = {'score': d4, 'max': 15, 'label': 'Volumen y escala'}

        # ── D5: Esfuerzo de testing (15 pts) ──────────────────────────────────
        d5 = 0
        dvars    = len(kw['dynamic_variables'])
        dual     = kw['dual_input']
        speech   = kw['speech_input']

        # Variables dinámicas TTS
        if dvars > 5:    d5 += 6
        elif dvars > 2:  d5 += 4
        elif dvars > 0:  d5 += 2
        if dvars > 3:
            flags.append(f'{dvars} variables dinámicas TTS — verificar disponibilidad en runtime Cloud')

        # Input dual (DTMF + speech)
        if dual:
            d5 += 5
            flags.append('DTMF + Speech input detectados — testing doble obligatorio')
        elif speech:
            d5 += 3

        # Dead ends también afectan testing
        if dead > 0:
            d5 += 4

        d5 = min(d5, 15)
        breakdown['D5_testing'] = {'score': d5, 'max': 15, 'label': 'Esfuerzo de testing'}

        # ── TOTAL ─────────────────────────────────────────────────────────────
        total = d1 + d2 + d3 + d4 + d5
        total = min(total, 100)

        # Nivel
        if total <= 20:
            level = 'SIMPLE'
        elif total <= 45:
            level = 'MODERADO'
        elif total <= 70:
            level = 'COMPLEJO'
        else:
            level = 'MUY COMPLEJO'

        return breakdown, total, level, flags

    # ── UTILIDADES ─────────────────────────────────────────────────────────────
    def _compute_depth(self, entry_id, adjacency, nodes) -> int:
        """BFS para calcular la profundidad máxima del árbol desde el entry node."""
        if not entry_id or entry_id not in nodes:
            # Si no hay entry, usamos el primer nodo como heurística
            entry_id = next(iter(nodes), None)
        if not entry_id:
            return 0

        visited = {entry_id}
        queue   = [(entry_id, 0)]
        max_d   = 0

        while queue:
            node_id, depth = queue.pop(0)
            max_d = max(max_d, depth)
            for neighbor in adjacency.get(node_id, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return max_d

    def _extract_services_recursive(self, obj, data_s, auth_s, api_s, _depth=0):
        """Busca recursivamente patrones {type, service} en cualquier nivel del config."""
        if _depth > 6 or not isinstance(obj, (dict, list)):
            return
        if isinstance(obj, list):
            for item in obj:
                self._extract_services_recursive(item, data_s, auth_s, api_s, _depth+1)
        elif isinstance(obj, dict):
            atype   = obj.get('type', '')
            service = obj.get('service') or obj.get('endpoint') or ''
            if service and isinstance(service, str):
                if atype == 'authenticate':
                    auth_s.add(service)
                elif atype in ('dataQuery', 'getData', 'dataAction'):
                    data_s.add(service)
                elif atype in ('apiCall', 'callApi', 'api'):
                    api_s.add(service)
            for v in obj.values():
                self._extract_services_recursive(v, data_s, auth_s, api_s, _depth+1)

    def _iter_strings(self, obj, _depth=0) -> list:
        """Itera recursivamente sobre todos los strings de un dict/list."""
        if _depth > 8:
            return []
        results = []
        if isinstance(obj, str):
            results.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                results.extend(self._iter_strings(v, _depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(self._iter_strings(item, _depth + 1))
        return results
