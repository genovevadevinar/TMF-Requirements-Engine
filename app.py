import streamlit as st
import pandas as pd
import os

st.set_page_config(
    page_title="TMF Requirements Engine",
    layout="wide"
)

st.title("TMF Requirements Engine")
st.caption("Prototype v1.8")


# ============================================================
# CARGAR ARCHIVOS
# ============================================================

rules = pd.read_csv("rules.csv")
sites = pd.read_csv("sites.csv")
site_documents = pd.read_csv("site_documents.csv")

sites["event"] = sites["event"].fillna("None")
sites["site_status"] = sites["site_status"].fillna("None")

rules = rules.fillna("ALL")
site_documents = site_documents.fillna("")


# ============================================================
# CALCULAR DOCUMENTOS REQUERIDOS
# ============================================================

def calculate_site(study, country, site, site_status, event):

    site_rules = rules[
        ((rules["study"] == "ALL") | (rules["study"] == study)) &
        ((rules["country"] == "ALL") | (rules["country"] == country)) &
        ((rules["site"] == "ALL") | (rules["site"] == site)) &
        ((rules["site_status"] == "ALL") | (rules["site_status"] == site_status)) &
        ((rules["event"] == "ALL") | (rules["event"] == event))
    ]

    results = []

    for _, rule in site_rules.iterrows():

        document = rule["document"]
        reason = rule["reason"]

        matching_documents = site_documents[
            (site_documents["study"] == study) &
            (site_documents["country"] == country) &
            (site_documents["site"] == site) &
            (site_documents["document"] == document)
        ]

        if len(matching_documents) > 0 and matching_documents["status"].astype(str).str.strip().str.lower().eq("present").any():
            status = "PRESENT"
        else:
            status = "MISSING"

        results.append({
            "Documento": document,
            "Estado": status,
            "Motivo": reason
        })

    # Eliminar documentos duplicados
    unique_results = {}

    for result in results:

        document = result["Documento"]

        if document not in unique_results:
            unique_results[document] = result

        else:
            existing_reason = unique_results[document]["Motivo"]

            if result["Motivo"] not in existing_reason:
                unique_results[document]["Motivo"] = (
                    existing_reason + " | " + result["Motivo"]
                )

    return list(unique_results.values())


# ============================================================
# WORKLIST
# ============================================================


def build_worklist():

    worklist_rows = []

    # Tareas documentales por centro
    for _, site_row in sites.iterrows():

        study = site_row["study"]
        country = site_row["country"]
        site = site_row["site"]
        site_status = site_row["site_status"]
        event = site_row["event"]

        results = calculate_site(
            study,
            country,
            site,
            site_status,
            event
        )

        for result in results:

            if result["Estado"] == "MISSING":

                task_id = (
                    str(study) + "|" +
                    str(country) + "|" +
                    str(site) + "|" +
                    str(event) + "|" +
                    str(result["Documento"])
                )

                worklist_rows.append({
                    "Task ID": task_id,
                    "Study": study,
                    "Country": country,
                    "Site": site,
                    "Site Status": site_status,
                    "Event": event,
                    "Documento": result["Documento"],
                    "Motivo": result["Motivo"]
                })

    # Tareas individuales de CV del personal
    personnel_docs = pd.read_csv(
        "personnel_documents.csv"
    ).fillna("")

    personnel = pd.read_csv(
        "sub_investigators.csv"
    ).fillna("")

    for _, person in personnel.iterrows():

        study = person["study"]
        country = person["country"]
        site = person["site"]
        person_id = person["person_id"]
        person_name = person["person_name"]
        person_role = person["person_role"]

        if person_role not in ["Sub-Investigator", "Principal Investigator"]:
            continue

        matching_docs = personnel_docs[
            (personnel_docs["study"] == study) &
            (personnel_docs["country"] == country) &
            (personnel_docs["site"] == site) &
            (personnel_docs["person_id"] == person_id) &
            (personnel_docs["document"] == "CV")
        ]

        statuses = matching_docs["status"].astype(str).str.upper().str.strip()

        if (statuses == "PRESENT").any():
            continue

        if (statuses == "PENDING REVIEW").any():
            reason = (
                "CV de " + str(person_name) +
                " (" + str(person_id) +
                ") pendiente de revisión"
            )

        else:
            reason = (
                "CV faltante de " + str(person_name) +
                " (" + str(person_id) + ")"
            )

        person_site = sites[
            (sites["study"] == study) &
            (sites["country"] == country) &
            (sites["site"] == site)
        ]

        if person_site.empty:
            person_site_status = "Unknown"
            person_event = "None"
        else:
            person_site_status = person_site.iloc[0]["site_status"]
            person_event = person_site.iloc[0]["event"]

        task_id = (
            str(study) + "|" +
            str(country) + "|" +
            str(site) + "|PERSON|" +
            str(person_id) + "|CV"
        )

        worklist_rows.append({
            "Task ID": task_id,
            "Study": study,
            "Country": country,
            "Site": site,
            "Site Status": person_site_status,
            "Event": person_event,
            "Documento": "CV - " + str(person_id),
            "Motivo": reason
        })

    return pd.DataFrame(worklist_rows)



