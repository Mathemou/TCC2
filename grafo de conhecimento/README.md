# Grafo de conhecimento instanciado — SIGAMAES (TCC2)

Este grafo instancia a ontologia de `diagrama uml/grafo.png` (`grafo.tonto`), com as extensões
de `grafo.corrigido.tonto`. Os dados e as regras vêm do **mesmo motor usado pelo protótipo**
(`../motor_regras.py`). As relações entre habilidades e o mapeamento para o **Inventário Portage
Operacionalizado (IPO)** estão em `../base_conhecimento/*.csv`. O grafo também tem **5 pacientes
fictícios**.

```
Prontuário → Avaliações → Relações entre habilidades (IPO) → Inconsistências
                        → Conhecimento (simples / composto) → Recomendações → Tratamentos
```

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `../base_conhecimento/habilidades_ipo.csv` | Itens do IPO (com faixa etária) associados a cada uma das 25 habilidades |
| `../base_conhecimento/relacoes_habilidades.csv` | As 26 relações tipadas, com os itens do IPO, a evidência e a justificativa de cada uma |
| `gerar_grafo_conhecimento.py` | Gera tudo a partir de `../motor_regras.py` e dos CSVs |
| `shapes.ttl` | Regras de validação SHACL |
| `grafo.corrigido.tonto` | Ontologia sugerida (validada com o `tonto-cli`) |
| `saida/grafo_conhecimento.ttl` | **O grafo**: TBox em gUFO + ABox, com 2041 triplas |
| `saida/relatorio_validacao.txt` | SHACL, base de conhecimento e conferências SPARQL × motor |
| `saida/grafo_relacoes_habilidades.png/.svg` | **Somente as relações entre as habilidades**, por tipo |
| `saida/grafo_camada_conhecimento.png/.svg` | Especialista → Conhecimento → Tratamento/Habilidade |
| `saida/grafo_paciente_P00X.png/.svg` | Grafo instanciado de cada paciente, com as inconsistências |

```bash
pip install rdflib pyshacl
python gerar_grafo_conhecimento.py
```

