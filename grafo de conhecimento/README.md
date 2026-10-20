# Grafo de conhecimento instanciado — SIGAMAES (TCC2)

Este grafo instancia a ontologia de `diagrama uml/grafo.png` (`grafo.tonto`), com as
extensões descritas em `grafo.corrigido.tonto`. As instâncias vêm do **mesmo motor de regras
usado pelo protótipo** (`../motor_regras.py`): as 25 habilidades do formulário, os 4
tratamentos, as 13 dependências entre habilidades e o conhecimento especialista. O grafo
também tem **4 pacientes fictícios**, com 100 avaliações e as recomendações calculadas para eles.

```
Prontuário → Avaliações → Conhecimento (simples / composto) → Recomendações → Tratamentos
```

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `gerar_grafo_conhecimento.py` | Gera tudo. Os dados e as regras vêm de `../motor_regras.py`. |
| `shapes.ttl` | Regras de validação SHACL: cardinalidades, enums, limiares, R5 e rastreabilidade. |
| `grafo.corrigido.tonto` | Versão sugerida da ontologia, com as correções da seção 5. |
| `saida/grafo_conhecimento.ttl` | **O grafo**: TBox em gUFO + ABox, com 1317 triplas. Abre no Protégé ou no GraphDB. |
| `saida/relatorio_validacao.txt` | Resultado do SHACL e conferência SPARQL × motor. |
| `saida/grafo_camada_conhecimento.png/.svg` | Camada especialista: Especialista → Conhecimento → Tratamento/Habilidade. |
| `saida/grafo_paciente_P00X.png/.svg` | Grafo instanciado de cada paciente. |

```bash
pip install rdflib pyshacl
python gerar_grafo_conhecimento.py
```

