"""
Gera o GRAFO DE CONHECIMENTO INSTANCIADO do protótipo SIGAMAES (TCC2).

    Ontologia (TBox)  ->  diagrama uml/grafo.png / grafo.tonto (OntoUML),
                          com as extensões de grafo.corrigido.tonto
    Instâncias (ABox) ->  dados e regras de ../motor_regras.py (os mesmos
                          usados pelo app.py), relações entre habilidades de
                          ../base_conhecimento/*.csv (derivadas do Inventário
                          Portage Operacionalizado) + pacientes fictícios

Saídas (pasta ./saida):
    grafo_conhecimento.ttl      TBox (em gUFO) + ABox, em RDF/Turtle
    relatorio_validacao.txt     validação SHACL + conferência do motor
    *.dot / *.png / *.svg       visualizações (requer Graphviz instalado)

Execução (a partir de qualquer pasta):
    pip install rdflib pyshacl
    python gerar_grafo_conhecimento.py

Todos os pacientes são FICTÍCIOS.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "saida"
sys.path.insert(0, str(BASE.parent))

import motor_regras as motor  # noqa: E402  (mesmo motor do app.py)

TCC = Namespace("http://example.org/sigamaes/ontologia#")
INST = Namespace("http://example.org/sigamaes/instancias#")
GUFO = Namespace("http://purl.org/nemo/gufo#")

SKILL_CATALOG = motor.SKILL_CATALOG
NAME_TO_CODE = {v: k for k, v in SKILL_CATALOG.items()}

# =====================================================================
# 1. MAPEAMENTO PROTÓTIPO -> ONTOLOGIA (grafo.png)
# =====================================================================

# Resposta do formulário -> literal do enum NivelHabilidade
STATUS_TO_NIVEL = {
    None: "NaoAvaliado",
    "Independente": "Alto",
    "Realiza com auxílio": "Moderado",
    "Não realiza": "Baixo",
}
NIVEL_TO_PESO = {"Alto": 0, "Moderado": 1, "Baixo": 2}

# Item do formulário -> subkind folha. None = instância direta de
# HabilidadeAutocuidado/HabilidadeMotora (genset incompleto).
SUBKIND_DO_ITEM = {
    "AC01": "Alimentacao", "AC02": "HigieneBucal", "AC03": "HigieneBucal",
    "AC04": "HigieneCorporal", "AC05": "HigieneCabelos", "AC06": "HigieneRosto",
    "AC07": "HigieneMaos", "AC08": "Vestuario",
    "AC09": "Calcados",          # validar
    "AC10": "UsoBanheiro",
    "MO01": "Caminhar",
    "MO02": "SubirEscadas",      # validar
}

HABILIDADES_FORA_DO_FORMULARIO = {
    "EX01": ("Correr", "Correr"),
    "EX02": ("Rolar", "Rolar"),
    "EX03": ("Sentar", "Sentar"),
    "EX04": ("Engatinhar", "Engatinhar"),
}

SUBKINDS_AUTOCUIDADO = ["Alimentacao", "HigieneCorporal", "HigieneBucal",
                        "HigieneCabelos", "HigieneRosto", "HigieneMaos",
                        "Vestuario", "Calcados", "UsoBanheiro"]
SUBKINDS_MOTORA = ["Caminhar", "Correr", "SubirEscadas", "Rolar",
                   "Sentar", "Engatinhar"]

ROTULOS = {
    "Pessoa": ("Pessoa", "Person"),
    "Prontuario": ("Prontuário", "Medical Record"),
    "Habilidade": ("Habilidade", "Skill"),
    "HabilidadeAutocuidado": ("Habilidade de Autocuidado", "Self-Care Skill"),
    "HabilidadeMotora": ("Habilidade Motora", "Motor Skill"),
    "Alimentacao": ("Alimentação", "Feeding"),
    "HigieneCorporal": ("Higiene Corporal", "Body Hygiene"),
    "HigieneBucal": ("Higiene Bucal", "Oral Hygiene"),
    "HigieneCabelos": ("Higiene dos Cabelos", "Hair Hygiene"),
    "HigieneRosto": ("Higiene do Rosto", "Face Hygiene"),
    "HigieneMaos": ("Higiene das Mãos", "Hand Hygiene"),
    "Vestuario": ("Vestuário", "Dressing"),
    "Calcados": ("Calçados", "Footwear"),
    "UsoBanheiro": ("Uso do Banheiro", "Toileting"),
    "Caminhar": ("Caminhar", "Walking"),
    "Correr": ("Correr", "Running"),
    "SubirEscadas": ("Subir Escadas", "Climbing Stairs"),
    "Rolar": ("Rolar", "Rolling"),
    "Sentar": ("Sentar", "Sitting"),
    "Engatinhar": ("Engatinhar", "Crawling"),
    "AvaliacaoHabilidade": ("Avaliação de Habilidade", "Skill Assessment"),
    "Tratamento": ("Tratamento", "Treatment"),
    "Recomendacao": ("Recomendação", "Recommendation"),
    "Especialista": ("Especialista", "Specialist"),
    "Conhecimento": ("Conhecimento", "Knowledge"),
    "RelacaoHabilidade": ("Relação entre Habilidades", "Skill Relation"),
    "PreRequisito": ("Pré-requisito", "Prerequisite"),
    "Facilitacao": ("Facilitação", "Facilitation"),
    "Composicao": ("Composição", "Composition"),
    "Inconsistencia": ("Inconsistência", "Inconsistency"),
    "ConhecimentoSimples": ("Conhecimento Simples", "Simple Knowledge"),
    "ConhecimentoComposto": ("Conhecimento Composto", "Composite Knowledge"),
}


def subkind_de(code: str) -> str:
    sub = SUBKIND_DO_ITEM.get(code)
    if sub:
        return sub
    return "HabilidadeAutocuidado" if code.startswith("AC") else "HabilidadeMotora"


# =====================================================================
# 2. CONHECIMENTO ESPECIALISTA
# =====================================================================

ESPECIALISTAS = {
    "esp_TO": "Terapeuta ocupacional (equipe AMAES – fictício)",
    "esp_FISIO": "Fisioterapeuta (equipe AMAES – fictício)",
}

# nome do tratamento (motor_regras) -> metadados do grafo
TRATAMENTOS = {
    "Treino de habilidades de autocuidado": {
        "id": "trat_autocuidado", "conhecimento": "con_autocuidado",
        "especialista": "esp_TO",
        "descricao": "Intervenção voltada às atividades de vida diária: "
                     "alimentação, higiene, vestuário e uso do banheiro.",
    },
    "Treino de habilidades motoras grossas": {
        "id": "trat_motor_grosso", "conhecimento": "con_motor_grosso",
        "especialista": "esp_FISIO",
        "descricao": "Intervenção voltada à locomoção, equilíbrio e atividades com bola.",
    },
    "Treino de habilidades motoras finas": {
        "id": "trat_motor_fino", "conhecimento": "con_motor_fino",
        "especialista": "esp_TO",
        "descricao": "Intervenção voltada à preensão, coordenação visomotora, "
                     "grafomotricidade e manipulação de objetos.",
    },
    motor.INTEGRADA: {
        "id": "trat_integrado", "conhecimento": "con_integrado",
        "especialista": "esp_TO",
        "descricao": "Programa multiprofissional que combina objetivos de "
                     "autocuidado e de desenvolvimento motor.",
    },
}
assert set(TRATAMENTOS) == set(motor.TREATMENTS), "Tratamentos fora de sincronia com motor_regras.py"
ID_TRAT = {nome: d["id"] for nome, d in TRATAMENTOS.items()}
NOME_TRAT = {d["id"]: nome for nome, d in TRATAMENTOS.items()}

# =====================================================================
# 3. PACIENTES FICTÍCIOS (respostas do formulário, por código)
# =====================================================================
I, A, N, B = "Independente", "Realiza com auxílio", "Não realiza", None

PACIENTES = {
    "P001": {
        "nome": "Paciente fictício A", "nascimento": date(2019, 3, 14),
        "prontuario": "PRT-2026-001", "data_avaliacao": date(2026, 9, 15),
        "data_recomendacao": date(2026, 9, 22),
        "perfil": "dificuldades predominantes de autocuidado",
        "respostas": {
            "AC01": A, "AC02": N, "AC03": N, "AC04": A, "AC05": N,
            "AC06": A, "AC07": A, "AC08": N, "AC09": N, "AC10": A,
            "MO01": I, "MO02": I, "MO03": I, "MO04": A, "MO05": I,
            "MO06": I, "MO07": I, "MO08": I, "MO09": A, "MO10": B,
            "MO11": I, "MO12": I, "MO13": A, "MO14": B, "MO15": A,
        },
    },
    "P002": {
        "nome": "Paciente fictício B", "nascimento": date(2020, 8, 2),
        "prontuario": "PRT-2026-002", "data_avaliacao": date(2026, 9, 16),
        "data_recomendacao": date(2026, 9, 23),
        "perfil": "dificuldades predominantes de motricidade fina",
        "respostas": {
            "AC01": A, "AC02": I, "AC03": B, "AC04": I, "AC05": I,
            "AC06": I, "AC07": I, "AC08": A, "AC09": A, "AC10": I,
            "MO01": I, "MO02": I, "MO03": I, "MO04": A, "MO05": I,
            "MO06": N, "MO07": N, "MO08": A, "MO09": N, "MO10": A,
            "MO11": A, "MO12": N, "MO13": N, "MO14": N, "MO15": A,
        },
    },
    "P003": {
        "nome": "Paciente fictício C", "nascimento": date(2018, 11, 20),
        "prontuario": "PRT-2026-003", "data_avaliacao": date(2026, 9, 17),
        "data_recomendacao": date(2026, 9, 24),
        "perfil": "sem dificuldades identificadas (caso controle)",
        "respostas": {c: I for c in SKILL_CATALOG} | {"MO10": B, "MO14": B},
    },
    "P004": {
        "nome": "Paciente fictício D", "nascimento": date(2019, 6, 5),
        "prontuario": "PRT-2026-004", "data_avaliacao": date(2026, 9, 18),
        "data_recomendacao": date(2026, 9, 25),
        "perfil": "dificuldades distribuídas entre autocuidado e motricidade fina",
        "respostas": {c: I for c in SKILL_CATALOG} | {
            "AC02": A, "AC03": N, "AC05": N, "AC08": A, "AC09": N,
            "MO04": A, "MO06": A, "MO09": N, "MO12": A, "MO13": N, "MO14": A,
        },
    },
    "P005": {
        "nome": "Paciente fictício E", "nascimento": date(2020, 1, 30),
        "prontuario": "PRT-2026-005", "data_avaliacao": date(2026, 9, 19),
        "data_recomendacao": date(2026, 9, 26),
        "perfil": "formulário com respostas inconsistentes",
        "respostas": {c: I for c in SKILL_CATALOG} | {
            "MO06": N, "AC02": I,                 # sem pinça, mas escova sozinho
            "AC09": N, "AC08": I,                 # sem fechos, mas veste-se sozinho
            "MO03": A, "MO01": I,                 # equilíbrio com auxílio, anda sozinho
            "AC01": A, "AC03": A, "AC05": A, "MO04": A,
            "MO07": A, "MO08": A, "MO09": N, "MO10": N, "MO11": A,
            "MO12": N, "MO13": N, "MO14": N, "MO15": A,
        },
    },
}


def respostas_por_nome(pid: str) -> dict:
    return {SKILL_CATALOG[c]: s for c, s in PACIENTES[pid]["respostas"].items()}


def prioridade_por_posicao(pos: int) -> str:
    """NivelPrioridade: 1º indicado = Alta, 2º = Media, demais = Baixa."""
    return {1: "Alta", 2: "Media"}.get(pos, "Baixa")


# =====================================================================
# 4. TBOX — ontologia do grafo.png em gUFO/OWL
# =====================================================================


def construir_tbox(g: Graph) -> None:
    ont = URIRef("http://example.org/sigamaes/ontologia")
    g.add((ont, RDF.type, OWL.Ontology))
    g.add((ont, RDFS.label, Literal("Ontologia SIGAMAES – recomendação de "
                                    "tratamentos para pessoas com TEA", lang="pt-br")))
    g.add((ont, RDFS.comment, Literal(
        "Tradução em gUFO do modelo OntoUML grafo.png/grafo.tonto. Elementos "
        "anotados com tcc:extensaoProposta=true não existem no diagrama "
        "original (ver grafo.corrigido.tonto).", lang="pt-br")))
    g.add((TCC.extensaoProposta, RDF.type, OWL.AnnotationProperty))

    def classe(nome, estereotipo, super_=None, gufo_super=None, extensao=False):
        c = TCC[nome]
        g.add((c, RDF.type, OWL.Class))
        g.add((c, RDF.type, GUFO[estereotipo]))
        pt, en = ROTULOS[nome]
        g.add((c, RDFS.label, Literal(pt, lang="pt-br")))
        g.add((c, RDFS.label, Literal(en, lang="en")))
        if super_:
            g.add((c, RDFS.subClassOf, TCC[super_]))
        if gufo_super:
            g.add((c, RDFS.subClassOf, GUFO[gufo_super]))
        if extensao:
            g.add((c, TCC.extensaoProposta, Literal(True)))

    for k in ["Pessoa", "Prontuario", "Habilidade", "Tratamento", "Especialista"]:
        classe(k, "Kind", gufo_super="FunctionalComplex")
    classe("HabilidadeAutocuidado", "SubKind", "Habilidade")
    classe("HabilidadeMotora", "SubKind", "Habilidade")
    for s in SUBKINDS_AUTOCUIDADO:
        classe(s, "SubKind", "HabilidadeAutocuidado")
    for s in SUBKINDS_MOTORA:
        classe(s, "SubKind", "HabilidadeMotora")
    for r in ["AvaliacaoHabilidade", "Recomendacao", "Conhecimento"]:
        classe(r, "Kind", gufo_super="Relator")
    classe("RelacaoHabilidade", "Kind", gufo_super="Relator", extensao=True)
    for tipo in motor.RELATION_TYPES:
        classe(tipo, "SubKind", "RelacaoHabilidade", extensao=True)
    tipos = list(motor.RELATION_TYPES)
    for i, a in enumerate(tipos):
        for b in tipos[i + 1:]:
            g.add((TCC[a], OWL.disjointWith, TCC[b]))
    classe("Inconsistencia", "Kind", gufo_super="Relator", extensao=True)
    classe("ConhecimentoSimples", "SubKind", "Conhecimento", extensao=True)
    classe("ConhecimentoComposto", "SubKind", "Conhecimento", extensao=True)
    g.add((TCC.ConhecimentoSimples, OWL.disjointWith, TCC.ConhecimentoComposto))

    for grupo in (["HabilidadeAutocuidado", "HabilidadeMotora"],
                  SUBKINDS_AUTOCUIDADO, SUBKINDS_MOTORA):
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                g.add((TCC[a], OWL.disjointWith, TCC[b]))

    for enum, valores in {"NivelHabilidade": ["NaoAvaliado", "Baixo", "Moderado", "Alto"],
                          "NivelPrioridade": ["Baixa", "Media", "Alta"],
                          "NivelInconsistencia": ["Moderada", "Alta"]}.items():
        g.add((TCC[enum], RDF.type, RDFS.Datatype))
        g.add((TCC[enum], RDFS.comment,
               Literal("Valores permitidos: " + ", ".join(valores), lang="pt-br")))

    def objprop(nome, dominio, alcance, mediacao=True, extensao=False, com=None):
        p = TCC[nome]
        g.add((p, RDF.type, OWL.ObjectProperty))
        g.add((p, RDFS.domain, TCC[dominio]))
        g.add((p, RDFS.range, TCC[alcance]))
        g.add((p, RDFS.label, Literal(nome)))
        if mediacao:
            g.add((p, RDFS.subPropertyOf, GUFO.mediates))
        if extensao:
            g.add((p, TCC.extensaoProposta, Literal(True)))
        if com:
            g.add((p, RDFS.comment, Literal(com, lang="pt-br")))

    objprop("pertenceA", "AvaliacaoHabilidade", "Pessoa")
    objprop("avalia", "AvaliacaoHabilidade", "Habilidade")
    objprop("destinadaA", "Recomendacao", "Pessoa")
    objprop("recomenda", "Recomendacao", "Tratamento")
    objprop("baseadaEm", "Recomendacao", "AvaliacaoHabilidade")
    objprop("aplica", "Especialista", "Conhecimento", mediacao=False)
    objprop("podeIndicar", "Conhecimento", "Tratamento")
    objprop("refereSe", "ConhecimentoSimples", "Habilidade", extensao=True,
            com="Habilidades cuja dificuldade pontua o tratamento (R1).")
    objprop("requer", "ConhecimentoComposto", "ConhecimentoSimples", mediacao=False, extensao=True,
            com="Conhecimento composto: indica o tratamento quando os conhecimentos "
                "requeridos atingem o limiar (R5 – intervenção integrada).")
    objprop("origem", "RelacaoHabilidade", "Habilidade", extensao=True,
            com="Pré-requisito: a habilidade necessária. Composição: a parte. "
                "Facilitação: a habilidade que facilita.")
    objprop("destino", "RelacaoHabilidade", "Habilidade", extensao=True,
            com="Pré-requisito: a habilidade dependente. Composição: o todo. "
                "Facilitação: a habilidade facilitada.")
    objprop("inconsistenciaDe", "Inconsistencia", "Pessoa", extensao=True)
    objprop("avaliacaoOrigem", "Inconsistencia", "AvaliacaoHabilidade", extensao=True)
    objprop("avaliacaoDestino", "Inconsistencia", "AvaliacaoHabilidade", extensao=True)
    objprop("violaRelacao", "Inconsistencia", "RelacaoHabilidade", extensao=True,
            com="Relação de pré-requisito ou composição contrariada pelas respostas (R7).")
    objprop("registra", "Prontuario", "Pessoa", mediacao=False, extensao=True)

    def dataprop(nome, alcance, com, extensao=False):
        p = TCC[nome]
        g.add((p, RDF.type, OWL.DatatypeProperty))
        g.add((p, RDFS.range, alcance))
        g.add((p, RDFS.label, Literal(nome)))
        g.add((p, RDFS.comment, Literal(com, lang="pt-br")))
        if extensao:
            g.add((p, TCC.extensaoProposta, Literal(True)))

    dataprop("nome", XSD.string, "Atributo de Pessoa, Habilidade e Tratamento")
    dataprop("dataDeNascimento", XSD.date, "Atributo de Pessoa")
    dataprop("identificador", XSD.string, "Atributo de Prontuario")
    dataprop("dataAvaliacao", XSD.date, "Atributo de AvaliacaoHabilidade")
    dataprop("nivel", XSD.string, "AvaliacaoHabilidade; valores de NivelHabilidade")
    dataprop("dataRecomendacao", XSD.date, "Atributo de Recomendacao")
    dataprop("justificativa", XSD.string, "Atributo de Recomendacao (R4)")
    dataprop("prioridade", XSD.string, "Recomendacao; valores de NivelPrioridade")
    dataprop("pontuacao", XSD.decimal, "Recomendacao; pontuação normalizada 0–1 (R3/R5)",
             extensao=True)
    dataprop("limiarIndicacao", XSD.decimal,
             "Conhecimento; pontuação mínima para indicar (R6) ou, no "
             "conhecimento composto, para cada conhecimento requerido (R5)", extensao=True)
    dataprop("minimoRequeridos", XSD.integer,
             "Conhecimento composto; quantos requeridos devem atingir o limiar (R5)",
             extensao=True)
    dataprop("pesoIndireto", XSD.decimal, "RelacaoHabilidade (R2)", extensao=True)
    dataprop("itemIPO", XSD.string,
             "Habilidade; item do Inventário Portage Operacionalizado e faixa etária",
             extensao=True)
    dataprop("idadeInicialIPO", XSD.integer,
             "Habilidade; limite inferior da faixa etária do primeiro item no IPO",
             extensao=True)
    dataprop("fundamentacao", XSD.string,
             "RelacaoHabilidade; justificativa com base nos itens do IPO", extensao=True)
    dataprop("evidencia", XSD.string,
             "RelacaoHabilidade; tipo de evidência (conteúdo do item, sequência etária, funcional)",
             extensao=True)
    dataprop("statusValidacao", XSD.string, "RelacaoHabilidade", extensao=True)
    dataprop("severidade", XSD.string, "Inconsistencia; valores de NivelInconsistencia",
             extensao=True)
    dataprop("descricao", XSD.string, "Atributo de Tratamento e Inconsistencia")


# =====================================================================
# 5. ABOX — instâncias
# =====================================================================


def hab_iri(code: str) -> URIRef:
    return INST[f"hab_{code}"]


def dec(x) -> Literal:
    return Literal(Decimal(str(round(float(x), 4))), datatype=XSD.decimal)


def construir_abox(g: Graph) -> dict:
    lbl = lambda s, t: g.add((s, RDFS.label, Literal(t, lang="pt-br")))

    # --- Habilidades -------------------------------------------------
    for code, nome in SKILL_CATALOG.items():
        h = hab_iri(code)
        g.add((h, RDF.type, TCC[subkind_de(code)]))
        g.add((h, RDF.type, OWL.NamedIndividual))
        g.add((h, TCC.nome, Literal(nome)))
        ipo = motor.SKILL_IPO[nome]
        for item in ipo["itens"]:
            g.add((h, TCC.itemIPO, Literal(item)))
        if ipo["idade_inicial"] is not None:
            g.add((h, TCC.idadeInicialIPO, Literal(ipo["idade_inicial"], datatype=XSD.integer)))
        if ipo["observacao"]:
            g.add((h, RDFS.comment, Literal(ipo["observacao"], lang="pt-br")))
        lbl(h, f"{code} – {nome}")
    for code, (sub, nome) in HABILIDADES_FORA_DO_FORMULARIO.items():
        h = hab_iri(code)
        g.add((h, RDF.type, TCC[sub]))
        g.add((h, RDF.type, OWL.NamedIndividual))
        g.add((h, TCC.nome, Literal(nome)))
        g.add((h, RDFS.comment, Literal("Subkind da ontologia ainda não presente "
                                        "no formulário do protótipo.", lang="pt-br")))
        lbl(h, f"{code} – {nome}")

    # --- Dependências -------------------------------------------------
    for rel in motor.RELATIONS:
        d = INST[f"rel_{rel['id']}"]
        g.add((d, RDF.type, TCC[rel["tipo"]]))
        g.add((d, TCC.origem, hab_iri(NAME_TO_CODE[rel["origem"]])))
        g.add((d, TCC.destino, hab_iri(NAME_TO_CODE[rel["destino"]])))
        g.add((d, TCC.pesoIndireto, dec(rel["peso"])))
        g.add((d, TCC.fundamentacao, Literal(rel["justificativa"])))
        g.add((d, TCC.evidencia, Literal(rel["evidencia"])))
        g.add((d, TCC.statusValidacao, Literal(rel["status"])))
        lbl(d, f"{rel['id']}: {rel['origem']} "
               f"{motor.RELATION_TYPES[rel['tipo']]['verbo']} {rel['destino']}")

    # --- Especialistas, tratamentos e conhecimento -------------------
    for e, nome in ESPECIALISTAS.items():
        g.add((INST[e], RDF.type, TCC.Especialista))
        lbl(INST[e], nome)
    for nome, meta in TRATAMENTOS.items():
        regra = motor.TREATMENTS[nome]
        ti = INST[meta["id"]]
        g.add((ti, RDF.type, TCC.Tratamento))
        g.add((ti, TCC.nome, Literal(nome)))
        g.add((ti, TCC.descricao, Literal(meta["descricao"])))
        lbl(ti, nome)
        k = INST[meta["conhecimento"]]
        g.add((k, RDF.type, TCC.ConhecimentoComposto if regra["type"] == "integrado"
               else TCC.ConhecimentoSimples))
        g.add((INST[meta["especialista"]], TCC.aplica, k))
        g.add((k, TCC.podeIndicar, ti))
        if regra["type"] == "integrado":
            for outro in regra["combines"]:
                g.add((k, TCC.requer, INST[TRATAMENTOS[outro]["conhecimento"]]))
            g.add((k, TCC.limiarIndicacao, dec(motor.LIMIAR_INTEGRADA)))
            g.add((k, TCC.minimoRequeridos,
                   Literal(motor.MIN_TRATAMENTOS_INTEGRADA, datatype=XSD.integer)))
            lbl(k, f"Indica {nome} quando ≥ {motor.MIN_TRATAMENTOS_INTEGRADA} "
                   f"conhecimentos requeridos atingem {motor.LIMIAR_INTEGRADA:.0%} (R5)")
        else:
            for skill in regra["skills"]:
                g.add((k, TCC.refereSe, hab_iri(NAME_TO_CODE[skill])))
            g.add((k, TCC.limiarIndicacao, dec(motor.LIMIAR_MINIMO)))
            lbl(k, f"Dificuldade nas habilidades-alvo indica {nome} "
                   f"(a partir de {motor.LIMIAR_MINIMO:.0%})")

    # --- Pacientes, prontuários, avaliações e recomendações ----------
    resultados = {}
    for pid, p in PACIENTES.items():
        pe = INST[f"pessoa_{pid}"]
        g.add((pe, RDF.type, TCC.Pessoa))
        g.add((pe, TCC.nome, Literal(p["nome"])))
        g.add((pe, TCC.dataDeNascimento, Literal(p["nascimento"], datatype=XSD.date)))
        lbl(pe, f"{p['nome']} ({pid})")

        pr = INST[f"prontuario_{pid}"]
        g.add((pr, RDF.type, TCC.Prontuario))
        g.add((pr, TCC.identificador, Literal(p["prontuario"])))
        g.add((pr, TCC.registra, pe))
        lbl(pr, f"Prontuário {p['prontuario']}")

        for code in SKILL_CATALOG:
            av = INST[f"aval_{pid}_{code}"]
            nivel = STATUS_TO_NIVEL[p["respostas"][code]]
            g.add((av, RDF.type, TCC.AvaliacaoHabilidade))
            g.add((av, TCC.pertenceA, pe))
            g.add((av, TCC.avalia, hab_iri(code)))
            g.add((av, TCC.dataAvaliacao, Literal(p["data_avaliacao"], datatype=XSD.date)))
            g.add((av, TCC.nivel, Literal(nivel)))
            lbl(av, f"Avaliação {pid}/{code}: {nivel}")

        for item in motor.detect_inconsistencies(respostas_por_nome(pid)):
            rel = item["relation"]
            inc = INST[f"inc_{pid}_{rel['id']}"]
            g.add((inc, RDF.type, TCC.Inconsistencia))
            g.add((inc, TCC.inconsistenciaDe, pe))
            g.add((inc, TCC.avaliacaoOrigem, INST[f"aval_{pid}_{NAME_TO_CODE[item['origem']]}"]))
            g.add((inc, TCC.avaliacaoDestino, INST[f"aval_{pid}_{NAME_TO_CODE[item['destino']]}"]))
            g.add((inc, TCC.violaRelacao, INST[f"rel_{rel['id']}"]))
            g.add((inc, TCC.severidade, Literal(item["severity"])))
            g.add((inc, TCC.descricao, Literal(item["message"])))
            lbl(inc, f"Inconsistência {pid}/{rel['id']} ({item['severity']})")

        ranking = motor.calculate_recommendations(respostas_por_nome(pid))
        resultados[pid] = ranking
        indicados = [r for r in ranking if r["indicated"]]
        for pos, r in enumerate(indicados, start=1):
            rec = INST[f"rec_{pid}_{pos}"]
            g.add((rec, RDF.type, TCC.Recomendacao))
            g.add((rec, TCC.destinadaA, pe))
            g.add((rec, TCC.recomenda, INST[ID_TRAT[r["treatment"]]]))
            g.add((rec, TCC.dataRecomendacao,
                   Literal(p["data_recomendacao"], datatype=XSD.date)))
            g.add((rec, TCC.prioridade, Literal(prioridade_por_posicao(pos))))
            g.add((rec, TCC.pontuacao, dec(r["score"])))
            for skill in sorted(r["contributions"]):
                g.add((rec, TCC.baseadaEm, INST[f"aval_{pid}_{NAME_TO_CODE[skill]}"]))
            if r["type"] == "integrado":
                just = (f"{pos}º de {len(indicados)} indicados; pontuação "
                        f"{r['score']:.1%} (R5, menor pontuação entre os tratamentos "
                        f"combinados). " + "; ".join(r["explanations"]) + ".")
            else:
                just = (f"{pos}º de {len(indicados)} indicados; pontuação "
                        f"{r['score']:.1%} = {r['raw']:g}/{r['max']:g} (R3). "
                        f"Contribuições R1/R2: " + "; ".join(r["explanations"]) + ".")
            g.add((rec, TCC.justificativa, Literal(just)))
            lbl(rec, f"Recomendação {pid} nº{pos}: {r['treatment']}")
    return resultados


# =====================================================================
# 6. CONFERÊNCIA INDEPENDENTE POR SPARQL
#    Recalcula R1–R3 só com o que está no grafo; R5/R6 usam os limiares
#    gravados nos nós Conhecimento.
# =====================================================================

SPARQL_SOMA_E_MAXIMO = """
PREFIX tcc: <http://example.org/sigamaes/ontologia#>
SELECT ?pessoa ?trat (SUM(?pts) AS ?soma) (SUM(?mx) AS ?maximo) WHERE {
  ?av tcc:pertenceA ?pessoa ; tcc:avalia ?h ; tcc:nivel ?n .
  FILTER (?n != "NaoAvaliado")
  VALUES (?n ?w) { ("Baixo" 2) ("Moderado" 1) ("Alto" 0) }
  {
    ?k tcc:refereSe ?h ; tcc:podeIndicar ?trat .               # R1 (fator 1)
    BIND(1 AS ?f)
  } UNION {
    ?d tcc:origem ?h ; tcc:destino ?h2 ; tcc:pesoIndireto ?f .
    ?k tcc:refereSe ?h2 ; tcc:podeIndicar ?trat .              # R2 (fator = peso indireto)
  }
  BIND(?w * ?f AS ?pts)
  BIND(2 * ?f AS ?mx)
} GROUP BY ?pessoa ?trat
"""

SPARQL_CONHECIMENTO = """
PREFIX tcc: <http://example.org/sigamaes/ontologia#>
SELECT ?trat ?limiar ?minimo ?requerido WHERE {
  ?k tcc:podeIndicar ?trat ; tcc:limiarIndicacao ?limiar .
  OPTIONAL { ?k tcc:minimoRequeridos ?minimo ; tcc:requer/tcc:podeIndicar ?requerido . }
}
"""


SPARQL_INCONSISTENCIAS = """
PREFIX tcc: <http://example.org/sigamaes/ontologia#>
SELECT ?pessoa ?rel ?sev WHERE {
  { ?rel a tcc:PreRequisito } UNION { ?rel a tcc:Composicao }
  ?rel tcc:origem ?ho ; tcc:destino ?hd .
  ?ao tcc:avalia ?ho ; tcc:pertenceA ?pessoa ; tcc:nivel ?no .
  ?ad tcc:avalia ?hd ; tcc:pertenceA ?pessoa ; tcc:nivel "Alto" .
  VALUES (?no ?sev) { ("Baixo" "Alta") ("Moderado" "Moderada") }
}
"""


def conferir_por_sparql(g: Graph) -> dict:
    """Retorna {(pid, trat_id): (pontuacao, indicado)} calculado só pelo grafo."""
    especificos, compostos = {}, {}
    for r in g.query(SPARQL_CONHECIMENTO):
        t = str(r.trat).split("#")[-1]
        if r.minimo is None:
            especificos[t] = float(r.limiar)
        else:
            c = compostos.setdefault(t, {"limiar": float(r.limiar),
                                         "minimo": int(r.minimo), "req": []})
            c["req"].append(str(r.requerido).split("#")[-1])
    soma = {}
    for r in g.query(SPARQL_SOMA_E_MAXIMO):
        pid = str(r.pessoa).split("_")[-1]
        t = str(r.trat).split("#")[-1]
        soma[(pid, t)] = (float(r.soma), float(r.maximo))
    out = {}
    for pid in PACIENTES:
        for t, limiar in especificos.items():
            s, m = soma.get((pid, t), (0.0, 0.0))
            score = s / m if m else 0.0
            out[(pid, t)] = (score, score >= limiar and s > 0)
        for t, c in compostos.items():
            passam = [out[(pid, r)][0] for r in c["req"] if out[(pid, r)][0] >= c["limiar"]]
            ok = len(passam) >= c["minimo"]
            out[(pid, t)] = (min(passam) if ok else 0.0, ok)
    return out


# =====================================================================
# 7. VISUALIZAÇÕES (Graphviz)
# =====================================================================
COR = {"kind": "#FF9AA2", "subkind": "#FFD9DD", "relator": "#9CF59C",
       "Alto": "#BBF7D0", "Moderado": "#FEF08A", "Baixo": "#FECACA",
       "NaoAvaliado": "#E5E7EB"}


def q(s):
    return '"' + str(s).replace('"', '\\"') + '"'


def dot_camada_conhecimento() -> str:
    L = ["digraph conhecimento {",
         '  graph [rankdir=LR, compound=true, fontname="Helvetica", nodesep=0.18, ranksep=1.0, '
         'label="Grafo de conhecimento — camada especialista (Especialista → Conhecimento → '
         'Tratamento / Habilidade)", labelloc=t, fontsize=18];',
         '  node [fontname="Helvetica", fontsize=10, style="filled,rounded", shape=box, color="#555555"];',
         '  edge [fontname="Helvetica", fontsize=8, color="#666666"];']
    for e, n in ESPECIALISTAS.items():
        L.append(f'  {e} [label={q("«Especialista»\\n" + n.split(" (")[0])}, fillcolor="{COR["kind"]}"];')
    for nome, meta in TRATAMENTOS.items():
        k, t = meta["conhecimento"], meta["id"]
        regra = motor.TREATMENTS[nome]
        if regra["type"] == "integrado":
            extra = (f"\\nrequer ≥ {motor.MIN_TRATAMENTOS_INTEGRADA} com ≥ "
                     f"{motor.LIMIAR_INTEGRADA:.0%} (R5)")
        else:
            extra = f"\\nlimiar {motor.LIMIAR_MINIMO:.0%} (R6)"
        tipo = "ConhecimentoComposto" if regra["type"] == "integrado" else "ConhecimentoSimples"
        L.append(f'  {k} [label={q("«" + tipo + "»\\n" + k + extra)}, fillcolor="{COR["relator"]}"];')
        L.append(f'  {t} [label={q("«Tratamento»\\n" + nome)}, fillcolor="{COR["kind"]}", penwidth=2];')
        L.append(f'  {meta["especialista"]} -> {k} [label="aplica"];')
        L.append(f'  {k} -> {t} [label="podeIndicar", color="#166534", penwidth=1.6];')
        if regra["type"] == "integrado":
            for outro in regra["combines"]:
                L.append(f'  {k} -> {TRATAMENTOS[outro]["conhecimento"]} [label="requer", '
                         'color="#7C3AED", fontcolor="#7C3AED", penwidth=1.6];')

    grupos = [("autocuidado", "Habilidades de autocuidado (formulário)",
               "Treino de habilidades de autocuidado"),
              ("grosso", "Habilidades motoras grossas (formulário)",
               "Treino de habilidades motoras grossas"),
              ("fino", "Habilidades motoras finas (formulário)",
               "Treino de habilidades motoras finas")]
    for gid, titulo, trat in grupos:
        L.append(f'  subgraph cluster_{gid} {{ label={q(titulo)}; style="rounded,dashed"; '
                 'color="#999999"; fontsize=11;')
        skills = motor.TREATMENTS[trat]["skills"]
        for s in skills:
            c = NAME_TO_CODE[s]
            idade = motor.SKILL_IPO[s]["idade_inicial"]
            ipo = f"\\nIPO desde {idade}-{idade + 1} anos" if idade is not None else "\\nsem item no IPO"
            L.append(f'    hab_{c} [label={q(c + " – " + s + "\\n«" + subkind_de(c) + "»" + ipo)}, '
                     f'fillcolor="{COR["subkind"]}"];')
        L.append("  }")
        ancora = NAME_TO_CODE[skills[len(skills) // 2]]
        L.append(f'  {TRATAMENTOS[trat]["conhecimento"]} -> hab_{ancora} [lhead=cluster_{gid}, '
                 'label="refereSe (todas)", style=dashed, color="#2563EB", fontcolor="#2563EB"];')
    L.append('  subgraph cluster_extra { label="Subkinds sem item no formulário"; '
             'style="rounded,dotted"; color="#999999"; fontsize=11;')
    for c, (sub, nome) in HABILIDADES_FORA_DO_FORMULARIO.items():
        L.append(f'    hab_{c} [label={q(c + " – " + nome + "\\n«" + sub + "»")}, '
                 f'fillcolor="{COR["subkind"]}"];')
    L.append("  }")
    estilo = {
        "PreRequisito": 'color="#DC2626", fontcolor="#DC2626", penwidth=1.4',
        "Composicao": 'color="#7C3AED", fontcolor="#7C3AED", penwidth=1.4, '
                      'arrowhead=diamond',
        "Facilitacao": 'color="#D97706", fontcolor="#D97706", style=dashed',
    }
    for rel in motor.RELATIONS:
        L.append(f'  hab_{NAME_TO_CODE[rel["origem"]]} -> hab_{NAME_TO_CODE[rel["destino"]]} '
                 f'[label="{rel["id"]}", {estilo[rel["tipo"]]}, constraint=false, fontsize=7];')
    L.append('  legrel [shape=note, fillcolor="#FFFFFF", fontsize=9, label="Relações (IPO):\\l'
             '— vermelho: pré-requisito (PR)\\l◆ roxo: composição (CO), losango no lado do todo\\l'
             '- - laranja: facilitação (FA)\\l"];')
    L.append("}")
    return "\n".join(L)


def dot_relacoes() -> str:
    """Somente as relações entre as 25 habilidades (pré-requisito, composição, facilitação)."""
    L = ["digraph relacoes {",
         '  graph [rankdir=LR, fontname="Helvetica", nodesep=0.25, ranksep=0.9, newrank=true, '
         'label="Relações entre habilidades derivadas do Inventário Portage Operacionalizado (IPO)", '
         'labelloc=t, fontsize=18];',
         '  node [fontname="Helvetica", fontsize=10, style="filled,rounded", shape=box, color="#555555"];',
         '  edge [fontname="Helvetica", fontsize=8];']
    grupos = [("autocuidado", "Autocuidado", "#FFE4E6", "Treino de habilidades de autocuidado"),
              ("grosso", "Motor grosso", "#E0F2FE", "Treino de habilidades motoras grossas"),
              ("fino", "Motor fino", "#EDE9FE", "Treino de habilidades motoras finas")]
    for gid, titulo, cor, trat in grupos:
        L.append(f'  subgraph cluster_{gid} {{ label={q(titulo)}; style="rounded,dashed"; '
                 'color="#999999"; fontsize=12;')
        for skill in motor.TREATMENTS[trat]["skills"]:
            c = NAME_TO_CODE[skill]
            ipo = motor.SKILL_IPO[skill]
            itens = ", ".join(ipo["itens"][:3]) + (" …" if len(ipo["itens"]) > 3 else "")
            L.append(f'    hab_{c} [label={q(skill + "\\n" + (itens or "sem item no IPO"))}, '
                     f'fillcolor="{cor}"];')
        L.append("  }")
    estilo = {
        "PreRequisito": 'color="#DC2626", fontcolor="#DC2626", penwidth=1.6',
        "Composicao": 'color="#7C3AED", fontcolor="#7C3AED", penwidth=1.8, arrowhead=diamond',
        "Facilitacao": 'color="#D97706", fontcolor="#D97706", style=dashed, constraint=false',
    }
    for rel in motor.RELATIONS:
        L.append(f'  hab_{NAME_TO_CODE[rel["origem"]]} -> hab_{NAME_TO_CODE[rel["destino"]]} '
                 f'[label="{rel["id"]}", {estilo[rel["tipo"]]}];')
    L.append('  leg [shape=note, fillcolor="#FFFFFF", fontsize=10, label="Legenda\\l'
             '— vermelho (PR): pré-requisito — origem é condição para o destino\\l'
             '◆ roxo (CO): composição — origem é parte do destino (losango no todo)\\l'
             '- - laranja (FA): facilitação — origem favorece o destino\\l'
             'Itens: A = Autocuidados, M = Desenvolvimento Motor (faixa etária)\\l"];')
    L.append("}")
    return "\n".join(L)


def dot_paciente(pid: str, ranking) -> str:
    """Tratamento <- Recomendação -> Avaliação -> Habilidade."""
    p = PACIENTES[pid]
    titulo = f"Grafo de conhecimento instanciado — {pid} ({p['perfil']})"
    L = [f"digraph paciente_{pid} {{",
         '  graph [rankdir=LR, compound=true, fontname="Helvetica", nodesep=0.10, ranksep=1.3, '
         f'newrank=true, label={q(titulo)}, labelloc=t, fontsize=18];',
         '  node [fontname="Helvetica", fontsize=10, style="filled,rounded", shape=box, color="#555555"];',
         '  edge [fontname="Helvetica", fontsize=8, color="#888888"];',
         f'  pessoa [label={q("«Pessoa»\\n" + p["nome"] + "\\nnasc. " + p["nascimento"].isoformat())}, '
         f'fillcolor="{COR["kind"]}", penwidth=2];',
         f'  prontuario [label={q("«Prontuário»\\n" + p["prontuario"])}, fillcolor="{COR["kind"]}"];',
         '  prontuario -> pessoa [label="registra"];']
    com, sem = [], []
    for code in SKILL_CATALOG:
        nivel = STATUS_TO_NIVEL[p["respostas"][code]]
        (com if NIVEL_TO_PESO.get(nivel, 0) > 0 else sem).append(code)

    def bloco(cid, titulo, codes):
        if not codes:
            return
        L.append(f'  subgraph cluster_{cid} {{ label={q(titulo)}; style="rounded,dashed"; '
                 'color="#999999"; fontsize=11;')
        for code in codes:
            nivel = STATUS_TO_NIVEL[p["respostas"][code]]
            L.append(f'    av_{code} [label={q("«Avaliação» " + code + "  nivel = " + nivel)}, '
                     f'fillcolor="{COR[nivel]}", fontsize=9];')
        L.append("  }")
        meio = codes[len(codes) // 2]
        L.append(f'  av_{meio} -> pessoa [ltail=cluster_{cid}, '
                 f'label={q(f"pertenceA ({len(codes)} avaliações)")}, '
                 'color="#9CA3AF", style=bold, constraint=false];')

    bloco("com", f"Avaliações com dificuldade (nivel Baixo/Moderado) — {len(com)}", com)
    bloco("sem", f"Avaliações sem dificuldade ou não avaliadas — {len(sem)}", sem)
    for code in com + sem:
        L.append(f'  hab_{code} [label={q(SKILL_CATALOG[code] + "  «" + subkind_de(code) + "»")}, '
                 f'fillcolor="{COR["subkind"]}", fontsize=9];')
        L.append(f'  av_{code} -> hab_{code} [label="avalia", fontsize=7];')

    indicados = [r for r in ranking if r["indicated"]]
    nao = [r for r in ranking if not r["indicated"]]
    if not indicados:
        L.append('  semind [label="Nenhuma Recomendação instanciada\\n(nenhum tratamento atingiu '
                 f'{motor.LIMIAR_MINIMO:.0%}: sem indicação suficiente — R6)", '
                 'fillcolor="#F3F4F6", shape=note];')
        L.append('  pessoa -> semind [style=dotted, arrowhead=none, constraint=false];')
    cores = ["#166534", "#2563EB", "#7C3AED", "#B45309"]
    L.append("  { rank=same; pessoa; prontuario; }")
    for pos, r in enumerate(indicados, start=1):
        t = ID_TRAT[r["treatment"]]
        cor = cores[(pos - 1) % 4]
        regra = "R5" if r["type"] == "integrado" else "R3"
        rotulo = (f"«Recomendação» nº{pos}\\nprioridade = {prioridade_por_posicao(pos)}"
                  f"\\npontuacao = {r['score']:.1%} ({regra})")
        L.append(f'  rec{pos} [label={q(rotulo)}, fillcolor="{COR["relator"]}", '
                 f'penwidth=2.2, color="{cor}"];')
        L.append(f'  {t} [label={q("«Tratamento»\\n" + r["treatment"])}, fillcolor="{COR["kind"]}", '
                 f'color="{cor}", penwidth=2];')
        L.append(f'  {t} -> rec{pos} [dir=back, label="recomenda", color="{cor}", '
                 f'fontcolor="{cor}", penwidth=2];')
        L.append(f'  rec{pos} -> pessoa [label="destinadaA", color="{cor}", fontcolor="{cor}", '
                 'style=dotted, constraint=false];')
        for skill in sorted(r["contributions"]):
            L.append(f'  rec{pos} -> av_{NAME_TO_CODE[skill]} [color="{cor}", arrowsize=0.5, penwidth=0.9];')
    if nao:
        linhas = "\\l".join(
            f"{r['treatment']}: " + (f"{r['score']:.1%}" if r["type"] != "integrado"
                                     else "R5 não satisfeita") for r in nao)
        L.append(f'  naoind [shape=note, fillcolor="#F9FAFB", fontsize=9, '
                 f'label={q("Não indicados (sem Recomendação):\\l" + linhas + "\\l")}];')
        L.append("  { rank=same; naoind; prontuario; }")
    for item in motor.detect_inconsistencies(respostas_por_nome(pid)):
        rel = item["relation"]
        cor = "#DC2626" if item["severity"] == "Alta" else "#D97706"
        nid = f"inc_{rel['id']}"
        rotulo = (f"«Inconsistência» {item['severity']}\\nviolaRelacao {rel['id']} "
                  f"({motor.RELATION_TYPES[rel['tipo']]['label']})")
        L.append(f'  {nid} [label={q(rotulo)}, shape=box, style="filled,rounded,bold", '
                 f'fillcolor="#FFF1F2", color="{cor}", fontcolor="{cor}", fontsize=9];')
        for papel, skill in (("avaliacaoOrigem", item["origem"]), ("avaliacaoDestino", item["destino"])):
            L.append(f'  {nid} -> av_{NAME_TO_CODE[skill]} [label="{papel}", color="{cor}", '
                     f'fontcolor="{cor}", style=bold, fontsize=7];')
    L.append('  leg [shape=note, fillcolor="#FFFFFF", fontsize=9, label="Arestas coloridas '
             'Recomendação → Avaliação = baseadaEm\\nCores das avaliações: vermelho = Baixo, '
             'amarelo = Moderado,\\nverde = Alto, cinza = NaoAvaliado"];')
    L.append("  { rank=same; leg; prontuario; }")
    L.append("}")
    return "\n".join(L)


def renderizar(nome: str, dot_src: str) -> None:
    caminho = SAIDA / f"{nome}.dot"
    caminho.write_text(dot_src, encoding="utf-8")
    if shutil.which("dot") is None:
        print(f"  (Graphviz não encontrado: apenas {caminho.name} foi gerado)")
        return
    for fmt in ("png", "svg"):
        extra = ["-Gdpi=150"] if fmt == "png" else []
        subprocess.run(["dot", f"-T{fmt}", *extra, str(caminho), "-o",
                        str(SAIDA / f"{nome}.{fmt}")], check=True)


# =====================================================================
# 8. EXECUÇÃO
# =====================================================================


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    for antigo in SAIDA.glob("grafo_paciente_*"):
        antigo.unlink()
    g = Graph()
    for pfx, ns in (("tcc", TCC), ("inst", INST), ("gufo", GUFO),
                    ("owl", OWL), ("rdfs", RDFS), ("xsd", XSD)):
        g.bind(pfx, ns)
    construir_tbox(g)
    resultados = construir_abox(g)
    ttl = SAIDA / "grafo_conhecimento.ttl"
    g.serialize(ttl, format="turtle", encoding="utf-8")
    print(f"Grafo salvo em {ttl} ({len(g)} triplas)")

    linhas = [f"Triplas no grafo: {len(g)}",
              f"Parâmetros: limiar mínimo {motor.LIMIAR_MINIMO:.0%} (R6), limiar da "
              f"integrada {motor.LIMIAR_INTEGRADA:.0%} com mínimo de "
              f"{motor.MIN_TRATAMENTOS_INTEGRADA} tratamentos (R5)", ""]

    try:
        from pyshacl import validate
        shapes = Graph().parse(BASE / "shapes.ttl", format="turtle")
        conforme, _, texto = validate(g, shacl_graph=shapes, inference="rdfs",
                                      allow_warnings=True)
        linhas += ["== Validação SHACL ==", f"Conforme: {conforme}", texto.strip(), ""]
        print(f"SHACL conforme: {conforme}")
    except ImportError:
        linhas += ["pyshacl não instalado: validação SHACL não executada.", ""]

    linhas.append("== Pontuações: SPARQL sobre o grafo x motor_regras.py (app.py) ==")
    sparql = conferir_por_sparql(g)
    divergencias = 0
    for pid, ranking in resultados.items():
        linhas.append(f"\n{pid} — {PACIENTES[pid]['perfil']}")
        pos = 0
        for r in ranking:
            s_q, ind_q = sparql[(pid, ID_TRAT[r["treatment"]])]
            ok = abs(s_q - r["score"]) < 1e-3 and ind_q == r["indicated"]
            divergencias += not ok
            if r["indicated"]:
                pos += 1
                status = f"{pos}º indicado, prioridade {prioridade_por_posicao(pos)}"
            else:
                status = "não indicado"
            linhas.append(f"  {r['treatment']:<45} motor={r['score']:6.1%}  "
                          f"sparql={s_q:6.1%}  {status:<30} {'OK' if ok else 'DIVERGE'}")
    linhas.append(f"\nDivergências: {divergencias}")
    print(f"Divergências SPARQL x motor: {divergencias}")

    linhas.append("\n== Base de conhecimento (relações derivadas do IPO) ==")
    contagem = {t: sum(r["tipo"] == t for r in motor.RELATIONS) for t in motor.RELATION_TYPES}
    linhas.append("Relações: " + ", ".join(f"{motor.RELATION_TYPES[t]['label']} = {n}"
                                           for t, n in contagem.items()))
    problemas = motor.validate_knowledge_base()
    linhas += [f"  PROBLEMA: {x}" for x in problemas] or ["  Sem problemas (ciclos, duplicatas, "
                                                           "ordem das faixas etárias do IPO)."]
    print(f"Problemas na base de conhecimento: {len(problemas)}")

    linhas.append("\n== Inconsistências (R7): SPARQL sobre o grafo x motor ==")
    via_sparql = {(str(r.pessoa).split("_")[-1], str(r.rel).split("rel_")[-1], str(r.sev))
                  for r in g.query(SPARQL_INCONSISTENCIAS)}
    via_motor = set()
    for pid in PACIENTES:
        for item in motor.detect_inconsistencies(respostas_por_nome(pid)):
            via_motor.add((pid, item["relation"]["id"], item["severity"]))
    for pid in PACIENTES:
        itens = sorted(x for x in via_motor if x[0] == pid)
        linhas.append(f"{pid}: {len(itens)} inconsistência(s)")
        for _, rid, sev in itens:
            rel = next(r for r in motor.RELATIONS if r["id"] == rid)
            linhas.append(f"  [{sev}] {rid} {rel['origem']} → {rel['destino']}")
    dif_inc = via_sparql ^ via_motor
    linhas.append(f"Divergências: {len(dif_inc)}")
    print(f"Divergências de inconsistências SPARQL x motor: {len(dif_inc)}")
    (SAIDA / "relatorio_validacao.txt").write_text("\n".join(linhas), encoding="utf-8")

    renderizar("grafo_camada_conhecimento", dot_camada_conhecimento())
    renderizar("grafo_relacoes_habilidades", dot_relacoes())
    for pid, ranking in resultados.items():
        renderizar(f"grafo_paciente_{pid}", dot_paciente(pid, ranking))
    print("Figuras geradas em", SAIDA)


if __name__ == "__main__":
    main()
