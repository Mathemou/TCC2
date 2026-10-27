
import streamlit as st
import networkx as nx
import random
import csv
import io
from collections import defaultdict

st.set_page_config(page_title="Protótipo SIGAMAES – Recomendação", page_icon="🧩", layout="wide")

# ---------------------------------------------------------------------
# DADOS E MOTOR DE REGRAS
# ---------------------------------------------------------------------
# Habilidades, tratamentos, relações entre habilidades e regras ficam em
# motor_regras.py (que lê base_conhecimento/*.csv), compartilhado com o
# gerador do grafo de conhecimento.
from motor_regras import (
    INTEGRADA,
    LIMIAR_INTEGRADA,
    LIMIAR_MINIMO,
    MIN_TRATAMENTOS_INTEGRADA,
    RELATION_TYPES,
    RELATIONS,
    RULES_TEXT,
    SKILL_CATALOG,
    SKILL_IPO,
    SKILLS,
    STATUS_WEIGHT,
    TREATMENTS,
    calculate_recommendations,
    calculate_skill_contributions,
    classify_case,
    detect_inconsistencies,
)

IMPORT_CODE_TO_STATUS = {
    0: None,
    1: "Independente",
    2: "Realiza com auxílio",
    3: "Não realiza",
}
STATUS_TO_IMPORT_CODE = {
    status: code for code, status in IMPORT_CODE_TO_STATUS.items()
}


def show_inconsistencies(answers):
    """R7: mostra as inconsistências agrupadas pela habilidade de origem."""
    inconsistencies = detect_inconsistencies(answers)
    if not inconsistencies:
        st.success("Nenhuma inconsistência encontrada entre as respostas.")
        return inconsistencies

    groups = defaultdict(list)
    for item in inconsistencies:
        key = (item["severity"], item["origem"], item["status_origem"],
               item["relation"]["tipo"])
        groups[key].append(item)

    for (severity, origem, status, tipo), items in sorted(
            groups.items(), key=lambda g: (g[0][0] != "Alta", g[0][1])):
        destinos = ", ".join(i["destino"] for i in items)
        if tipo == "PreRequisito":
            texto = (f"**{origem}** está como “{status}”, mas é **pré-requisito** de: "
                     f"{destinos} — marcada(s) como “Independente”.")
        else:
            texto = (f"**{origem}** está como “{status}”, mas é **parte** de: "
                     f"{destinos} — marcada(s) como “Independente”.")
        alerta = st.error if severity == "Alta" else st.warning
        alerta(f"Inconsistência {severity.lower()} · {texto}", icon="⚠️")
        with st.expander("Fundamentação no Inventário Portage Operacionalizado"):
            for item in items:
                rel = item["relation"]
                st.markdown(
                    f"- **{rel['id']}** — {rel['origem']} "
                    f"({rel['itens_origem'] or 'sem item no IPO'}) "
                    f"{RELATION_TYPES[rel['tipo']]['verbo']} {rel['destino']} "
                    f"({rel['itens_destino'] or 'sem item no IPO'}).  \n"
                    f"  {rel['justificativa']}  \n  _{rel['status']}_"
                )
    return inconsistencies


def get_skill_catalog():
    return SKILL_CATALOG.copy()