As figuras precisam do [Graphviz](https://graphviz.org/download/) (`dot`) no PATH. Se você editar
os CSVs ou `motor_regras.py`, rode o script de novo: o grafo, a validação e as figuras são regenerados.

## 1. Relações entre habilidades (base: IPO)

### Como as relações foram derivadas

Pelo que encontrei nas versões do IPO publicadas online, o inventário lista **580 comportamentos
por área e faixa etária (0 a 6 anos)**, mas **não declara explicitamente quais itens dependem de
quais**. Por isso, cada relação foi **derivada** dos itens do IPO e registra o tipo de evidência usado:

- **Conteúdo do item:** o próprio texto do item mostra a relação. Por exemplo, A-85 ("vai ao
  banheiro a tempo, retira a roupa, usa papel higiênico, dá descarga e veste-se sem ajuda")
  inclui o vestir-se como parte da tarefa. Já M-78 descreve segurar o lápis entre o polegar e o
  indicador, que é a própria pinça (M-32) aplicada ao lápis.
- **Sequência etária:** o pré-requisito aparece no IPO em uma faixa etária anterior ou igual à da
  habilidade que depende dele. Por exemplo, ficar em pé sozinho (M-37, 0-1) vem antes de andar
  sozinho (M-55, 1-2).
- **Funcional:** a relação vem só da natureza da tarefa. Só é usada para *Fio dental*, que não tem
  item no IPO.

Todas as relações estão marcadas como **"validar com as orientadoras"**. A numeração dos itens
segue a versão consultada (ver *Fontes*) e deve ser conferida na edição do Manual usada no TCC.

### Os tipos

| Tipo | Significado | Peso indireto (R2) | Gera inconsistência (R7)? |
|---|---|---|---|
| **Pré-requisito** (17) | A origem é condição necessária para o destino | 0,5 | Sim |
| **Composição** (2) | A origem é parte do destino | 0,5 | Sim |
| **Facilitação** (7) | A origem favorece o destino, mas não é necessária | 0,25 | Não |
| Causalidade | — | — | Não modelada por enquanto |

Resumo das relações (detalhes e justificativas no CSV e na figura `grafo_relacoes_habilidades`):

- **Pré-requisitos:**
  - Preensão → Escovação, Alimentação, Fio dental, Cuidado com o cabelo e Manuseio de ajustes;
  - Preensão → Lápis, Encaixe, Empilhar, Contas, Dobrar papel, Quebra-cabeças, Tesoura e Fechos/maçanetas;
  - Lápis → Escrita/desenho;
  - Equilíbrio estático → Locomoção geral → Locomoção específica;
  - Equilíbrio estático → Equilíbrio dinâmico.
- **Composições:** Manuseio de ajustes ◆ Vestuário (A-54/A-58/A-81 ressalvam os fechos) e
  Vestuário ◆ Tarefas de banheiro (A-85).
- **Facilitações:**
  - Equilíbrio dinâmico → Locomoção específica;
  - Equilíbrio estático → Vestuário;
  - Locomoção geral → Tarefas de banheiro;
  - Fechos/maçanetas → Manuseio de ajustes;
  - Lápis → Tesoura;
  - Empilhar e Encaixe → Quebra-cabeças.

As 13 dependências genéricas da versão anterior foram substituídas por estas relações. Três delas
foram removidas porque não encontrei base para elas no IPO: Cuidado com as mãos → Alimentação,
Cuidado com as mãos → Fio dental e Locomoção geral → Vestuário.

### Verificações automáticas da base

`motor_regras.validate_knowledge_base()` e o SHACL verificam quatro coisas:
- não há ciclos de pré-requisito ou composição;
- não há pares duplicados;
- todo **pré-requisito aparece no IPO em faixa etária igual ou anterior** à da habilidade dependente;
- os itens do IPO seguem o formato `A-36 (2-3)`.

## 2. Inconsistências (regra R7) — apenas alerta

| Relação | Situação | Severidade |
|---|---|---|
| Pré-requisito | Destino "Independente" e pré-requisito "Não realiza" | **Alta** |
| Pré-requisito | Destino "Independente" e pré-requisito "Realiza com auxílio" | Moderada |
| Composição | Todo "Independente" e parte "Não realiza" | **Alta** |
| Composição | Todo "Independente" e parte "Realiza com auxílio" | Moderada |

A facilitação nunca gera inconsistência, e respostas em branco não são verificadas. As
inconsistências **não mudam a pontuação nem a recomendação**: aparecem no app como alerta, com a
fundamentação no IPO.

No grafo, cada inconsistência é um nó `«relator» Inconsistencia` ligado à pessoa, às duas
avaliações contraditórias (`avaliacaoOrigem` e `avaliacaoDestino`) e à relação violada
(`violaRelacao`). O SHACL confere as duas direções:
- toda violação existente nas respostas está registrada;
- todo registro corresponde a uma violação real, com a severidade correta.

| Paciente | Inconsistências |
|---|---|
| P001 | nenhuma |
| P002 | **Alta:** Preensão "Não realiza" × Escovação e Cuidado com o cabelo "Independente" · Moderada: Vestuário × Tarefas de banheiro |
| P003 | nenhuma |
| P004 | 7 moderadas: Preensão "com auxílio" × 6 habilidades "Independente", e Vestuário × Tarefas de banheiro |
| P005 | **Alta:** Preensão × Escovação · **Alta:** Manuseio de ajustes × Vestuário (composição) · Moderada: Equilíbrio estático × Locomoção geral |

P002 e P004 foram criados antes das relações existirem. As inconsistências que aparecem neles são
um exemplo real do tipo de erro de preenchimento que a regra pega.

## 3. Regras do motor

| Regra | Descrição |
|---|---|
| R1 | Dificuldade em uma habilidade pontua os tratamentos que a trabalham: com auxílio vale 1, não realiza vale 2. |
| R2 | Dificuldade em uma habilidade **relacionada** a outra do tratamento contribui com peso indireto: 0,5 (pré-requisito, composição) ou 0,25 (facilitação). |
| R3 | Pontuação normalizada = soma ÷ máximo possível, considerando só as habilidades avaliadas. |
| R4 | Cada ponto é rastreável até uma resposta, pelo atributo `justificativa`. |
| R5 | A intervenção integrada só é indicada se ≥ 2 tratamentos específicos atingem 30%. Nesse caso aparece em 1º lugar. |
| R6 | Tratamentos abaixo de 15% não são indicados. Se nenhum passar, o resultado é "sem indicação suficiente". |
| R7 | Inconsistências entre respostas (seção 2). Só alertam. |

### Resultados

| Paciente | Perfil | Indicados (prioridade) |
|---|---|---|
| P001 | autocuidado | Autocuidado 60,5% (Alta) |
| P002 | motor fino | Integrada 34,9% (Alta) · Motor fino 86,1% (Media) · Autocuidado 34,9% (Baixa) |
| P003 | sem dificuldades | — sem indicação suficiente |
| P004 | distribuído | Integrada 38,5% (Alta) · Autocuidado 42,1% (Media) · Motor fino 38,5% (Baixa) |
| P005 | formulário inconsistente | Integrada 40,4% · Motor fino 85,2% · Autocuidado 40,4% · Motor grosso 24,1% |

As pontuações mudaram em relação à versão anterior, porque as relações agora são outras e têm
pesos por tipo. Por exemplo, Preensão passou a ser pré-requisito de 5 habilidades de autocuidado.
Uma dificuldade de pinça agora também pesa no treino de autocuidado, e por isso P002 passou a
receber a intervenção integrada. Em P001, o motor fino caiu para 11,3% e deixou de ser indicado.
Vale discutir com as orientadoras se esse efeito é o desejado.

As pontuações e as inconsistências foram **recalculadas por SPARQL usando só o grafo**. As duas
batem com o motor do protótipo, sem nenhuma divergência.

## 4. Classes da ontologia instanciadas

| Classe | Instâncias |
|---|---|
| Pessoa / Prontuario | 5 / 5 (fictícios) |
| Habilidade e subkinds | 29: os 25 itens do formulário, com `itemIPO` e `idadeInicialIPO`, mais 4 subkinds sem item no formulário |
| AvaliacaoHabilidade | 125 |
| **RelacaoHabilidade**: PreRequisito / Composicao / Facilitacao | 17 / 2 / 7 |
| **Inconsistencia** | 13 |
| ConhecimentoSimples / ConhecimentoComposto | 3 / 1 |
| Recomendacao / Tratamento / Especialista | 11 / 4 / 2 |

## 5. Validação

- **SHACL:** o grafo está conforme. Injetei erros de propósito e todos foram detectados:
  - inconsistência apagada;
  - inconsistência inventada sobre uma facilitação;
  - severidade errada;
  - pré-requisito com faixa etária invertida;
  - relação com dois tipos;
  - item do IPO mal formatado;
  - além dos testes anteriores de R5, limiares e enums.
- **Tonto:** `grafo.corrigido.tonto` passa no `tonto-cli validate` local, sem erros. Para validar
  também com a API do OntoUML, que não consegui acessar daqui, rode
  `npx tonto-cli validate <pasta> --with-api`.

## 6. Consultas SPARQL úteis para o texto

```sparql
PREFIX tcc: <http://example.org/sigamaes/ontologia#>

# Inconsistências de cada paciente, com a relação e a fundamentação no IPO
SELECT ?paciente ?severidade ?origem ?destino ?fundamentacao WHERE {
  ?i tcc:inconsistenciaDe/tcc:nome ?paciente ; tcc:severidade ?severidade ; tcc:violaRelacao ?r .
  ?r tcc:origem/tcc:nome ?origem ; tcc:destino/tcc:nome ?destino ; tcc:fundamentacao ?fundamentacao .
} ORDER BY ?paciente ?severidade

# Pré-requisitos de uma habilidade, com os itens do IPO
SELECT ?prereq ?item WHERE {
  ?r a tcc:PreRequisito ; tcc:destino/tcc:nome "Escovação" ; tcc:origem ?h .
  ?h tcc:nome ?prereq ; tcc:itemIPO ?item .
}
```

## 7. Pontos em aberto para validar com as orientadoras

- **As relações em si.** Revisar o CSV linha a linha. O mais importante é decidir se cada
  pré-requisito é mesmo *necessário* ou se deveria ser *facilitação*.
- **A numeração dos itens** na edição do Manual usada no TCC.
- **Mapeamentos sem correspondência direta:** *Fio dental* não tem item no IPO, e
  *Manuseio de ajustes* foi mapeado aos itens de botões, zíper, colchetes, fivelas e laços.
- **O nível "Moderada"** (pré-requisito "com auxílio"). Em P004, ele gera 7 alertas a partir de
  uma única resposta. O app agrupa esses alertas por habilidade de origem, mas talvez valha
  manter só o nível Alto.
- **Os pesos indiretos** por tipo (0,5 e 0,25), os limiares (15% e 30%) e uma cobertura mínima
  de habilidades avaliadas.

## Fontes consultadas

- Itens e faixas etárias: [Guia Portage de Educação Pré-Escolar — Inventário Portage Operacionalizado (Instituto Itard)](https://files.institutoitard.com.br/pdf/Guia_Portage_Inventario_Operacionalizado_Escala_em_PDF.pdf)
- Conferência cruzada da sequência dos itens: [Roteiro baseado na Escala Portage de Desenvolvimento](https://irp-cdn.multiscreensite.com/a12de2b1/pdf/ROTEIROESCALAPORTAGEDEDESENVOLVIMENTO.pdf)
- Estrutura do IPO (5 áreas, 580 itens, 0–6 anos): [PUC Goiás — Inventário Portage Operacionalizado como acompanhamento do desenvolvimento infantil](https://repositorio.pucgoias.edu.br/jspui/bitstream/123456789/9509/1/INVENTARIO%20PORTAGE%20OPERACIONALIZADO%20COMO%20ACOMPANHAMENTO%20DE%20DESENVOLVIMENTO%20INFANTIL.pdf)
- Referência do Manual: Williams, L. C. A.; Aiello, A. L. R. *O Inventário Portage Operacionalizado:
  intervenção com famílias*. São Paulo: Memnon, 2001.
