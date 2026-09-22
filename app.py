
import streamlit as st
import networkx as nx
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
    "Em branco": 0,
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
            if SKILLS[k] == "autocuidado"
        ),
        "motor": sum(
            STATUS_WEIGHT[v] for k, v in answers.items()
            if SKILLS[k] == "motor"
        ),
    }

    if scores["autocuidado"] == 0 and scores["motor"] == 0:
        return "Sem dificuldades identificadas", scores

    if scores["autocuidado"] > scores["motor"]:
        return "Predomínio de dificuldades de autocuidado", scores
    if scores["motor"] > scores["autocuidado"]:
        return "Predomínio de dificuldades motoras", scores
    return "Dificuldades distribuídas entre os dois domínios", scores


st.title("🧩 Protótipo — Sistema de Apoio à Recomendação")
st.caption("Protótipo acadêmico baseado em formulário + grafo de habilidades + regras determinísticas.")

st.info(
    "Este protótipo demonstra uma abordagem de apoio à decisão. "
    "A recomendação não substitui avaliação profissional e as regras "
    "devem ser validadas por especialistas."
)

tab1, tab2, tab3 = st.tabs(["1. Formulário", "2. Resultado", "3. Grafo"])

with tab1:
    st.subheader("Classificação das habilidades")

    st.write(
        "Para cada habilidade, indique o nível de desempenho observado "
        "no prontuário/classificação realizada pela equipe."
    )

    answers = {}

    col1, col2 = st.columns(2)

    for i, (skill, domain) in enumerate(SKILLS.items()):
        container = col1 if i % 2 == 0 else col2
        with container:
            answers[skill] = st.radio(
                f"{skill} ({domain})",
                list(STATUS_WEIGHT.keys()),
                horizontal=False,
                key=f"skill_{i}",
            )

    if st.button("Processar classificação", type="primary"):
        st.session_state["answers"] = answers
        st.session_state["processed"] = True
        st.success("Classificação processada. Veja a aba Resultado.")

with tab2:
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

with tab3:
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

st.divider()
st.caption("Protótipo para TCC — substitua os nomes das intervenções e valide as regras com profissionais da AMAES.")