def parse_imported_form(file_bytes):
    errors = []
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except UnicodeDecodeError:
            return {"forms": {}, "errors": ["O arquivo não está em UTF-8 ou Latin-1."]}

    try:
        sample = text[:4096]
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;").delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = [field.strip().lower() for field in (reader.fieldnames or [])]
    required_fields = {"habilidade_id", "resposta"}
    if not required_fields.issubset(fieldnames):
        return {
            "forms": {},
            "errors": [
                "O arquivo deve conter as colunas 'habilidade_id' e 'resposta'."
            ],
        }

    field_map = {
        original: normalized
        for original, normalized in zip(reader.fieldnames, fieldnames)
    }
    has_patient = "paciente_id" in fieldnames
    forms = defaultdict(dict)
    row_numbers = defaultdict(dict)

    for line_number, raw_row in enumerate(reader, start=2):
        row = {
            field_map[key]: (value.strip() if value is not None else "")
            for key, value in raw_row.items()
            if key is not None
        }
        skill_id = row.get("habilidade_id", "").upper()
        patient_id = row.get("paciente_id", "geral") if has_patient else "geral"
        response_text = row.get("resposta", "")

        if skill_id not in SKILL_CATALOG:
            errors.append(
                f"Linha {line_number}: habilidade_id inválido '{skill_id}'."
            )
            continue
        if not response_text.isdigit() or int(response_text) not in IMPORT_CODE_TO_STATUS:
            errors.append(
                f"Linha {line_number}: resposta deve ser um código entre 0 e 3."
            )
            continue
        if not patient_id:
            errors.append(f"Linha {line_number}: paciente_id não pode ser vazio.")
            continue
        if skill_id in forms[patient_id]:
            errors.append(
                f"Linha {line_number}: habilidade {skill_id} duplicada para o paciente '{patient_id}'."
            )
            continue

        forms[patient_id][skill_id] = IMPORT_CODE_TO_STATUS[int(response_text)]
        row_numbers[patient_id][skill_id] = line_number

    expected_ids = set(SKILL_CATALOG)
    for patient_id, answers in forms.items():
        missing_ids = expected_ids - set(answers)
        if missing_ids:
            errors.append(
                f"Paciente '{patient_id}': habilidades ausentes: "
                f"{', '.join(sorted(missing_ids))}."
            )

    return {"forms": dict(forms), "errors": errors}


def apply_imported_answers(answers):
    for index, (skill_id, skill) in enumerate(SKILL_CATALOG.items()):
        value = answers[skill_id]
        st.session_state[f"skill_v2_{index}"] = value
        st.session_state["form_answers"][skill] = value
    st.session_state["processed"] = False
    st.session_state["active_tab"] = tab_labels[0]


def create_template_csv():
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["habilidade_id", "resposta"])
    for skill_id in SKILL_CATALOG:
        writer.writerow([skill_id, ""])
    return output.getvalue()


def create_answers_csv(answers):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["habilidade_id", "resposta"])
    for skill_id, skill in SKILL_CATALOG.items():
        writer.writerow([skill_id, STATUS_TO_IMPORT_CODE[answers.get(skill)]])
    return output.getvalue()


def show_results():
    st.session_state["active_tab"] = "2. Resultado"


def save_form_answer(skill, widget_key):
    st.session_state["form_answers"][skill] = st.session_state[widget_key]


def apply_form_preset(value, domain=None):
    for i, skill in enumerate(SKILLS):
        if domain is None or SKILLS[skill] == domain:
            st.session_state[f"skill_v2_{i}"] = value
            st.session_state["form_answers"][skill] = value
    st.session_state["processed"] = False
    st.session_state["active_tab"] = tab_labels[0]


st.title("🧩 Protótipo — Sistema de Apoio à Recomendação")
st.caption("Protótipo acadêmico baseado em formulário + grafo de habilidades + regras determinísticas.")

st.info(
    "Este protótipo demonstra uma abordagem de apoio à decisão. "
    "A recomendação não substitui avaliação profissional e as regras "
    "devem ser validadas por especialistas."
)

tab_labels = ["1. Formulário", "2. Resultado", "3. Explicação", "4. Grafo"]
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = tab_labels[0]
if "form_answers" not in st.session_state:
    st.session_state["form_answers"] = {}

