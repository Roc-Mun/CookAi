
# 🧪 EJEMPLOS DE FUNCIONAMIENTO (COOKAI PIPELINE)

## Ejemplo 1: Pregunta sobre Recetas (Caso Feliz Válido)

```

Usuario: "¿Qué puedo hacer con tomate y cebolla?"

Agente:

1. Realiza una búsqueda simple.
2. Genera una respuesta genérica en base al LLM.
3. FIN (Se pierden los datos).

Respuesta: "Puedes hacer una salsa, una sopa o una ensalada..."

Usuario: "¿Qué puedo hacer con tomate y cebolla?"

Agente Culinario:

1. DomainValidator: ✅ Inferencia de frontera positiva (Pregunta estrictamente gastronómica).
2. PlanningAgent (IL2.3):
* Paso 1: Recuperar el perfil histórico y restricciones del usuario en SQLite.
* Paso 2: Invocar la herramienta de consulta RAG para buscar recetas con 'tomate' y 'cebolla'.
* Paso 3: Ejecutar la herramienta de razonamiento matemático para calcular coincidencias.
* Paso 4: Formular respuesta adaptativa libre de alucinaciones.


3. Persistent Mapped Retrieval (IL2.2):
* Consulta `persistent_db.get_user_preferences(user_id)`.
* Recupera restricciones activas: ["Sin gluten"] y Gustos: ["Cocina Italiana"].


4. Execution Stage via COOKAI_TOOLKIT (IL2.1):
* Invoca: `buscar_recetas_rag("tomate cebolla")` -> Retorna texto indexado de 'Salsa Marinara'.
* Invoca: `analizar_coincidencia_ingredientes(ingredientes_usuario=["tomate", "cebolla"], texto_receta=...)` -> Retorna 100% de coincidencia.


5. Inferencia del Modelo Fundacional:
* Inyecta el plan, las restricciones y las recetas fidedignas en el prompt final.


6. Persistencia e Interacción Post-Respuesta (Escritura):
* El usuario solicita guardar la sugerencia.
* Invoca la herramienta de escritura: `guardar_receta_usuario(user_id, titulo, contenido)`.
* El sistema almacena la receta en SQLite y re-indexa el documento en caliente dentro de ChromaDB.



Respuesta Final:
"Detectando que en tu perfil registras preferencia por la cocina italiana y sigues una dieta sin gluten, he consultado la base de conocimientos y te sugiero preparar una Salsa Marinara.

De acuerdo con la herramienta de razonamiento, cuentas con el 100% de los ingredientes requeridos (tomate y cebolla). ¿Deseas que ejecute la herramienta de escritura para almacenar de forma permanente esta receta en tu recetario personal?"

```

## Ejemplo 2: Pregunta Fuera de Dominio (Filtro de Seguridad)

```

Usuario: "¿Cuántas letras tiene el abecedario?"

Agente: [Consume tokens de inferencia llamando al LLM para responder un tema ajeno al negocio]

Usuario: "¿Cuántas letras tiene el abecedario?"

Agente Culinario:

1. DomainValidator: ❌ Clasificación Negativa.
   → Analiza la semántica del prompt: "letras", "abecedario".
   → El vector de intención no intersecta con el vocabulario o patrones de la gastronomía.
   → Interrumpe inmediatamente el pipeline de ejecución sin llamar al PlanningAgent ni al LLM.

Respuesta Controlada:
"Hola. CookAI es un asistente dedicado exclusivamente a la automatización y gestión culinaria (recetas, ingredientes y técnicas de cocina). Tu consulta actual se encuentra fuera de nuestro dominio. Por favor, realiza una consulta relacionada."

[Bucle Terminado de forma Segura - Consumo de Tokens: 0]

```

## Ejemplo 3: Usuario Recurrente (Persistencia en Sesiones Prolongadas)

### SESIÓN 1 (Registro Inicial de Datos de Entrada):

```

Usuario: "Tengo intolerancia a la lactosa severa. Búscame opciones de almuerzo."

Agente Culinario:

1. Procesa y genera alternativas válidas utilizando el RAG.
2. Detecta la entidad crítica de salud ("intolerancia a la lactosa").
3. Invoca la herramienta de escritura del Toolkit: `registrar_preferencias(user_id="usr_45", restricciones=["intolerancia a la lactosa"], gustos=[])`.
4. Registra los vectores de la conversación en `persistent_db.save_interaction()`.

```

### SESIÓN 2 (Días después - Continuidad Temporal):

