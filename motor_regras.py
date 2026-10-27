"""
Motor de regras do protótipo SIGAMAES.

Módulo único com os DADOS (habilidades, tratamentos, relações entre
habilidades) e as REGRAS. É usado pela interface (app.py) e pelo gerador do grafo de
conhecimento (grafo de conhecimento/gerar_grafo_conhecimento.py), para que
os dois produzam sempre o mesmo resultado.

Regras
------
R1  Dificuldade em uma habilidade pontua os tratamentos que trabalham essa
    habilidade (Não realiza = 2, Realiza com auxílio = 1, Independente = 0).
R2  Dificuldade em uma habilidade RELACIONADA a outra habilidade do
    tratamento contribui com peso indireto, conforme o tipo da relação:
    pré-requisito e composição = 0,5 × peso; facilitação = 0,25 × peso.
R3  Pontuação NORMALIZADA: soma das contribuições ÷ pontuação máxima possível
    do tratamento, considerando apenas as habilidades avaliadas (respostas em
    branco não entram no numerador nem no denominador). Resultado entre 0 e 1.
R4  Toda pontuação é rastreável até as respostas do formulário.
R5  A intervenção integrada é indicada somente quando pelo menos
    MIN_TRATAMENTOS_INTEGRADA tratamentos específicos atingem LIMIAR_INTEGRADA.
    Sua pontuação é a MENOR entre essas pontuações e, quando indicada, ela é
    apresentada em 1º lugar, pois engloba os tratamentos específicos.
R6  Tratamentos específicos abaixo de LIMIAR_MINIMO não são indicados.
    Se nenhum tratamento for indicado: "sem indicação suficiente".
R7  INCONSISTÊNCIAS (apenas alertam; não alteram a pontuação):
    - pré-requisito: a habilidade dependente está "Independente" mas o
      pré-requisito está "Não realiza" (Alta) ou "Realiza com auxílio" (Moderada);
    - composição: o todo está "Independente" mas a parte está
      "Não realiza" (Alta) ou "Realiza com auxílio" (Moderada);
    - facilitação não gera inconsistência (a habilidade facilitadora não é
      condição necessária);
    - respostas em branco não são verificadas.

As relações entre habilidades ficam em base_conhecimento/relacoes_habilidades.csv
e o mapeamento das habilidades para os itens do Inventário Portage
Operacionalizado (IPO) em base_conhecimento/habilidades_ipo.csv. Os dois arquivos
podem ser editados (Excel, separador ";") sem alterar o código.

Os limiares são valores de partida e devem ser validados com a equipe clínica.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

BASE_CONHECIMENTO = Path(__file__).resolve().parent / "base_conhecimento"

# ---------------------------------------------------------------------
# Parâmetros das regras (validar com os profissionais)
# ---------------------------------------------------------------------
LIMIAR_MINIMO = 0.15            # R6
LIMIAR_INTEGRADA = 0.30         # R5
MIN_TRATAMENTOS_INTEGRADA = 2   # R5
PESO_MAXIMO = 2                 # peso de "Não realiza"

# ---------------------------------------------------------------------
# Habilidades do formulário
# ---------------------------------------------------------------------
SKILL_CATALOG = {
    "AC01": "Alimentação",
    "AC02": "Escovação",
    "AC03": "Fio dental",
    "AC04": "Cuidado com o corpo",
    "AC05": "Cuidado com o cabelo",
    "AC06": "Cuidado com o rosto",
    "AC07": "Cuidado com as mãos",
    "AC08": "Vestuário",
    "AC09": "Manuseio de ajustes",
    "AC10": "Tarefas de banheiro",
    "MO01": "Locomoção geral",
    "MO02": "Locomoção específica",
    "MO03": "Equilíbrio estático",
    "MO04": "Equilíbrio dinâmico",
    "MO05": "Arremessar, receber, rolar e chutar bolas",
    "MO06": "Preensão",
    "MO07": "Encaixe de pinos e argolas",
    "MO08": "Empilhar peças",
    "MO09": "Enfiagem de contas",
    "MO10": "Dobrar papel",
    "MO11": "Montagem de quebra-cabeças",
    "MO12": "Preensão e controle de lápis",
    "MO13": "Escrita, cópia de letras e desenho",
    "MO14": "Uso de tesoura",
    "MO15": "Manipulação de fechos, trincos e maçanetas",
}
SKILLS = {
    name: ("autocuidado" if code.startswith("AC") else "motor")
    for code, name in SKILL_CATALOG.items()
}

STATUS_WEIGHT = {
    "Independente": 0,
    "Realiza com auxílio": 1,
    "Não realiza": 2,
}

# ---------------------------------------------------------------------
# Tratamentos
# Os nomes são exemplos do protótipo; substituir pelos tratamentos reais
# da AMAES, validados pelas orientadoras/profissionais.
# ---------------------------------------------------------------------
INTEGRADA = "Intervenção integrada autocuidado + motor"

TREATMENTS = {
    "Treino de habilidades de autocuidado": {
        "type": "especifico",
        "domain": "autocuidado",
        "skills": [s for s, d in SKILLS.items() if d == "autocuidado"],
        "priority": 1,
    },
    "Treino de habilidades motoras grossas": {
        "type": "especifico",
        "domain": "motor",
        "skills": ["Locomoção geral", "Locomoção específica",
                   "Equilíbrio estático", "Equilíbrio dinâmico",
                   "Arremessar, receber, rolar e chutar bolas"],
        "priority": 1,
    },
    "Treino de habilidades motoras finas": {
        "type": "especifico",
        "domain": "motor",
        "skills": ["Preensão", "Encaixe de pinos e argolas",
                   "Empilhar peças", "Enfiagem de contas", "Dobrar papel",
                   "Montagem de quebra-cabeças", "Preensão e controle de lápis",
                   "Escrita, cópia de letras e desenho", "Uso de tesoura",
                   "Manipulação de fechos, trincos e maçanetas"],
        "priority": 1,
    },
    INTEGRADA: {
        "type": "integrado",
        "domain": "integrado",
        "skills": [],          # não pontua por habilidade (R5)
        "combines": ["Treino de habilidades de autocuidado",
                     "Treino de habilidades motoras grossas",
                     "Treino de habilidades motoras finas"],
        "priority": 2,
    },
}
SPECIFIC_TREATMENTS = [t for t, d in TREATMENTS.items() if d["type"] == "especifico"]

# ---------------------------------------------------------------------
# Relações entre habilidades (base_conhecimento/*.csv)
# ---------------------------------------------------------------------
# Causalidade fica para trabalho futuro (não modelada).
RELATION_TYPES = {
    "PreRequisito": {"label": "Pré-requisito", "peso": 0.5, "inconsistencia": True,
                     "verbo": "é pré-requisito de"},
    "Composicao": {"label": "Composição", "peso": 0.5, "inconsistencia": True,
                   "verbo": "é parte de"},
    "Facilitacao": {"label": "Facilitação", "peso": 0.25, "inconsistencia": False,
                    "verbo": "facilita"},
}


def _read_csv(name):
    with open(BASE_CONHECIMENTO / name, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f, delimiter=";")]


def _load_ipo():
    data = {}
    for row in _read_csv("habilidades_ipo.csv"):
        items = [i.strip() for i in row["itens_ipo"].split(",") if i.strip()]
        ages = [int(m) for m in re.findall(r"\((\d)-\d\)", row["itens_ipo"])]
        data[SKILL_CATALOG[row["codigo"]]] = {
            "codigo": row["codigo"],
            "itens": items,
            "idade_inicial": min(ages) if ages else None,
            "observacao": row["observacao"],
        }
    return data


def _load_relations():
    relations = []
    for row in _read_csv("relacoes_habilidades.csv"):
        tipo = row["tipo"]
        if tipo not in RELATION_TYPES:
            raise ValueError(f"Relação {row['id']}: tipo desconhecido '{tipo}'")
        relations.append({
            "id": row["id"],
            "tipo": tipo,
            "origem": SKILL_CATALOG[row["origem"]],
            "destino": SKILL_CATALOG[row["destino"]],
            "peso": RELATION_TYPES[tipo]["peso"],
            "itens_origem": row["itens_ipo_origem"],
            "itens_destino": row["itens_ipo_destino"],
            "evidencia": row["evidencia"],
            "justificativa": row["justificativa"],
            "status": row["status"],
        })
    return relations


SKILL_IPO = _load_ipo()
RELATIONS = _load_relations()


def validate_knowledge_base():
    """Verifica a própria base de conhecimento. Retorna lista de problemas."""
    problems = []
    ids = [r["id"] for r in RELATIONS]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"Identificador de relação repetido: {dup}")
    pairs = {}
    for r in RELATIONS:
        if r["origem"] == r["destino"]:
            problems.append(f"{r['id']}: origem e destino iguais")
        key = (r["origem"], r["destino"])
        if key in pairs:
            problems.append(f"{r['id']} repete o par de {pairs[key]}")
        pairs[key] = r["id"]
        if r["tipo"] == "PreRequisito":
            a = SKILL_IPO[r["origem"]]["idade_inicial"]
            b = SKILL_IPO[r["destino"]]["idade_inicial"]
            if a is not None and b is not None and a > b:
                problems.append(
                    f"{r['id']}: pré-requisito '{r['origem']}' surge no IPO ({a} anos) "
                    f"depois de '{r['destino']}' ({b} anos)")
    # pré-requisitos e composições não podem formar ciclo
    graph = defaultdict(list)
    for r in RELATIONS:
        if r["tipo"] != "Facilitacao":
            graph[r["origem"]].append(r["destino"])
    state = {}

    def visit(node, path):
        state[node] = 1
        for nxt in graph[node]:
            if state.get(nxt) == 1:
                problems.append("Ciclo de pré-requisito/composição: "
                                + " → ".join(path + [nxt]))
            elif nxt not in state:
                visit(nxt, path + [nxt])
        state[node] = 2

    for node in list(graph):
        if node not in state:
            visit(node, [node])
    return problems


# ---------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------
def _score_specific(treatment, answers):
    """R1 + R2 + R3 para um tratamento específico."""
    skills = TREATMENTS[treatment]["skills"]
    raw = 0.0
    maximum = 0.0
    explanations = []
    contributions = defaultdict(float)
    evaluated = 0

    for skill in skills:                                          # R1
        status = answers.get(skill)
        if status is None:
            continue
        evaluated += 1
        weight = STATUS_WEIGHT[status]
        maximum += PESO_MAXIMO
        if weight:
            raw += weight
            contributions[skill] += weight
            explanations.append(f"{skill}: {status} (peso {weight})")

    for rel in RELATIONS:                                         # R2
        source, target = rel["origem"], rel["destino"]
        if target not in skills:
            continue
        status = answers.get(source)
        if status is None:
            continue
        weight = STATUS_WEIGHT[status]
        maximum += PESO_MAXIMO * rel["peso"]
        if weight:
            points = weight * rel["peso"]
            raw += points
            contributions[source] += points
            explanations.append(
                f"{source} {RELATION_TYPES[rel['tipo']]['verbo']} {target} "
                f"[{rel['id']}]: {status} (peso indireto {points:g})"
            )

    score = raw / maximum if maximum else 0.0                     # R3
    return {
        "treatment": treatment,
        "type": "especifico",
        "score": round(score, 4),
        "raw": round(raw, 2),
        "max": round(maximum, 2),
        "evaluated": evaluated,
        "total_skills": len(skills),
        "indicated": score >= LIMIAR_MINIMO and raw > 0,          # R6
        "explanations": explanations,
        "contributions": dict(contributions),
        "rule": "R1–R3",
    }


def _score_integrated(treatment, specific_results):
    """R5: indicada quando >= N tratamentos específicos passam do limiar."""
    combines = TREATMENTS[treatment]["combines"]
    passing = [r for r in specific_results
               if r["treatment"] in combines and r["score"] >= LIMIAR_INTEGRADA]
    indicated = len(passing) >= MIN_TRATAMENTOS_INTEGRADA
    score = min(r["score"] for r in passing) if indicated else 0.0
    contributions = defaultdict(float)
    explanations = []
    for r in passing:
        explanations.append(
            f"{r['treatment']}: {r['score']:.0%} (≥ limiar {LIMIAR_INTEGRADA:.0%})"
        )
        if indicated:
            for skill, pts in r["contributions"].items():
                contributions[skill] += pts
    if not indicated:
        explanations.append(
            f"Somente {len(passing)} tratamento(s) específico(s) atingiu(ram) "
            f"{LIMIAR_INTEGRADA:.0%}; são necessários {MIN_TRATAMENTOS_INTEGRADA}."
        )
    return {
        "treatment": treatment,
        "type": "integrado",
        "score": round(score, 4),
        "raw": None,
        "max": None,
        "evaluated": None,
        "total_skills": None,
        "indicated": indicated,
        "explanations": explanations,
        "contributions": dict(contributions) if indicated else {},
        "combined": [r["treatment"] for r in passing],
        "rule": "R5",
    }


def calculate_recommendations(answers):
    """
    Retorna todos os tratamentos ordenados:
      1. integrada, se indicada (R5);
      2. demais indicados, por pontuação normalizada (desempate: prioridade);
      3. não indicados, por pontuação.
    """
    specific = [_score_specific(t, answers) for t in SPECIFIC_TREATMENTS]
    integrated = [_score_integrated(t, specific)
                  for t, d in TREATMENTS.items() if d["type"] == "integrado"]
    results = specific + integrated

    def key(r):
        return (
            r["indicated"],
            r["indicated"] and r["type"] == "integrado",
            r["score"],
            -TREATMENTS[r["treatment"]]["priority"],
        )

    results.sort(key=key, reverse=True)
    return results


def calculate_skill_contributions(answers):
    return {r["treatment"]: r["contributions"]
            for r in calculate_recommendations(answers)}


LEVEL_ORDER = {"Não realiza": 0, "Realiza com auxílio": 1, "Independente": 2}


def detect_inconsistencies(answers):
    """R7: respostas que contradizem relações de pré-requisito ou composição."""
    found = []
    for rel in RELATIONS:
        if not RELATION_TYPES[rel["tipo"]]["inconsistencia"]:
            continue
        a, b = answers.get(rel["origem"]), answers.get(rel["destino"])
        if a is None or b is None or b != "Independente":
            continue
        if a == "Não realiza":
            severity = "Alta"
        elif a == "Realiza com auxílio":
            severity = "Moderada"
        else:
            continue
        if rel["tipo"] == "PreRequisito":
            message = (f"{rel['destino']} está como \"{b}\", mas o pré-requisito "
                       f"{rel['origem']} está como \"{a}\".")
        else:
            message = (f"{rel['destino']} está como \"{b}\", mas a parte "
                       f"{rel['origem']} está como \"{a}\".")
        found.append({
            "relation": rel,
            "severity": severity,
            "origem": rel["origem"],
            "destino": rel["destino"],
            "status_origem": a,
            "status_destino": b,
            "message": message,
        })
    found.sort(key=lambda i: (i["severity"] != "Alta", i["relation"]["id"]))
    return found


def classify_case(answers):
    scores = {
        domain: sum(STATUS_WEIGHT[v] for k, v in answers.items()
                    if v is not None and SKILLS[k] == domain)
        for domain in ("autocuidado", "motor")
    }
    if scores["autocuidado"] == 0 and scores["motor"] == 0:
        return "Sem dificuldades identificadas", scores
    if scores["autocuidado"] > scores["motor"]:
        return "Predomínio de dificuldades de autocuidado", scores
    if scores["motor"] > scores["autocuidado"]:
        return "Predomínio de dificuldades motoras", scores
    return "Dificuldades distribuídas entre os dois domínios", scores


RULES_TEXT = f"""R1 — dificuldade em uma habilidade pontua os tratamentos
     que trabalham essa habilidade (com auxílio = 1, não realiza = 2).

R2 — dificuldade em uma habilidade relacionada a outra habilidade
     do tratamento contribui com peso indireto: pré-requisito e
     composição = 0,5 × peso; facilitação = 0,25 × peso.

R3 — pontuação normalizada = soma ÷ máximo possível do tratamento
     (só habilidades avaliadas entram no cálculo).

R4 — cada ponto é rastreável até uma resposta do formulário.

R5 — a intervenção integrada é indicada quando ≥ {MIN_TRATAMENTOS_INTEGRADA} tratamentos
     específicos atingem {LIMIAR_INTEGRADA:.0%}; sua pontuação é a menor delas
     e ela é apresentada em 1º lugar.

R6 — tratamentos abaixo de {LIMIAR_MINIMO:.0%} não são indicados; sem nenhum
     indicado, o resultado é "sem indicação suficiente".

R7 — inconsistências: habilidade "Independente" cujo pré-requisito
     (ou parte, na composição) "Não realiza" (Alta) ou "Realiza com
     auxílio" (Moderada). Só alerta; não altera a pontuação."""