# ============================================================
# CARGAR ESTADOS DE WORKLIST
# ============================================================

STATUS_FILE = "worklist_status.csv"


def load_worklist_status():

    if os.path.exists(STATUS_FILE):

        status_df = pd.read_csv(STATUS_FILE)

        if "Task ID" in status_df.columns and "Estado Tarea" in status_df.columns:
            return status_df

    return pd.DataFrame(columns=["Task ID", "Estado Tarea"])


def save_worklist_status(status_df):

    status_df.to_csv(
        STATUS_FILE,
        index=False
    )


# ============================================================
# CONSTRUIR WORKLIST
# ============================================================

worklist = build_worklist()

status_df = load_worklist_status()


# Crear estados OPEN para tareas nuevas

if len(worklist) > 0:

    existing_ids = set(status_df["Task ID"].astype(str))

    new_rows = []

    for task_id in worklist["Task ID"]:

        if str(task_id) not in existing_ids:

            new_rows.append({
                "Task ID": task_id,
                "Estado Tarea": "OPEN"
            })

    if len(new_rows) > 0:

        new_status_df = pd.DataFrame(new_rows)

        status_df = pd.concat(
            [status_df, new_status_df],
            ignore_index=True
        )

        save_worklist_status(status_df)


# Unir estados con Worklist

if len(worklist) > 0:

    worklist = worklist.merge(
        status_df,
        on="Task ID",
        how="left"
    )

    worklist["Estado Tarea"] = worklist["Estado Tarea"].fillna("OPEN")


# ============================================================
# NAVEGACION
# ============================================================

page = st.sidebar.radio(
    "Navegacion",
    [
        "Site Requirements",
        "Site Dashboard",
        "Worklist",
        "Personnel Requirements",
        "FDA 1572 Review",
        "Importar Veeva",
    ]
)


# ============================================================
# SITE REQUIREMENTS
# ============================================================

if page == "Site Requirements":

    st.header("Site Requirements")

    # ----------------------------
    # SELECTORES
    # ----------------------------

    site_options = []

    for _, row in sites.iterrows():

        label = (
            str(row["study"]) +
            " / " +
            str(row["country"]) +
            " / " +
            str(row["site"])
        )

        site_options.append(label)

    selected_site = st.selectbox(
        "Seleccionar Site",
        site_options
    )

    selected_index = site_options.index(selected_site)

    selected_row = sites.iloc[selected_index]

    study = selected_row["study"]
    country = selected_row["country"]
    site = selected_row["site"]
    site_status = selected_row["site_status"]
    event = selected_row["event"]

    st.write("Study:", study)
    st.write("Country:", country)
    st.write("Site:", site)
    st.write("Site Status:", site_status)
    st.write("Event:", event)

    # ----------------------------
    # CALCULAR RESULTADOS
    # ----------------------------

    results = calculate_site(
        study,
        country,
        site,
        site_status,
        event
    )

    # ----------------------------
    # METRICAS
    # ----------------------------

    total_required = len(results)

    total_present = len([
        r for r in results
        if r["Estado"] == "PRESENT"
    ])

    total_missing = len([
        r for r in results
        if r["Estado"] == "MISSING"
    ])

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Requeridos",
        total_required
    )

    col2.metric(
        "Presentes",
        total_present
    )

    col3.metric(
        "Faltantes",
        total_missing
    )

    # ----------------------------
    # FILTRO
    # ----------------------------

    filter_status = st.radio(
        "Mostrar",
        [
            "Todos",
            "Solo faltantes"
        ],
        horizontal=True
    )

    # ----------------------------
    # RESULTADOS
    # ----------------------------

    st.subheader("Documentos requeridos")

    for result in results:

        if (
            filter_status == "Solo faltantes"
            and result["Estado"] != "MISSING"
        ):
            continue

        if result["Estado"] == "PRESENT":

            st.success(
                "PRESENT - " +
                result["Documento"]
            )

        else:

            st.error(
                "MISSING - " +
                result["Documento"]
            )

        st.write(
            "Motivo: " +
            result["Motivo"]
        )