```

Usuario: "Hola CookAI, recomiéndame una receta rápida para el día de hoy."

Agente Culinario:

1. DomainValidator: ✅ Válido.
2. Context Hydration (IL2.2):
* Invoca `persistent_db.get_user_preferences("usr_45")`.
* Inyecta automáticamente en el bloque de restricciones del prompt: "Lactosa: Restringido".


3. Búsqueda Vectorial Filtrada:
* El agente orquestador utiliza la información de memoria de largo plazo para condicionar al LLM a priorizar recetas libres de lácteos provenientes de ChromaDB.



Respuesta Final:
"Bienvenido de vuelta. Con base en tu perfil de salud almacenado (Intolerancia a la lactosa), he seleccionado las siguientes opciones rápidas de la base de conocimientos RAG que no contienen ningún componente lácteo:

1. Crema de Zapallo con Leche de Coco (20 minutos)
2. Salteado de Pollo y Verduras al Wok (15 minutos)

¿Te gustaría consultar los sustitutos de algún ingrediente para estas opciones?"


```
## Ejemplo 4: Orquestación de Tareas Complejas Multi-Etapa (ReAct & Plan)

### Entrada del Usuario:
"Necesito una receta rápida de cena (menos de 30 min), que sea vegetariana, económica y que use champiñones que tengo en el refrigerador."

### TRAZA DE EJECUCIÓN DEL ORQUESTADOR (`agent.py`):

```

[FASE 1: COMPLIANCE DE ENTRADA]
└─ DomainValidator -> Evaluando tokens... [OK] -> Estado: Continuar.

[FASE 2: PLANIFICACIÓN COGNITIVA - IL2.3]
└─ PlanningAgent.create_plan() -> Generando grafo de resolución secuencial:
Step 1: Recuperar perfil histórico del usuario "usr_99".
Step 2: Consultar la base vectorial ChromaDB buscando coincidencias semánticas para "cena vegetariana champiñones".
Step 3: Evaluar determinísticamente la viabilidad de los ingredientes.
Step 4: Filtrar el set por restricciones de tiempo y presupuesto.
Step 5: Emitir juicio experto con justificación.

[FASE 3: HIDRATACIÓN DE CONTEXTO HÍBRIDO - IL2.2]
├─ persistent_db.get_user_preferences("usr_99") -> Inyecta: []
└─ persistent_db.get_recent_interactions("usr_99") -> Inyecta historial reciente de la sesión.

[FASE 4: EJECUCIÓN ADAPTATIVA DEL TOOLKIT - IL2.1]
├─ Ejecuta: COOKAI_TOOLKIT["buscar_recetas_rag"]("cena vegetariana champiñones")
│  └─ Retorna Chunks: [Receta 1: Risotto de Hongos (45 min) | Receta 2: Salteado de Champiñones y Tofu (15 min)].
├─ Ejecuta: COOKAI_TOOLKIT["analizar_coincidencia_ingredientes"](ingredientes_usuario=["champiñones"], texto_receta=...)
│  └─ Retorna: { "porcentaje_coincidencia": "100%", "viable": true }
└─ Procesamiento de Criterios: El agente descarta el 'Risotto' debido a que el paso del plan exige un tiempo menor a 30 minutos. Selecciona el 'Salteado de Tofu'.

[FASE 5: INFERENCIA Y PERSISTENCIA FINAL]
├─ LLM genera la respuesta estructurada final combinando las evidencias.
└─ persistent_db.save_interaction() -> Almacena la secuencia en la bitácora relacional.

RESPUESTA TRANSMITIDA AL CLIENTE:
"Analizando tus requerimientos de tiempo (<30 min), dieta vegetariana y el uso de champiñones, he elaborado un plan de preparación óptimo.

De las recetas validadas en nuestro RAG, la opción ideal es el Salteado de Champiñones y Tofu. De acuerdo con nuestra herramienta de cómputo, el plato es 100% viable con tus insumos actuales y requiere únicamente 15 minutos de cocción, cumpliendo con tus parámetros económicos.

¿Deseas activar la herramienta de escritura para guardar esta opción en tu recetario histórico?"

```

---

## 📊 Matriz de Madurez Tecnológica del Agente

| Dimensión Operacional | Comportamiento ANTES (Básico) | Pipeline CookAI ACTUAL (Avanzado) | Indicador Soportado |
|---------|-------|-------|---|
| **Frontera de Entrada** | Procesaba cualquier texto expuesto. | Validación estricta y lúdica de intenciones. | **IE6 / IE10** |
| **Ejecución de Código** | Invocaciones estáticas manuales. | Mapeo e invocación dinámica vía `COOKAI_TOOLKIT`. | **IL2.1** |
| **Estrategia Cognitiva** | Respuesta directa en un solo paso. | Descomposición estructurada (*Plan-and-Execute*). | **IL2.3** |
| **Arquitectura de Memoria** | Memoria volátil en RAM (Se borraba). | Capa Dual: Corto Plazo (Historial) y Largo Plazo (SQLite). | **IL2.2** |
| **Ingesta de Conocimiento** | Respuestas basadas en preentrenamiento. | Recuperación semántica exacta basada en ChromaDB. | **IL2.1 / IE3** |

```