import pandas as pd
from pathlib import Path

ARCHIVO = Path("importaciones_veeva") / "Example CV-FDF.xlsx"

COLUMNAS_REQUERIDAS = [
    "Name",
    "Status",
    "Document number",
    "Study",
    "Country",
    "Study site",
    "Clasification",
    "Created by",
]

ESTADOS_VALIDOS = {
    "APPROVED",
    "IN PROGRESS",
    "IN REVIEW",
    "QC REJECTED",
}


def importar_veeva(archivo):
    df = pd.read_excel(archivo, dtype=str).fillna("")

    # Limpiar espacios y preservar los identificadores como texto.
    df.columns = df.columns.str.strip()

    faltantes = [
        columna
        for columna in COLUMNAS_REQUERIDAS
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"Faltan estas columnas en el Excel: {faltantes}"
        )

    df = df[COLUMNAS_REQUERIDAS].copy()

    for columna in COLUMNAS_REQUERIDAS:
        df[columna] = df[columna].astype(str).str.strip()

    df["Status normalizado"] = (
        df["Status"].str.upper().str.strip()
    )

    df["Estado reconocido"] = df["Status normalizado"].isin(
        ESTADOS_VALIDOS
    )

    return df


if __name__ == "__main__":
    try:
        documentos = importar_veeva(ARCHIVO)

        print("\nIMPORTACIÓN DE PRUEBA EXITOSA")
        print(f"Documentos leídos: {len(documentos)}")

        print("\nColumnas reconocidas:")
        print(documentos.columns.tolist())

        print("\nEstados encontrados:")
        print(documentos["Status"].value_counts().to_string())

        print("\nEstados no reconocidos:")
        print(
            documentos.loc[
                ~documentos["Estado reconocido"], "Status"
            ].unique().tolist()
        )

        print("\nVista previa:")
        print(
            documentos[
                ["Name", "Status", "Study", "Country",
                 "Study site", "Clasification", "Created by"]
            ].to_string(index=False)
        )

    except Exception as error:
        print(f"\nERROR DE IMPORTACIÓN: {error}")
def documentos_que_requieren_accion_do(documentos):

    estados_que_requieren_accion = [
        "IN PROGRESS",
        "QC REJECTED",
    ]

    tareas_do = documentos[
        documentos["Status normalizado"].isin(
            estados_que_requieren_accion
        )
    ].copy()

    return tareas_do
def preparar_vista_previa(documentos):

    estados_accion_do = ["IN PROGRESS", "QC REJECTED"]
    estados_sin_accion = ["APPROVED", "IN REVIEW"]

    accion_do = documentos[
        documentos["Status normalizado"].isin(estados_accion_do)
    ].copy()

    sin_accion = documentos[
        documentos["Status normalizado"].isin(estados_sin_accion)
    ].copy()

    revision = documentos[
        ~documentos["Status normalizado"].isin(
            estados_accion_do + estados_sin_accion
        )
    ].copy()

    return {
        "accion_do": accion_do,
        "sin_accion": sin_accion,
        "revision": revision,
    }

