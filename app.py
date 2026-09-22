
import streamlit as st
import networkx as nx
import random
from collections import defaultdict

st.set_page_config(page_title="Protótipo SIGAMAES – Recomendação", page_icon="🧩", layout="wide")

# ---------------------------------------------------------------------
# MODELO DO GRAFO
# ---------------------------------------------------------------------
# A ideia é representar:
# habilidade -> domínio -> objetivo/intervenção
# e relações de dependência entre habilidades.
#
# Os nomes dos tratamentos abaixo são exemplos para o protótipo.
# No TCC, devem ser substituídos pelos tratamentos reais disponibilizados
# pela AMAES e validados pelas orientadoras/profissionais.
SKILLS = {
    "Alimentação": "autocuidado",
    "Escovação": "autocuidado",
    "Fio dental": "autocuidado",
    "Cuidado com o corpo": "autocuidado",
    "Cuidado com o cabelo": "autocuidado",
    "Cuidado com o rosto": "autocuidado",
    "Cuidado com as mãos": "autocuidado",
    "Vestuário": "autocuidado",
    "Manuseio de ajustes": "autocuidado",
    "Tarefas de banheiro": "autocuidado",
    "Locomoção geral": "motor",
    "Locomoção específica": "motor",
    "Equilíbrio estático": "motor",
    "Equilíbrio dinâmico": "motor",
    "Arremessar, receber, rolar e chutar bolas": "motor",
    "Preensão": "motor",
    "Encaixe de pinos e argolas": "motor",
    "Empilhar peças": "motor",
    "Enfiagem de contas": "motor",
    "Dobrar papel": "motor",
    "Montagem de quebra-cabeças": "motor",
    "Preensão e controle de lápis": "motor",
    "Escrita, cópia de letras e desenho": "motor",
    "Uso de tesoura": "motor",
    "Manipulação de fechos, trincos e maçanetas": "motor",
}

TREATMENTS = {
    "Treino de habilidades de autocuidado": {
        "domain": "autocuidado",
        "skills": [skill for skill, domain in SKILLS.items()
                   if domain == "autocuidado"],
        "priority": 1,
    },
    "Treino de habilidades motoras grossas": {
        "domain": "motor",
        "skills": ["Locomoção geral", "Locomoção específica",
                   "Equilíbrio estático", "Equilíbrio dinâmico",
                   "Arremessar, receber, rolar e chutar bolas"],
        "priority": 1,
    },
    "Treino de habilidades motoras finas": {
        "domain": "motor",
        "skills": ["Preensão", "Encaixe de pinos e argolas",
                   "Empilhar peças", "Enfiagem de contas", "Dobrar papel",
                   "Montagem de quebra-cabeças", "Preensão e controle de lápis",
                   "Escrita, cópia de letras e desenho", "Uso de tesoura",
                   "Manipulação de fechos, trincos e maçanetas"],
        "priority": 1,
    },
    "Intervenção integrada autocuidado + motor": {
        "domain": "integrado",
        "skills": list(SKILLS.keys()),
        "priority": 2,
    },
}

# Relações simplificadas de dependência/apoio.
DEPENDENCIES = [
    ("Cuidado com as mãos", "Alimentação"),
    ("Cuidado com as mãos", "Fio dental"),
    ("Preensão", "Alimentação"),
    ("Preensão", "Vestuário"),
    ("Locomoção geral", "Tarefas de banheiro"),
    ("Locomoção geral", "Vestuário"),
    ("Equilíbrio dinâmico", "Locomoção específica"),
    ("Equilíbrio estático", "Vestuário"),
    ("Preensão e controle de lápis", "Escrita, cópia de letras e desenho"),
    ("Preensão", "Encaixe de pinos e argolas"),
    ("Preensão", "Enfiagem de contas"),
    ("Preensão", "Uso de tesoura"),
    ("Manipulação de fechos, trincos e maçanetas", "Vestuário"),
]

STATUS_WEIGHT = {
    "Independente": 0,
    "Realiza com auxílio": 1,
    "Não realiza": 2,
}

def build_graph():
    g = nx.DiGraph()

    for skill, domain in SKILLS.items():
        g.add_node(skill, type="habilidade", domain=domain)

    for treatment, data in TREATMENTS.items():
        g.add_node(treatment, type="tratamento", domain=data["domain"])
        for skill in data["skills"]:
            g.add_edge(skill, treatment, relation="indica")

    for parent, child in DEPENDENCIES:
        g.add_edge(parent, child, relation="apoia")

    return g

GRAPH = build_graph()

def calculate_skill_contributions(answers):
    contributions = {
        treatment: defaultdict(float)
        for treatment in TREATMENTS
    }

    for skill, status in answers.items():
        if status is None:
            continue

        weight = STATUS_WEIGHT[status]
        if weight == 0:
            continue

        for treatment, data in TREATMENTS.items():
            if skill in data["skills"]:
                contributions[treatment][skill] += weight

            for source, target in DEPENDENCIES:
                if source == skill and target in data["skills"]:
                    contributions[treatment][skill] += weight * 0.5

    return {
        treatment: dict(skill_scores)
        for treatment, skill_scores in contributions.items()
    }

