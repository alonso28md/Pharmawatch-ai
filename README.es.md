<div align="center">

# 🩺 PharmaWatch AI

### Apoyo a la decisión en tecnovigilancia de productos sanitarios (Reglamento (UE) 2017/745)

*Biomedical Engineering Portfolio · Alonso Martín Díez · Universidad Europea de Madrid · 2026*

**[English README](README.md)** — documentación completa en inglés.

</div>

---

> [!IMPORTANT]
> **Prototipo de apoyo a la decisión, no es un producto sanitario.** Toda salida requiere la
> revisión de un profesional de vigilancia. No introduzcas datos identificativos de pacientes:
> las descripciones se envían a la API de un modelo de terceros. Las etiquetas de evaluación
> son borradores escritos por IA pendientes de validación experta y los umbrales son propuestos.

## Qué hace

- **Consulta normativa:** responde en español o inglés a partir del texto indexado de los
  artículos de vigilancia del MDR, el anexo VIII y la guía de la AEMPS, citando los fragmentos
  exactos. Si el corpus no responde, se abstiene.
- **Triaje de incidentes:** un agente LangGraph extrae los hechos, determina la clase del
  producto y la categoría del incidente y propone la notificación. **Los plazos y destinatarios
  salen de una tabla de reglas, no del modelo.** Si faltan datos o hay duda entre categorías,
  retiene la decisión y la deriva a una persona (escalado bloqueante).

**Alcance:** tecnovigilancia de productos sanitarios según el MDR (sobre todo las obligaciones
del fabricante del artículo 87), con la guía de la AEMPS como contexto nacional. No cubre
medicamentos (farmacovigilancia) ni productos para diagnóstico in vitro.

## Resultados de evaluación

Partición `test` del dataset v2: 84 casos × 3 repeticiones, modelo `claude-sonnet-5-5`, commit
`938b456`, 27-10-2026. Ningún error llegó al usuario sin escalado bloqueante y todos los casos
que necesitaban a una persona se escalaron; el coste es el sobre-escalado (33,3 %), que baja la
exactitud de plazo y destinatarios a 56,8 % (100 % en los casos en que el sistema sí decidió).
Tablas completas y limitaciones: [docs/evaluation.md](docs/evaluation.md).

## Inicio rápido

```bash
cd frontend
npm ci
npm run dev:mock        # interfaz con datos de ejemplo, sin backend ni coste
```

Instalación completa, Docker, variables y pruebas: [README.md](README.md#-quick-start) y
[docs/development.md](docs/development.md).

## Licencia

MIT — ver [LICENSE](LICENSE).
