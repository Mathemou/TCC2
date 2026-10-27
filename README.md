# Protótipo TCC — Recomendação baseada em regras e grafo

## Objetivo

Demonstrar uma alternativa mais simples e explicável ao uso de uma rede neural:

**Prontuário → Formulário de classificação → Grafo de habilidades → Motor de regras → Tratamentos ordenados**

O protótipo não pretende realizar diagnóstico nem substituir avaliação profissional.

## Executar

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

Depois abra o endereço indicado pelo Streamlit no navegador.

## Estrutura conceitual

### Entrada
Para cada habilidade do domínio de autocuidado ou motor, o avaliador informa:

- Independente = 0
- Realiza com auxílio = 1
- Não realiza = 2

Todas as habilidades começam sem seleção. Quando uma pergunta permanece sem
preenchimento, ela é considerada uma habilidade que não foi trabalhada e não
contribui para a pontuação do grafo.

O formulário contém 25 habilidades:

- Autocuidado: Alimentação, Escovação, Fio dental, Cuidado com o corpo,
  Cuidado com o cabelo, Cuidado com o rosto, Cuidado com as mãos, Vestuário,
  Manuseio de ajustes e Tarefas de banheiro.
- Motor: Locomoção geral, Locomoção específica, Equilíbrio estático,
  Equilíbrio dinâmico, Arremessar, receber, rolar e chutar bolas, Preensão,
  Encaixe de pinos e argolas, Empilhar peças, Enfiagem de contas, Dobrar papel,
  Montagem de quebra-cabeças, Preensão e controle de lápis, Escrita, cópia de
  letras e desenho, Uso de tesoura e Manipulação de fechos, trincos e maçanetas.

### Grafo

Existem três tipos principais de relação:

1. **habilidade → tratamento**
   - indica que determinado tratamento trabalha aquela habilidade.

2. **habilidade → habilidade**
   - relações derivadas do *Inventário Portage Operacionalizado* (IPO), de três tipos:
     **pré-requisito** (a origem é necessária para o destino), **composição** (a origem é
     parte do destino) e **facilitação** (a origem favorece o destino). Causalidade ainda
     não é modelada.
   - ficam em `base_conhecimento/relacoes_habilidades.csv`, com os itens do IPO e a
     justificativa de cada uma, e podem ser editadas no Excel (separador `;`). O mapeamento
     das 25 habilidades para os itens do IPO está em `base_conhecimento/habilidades_ipo.csv`.

3. **resposta → peso**
   - a resposta do formulário transforma a classificação em uma evidência quantitativa.

### Motor de regras

O sistema soma os pesos das dificuldades relacionadas a cada tratamento.

Exemplo:

- Higiene oral = "Não realiza" → peso 2
- Tratamento de autocuidado trabalha higiene oral
- tratamento recebe +2

Uma relação indireta pode receber peso parcial:

- Preensão = "Realiza com auxílio" → peso 1
- Preensão é pré-requisito de Escovação
- tratamento recebe +0,5 se trabalha Escovação (0,25 se a relação for de facilitação)

A soma é **normalizada** pela pontuação máxima que o tratamento poderia atingir, considerando
só as habilidades avaliadas. Assim, tratamentos que cobrem muitas habilidades não ficam em
vantagem só por serem maiores.

- Um tratamento abaixo de **15%** não é indicado. Se nenhum for indicado, o resultado é
  "sem indicação suficiente".
- A **intervenção integrada** não pontua por habilidade. Ela é indicada quando pelo menos
  **2 tratamentos específicos atingem 30%**, ou seja, quando a dificuldade está distribuída
  entre domínios. Nesse caso aparece em 1º lugar.

### Inconsistências

O sistema avisa quando as respostas se contradizem segundo as relações. Por exemplo, Escovação
"Independente" com o pré-requisito Preensão "Não realiza" gera um alerta **alto**. Se o
pré-requisito estiver "com auxílio", o alerta é **moderado**. Vale o mesmo para composição,
com o todo "Independente" e a parte com dificuldade. Facilitação não gera alerta.

As inconsistências aparecem na aba Resultado e no grafo do paciente, com a fundamentação no IPO.
**São apenas alertas: não alteram a pontuação nem a recomendação.**

Os dados e as regras ficam em `motor_regras.py`, incluindo os limiares no topo do arquivo.
Esse módulo é usado pelo `app.py` e pelo gerador do grafo de conhecimento
(`grafo de conhecimento/`), então os dois sempre produzem o mesmo resultado.

## O que deve ser validado no TCC

Os nomes e pesos deste protótipo são apenas ilustrativos. Para a versão acadêmica, recomenda-se levantar com profissionais:

- quais habilidades entram no formulário;
- como cada habilidade deve ser classificada;
- quais tratamentos trabalham cada habilidade;
- as relações entre habilidades e o tipo de cada uma (`base_conhecimento/relacoes_habilidades.csv`);
- a numeração dos itens do IPO na edição do Manual usada no TCC;
- quais regras determinam prioridade;
- como lidar com empate;
- quais resultados devem ser considerados "sem indicação suficiente".

Uma etapa particularmente importante é validar as regras com especialistas e registrar o racional de cada regra.