def calculate_recommendations(answers):
    """
    Motor de regras determinístico.

    Regra básica:
      - soma-se a gravidade das dificuldades das habilidades de cada tratamento;
      - dificuldades diretamente relacionadas ao tratamento têm peso 1;
      - dificuldades em habilidades que apoiam outra habilidade têm peso 0.5;
      - empate é resolvido pela prioridade configurada no tratamento.

    Isso torna o resultado explicável: cada ponto pode ser rastreado
    até uma resposta do formulário.
    """
    direct = defaultdict(float)
    explanations = defaultdict(list)

    for skill, status in answers.items():
        if status is None:
            continue

        weight = STATUS_WEIGHT[status]
        if weight == 0:
            continue

        for treatment, data in TREATMENTS.items():
            if skill in data["skills"]:
                direct[treatment] += weight
                explanations[treatment].append(
                    f"{skill}: {status} (peso {weight})"
                )

            # Propagação simples pelo grafo: se a habilidade é pré-requisito
            # de outra habilidade contemplada no tratamento, ela contribui
            # parcialmente para a pontuação.
            for source, target in DEPENDENCIES:
                if source == skill and target in data["skills"]:
                    direct[treatment] += weight * 0.5
                    explanations[treatment].append(
                        f"{skill} influencia {target}: {status} "
                        f"(peso indireto {weight * 0.5:g})"
                    )

    results = []
    for treatment, score in direct.items():
        results.append({
            "treatment": treatment,
            "score": round(score, 2),
            "explanations": explanations[treatment],
        })

    # Inclui tratamentos sem dificuldade, para permitir comparação.
    for treatment in TREATMENTS:
        if not any(r["treatment"] == treatment for r in results):
            results.append({
                "treatment": treatment,
                "score": 0,
                "explanations": [],
            })

    results.sort(
        key=lambda x: (
            x["score"],
            -TREATMENTS[x["treatment"]]["priority"]
        ),
        reverse=True
    )

    return results

def classify_case(answers):
    scores = {
        "autocuidado": sum(
            STATUS_WEIGHT[v] for k, v in answers.items()
            if v is not None and SKILLS[k] == "autocuidado"
        ),
        "motor": sum(
            STATUS_WEIGHT[v] for k, v in answers.items()
            if v is not None and SKILLS[k] == "motor"
        ),
    }

    if scores["autocuidado"] == 0 and scores["motor"] == 0:
        return "Sem dificuldades identificadas", scores

    if scores["autocuidado"] > scores["motor"]:
        return "Predomínio de dificuldades de autocuidado", scores
    if scores["motor"] > scores["autocuidado"]:
        return "Predomínio de dificuldades motoras", scores
    return "Dificuldades distribuídas entre os dois domínios", scores


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

        st.markdown("### Tratamentos ordenados")

        for idx, result in enumerate(results, start=1):
            treatment = result["treatment"]
            score = result["score"]

            if idx == 1 and score > 0:
                st.success(f"**{idx}º — {treatment}**  \nPontuação: **{score}**")
            else:
                st.write(f"**{idx}º — {treatment}** — pontuação: **{score}**")

            if result["explanations"]:
                with st.expander("Por que este tratamento recebeu essa pontuação?"):
                    for explanation in result["explanations"]:
                        st.write("• " + explanation)

        st.markdown("### Regras acionadas")
        st.code(
            """R1 — dificuldade em uma habilidade aumenta a pontuação
     dos tratamentos que trabalham essa habilidade.

R2 — dificuldade em uma habilidade que apoia outra habilidade
     recebe contribuição indireta (0,5 × peso da dificuldade).

R3 — quanto maior a soma das dificuldades relacionadas,
     maior a prioridade do tratamento.

R4 — o sistema mantém uma justificativa rastreável,
     mostrando quais respostas contribuíram para o resultado.""",
            language="text"
        )

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
        st.write(", ".join(data["skills"]))

    st.markdown("**Dependências/relacionamentos usados no protótipo**")
    for source, target in DEPENDENCIES:
        st.write(f"{source} → {target}")

    st.markdown("### Como transformar isso em um modelo formal")
    st.write(
        "Cada habilidade pode ser um nó do grafo. Arestas representam "
        "relações de dependência/apoio. Tratamentos são nós conectados "
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
    recommended_treatment = graph_results[0]["treatment"]
    skill_contributions = calculate_skill_contributions(graph_answers)
    recommended_contributions = skill_contributions[recommended_treatment]
    graph = nx.DiGraph()
    graph.add_node("paciente", label="Paciente", node_type="paciente")
    graph.add_node("autocuidado", label="Autocuidado", node_type="categoria")
    graph.add_node("motor", label="Motor", node_type="categoria")
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
        f'  "{dot_text(recommended_treatment)}" [label="Intervenção sugerida\\n{dot_text(recommended_treatment)}", '
        'shape=box, fillcolor="#86EFAC", color="#166534", penwidth=2];',
    ]

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

    dot_lines.append("}")
    st.graphviz_chart("\n".join(dot_lines), use_container_width=True)

    st.markdown(
        f"**Intervenção sugerida:** {recommended_treatment}  "
        f"(pontuação total: {graph_results[0]['score']})"
    )
    st.caption(
        "As setas verdes mostram contribuições positivas. As setas tracejadas "
        "representam habilidades sem contribuição para esta intervenção."
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