def comparar_cv_veeva(persona, documentos_veeva):
    """
    Compare one investigator's CV against imported Veeva documents.
    Does not modify the Worklist or task statuses.
    """
    import re
    import unicodedata

    def normalizar(valor):
        texto = str(valor or "").strip().casefold()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        )
        texto = re.sub(r"\s+", " ", texto)
        return texto

    resultado = {
        "Veeva CV Check": "Unable to verify",
        "Veeva Document Status": "",
    }

    if documentos_veeva is None or documentos_veeva.empty:
        return resultado

    campos_persona = [
        "study", "country", "site", "person_name", "person_role"
    ]
    if any(campo not in persona.index for campo in campos_persona):
        return resultado

    estudio = normalizar(persona["study"])
    pais = normalizar(persona["country"])
    centro = normalizar(persona["site"])
    nombre = normalizar(persona["person_name"])
    rol = normalizar(persona["person_role"])

    if not all([estudio, pais, centro, nombre, rol]):
        return resultado

    documentos = documentos_veeva.copy()

    columnas_requeridas = [
        "Study", "Country", "Study site", "Name", "Clasification", "Status"
    ]
    if any(
        columna not in documentos.columns
        for columna in columnas_requeridas
    ):
        return resultado

    # Confirm study, country and site before checking the person.
    def normalizar_centro(valor):
        centro_normalizado = normalizar(valor)
        centro_normalizado = re.sub(
            r"^site\s*", "", centro_normalizado
        )
        return centro_normalizado.strip()

    coincidencias_contexto = documentos[
        documentos["Study"].map(normalizar).eq(estudio)
        & documentos["Country"].map(normalizar).eq(pais)
        & documentos["Study site"].map(normalizar_centro).eq(
            normalizar_centro(centro)
        )
    ].copy()

    if coincidencias_contexto.empty:
        return resultado

    clasificacion = coincidencias_contexto["Clasification"].map(normalizar)

    # First find CV records by person name, without filtering by role.
    es_cv = clasificacion.str.contains(
        r"\bcv\b|curriculum vitae", regex=True, na=False
    )
    cvs = coincidencias_contexto[es_cv].copy()

    nombres = cvs["Name"].map(normalizar)
    documentos_persona = cvs[
        nombres.str.contains(re.escape(nombre), regex=True, na=False)
    ].copy()

    if documentos_persona.empty:
        resultado["Veeva CV Check"] = (
            "CV not found in Veeva — Review required"
        )
        return resultado

    # Check whether the document classification agrees with the person's role.
    clasificaciones_persona = (
        documentos_persona["Clasification"].map(normalizar)
    )

    if "principal investigator" in rol or rol == "pi":
        rol_correcto = clasificaciones_persona.str.contains(
            r"\bpi\b|principal investigator", regex=True, na=False
        )
    elif (
        "sub-investigator" in rol
        or "sub investigator" in rol
        or rol == "sub-i"
    ):
        rol_correcto = clasificaciones_persona.str.contains(
            r"sub.?i|sub.?investigator", regex=True, na=False
        )
    else:
        return resultado

    if not rol_correcto.all():
        resultado["Veeva CV Check"] = (
            "Role/classification mismatch — Review required"
        )
        estados = (
            documentos_persona["Status"]
            .map(normalizar)
            .str.upper()
        )
        estados_validos = {
            "APPROVED", "IN PROGRESS", "IN REVIEW", "QC REJECTED"
        }
        estados = estados[estados.isin(estados_validos)]
        resultado["Veeva Document Status"] = ", ".join(
            sorted(estados.unique())
        )
        return resultado

    estados = (
        documentos_persona["Status"]
        .map(normalizar)
        .str.upper()
    )
    estados_validos = {
        "APPROVED", "IN PROGRESS", "IN REVIEW", "QC REJECTED"
    }
    estados = estados[estados.isin(estados_validos)]

    if estados.empty:
        return resultado

    estados_unicos = sorted(estados.unique())
    resultado["Veeva Document Status"] = ", ".join(estados_unicos)

    if len(estados_unicos) > 1:
        resultado["Veeva CV Check"] = (
            "Multiple CV records — Review required"
        )
    else:
        estado = estados_unicos[0]
        resultado["Veeva CV Check"] = {
            "APPROVED": "CV found — Approved",
            "IN REVIEW": "CV found — In Review",
            "IN PROGRESS": "CV found — Action required",
            "QC REJECTED": "CV found — Action required",
        }[estado]

    return resultado