As figuras precisam do [Graphviz](https://graphviz.org/download/) (`dot`) no PATH.
Se você mudar habilidades, tratamentos ou limiares em `motor_regras.py`, basta rodar o script
de novo: o grafo, a validação e as figuras são regenerados.

## 1. Regras do motor (`motor_regras.py`)

| Regra | Descrição |
|---|---|
| R1 | Dificuldade em uma habilidade pontua os tratamentos que a trabalham: com auxílio vale 1, não realiza vale 2. |
| R2 | Dificuldade em uma habilidade que *apoia* outra habilidade do tratamento contribui com 0,5 × peso. |
| R3 | **Pontuação normalizada** = soma ÷ máximo possível do tratamento. Respostas em branco não entram no cálculo. |
| R4 | Cada ponto é rastreável até uma resposta do formulário. Isso fica registrado no atributo `justificativa`. |
| R5 | **Intervenção integrada:** é indicada só quando ≥ 2 tratamentos específicos atingem **30%**. A pontuação dela é a menor dessas, e ela aparece em 1º lugar. |
| R6 | **Limiar mínimo:** tratamentos abaixo de **15%** não são indicados. Se nenhum for indicado, o resultado é "sem indicação suficiente". |

Os limiares (15%, 30% e o mínimo de 2 tratamentos) são valores de partida. Eles estão no topo
de `motor_regras.py` e precisam ser validados com a equipe clínica.

## 2. Como cada classe foi instanciada

| Classe (estereótipo) | Instâncias |
|---|---|
| Pessoa «kind» | 4 pacientes fictícios: P001 a P004 |
| Prontuario «kind» | 4 |
| Habilidade e subkinds | 29: os 25 itens do formulário mais Correr, Rolar, Sentar e Engatinhar |
| AvaliacaoHabilidade «relator» | 100: 25 por paciente |
| Tratamento «kind» | 4 |
| Recomendacao «relator» | 7: só os tratamentos indicados viram recomendação |
| Especialista «kind» | 2: terapeuta ocupacional e fisioterapeuta |
| ConhecimentoSimples «subkind» de Conhecimento | 3: um por tratamento específico, ligado às habilidades (`refereSe`), com `limiarIndicacao` de 15% |
| ConhecimentoComposto «subkind» de Conhecimento | 1: `con_integrado`, que `requer` os 3 conhecimentos simples, com `limiarIndicacao` de 30% e `minimoRequeridos` = 2 |
| DependenciaHabilidade «relator» | 13 |

### Item do formulário → subkind

| Item | Subkind | | Item | Subkind |
|---|---|---|---|---|
| AC01 Alimentação | Alimentacao | | AC08 Vestuário | Vestuario |
| AC02 Escovação | HigieneBucal | | AC09 Manuseio de ajustes | Calcados ⚠ |
| AC03 Fio dental | HigieneBucal | | AC10 Tarefas de banheiro | UsoBanheiro |
| AC04 Cuidado com o corpo | HigieneCorporal | | MO01 Locomoção geral | Caminhar |
| AC05 Cuidado com o cabelo | HigieneCabelos | | MO02 Locomoção específica | SubirEscadas ⚠ |
| AC06 Cuidado com o rosto | HigieneRosto | | MO03 a MO15 | instância direta de HabilidadeMotora |
| AC07 Cuidado com as mãos | HigieneMaos | | | |

⚠ Esses dois mapeamentos são interpretações minhas e precisam ser confirmados com as orientadoras.

### Formulário → `NivelHabilidade` e posição → `NivelPrioridade`

| Formulário | `nivel` | Peso |
|---|---|---|
| Independente | Alto | 0 |
| Com auxílio | Moderado | 1 |
| Não realiza | Baixo | 2 |
| Em branco | NaoAvaliado | — |

A prioridade segue a posição entre os tratamentos indicados: o 1º recebe **Alta**, o 2º
**Media** e os demais **Baixa**.

## 3. Resultados

| Paciente | Perfil | Indicados (prioridade) | Não indicados |
|---|---|---|---|
| P001 | autocuidado | Autocuidado 58,9% (Alta) · Motor fino 15,0% (Media) | Motor grosso 13,6% · Integrada (só 1 tratamento ≥ 30%) |
| P002 | motor fino | Motor fino 83,3% (Alta) · Autocuidado 21,1% (Media) | Motor grosso 13,6% · Integrada |
| P003 | sem dificuldades | — **sem indicação suficiente** | todos |
| P004 | distribuído | **Integrada 32,1% (Alta)** · Motor fino 37,5% (Media) · Autocuidado 32,1% (Baixa) | Motor grosso 13,6% |

Agora a intervenção integrada só aparece quando a dificuldade está espalhada por mais de um
domínio, como em P004. Antes ela era a 1ª colocada em todos os casos com alguma dificuldade.

As pontuações foram **recalculadas por SPARQL usando só o conteúdo do grafo**, incluindo os
limiares gravados nos nós Conhecimento. Elas batem com o motor do protótipo em todos os
casos, sem divergência.

## 4. Validação (SHACL — `shapes.ttl`)

- Cardinalidades de todos os relators, valores dos enums e domínio único de cada habilidade.
- Todo Conhecimento é **Simples ou Composto, nunca os dois**. O simples precisa de habilidades,
  e o composto precisa requerer pelo menos 2 conhecimentos simples.
- **R5/R6:** nenhuma recomendação fica abaixo do limiar do seu Conhecimento. Uma recomendação da
  integrada só é válida se pelo menos 2 tratamentos requeridos foram recomendados à mesma
  pessoa, na mesma data, com pontuação ≥ 30%.
- **Explicabilidade:** cada avaliação em `baseadaEm` mostra dificuldade e tem um caminho de
  conhecimento até o tratamento recomendado. O caminho pode ser direto, por dependência ou
  passar pelo conhecimento composto.
- Coerência de pessoa e ausência de duplicatas.

O grafo está conforme. Também injetei erros de propósito (integrada sem R5 satisfeita,
pontuação abaixo do limiar, conhecimento simples e composto ao mesmo tempo, enum inválido…),
e todos foram detectados.

## 5. Correções e extensões na ontologia (`grafo.corrigido.tonto`)

1. **Cardinalidades das mediações invertidas.** No Tonto, a 1ª cardinalidade é a do lado do
   relator. O correto é `[0..*] -- pertenceA -- [1] Pessoa`, e o mesmo vale para `avalia`,
   `destinadaA`, `recomenda` e `baseadaEm`.
2. **Conhecimento** passa a mediar Especialista, Tratamento e (via `ConhecimentoSimples`)
   Habilidade.
3. **DependenciaHabilidade** representa a regra R2.
4. **Prontuário** ligado à Pessoa por `registra`.
5. `nivel` e `prioridade` passam a usar os enums.
6. Generalization sets declarados.
7. **Regras R5/R6:** Conhecimento é especializado em `ConhecimentoSimples`, que se refere a
   habilidades, e `ConhecimentoComposto`, que requer ≥ 2 conhecimentos simples. Ganha também
   os atributos `limiarIndicacao` e `minimoRequeridos`. A Recomendacao ganha o atributo
   `pontuacao`, de 0 a 1.

No `.ttl`, os elementos novos têm a marca `tcc:extensaoProposta true`.

## 6. Consultas SPARQL úteis para o texto

```sparql
PREFIX tcc: <http://example.org/sigamaes/ontologia#>
PREFIX inst: <http://example.org/sigamaes/instancias#>

# Por que cada tratamento foi recomendado ao P004?
SELECT ?prioridade ?pontuacao ?tratamento ?habilidade ?nivel WHERE {
  ?r tcc:destinadaA inst:pessoa_P004 ; tcc:prioridade ?prioridade ; tcc:pontuacao ?pontuacao ;
     tcc:recomenda/tcc:nome ?tratamento ; tcc:baseadaEm ?av .
  ?av tcc:nivel ?nivel ; tcc:avalia/tcc:nome ?habilidade .
} ORDER BY DESC(?pontuacao)

# Quais conhecimentos a intervenção integrada combina, e com qual limiar?
SELECT ?requerido ?limiar ?minimo WHERE {
  ?k a tcc:ConhecimentoComposto ; tcc:limiarIndicacao ?limiar ; tcc:minimoRequeridos ?minimo ;
     tcc:requer/tcc:podeIndicar/tcc:nome ?requerido .
}
```

## 7. Pontos em aberto para validar com a equipe

- Os valores dos limiares: 15%, 30% e o mínimo de 2 tratamentos.
- **Cobertura mínima.** Com a normalização, um paciente que teve só 1 habilidade avaliada pode
  chegar a 100%. A tela de resultado mostra quantas habilidades foram avaliadas por tratamento,
  mas pode valer a pena exigir uma cobertura mínima, por exemplo 50% das habilidades.
- O critério de desempate e se a integrada deve mesmo aparecer em 1º quando é indicada.