with st.sidebar.expander("Ferramentas de teste"):
    st.caption("Preenche o formulário com uma configuração aleatória.")
    if st.button("Gerar configuração aleatória", use_container_width=True):
        random_options = list(STATUS_WEIGHT) + [None]
        for i, skill in enumerate(SKILLS):
            random_value = random.choice(random_options)
            st.session_state[f"skill_v2_{i}"] = random_value
            st.session_state["form_answers"][skill] = random_value
        st.session_state["processed"] = False
        st.session_state["active_tab"] = tab_labels[0]
        st.success("Configuração gerada.")

    st.caption("Importar formulário preenchido")
    st.download_button(
        "Baixar modelo CSV vazio",
        data=create_template_csv(),
        file_name="modelo_formulario_vazio.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "Baixar respostas atuais",
        data=create_answers_csv(st.session_state["form_answers"]),
        file_name="respostas_formulario.csv",
        mime="text/csv",
        use_container_width=True,
        help="Exporta as respostas atuais, usando 0 para habilidades em branco.",
    )
    imported_file = st.file_uploader(
        "Selecione um arquivo CSV ou TXT",
        type=["csv", "txt"],
        help="Use habilidade_id,resposta ou paciente_id,habilidade_id,resposta.",
    )
    if imported_file is not None:
        imported_data = parse_imported_form(imported_file.getvalue())
        if imported_data["errors"]:
            st.error("O formulário não foi aplicado porque existem erros:")
            for error in imported_data["errors"]:
                st.write(f"- {error}")
        elif imported_data["forms"]:
            patient_ids = list(imported_data["forms"])
            selected_patient = patient_ids[0]
            if len(patient_ids) > 1:
                selected_patient = st.selectbox(
                    "Selecione o paciente",
                    patient_ids,
                    key="import_patient",
                )
            if st.button(
                "Aplicar formulário importado",
                use_container_width=True,
                key="apply_imported_form",
            ):
                apply_imported_answers(imported_data["forms"][selected_patient])
                st.success(
                    f"{len(SKILL_CATALOG)} respostas importadas para o paciente "
                    f"'{selected_patient}'. Revise o formulário antes de processar."
                )

    st.caption("Preenchimento rápido por categoria e desempenho")
    preset_options = [
        ("Autocuidado: tudo em branco", None, "autocuidado"),
        ("Autocuidado: tudo independente", "Independente", "autocuidado"),
        ("Autocuidado: tudo com auxílio", "Realiza com auxílio", "autocuidado"),
        ("Autocuidado: nada realiza", "Não realiza", "autocuidado"),
        ("Motor: tudo em branco", None, "motor"),
        ("Motor: tudo independente", "Independente", "motor"),
        ("Motor: tudo com auxílio", "Realiza com auxílio", "motor"),
        ("Motor: nada realiza", "Não realiza", "motor"),
        ("Todas: tudo em branco", None, None),
        ("Todas: tudo independente", "Independente", None),
        ("Todas: tudo com auxílio", "Realiza com auxílio", None),
        ("Todas: nada realiza", "Não realiza", None),
    ]
    for label, value, domain in preset_options:
        if st.button(label, use_container_width=True, key=f"preset_{label}"):
            apply_form_preset(value, domain)
            st.success("Configuração aplicada.")

active_tab = st.radio(
    "Navegação",
    tab_labels,
    horizontal=True,
    label_visibility="collapsed",
    key="active_tab",
)
active_tab_index = tab_labels.index(active_tab)

if active_tab_index == 0:
    st.subheader("Classificação das habilidades")

    st.write(
        "Para cada habilidade, indique o nível de desempenho observado "
        "no prontuário/classificação realizada pela equipe."
    )

    answers = {}

    col1, col2 = st.columns(2)

    for i, (skill, domain) in enumerate(SKILLS.items()):
        container = col1 if i % 2 == 0 else col2
        widget_key = f"skill_v2_{i}"
        saved_answer = st.session_state["form_answers"].get(skill)
        answer_index = (
            list(STATUS_WEIGHT).index(saved_answer)
            if saved_answer in STATUS_WEIGHT
            else None
        )
        with container:
            answers[skill] = st.radio(
                f"{skill} ({domain})",
                list(STATUS_WEIGHT.keys()),
                index=answer_index,
                horizontal=False,
                key=widget_key,
                on_change=save_form_answer,
                args=(skill, widget_key),
            )

    if st.button("Processar classificação", type="primary"):
        st.session_state["answers"] = answers
        st.session_state["form_answers"].update(answers)
        st.session_state["processed"] = True
        st.success(
            "Classificação processada. Veja a aba Resultado acima "
            "ou clique no botão abaixo."
        )
        n_inconsistencias = len(detect_inconsistencies(answers))
        if n_inconsistencias:
            st.warning(
                f"Foram encontradas {n_inconsistencias} inconsistência(s) entre as "
                "respostas. Elas estão detalhadas na aba Resultado; revise o "
                "formulário se necessário.",
                icon="⚠️",
            )
        st.button("Resultado", type="tertiary", on_click=show_results)