def comparar_fdf_veeva(persona, documentos_veeva):
    """
    Compare one investigator's Financial Disclosure Form (FDF)
    against imported Veeva documents.
    Does not modify the Worklist or task statuses.
    """
    import re
    import unicodedata

    def normalizar(valor):
        texto = str(valor or "").strip().casefold()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        )
        return re.sub(r"\s+", " ", texto)

    resultado = {
        "Veeva FDF Check": "Unable to verify",
        "Veeva FDF Status": "",
    }

    if documentos_veeva is None or documentos_veeva.empty:
        return resultado

    campos_persona = [
        "study", "country", "site", "person_name", "person_role"
    ]
    if any(campo not in persona.index for campo in campos_persona):
        return resultado

    estudio = normalizar(persona["study"])
    pais = normalizar(persona["country"])
    centro = normalizar(persona["site"])
    nombre = normalizar(persona["person_name"])
    rol = normalizar(persona["person_role"])

    if not all([estudio, pais, centro, nombre, rol]):
        return resultado

    columnas = [
        "Study", "Country", "Study site", "Name",
        "Clasification", "Status"
    ]
    if any(columna not in documentos_veeva.columns for columna in columnas):
        return resultado

    def normalizar_centro(valor):
        return re.sub(
            r"^site\s*", "", normalizar(valor)
        ).strip()

    documentos = documentos_veeva.copy()

    contexto = documentos[
        documentos["Study"].map(normalizar).eq(estudio)
        & documentos["Country"].map(normalizar).eq(pais)
        & documentos["Study site"].map(normalizar_centro).eq(
            normalizar_centro(centro)
        )
    ].copy()

    if contexto.empty:
        return resultado

    clasificacion = contexto["Clasification"].map(normalizar)

    es_fdf = clasificacion.str.contains(
        r"\bfdf\b|financial disclosure",
        regex=True,
        na=False
    )
    fdfs = contexto[es_fdf].copy()

    if fdfs.empty:
        resultado["Veeva FDF Check"] = (
            "FDF not found in Veeva — Review required"
        )
        return resultado

    clasificaciones = fdfs["Clasification"].map(normalizar)

    if "principal investigator" in rol or rol == "pi":
        rol_correcto = clasificaciones.str.contains(
            r"\bpi\b|principal investigator",
            regex=True,
            na=False
        )
    elif (
        "sub-investigator" in rol
        or "sub investigator" in rol
        or rol == "sub-i"
    ):
        rol_correcto = clasificaciones.str.contains(
            r"sub.?i|sub.?investigator",
            regex=True,
            na=False
        )
    else:
        return resultado

    nombres = fdfs["Name"].map(normalizar)
    coincidencias = fdfs[
        nombres.str.contains(re.escape(nombre), regex=True, na=False)
    ].copy()

    if coincidencias.empty:
        resultado["Veeva FDF Check"] = (
            "FDF not found for this person — Review required"
        )
        return resultado

    clasificaciones_persona = coincidencias["Clasification"].map(normalizar)

    if "principal investigator" in rol or rol == "pi":
        rol_persona_correcto = clasificaciones_persona.str.contains(
            r"\bpi\b|principal investigator",
            regex=True,
            na=False
        )
    else:
        rol_persona_correcto = clasificaciones_persona.str.contains(
            r"sub.?i|sub.?investigator",
            regex=True,
            na=False
        )

    if not rol_persona_correcto.all():
        resultado["Veeva FDF Check"] = (
            "Role/classification mismatch — Review required"
        )
    else:
        resultado["Veeva FDF Check"] = "FDF found — Review status"

    estados = (
        coincidencias["Status"]
        .map(normalizar)
        .str.upper()
    )
    estados_validos = {
        "APPROVED", "IN PROGRESS", "IN REVIEW", "QC REJECTED"
    }
    estados = estados[estados.isin(estados_validos)]

    resultado["Veeva FDF Status"] = ", ".join(
        sorted(estados.unique())
    )

    if rol_correcto.empty:
        resultado["Veeva FDF Check"] = (
            "Role/classification mismatch — Review required"
        )

    if estados.empty:
        resultado["Veeva FDF Check"] = (
            "FDF found — Status requires review"
        )
    elif len(estados.unique()) > 1:
        resultado["Veeva FDF Check"] = (
            "Multiple FDF records — Review required"
        )
    elif rol_persona_correcto.all():
        estado = estados.iloc[0]
        resultado["Veeva FDF Check"] = {
            "APPROVED": "FDF found — Approved",
            "IN REVIEW": "FDF found — In Review",
            "IN PROGRESS": "FDF found — Action required",
            "QC REJECTED": "FDF found — Action required",
        }[estado]

    return resultado