# TMF Requirements Engine (prototipo)

Prototipo en Python (Streamlit) para verificar qué documentos requiere cada centro de un estudio clínico en el Trial Master File (TMF), detectar los que faltan y organizar el seguimiento.

> **Todos los datos son ficticios (sintéticos).** Ningún estudio, centro, persona o documento es real.
> Es un prototipo de prueba, desarrollado con **asistencia de IA**, y no está pensado para uso productivo.

## Qué hace

| Pantalla | Función |
|---|---|
| **Site Requirements** | Motor de reglas: calcula los documentos requeridos de un centro según estudio, país, centro, estado del centro y eventos (por ejemplo, cambio de investigador), y marca cada uno como `PRESENT` o `MISSING`. |
| **Site Dashboard** | Resumen general con filtros por estudio, país, estado y evento. |
| **Worklist** | Lista de tareas generada a partir de los documentos faltantes, con estados editables (`OPEN`, `IN PROGRESS`, `COMPLETED`) que se guardan en un CSV. |
| **Personnel Requirements** | Seguimiento del CV de cada integrante del equipo del centro, con carga de archivos y registro del estado. |
| **FDA 1572 Review** | Carga un Formulario FDA 1572 en PDF, extrae el texto y lo compara con los investigadores registrados. |
| **Importar Veeva** | Importa un Excel con formato de exportación tipo Veeva, valida columnas y estados, y lo compara con los CVs y formularios de divulgación financiera (FDF) del personal. |

## Cómo ejecutarlo

Requiere Python 3.10 o superior.

```bash
# 1. Crear y activar un entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar la aplicación
streamlit run app.py
```

Se abre en `http://localhost:8501`.

## Estructura

```
app.py                      Aplicación principal (Streamlit)
importar_veeva.py           Lectura, validación y comparación del Excel tipo Veeva
rules.csv                   Reglas de documentos requeridos
sites.csv                   Centros, estados y eventos (datos ficticios)
site_documents.csv          Documentos presentes por centro (ficticios)
sub_investigators.csv       Personal de cada centro (ficticio)
personnel_documents.csv     Documentos cargados por persona
worklist_status.csv         Estado de las tareas de la Worklist
importaciones_veeva/        Excel de ejemplo con datos ficticios
```

## Límites actuales

- Los datos se guardan en archivos CSV: no hay base de datos, usuarios ni permisos.
- No hay pruebas automáticas.
- La lógica de la comparación de documentos es una primera versión y puede dejar casos sin cubrir.
- Todo el código está en un solo archivo (`app.py`), que convendría dividir en módulos.

## Próximos pasos posibles

- Pruebas automáticas de las reglas y de las comparaciones.
- Aprobación humana explícita antes de marcar documentos como completos.
- Registro de cambios (quién modificó qué y cuándo).
- Separar el código en módulos.

---

## English summary

Prototype built with Python and Streamlit to check which documents each clinical-trial site requires in the Trial Master File (TMF), flag missing ones and track follow-up: a rules engine, a site dashboard, a task worklist, personnel CV tracking, FDA Form 1572 review and import of a Veeva-style Excel export with validations.

**All data is synthetic.** This is a test prototype developed with AI assistance; it is not intended for production use. Run it with `pip install -r requirements.txt` and `streamlit run app.py`.
