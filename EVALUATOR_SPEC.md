# EVALUATOR_SPEC.md — OrchestrIA
## Qué es este documento
Define el criterio de calidad que debe cumplir cualquier output de OrchestrIA
antes de ser entregado al cliente. El Evaluator Agent valida contra estos criterios.
Sin criterios definidos, no se escribe código de negocio.

---

## Criterios universales (todos los verticales)

### 1. Completitud
- El output responde a TODAS las preguntas del input
- No hay secciones vacías ni placeholders sin resolver
- Umbral: 100% — cualquier campo vacío es fallo

### 2. Coherencia interna
- El output no se contradice consigo mismo
- Las conclusiones son consistentes con los datos de entrada
- Umbral: 0 contradicciones detectables

### 3. Confianza mínima
- Cada claim del output tiene evidencia en el input
- No se inventan datos ni se extrapola sin indicarlo
- Umbral: 0 claims sin respaldo

### 4. Formato correcto
- El output sigue exactamente el schema definido para ese vertical
- Tipos de datos correctos, campos obligresentes
- Umbral: validación Pydantic pasa sin errores

---

## Criterios por vertical

### IVR·IA
- Todos los nodos del YAML de entrada aparecen en el grafo de salida
- Cada error detectado incluye: tipo, nodo afectado, descripción, severidad
- El resumen ejecutivo tiene entre 150 y 400 palabras
- Tiempo de procesamiento < 5 minutos para YAMLs de hasta 500 nodos
- Umbral de utilidad: consultor Genesys senior valida output como correcto

### HELIX
- Ninguna comunicación sale sin firma médica explícita
- Audit log registra: usuario, timestamp, acción, paciente
- Modo read-only por defecto — escritura requiere acción explícita
- 0 datos de historial clínico en el output (solo datos de contacto y cita)

### SIGNALIA ENGINE
- Cada oportunidad incluye: empresa, probabilidad, señales detectadas, razonamiento
- Probabilidad calculada con mínimo 2 señales independientes
- Umbral de utilidad: >30% de oportunidades marcadas como útiles por el usuario
- 0 fuentes ilegales o bloqueadas en la ingesta

#nes clínicas usan SOLO reglas deterministas — nunca LLM
- Readiness Score calculado con algoritmo documentado y auditable
- Si Hamstring Risk Score > umbral → STOP, sin excepciones
- Revisión de fisioterapeuta certificado antes de cada release

---

## Protocolo del Evaluator Agent

### Flujo de validación
1. Recibe output del agente de negocio
2. Ejecuta criterios universales
3. Ejecuta criterios del vertical correspondiente
4. Si PASA → entrega al cliente
5. Si FALLA → retry con contexto del fallo (máximo 2 reintentos)
6. Si FALLA tras 2 reintentos → escala a revisión humana

### Respuesta del Evaluator
```json
{
  "passed": true/false,
  "score": 0-100,
  "failures": ["descripción del fallo si hay"],
  "action": "deliver" | "retry" | "escalate"
}
```

### Regla de oro
Si tienes dudas sobre si un output pasa o no, NO pasa.
El criterio de calidad es el del cliente, no el del sistema.

---

## Contrato de lanzamiento
Antes de entregar cualquier output al cliente, las tres preguntas:
1. ¿El dado que el output es correcto? 
2. ¿Langfuse muestra consistencia en los últimos N casos?
3. ¿Un humano del dominio ha revisado el output?
Si alguna es NO → no se entrega.