# ============================================================
# SITE DASHBOARD
# ============================================================

elif page == "Site Dashboard":

    st.header("Site Dashboard")

    # ----------------------------
    # FILTROS
    # ----------------------------

    filter_study = st.selectbox(
        "Study",
        ["Todos"] +
        sorted(
            sites["study"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
    )

    filter_country = st.selectbox(
        "Country",
        ["Todos"] +
        sorted(
            sites["country"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
    )

    filter_site_status = st.selectbox(
        "Site Status",
        ["Todos"] +
        sorted(
            sites["site_status"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
    )

    filter_event = st.selectbox(
        "Event",
        ["Todos"] +
        sorted(
            sites["event"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
    )

    filter_overall_status = st.selectbox(
        "Estado General",
        [
            "Todos",
            "OK",
            "PENDIENTE"
        ]
    )

    # ----------------------------
    # CONSTRUIR TABLA
    # ----------------------------

    dashboard_rows = []

    for _, site_row in sites.iterrows():

        study = site_row["study"]
        country = site_row["country"]
        site = site_row["site"]
        site_status = site_row["site_status"]
        event = site_row["event"]

        if (
            filter_study != "Todos"
            and str(study) != str(filter_study)
        ):
            continue

        if (
            filter_country != "Todos"
            and str(country) != str(filter_country)
        ):
            continue

        if (
            filter_site_status != "Todos"
            and str(site_status) != str(filter_site_status)
        ):
            continue

        if (
            filter_event != "Todos"
            and str(event) != str(filter_event)
        ):
            continue

        results = calculate_site(
            study,
            country,
            site,
            site_status,
            event
        )

        total_required = len(results)

        total_present = len([
            r for r in results
            if r["Estado"] == "PRESENT"
        ])

        total_missing = len([
            r for r in results
            if r["Estado"] == "MISSING"
        ])

        if total_missing == 0:
            overall_status = "OK"
        else:
            overall_status = "PENDIENTE"

        missing_documents = [
            r["Documento"]
            for r in results
            if r["Estado"] == "MISSING"
        ]

        if len(missing_documents) == 0:
            missing_text = "Ninguno"
        else:
            missing_text = ", ".join(missing_documents)

        if (
            filter_overall_status != "Todos"
            and overall_status != filter_overall_status
        ):
            continue

        dashboard_rows.append({
            "Study": study,
            "Country": country,
            "Site": site,
            "Site Status": site_status,
            "Event": event,
            "Requeridos": total_required,
            "Presentes": total_present,
            "Faltantes": total_missing,
            "Estado General": overall_status,
            "Documentos Faltantes": missing_text
        })

    dashboard_df = pd.DataFrame(dashboard_rows)

    # ----------------------------
    # TABLA
    # ----------------------------

    if len(dashboard_df) == 0:

        st.info(
            "No hay sitios que coincidan con los filtros."
        )

    else:

        st.dataframe(
            dashboard_df,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------
        # RESUMEN GENERAL
        # ----------------------------

        st.subheader("Resumen general")

        total_sites = len(dashboard_df)

        sites_ok = len(
            dashboard_df[
                dashboard_df["Estado General"] == "OK"
            ]
        )

        sites_pending = len(
            dashboard_df[
                dashboard_df["Estado General"] == "PENDIENTE"
            ]
        )

        total_documents = int(
            dashboard_df["Requeridos"].sum()
        )

        total_present = int(
            dashboard_df["Presentes"].sum()
        )

        total_missing = int(
            dashboard_df["Faltantes"].sum()
        )

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        col1.metric(
            "Sites",
            total_sites
        )

        col2.metric(
            "Sites OK",
            sites_ok
        )

        col3.metric(
            "Sites Pendientes",
            sites_pending
        )

        col4.metric(
            "Documentos Requeridos",
            total_documents
        )

        col5.metric(
            "Documentos Presentes",
            total_present
        )

        col6.metric(
            "Documentos Faltantes",
            total_missing
        )


# ============================================================
# WORKLIST
# ============================================================

elif page == "Worklist":

    st.header("Worklist")

    if len(worklist) == 0:

        st.success(
            "No hay documentos pendientes."
        )

    else:

        # ----------------------------
        # METRICAS
        # ----------------------------

        total_tasks = len(worklist)

        total_sites_pending = worklist[
            ["Study", "Country", "Site"]
        ].drop_duplicates().shape[0]

        open_tasks = len(
            worklist[
                worklist["Estado Tarea"] == "OPEN"
            ]
        )

        in_progress_tasks = len(
            worklist[
                worklist["Estado Tarea"] == "IN PROGRESS"
            ]
        )

        completed_tasks = len(
            worklist[
                worklist["Estado Tarea"] == "COMPLETED"
            ]
        )

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric(
            "Documentos pendientes",
            total_tasks
        )

        col2.metric(
            "Sites con pendientes",
            total_sites_pending
        )

        col3.metric(
            "OPEN",
            open_tasks
        )

        col4.metric(
            "IN PROGRESS",
            in_progress_tasks
        )

        col5.metric(
            "COMPLETED",
            completed_tasks
        )

        # ----------------------------
        # FILTROS
        # ----------------------------

        st.subheader("Filtros")

        col1, col2, col3 = st.columns(3)

        with col1:

            worklist_study = st.selectbox(
                "Study",
                ["Todos"] +
                sorted(
                    worklist["Study"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
            )

        with col2:

            worklist_country = st.selectbox(
                "Country",
                ["Todos"] +
                sorted(
                    worklist["Country"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
            )

        with col3:

            worklist_status = st.selectbox(
                "Estado de tarea",
                [
                    "Todos",
                    "OPEN",
                    "IN PROGRESS",
                    "COMPLETED"
                ]
            )

        filtered_worklist = worklist.copy()

        if worklist_study != "Todos":

            filtered_worklist = filtered_worklist[
                filtered_worklist["Study"].astype(str)
                == str(worklist_study)
            ]

        if worklist_country != "Todos":

            filtered_worklist = filtered_worklist[
                filtered_worklist["Country"].astype(str)
                == str(worklist_country)
            ]

        if worklist_status != "Todos":

            filtered_worklist = filtered_worklist[
                filtered_worklist["Estado Tarea"].astype(str)
                == str(worklist_status)
            ]

        # ----------------------------
        # EDITOR DE TAREAS
        # ----------------------------

        st.subheader("Tareas")

        if len(filtered_worklist) == 0:

            st.info(
                "No hay tareas que coincidan con los filtros."
            )

        else:

            editable_columns = [
                "Task ID",
                "Study",
                "Country",
                "Site",
                "Site Status",
                "Event",
                "Documento",
                "Motivo",
                "Estado Tarea"
            ]

            editor_df = filtered_worklist[
                editable_columns
            ].copy()

            edited_df = st.data_editor(
                editor_df,
                column_config={
                    "Estado Tarea": st.column_config.SelectboxColumn(
                        "Estado Tarea",
                        options=[
                            "OPEN",
                            "IN PROGRESS",
                            "COMPLETED"
                        ],
                        required=True
                    )
                },
                disabled=[
                    "Task ID",
                    "Study",
                    "Country",
                    "Site",
                    "Site Status",
                    "Event",
                    "Documento",
                    "Motivo"
                ],
                hide_index=True,
                use_container_width=True
            )

            # ----------------------------
            # GUARDAR CAMBIOS
            # ----------------------------

            if st.button("Guardar cambios"):

                full_status_df = load_worklist_status()

                for _, edited_row in edited_df.iterrows():

                    task_id = edited_row["Task ID"]
                    new_status = edited_row["Estado Tarea"]

                    full_status_df.loc[
                        full_status_df["Task ID"].astype(str)
                        == str(task_id),
                        "Estado Tarea"
                    ] = new_status

                save_worklist_status(
                    full_status_df
                )

                st.success(
                    "Cambios guardados correctamente."
                )

                st.rerun()




elif page == "Personnel Requirements":

    st.header("Personnel Requirements")
    st.write(
        "Control individual de documentos requeridos "
        "y documentos registrados por persona."
    )

    personnel_file = "sub_investigators.csv"
    documents_file = "personnel_documents.csv"

    if not os.path.exists(personnel_file):
        st.error("No se encontró el archivo de personal.")

    elif not os.path.exists(documents_file):
        st.error("No se encontró personnel_documents.csv.")

    else:
        personnel = pd.read_csv(personnel_file).fillna("")
        documents = pd.read_csv(documents_file).fillna("")

        required_personnel_columns = [
            "study", "country", "site",
            "person_id", "person_role", "cv_status"
        ]
        required_document_columns = [
            "study", "country", "site",
            "person_id", "document", "status"
        ]

        if not all(c in personnel.columns for c in required_personnel_columns):
            st.error("El archivo de personal tiene columnas incorrectas.")

        elif not all(c in documents.columns for c in required_document_columns):
            st.error("El archivo de documentos tiene columnas incorrectas.")

        else:
            person_options = {}
            for _, person in personnel.iterrows():
             
                person_name = str(person.get("person_name", "")).strip()

                if person_name:
                    label = (
                        f'{person_name} ({person["person_id"]}) — '
                        f'{person["person_role"]} — '
                        f'{person["site"]} — {person["study"]}'
                    )
                else:
                    label = (
                        f'{person["person_id"]} — '
                        f'{person["person_role"]} — '
                        f'{person["site"]} — {person["study"]}'
                    )

                person_options[label] = person["person_id"]

            selected_label = st.selectbox(
                "Seleccionar persona",
                list(person_options.keys())
            )
            selected_person_id = person_options[selected_label]

            selected_person = personnel[
                personnel["person_id"].astype(str)
                == str(selected_person_id)
            ].iloc[0]

            st.subheader("Requisito individual")
            st.write("Study:", selected_person["study"])
            st.write("Country:", selected_person["country"])
            st.write("Site:", selected_person["site"])
            st.write("Persona:", selected_person["person_id"])
            st.write("Rol:", selected_person["person_role"])
            st.write("Documento requerido: CV")

           
            st.subheader("Registrar documento")

            with st.form("document_entry_form"):
                document_type = st.selectbox(
                    "Tipo de documento",
                    ["CV", "Training Certificate", "Other"]
                )

                uploaded_file = st.file_uploader(
                    "Adjuntar archivo",
                    type=["pdf", "doc", "docx", "jpg", "jpeg", "png"]
                )

                submitted = st.form_submit_button("Guardar documento")

            if submitted:
                if uploaded_file is None:
                    st.error("Primero tenés que adjuntar un archivo.")
                else:
                    import os
                    import re
                    import uuid

                    upload_folder = "uploaded_documents"
                    os.makedirs(upload_folder, exist_ok=True)

                    safe_person_id = re.sub(
                        r"[^A-Za-z0-9_-]", "_",
                        str(selected_person["person_id"])
                    )

                    safe_filename = re.sub(
                        r"[^A-Za-z0-9._-]", "_",
                        uploaded_file.name
                    )

                    stored_filename = (
                        f'{safe_person_id}_{uuid.uuid4().hex[:8]}_'
                        f'{safe_filename}'
                    )
                    file_path = os.path.join(
                        upload_folder, stored_filename
                    )

                    with open(file_path, "wb") as file:
                        file.write(uploaded_file.getbuffer())

                    
                    
                    new_record = {
                        "study": selected_person["study"],
                        "country": selected_person["country"],
                        "site": selected_person["site"],
                        "person_id": selected_person["person_id"],
                        "document": document_type,
                        "status": "PENDING REVIEW",
                        "filename": stored_filename
                    }

                    same_document = (
                        (documents["study"].astype(str) == str(selected_person["study"])) &
                        (documents["country"].astype(str) == str(selected_person["country"])) &
                        (documents["site"].astype(str) == str(selected_person["site"])) &
                        (documents["person_id"].astype(str) == str(selected_person["person_id"])) &
                        (documents["document"].astype(str) == str(document_type))
                    )

                    documents = documents[~same_document].copy()

                    documents = pd.concat(
                        [documents, pd.DataFrame([new_record])],
                        ignore_index=True
                    )

                    documents.to_csv(documents_file, index=False)


                    st.success(
                        "Archivo guardado. El documento quedó pendiente de revisión."
                    )
                    st.rerun()

            st.subheader("Documentos registrados para esta persona")

            person_docs = documents[
                (documents["study"].astype(str) == str(selected_person["study"])) &
                (documents["country"].astype(str) == str(selected_person["country"])) &
                (documents["site"].astype(str) == str(selected_person["site"])) &
                (documents["person_id"].astype(str) == str(selected_person["person_id"]))
            ]

        

            if len(person_docs) > 0:
                st.dataframe(
                    person_docs[["person_id", "document", "status"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No hay documentos registrados para esta persona.")

          
            st.subheader("Resumen de personas")
            summary_rows = []

            for _, person in personnel.iterrows():
                person_docs_for_summary = documents[
                    (documents["study"].astype(str) == str(person["study"])) &
                    (documents["country"].astype(str) == str(person["country"])) &
                    (documents["site"].astype(str) == str(person["site"])) &
                    (documents["person_id"].astype(str) == str(person["person_id"])) &
                    (documents["document"].astype(str).str.strip().str.upper() == "CV")
                ]

                statuses = (
                    person_docs_for_summary["status"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )

                if (statuses == "PRESENT").any():
                    cv_status = "PRESENT"
                elif (statuses == "PENDING REVIEW").any():
                    cv_status = "PENDING REVIEW"
                else:
                    cv_status = "MISSING"

                summary_rows.append({
                    "study": person["study"],
                    "country": person["country"],
                    "site": person["site"],
                    "person_id": person["person_id"],
                    "person_role": person["person_role"],
                    "CV registrado": cv_status
                })

            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True
            )

elif page == "FDA 1572 Review":
    st.header("FDA Form 1572 Review")

    
    
    if "fda_1572_pdf_bytes" not in st.session_state:
        st.session_state["fda_1572_pdf_bytes"] = None
        st.session_state["fda_1572_pdf_name"] = None

    uploaded_pdf = st.file_uploader(
        "Cargar formulario FDA 1572 (PDF)",
        type=["pdf"],
        key="fda_1572_pdf"
    )

    if uploaded_pdf is not None:
        st.session_state["fda_1572_pdf_bytes"] = uploaded_pdf.getvalue()
        st.session_state["fda_1572_pdf_name"] = uploaded_pdf.name

    pdf_bytes = st.session_state["fda_1572_pdf_bytes"]
    pdf_name = st.session_state["fda_1572_pdf_name"]



   
    if pdf_bytes is not None:
        st.success(f"PDF cargado: {pdf_name}")

        try:
            import pymupdf

            pdf_document = pymupdf.open(
                stream=pdf_bytes,
                filetype="pdf"
            )

            extracted_text = "\n".join(
                page.get_text() for page in pdf_document
            )

            st.subheader("Texto extraído del formulario")
            st.text_area(
                "Contenido del PDF",
                extracted_text,
                height=300
            )

            pdf_document.close()
            st.subheader("Comparación de investigadores")

            import pandas as pd
            import re

           

            # Normalizar el texto extraído del PDF
            texto_normalizado = re.sub(
                r"\s+",
                " ",
                extracted_text
            ).casefold()

            # Leer los investigadores registrados
            investigadores = pd.read_csv("sub_investigators.csv")

            # Extraer los subinvestigadores del campo específico del FDA 1572
            nombres_pdf = []

            documento_pdf = pymupdf.open(
                stream=pdf_bytes,
                filetype="pdf"
            )
            nombre_pi_pdf = ""


            for pagina in documento_pdf:
                for campo in pagina.widgets() or []:
                    if campo.field_name == "db_invest_name":
                        nombre_pi_pdf = (campo.field_value or "").strip()
                    if campo.field_name == "db_sub_inv_names":
                        valor = campo.field_value or ""
                        nombres_pdf = [
                            nombre.strip()
                            for nombre in valor.splitlines()
                            if nombre.strip()
                        ]
                        break
                if nombres_pdf:
                    break
            documento_pdf.close()
            
            # Leer los investigadores registrados
            

            resultados = []

            for _, persona in investigadores.iterrows():
                nombre = str(persona["person_name"]).strip()
                rol = str(persona["person_role"]).strip()

                if rol == "Principal Investigator":
                    if nombre_pi_pdf and nombre.casefold() == nombre_pi_pdf.casefold():
                        estado = "Encontrado en el FDA 1572"
                    else:
                        estado = "No identificado en el FDA 1572"
                elif nombre.casefold() in [
                    n.casefold() for n in nombres_pdf
                ]:
                    estado = "Encontrado en el FDA 1572"
                else:
                    estado = "No identificado en el FDA 1572"
                resultados.append({
                    "Nombre": nombre,
                    "Rol": rol,
                    "Resultado": estado,
                })

            
            tabla_resultados = pd.DataFrame(resultados)

            investigadores["person_name"] = investigadores[
                "person_name"
            ].astype(str).str.strip()

            estados_cv = investigadores.set_index(
                "person_name"
            )["cv_status"].to_dict()

            tabla_resultados["Estado del CV"] = tabla_resultados[
                "Nombre"
            ].map(estados_cv)

            

            tabla_resultados["Name check"] = tabla_resultados[
                "Resultado"
            ].replace({
                "Encontrado en el FDA 1572": "Match",
                "No identificado en el FDA 1572": "Review discrepancy"
            })

            tabla_resultados["Acción recomendada"] = tabla_resultados[
                "Name check"
            ].map({
                "Match": "No name discrepancy detected",
                "Review discrepancy": (
                    "Confirm whether the investigator should be listed on the form "
                    "and whether the site record is up to date"
                )
            }).fillna("")

            condicion_cv_faltante = (
                (tabla_resultados["Name check"] == "Match")
                & (tabla_resultados["Estado del CV"] == "Missing")
            )

            tabla_resultados.loc[
                condicion_cv_faltante,
                "Acción recomendada"
            ] = "Local CV record missing; verify against Veeva"

            # Compare against the Veeva Excel currently held in session state.
            from importar_veeva import comparar_cv_veeva, comparar_fdf_veeva

            documentos_veeva = st.session_state.get("veeva_documentos")
            resultados_veeva = []
            resultados_fdf = []

            for _, persona in investigadores.iterrows():
                if documentos_veeva is None:
                    resultados_veeva.append({
                        "Veeva CV Check": "Unable to verify",
                        "Veeva Document Status": "",
                    })
                    resultados_fdf.append({
                        "Veeva FDF Check": "Unable to verify",
                        "Veeva FDF Status": "",
                    })
                else:
                    resultados_veeva.append(
                        comparar_cv_veeva(persona, documentos_veeva)
                    )
                    resultados_fdf.append(
                        comparar_fdf_veeva(persona, documentos_veeva)
                    )

            tabla_veeva = pd.DataFrame(resultados_veeva)
            tabla_fdf = pd.DataFrame(resultados_fdf)

            tabla_resultados["Veeva CV Check"] = tabla_veeva[
                "Veeva CV Check"
            ].values
            tabla_resultados["Veeva Document Status"] = tabla_veeva[
                "Veeva Document Status"
            ].values

            tabla_resultados["Veeva FDF Check"] = tabla_fdf[
                "Veeva FDF Check"
            ].values
            tabla_resultados["Veeva FDF Status"] = tabla_fdf[
                "Veeva FDF Status"
            ].values
            # Mark CV as present when it is found in Veeva.
            tabla_resultados.loc[
                tabla_resultados["Veeva CV Check"].isin([
                    "CV found — Approved",
                    "CV found — In Review",
                    "CV found — Action required",
                    "Role/classification mismatch — Review required",
                ]),
                "Estado del CV"
            ] = "Present"
            # Update recommended actions using the Veeva comparison.
            for indice, fila in tabla_resultados.iterrows():
                resultado_veeva = fila["Veeva CV Check"]

                if resultado_veeva == "Role/classification mismatch — Review required":
                    tabla_resultados.at[
                        indice, "Acción recomendada"
                    ] = "Review Veeva document classification and investigator role"

                elif resultado_veeva == "CV found — Action required":
                    tabla_resultados.at[
                        indice, "Acción recomendada"
                    ] = "Follow up on the Veeva CV document status"

                elif resultado_veeva == "CV found — In Review":
                    tabla_resultados.at[
                        indice, "Acción recomendada"
                    ] = "Monitor Veeva CV review"

                elif resultado_veeva == "CV found — Approved":
                    if fila["Estado del CV"] == "Missing":
                        tabla_resultados.at[
                            indice, "Acción recomendada"
                        ] = "Veeva CV approved; reconcile local CV record"

                elif resultado_veeva == "CV not found in Veeva — Review required":
                    if fila["Name check"] == "Match":
                        tabla_resultados.at[
                            indice, "Acción recomendada"
                        ] = "CV not matched in Veeva; verify document and site records"
            tabla_resultados = tabla_resultados.drop(
                columns=["Resultado"]
            )

            tabla_resultados = tabla_resultados[
                [
                    "Nombre",
                    "Rol",
                    "Name check",
                    "Estado del CV",
                    "Veeva CV Check",
                    "Veeva Document Status",
                    "Veeva FDF Check",
                    "Veeva FDF Status",
                    "Acción recomendada",
                ]
            ]

            def resaltar_cv(valor):
                if valor == "Missing":
                    return "background-color: #FDE2E2; color: #991B1B"
                elif valor == "Present":
                    return "background-color: #D1FAE5; color: #065F46"
                return ""

            tabla_estilizada = tabla_resultados.style.map(
                resaltar_cv,
                subset=["Estado del CV"]
            )

            st.dataframe(
                tabla_estilizada,
                use_container_width=True,
                hide_index=True
            )
        except Exception as e:
            st.error(f"No se pudo leer el PDF: {e}")


  

# ============================================================

if page == "FDA 1572 Review":

    documentos_veeva = st.session_state.get("veeva_documentos")

    if documentos_veeva is not None:

        st.divider()
        st.subheader("Documentos importados desde Veeva")

        st.caption(
            "Vista de consulta. Estos datos no modifican "
            "la revisión del PDF ni la Worklist."
        )

        columnas_veeva = [
            "Name",
            "Status",
            "Study",
            "Country",
            "Study site",
            "Clasification",
            "Created by"
        ]

        st.dataframe(
            documentos_veeva[columnas_veeva],
            use_container_width=True,
            hide_index=True
        )
# IMPORTAR VEEVA
# ============================================================

if "veeva_documentos" not in st.session_state:
    st.session_state["veeva_documentos"] = None

if "veeva_vista_previa" not in st.session_state:
    st.session_state["veeva_vista_previa"] = None

if page == "Importar Veeva":

    st.header("Importar Excel de Veeva")

    st.write(
        "Seleccioná el Excel exportado desde Veeva Vault "
        "para revisar los documentos y sus estados."
    )

    archivo_veeva = st.file_uploader(
        "Seleccionar archivo Excel",
        type=["xlsx"],
        key="importar_veeva_excel"
    )

    if archivo_veeva is not None:
        if st.button("Preparar vista previa", key="procesar_veeva"):
            try:
                from importar_veeva import (
                    importar_veeva,
                    preparar_vista_previa,
                )

                documentos = importar_veeva(archivo_veeva)

                if documentos.empty:
                    st.session_state["veeva_documentos"] = None
                    st.session_state["veeva_vista_previa"] = None
                    st.warning("El archivo no contiene documentos.")

                elif documentos["Study"].nunique() != 1:
                    st.session_state["veeva_documentos"] = None
                    st.session_state["veeva_vista_previa"] = None
                    st.error(
                        "El archivo debe contener documentos de un solo estudio. "
                        "No se preparó la vista previa."
                    )

                else:
                    st.session_state["veeva_documentos"] = documentos
                    st.session_state["veeva_vista_previa"] = preparar_vista_previa(
                        documentos
                    )

            except Exception as error:
                st.error(f"No se pudo procesar el archivo: {error}")

    documentos = st.session_state["veeva_documentos"]
    vista = st.session_state["veeva_vista_previa"]

    if documentos is not None and vista is not None:

        st.success(
            f"Vista previa disponible: {len(documentos)} documentos."
        )

        st.subheader("Alcance de la importación")
        st.write("Estudio:", documentos["Study"].iloc[0])

        centros = (
            documentos[["Country", "Study site"]]
            .drop_duplicates()
            .sort_values(["Country", "Study site"])
        )

        st.write("Países y centros incluidos:")
        st.dataframe(
            centros,
            use_container_width=True,
            hide_index=True
        )

        columnas = [
            "Name", "Status", "Study", "Country",
            "Study site", "Clasification", "Created by"
        ]

        st.subheader(
            f"Requieren acción del DO ({len(vista['accion_do'])})"
        )
        st.dataframe(
            vista["accion_do"][columnas],
            use_container_width=True,
            hide_index=True
        )

        st.subheader(
            f"Sin acción del DO ({len(vista['sin_accion'])})"
        )
        st.dataframe(
            vista["sin_accion"][columnas],
            use_container_width=True,
            hide_index=True
        )

        st.subheader(
            f"Estados para revisión ({len(vista['revision'])})"
        )
        st.dataframe(
            vista["revision"][columnas],
            use_container_width=True,
            hide_index=True
        )

        st.info(
            "Esta es una vista previa. No se modificaron "
            "la Worklist ni los estados de las tareas."
        )