if active_tab_index == 1:
    st.subheader("Inferência baseada em regras")

    if not st.session_state.get("processed"):
        st.warning("Preencha o formulário e clique em 'Processar classificação'.")
    else:
        answers = st.session_state["answers"]
        case_class, domain_scores = classify_case(answers)
        results = calculate_recommendations(answers)

        st.markdown(f"### Classificação do caso")
        st.write(case_class)

        c1, c2 = st.columns(2)
        c1.metric("Pontuação — autocuidado", domain_scores["autocuidado"])
        c2.metric("Pontuação — motor", domain_scores["motor"])

        st.markdown("### Inconsistências nas respostas")
        st.caption(
            "Respostas que contradizem relações de pré-requisito ou composição "
            "entre habilidades (regra R7). Servem apenas de alerta: não alteram "
            "a pontuação nem a recomendação."
        )
        show_inconsistencies(answers)

        indicated = [r for r in results if r["indicated"]]
        not_indicated = [r for r in results if not r["indicated"]]

        def describe_score(result):
            if result["type"] == "integrado":
                if result["indicated"]:
                    return (f"Pontuação: **{result['score']:.0%}** "
                            f"(R5 — combina {len(result['combined'])} tratamentos "
                            f"≥ {LIMIAR_INTEGRADA:.0%})")
                return "Não indicada pela regra R5"
            return (f"Pontuação: **{result['score']:.0%}** "
                    f"({result['raw']:g} de {result['max']:g} pontos possíveis; "
                    f"{result['evaluated']}/{result['total_skills']} habilidades avaliadas)")

        def show_explanations(result):
            if result["explanations"]:
                with st.expander("Por que este tratamento recebeu essa pontuação?"):
                    for explanation in result["explanations"]:
                        st.write("• " + explanation)

        st.markdown("### Tratamentos indicados")
        if not indicated:
            st.info(
                "**Sem indicação suficiente.** Nenhum tratamento atingiu o "
                f"limiar mínimo de {LIMIAR_MINIMO:.0%} (regra R6)."
            )
        for idx, result in enumerate(indicated, start=1):
            prioridade = {1: "Alta", 2: "Média"}.get(idx, "Baixa")
            text = (f"**{idx}º — {result['treatment']}** · prioridade {prioridade}  \n"
                    f"{describe_score(result)}")
            if idx == 1:
                st.success(text)
            else:
                st.write(text)
            show_explanations(result)

        if not_indicated:
            st.markdown("### Não indicados")
            for result in not_indicated:
                st.write(f"{result['treatment']} — {describe_score(result)}")
                show_explanations(result)

        st.markdown("### Regras do motor")
        st.code(RULES_TEXT, language="text")

if active_tab_index == 2:
    st.subheader("Representação do conhecimento")

    st.write(
        "O grafo relaciona habilidades, dependências entre habilidades "
        "e tratamentos. No TCC, ele pode ser construído a partir das "
        "habilidades do Portage e dos tratamentos disponíveis na instituição."
    )

    st.markdown("**Habilidades → tratamentos**")
    for treatment, data in TREATMENTS.items():
        st.write(f"**{treatment}**")
        if data["type"] == "integrado":
            st.write(
                f"Não pontua por habilidade. É indicada quando pelo menos "
                f"{MIN_TRATAMENTOS_INTEGRADA} destes tratamentos atingem "
                f"{LIMIAR_INTEGRADA:.0%}: " + ", ".join(data["combines"]) + "."
            )
        else:
            st.write(", ".join(data["skills"]))

    st.markdown("### Relações entre habilidades")
    st.write(
        "As relações foram derivadas do Inventário Portage Operacionalizado (IPO): "
        "do conteúdo dos itens e da sequência das faixas etárias. Ficam em "
        "`base_conhecimento/relacoes_habilidades.csv` e podem ser editadas."
    )
    descricoes = {
        "PreRequisito": "a habilidade de origem é condição necessária para a de "
                        "destino. Gera inconsistência e peso indireto 0,5.",
        "Composicao": "a habilidade de origem é parte da de destino. Gera "
                      "inconsistência e peso indireto 0,5.",
        "Facilitacao": "a habilidade de origem favorece a de destino, mas não é "
                       "necessária. Não gera inconsistência; peso indireto 0,25.",
    }
    for tipo, info in RELATION_TYPES.items():
        rels = [r for r in RELATIONS if r["tipo"] == tipo]
        st.markdown(f"**{info['label']}** ({len(rels)}) — {descricoes[tipo]}")
        st.dataframe(
            [{
                "ID": r["id"],
                "Origem": r["origem"],
                "Itens IPO (origem)": r["itens_origem"] or "—",
                "Destino": r["destino"],
                "Itens IPO (destino)": r["itens_destino"] or "—",
                "Evidência": r["evidencia"],
                "Justificativa": r["justificativa"],
            } for r in rels],
            hide_index=True,
        )
    st.caption("Causalidade ainda não é modelada.")

    with st.expander("Itens do IPO associados a cada habilidade do formulário"):
        st.dataframe(
            [{
                "Código": info["codigo"],
                "Habilidade": skill,
                "Itens do IPO (faixa etária)": ", ".join(info["itens"]) or "—",
                "Observação": info["observacao"],
            } for skill, info in SKILL_IPO.items()],
            hide_index=True,
        )
        st.caption("A = Autocuidados, M = Desenvolvimento Motor. A numeração deve "
                   "ser conferida na edição do Manual usada no TCC.")

    st.markdown("### Como transformar isso em um modelo formal")
    st.write(
        "Cada habilidade pode ser um nó do grafo. Arestas representam "
        "relações tipadas (pré-requisito, facilitação, composição). Tratamentos são nós conectados "
        "às habilidades que trabalham. As respostas do formulário "
        "atribuem pesos às habilidades e o motor de regras percorre "
        "essas relações para produzir uma ordenação explicável."
    )

if active_tab_index == 3:
    st.subheader("Grafo do formulário do paciente")
    st.write(
        "A visualização relaciona o paciente às categorias e às habilidades "
        "preenchidas no formulário. A cor de cada habilidade representa o "
        "desempenho informado."
    )

    graph_answers = st.session_state.get("form_answers", {})
    graph_results = calculate_recommendations(graph_answers)
    top_result = graph_results[0] if graph_results[0]["indicated"] else None
    recommended_treatment = top_result["treatment"] if top_result else None
    skill_contributions = calculate_skill_contributions(graph_answers)
    recommended_contributions = (
        skill_contributions[recommended_treatment] if top_result else {}
    )
    graph = nx.DiGraph()
    graph.add_node("paciente", label="Paciente", node_type="paciente")
    graph.add_node("autocuidado", label="Autocuidado", node_type="categoria")
    graph.add_node("motor", label="Motor", node_type="categoria")
    if top_result:
        graph.add_node(
            recommended_treatment,
            label=recommended_treatment,
            node_type="intervencao",
        )
    graph.add_edge("paciente", "autocuidado")
    graph.add_edge("paciente", "motor")

    for skill, domain in SKILLS.items():
        graph.add_node(
            skill,
            label=skill,
            node_type="habilidade",
            status=graph_answers.get(skill),
        )
        graph.add_edge(domain, skill)

        if top_result:
            contribution = recommended_contributions.get(skill, 0)
            graph.add_edge(skill, recommended_treatment, contribution=contribution)

    status_colors = {
        None: "#E5E7EB",
        "Independente": "#BBF7D0",
        "Realiza com auxílio": "#FEF08A",
        "Não realiza": "#FECACA",
    }

    def dot_text(value):
        return str(value).replace("\\", "\\\\").replace('"', '\\"')

    dot_lines = [
        "digraph paciente {",
        '  graph [rankdir=LR, bgcolor="white", pad="0.3", nodesep="0.35", ranksep="1.1"];',
        '  node [fontname="Arial", fontsize=11, style="filled", color="#64748B"];',
        '  edge [color="#94A3B8", arrowsize=0.7];',
        '  "paciente" [label="Paciente", shape=ellipse, fillcolor="#BFDBFE", fontsize=14];',
        '  "autocuidado" [label="Autocuidado", shape=box, fillcolor="#DDD6FE", fontsize=13];',
        '  "motor" [label="Motor", shape=box, fillcolor="#DDD6FE", fontsize=13];',
    ]
    if top_result:
        dot_lines.append(
            f'  "{dot_text(recommended_treatment)}" [label="Intervenção sugerida\\n'
            f'{dot_text(recommended_treatment)}\\n{top_result["score"]:.0%}", '
            'shape=box, fillcolor="#86EFAC", color="#166534", penwidth=2];'
        )

    for skill, domain in SKILLS.items():
        status = graph_answers.get(skill)
        status_label = status if status is not None else "Em branco"
        dot_lines.append(
            f'  "{dot_text(skill)}" [label="{dot_text(skill)}\\n{dot_text(status_label)}", '
            f'fillcolor="{status_colors.get(status, status_colors[None])}"];'
        )

    for source, target in graph.edges:
        edge_data = graph.edges[source, target]
        contribution = edge_data.get("contribution")
        edge_style = (
            'color="#166534", penwidth=2'
            if contribution is not None and contribution > 0
            else 'color="#CBD5E1", style=dashed'
        )
        edge_label = (
            f', label="contribuição: {contribution:g}"'
            if contribution is not None
            else ""
        )
        dot_lines.append(
            f'  "{dot_text(source)}" -> "{dot_text(target)}" '
            f'[{edge_style}{edge_label}];'
        )

    graph_inconsistencies = detect_inconsistencies(graph_answers)
    for item in graph_inconsistencies:
        color = "#DC2626" if item["severity"] == "Alta" else "#D97706"
        dot_lines.append(
            f'  "{dot_text(item["origem"])}" -> "{dot_text(item["destino"])}" '
            f'[color="{color}", fontcolor="{color}", penwidth=2.5, style=bold, '
            f'constraint=false, label="⚠ {item["relation"]["id"]}"];'
        )

    dot_lines.append("}")
    st.graphviz_chart("\n".join(dot_lines), use_container_width=True)

    if top_result:
        st.markdown(
            f"**Intervenção sugerida:** {recommended_treatment}  "
            f"(pontuação normalizada: {top_result['score']:.0%})"
        )
    else:
        st.markdown(
            "**Sem indicação suficiente:** nenhum tratamento atingiu o limiar "
            f"mínimo de {LIMIAR_MINIMO:.0%}."
        )
    st.caption(
        "As setas verdes mostram contribuições positivas. As setas tracejadas "
        "representam habilidades sem contribuição para esta intervenção. "
        "Setas vermelhas (alta) ou laranja (moderada) marcadas com ⚠ ligam "
        "habilidades com respostas inconsistentes."
    )

    st.markdown("**Legenda**")
    legend_columns = st.columns(4)
    for column, (status, color) in zip(legend_columns, status_colors.items()):
        label = status if status is not None else "Em branco"
        column.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'background:{color};border:1px solid #64748B;margin-right:6px;">'
            f'</span>{label}',
            unsafe_allow_html=True,
        )

st.divider()
st.caption("Protótipo para TCC — substitua os nomes das intervenções e valide as regras com profissionais da AMAES.")
