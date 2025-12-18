# Guia de Interpretação dos Resultados do Modelo de Otimização

## Visão Geral

Este documento explica como interpretar os resultados gerados pelo modelo de otimização com realocação entre SKUs. Os resultados são salvos em arquivos CSV e Excel na pasta `resultados/`.

## Estrutura dos Arquivos de Resultado

O modelo gera dois tipos de arquivos principais:

1. **resultado_realocação_completo_[timestamp].csv**: Resultado detalhado por SKU e embalagem
2. **resumo_por_classe_completo_[timestamp].csv**: Resumo agregado por classe de produto

## Colunas do Resultado Detalhado

### Colunas Identificadoras

- **item**: Código numérico do SKU (ex: 2000211)
- **embalagem**: Descrição da embalagem (ex: "CX 6 BJ 30 UN")
- **classe**: Classe do produto (ex: "BRANCO_GRANDE_MTQ")
- **tipo**: Tipo de alocação:
  - `EXCEDENTE`: Otimização do estoque excedente (após atender pedidos)
  - `ESTOQUE_TOTAL`: Otimização de todo o estoque (quando pedidos são ignorados)
  - `PEDIDO`: Atendimento de pedidos de clientes

### Colunas de Quantidade

- **quantidade**: Quantidade total alocada pelo modelo para esta combinação SKU x Embalagem
- **estoque_original**: Estoque disponível original do SKU (antes da otimização)
- **estoque_excedente**: Estoque excedente do SKU (estoque original - pedidos atendidos)

### Colunas Financeiras

- **preço**: Preço unitário da combinação SKU x Embalagem (R$)
- **custo_ytd**: Custo unitário do SKU (R$)
- **margem_unitária**: Margem unitária = preço - custo_ytd (R$)
- **receita_total**: Receita total = quantidade × preço (R$)
- **custo_total**: Custo total = quantidade × custo_ytd (R$)
- **margem_total**: Margem total = quantidade × margem_unitária (R$)

### Colunas de Variação (Realocação)

- **variação_qtd**: Variação absoluta de quantidade = quantidade - estoque_referência
  - Para `EXCEDENTE`: compara com `estoque_excedente`
  - Para `ESTOQUE_TOTAL`: compara com `estoque_original`
  - Valores positivos: SKU recebeu volume de outros SKUs
  - Valores negativos: SKU perdeu volume para outros SKUs
  - Zero: sem realocação

- **variação_pct**: Variação percentual = (variação_qtd / estoque_referência) × 100
  - Exemplo: +85.0% significa que o SKU recebeu 85% a mais que seu estoque original

## Interpretação dos Resultados

### 1. Entendendo a Realocação

O modelo permite mover volume entre SKUs da mesma classe para maximizar a margem total. Isso significa:

- **SKUs com maior margem unitária** tendem a receber mais volume
- **SKUs com menor margem unitária** tendem a perder volume
- A soma total de volume por classe permanece constante (não cria nem destrói estoque)

### 2. Exemplo Prático de Realocação

Considere o SKU 2000211 (BRANCO_GRANDE_MTQ):
- Estoque original: 8,993 unidades
- Quantidade alocada: 16,635 unidades
- Variação: +7,642 unidades (+85.0%)
- Margem unitária: R$ 66.25/un

**Interpretação**: Este SKU recebeu 7,642 unidades adicionais de outros SKUs da mesma classe (BRANCO_GRANDE_MTQ) porque tem uma margem unitária alta. Isso aumenta a margem total da classe.

### 3. Análise de Variações Negativas

SKUs com variação negativa perderam volume para outros SKUs da mesma classe:

Exemplo: SKU 2000632 (VERMELHO_GRANDE_HE):
- Estoque original: 4,053 unidades
- Quantidade alocada: 1,879 unidades
- Variação: -2,174 unidades (-53.6%)
- Margem unitária: R$ 61.51/un

**Interpretação**: Este SKU perdeu 2,174 unidades porque outros SKUs da classe VERMELHO_GRANDE_HE tem margem maior. O volume foi realocado para SKUs mais rentáveis.

### 4. Métricas de Sucesso

#### Ganho de Margem
Compare a margem otimizada com a margem baseline (sem realocação):
- **Ganho absoluto**: Diferença em R$ entre margem otimizada e baseline
- **Ganho percentual**: Percentual de aumento da margem

Exemplo do log:
```
Margem Baseline: R$ 3,866,262.91
Margem Otimizada: R$ 4,352,755.82
GANHO MARGEM: R$ 486,492.91 (12.58%)
```

**Interpretação**: A realocação gerou um ganho adicional de R$ 486,492.91 (12.58%) em relação a não fazer realocação.

#### Variação de Custo
Quando o objetivo e maximizar margem, o custo pode aumentar:
- Isso e esperado: SKUs com maior margem podem ter custo maior
- O importante e o ganho líquido: margem otimizada - margem baseline

### 5. Análise por Classe

O resumo por classe mostra:
- **num_skus**: Quantidade de SKUs únicos na classe
- **qtd_alocada**: Quantidade total alocada na classe
- **estoque_original**: Estoque original total da classe
- **margem_total**: Margem total gerada pela classe
- **variação_total**: Soma das variações (deve ser zero ou próximo, pois volume e preservado)

**Classes com maior margem total** são as mais importantes para o negócio:
1. BRANCO_GRANDE_MTQ: R$ 1,410,214.42
2. BRANCO_EXTRA_MTQ: R$ 1,027,551.25
3. BRANCO_JUMBO_MTQ: R$ 732,738.97

### 6. Tipos de Alocação

#### ESTOQUE_TOTAL
Quando `atender_pedidos=false` e `usar_apenas_excedente=false`:
- O modelo otimiza TODO o estoque disponível
- Não considera pedidos de clientes
- Útil para análise de mix otimo sem restrições de pedidos

#### EXCEDENTE
Quando `atender_pedidos=true` ou `usar_apenas_excedente=true`:
- O modelo otimiza apenas o estoque que sobra após atender pedidos
- Garante que pedidos sejam atendidos primeiro
- Útil para operação diaria com pedidos confirmados

#### PEDIDO
Quando `atender_pedidos=true`:
- Representa o atendimento de pedidos de clientes
- Quantidade pode ser parcial (se estoque insuficiente)
- Percentual de atendimento mostra quanto do pedido foi atendido

## Perguntas Frequentes

### Por que alguns SKUs tem variação de 100%?

Variação de 100% significa que o SKU recebeu o dobro do seu estoque original. Isso acontece quando:
- O SKU tem margem unitária muito alta
- Outros SKUs da mesma classe tem margem menor
- O modelo realoca volume para maximizar a margem total

### Por que o custo otimizado e maior que o baseline?

Quando o objetivo e maximizar margem:
- O modelo prioriza SKUs com maior margem, mesmo que tenham custo maior
- O ganho líquido (margem otimizada - margem baseline) e positivo
- Exemplo: Se custo aumenta R$ 337,452 mas margem aumenta R$ 486,492, o ganho líquido e R$ 149,040

### Como interpretar variações negativas?

Variações negativas são esperadas e desejáveis:
- Significam que volume foi movido de SKUs menos rentáveis para mais rentáveis
- A margem total aumenta mesmo com algumas variações negativas
- O modelo sempre preserva o volume total por classe

### O que significa "variação_total" zero por classe?

A variação total por classe deve ser zero (ou próximo de zero) porque:
- O modelo não cria nem destrói estoque
- Volume apenas e realocado entre SKUs da mesma classe
- A soma de todas as variações positivas = soma de todas as variações negativas

## Exemplo de Interpretação Completa

Considere o resultado do SKU 2000211:

```
item: 2000211
classe: BRANCO_GRANDE_MTQ
embalagem: CX 6 BJ 30 UN
estoque_original: 8,993 unidades
quantidade: 16,635 unidades
variação_qtd: +7,642 unidades
variação_pct: +85.0%
margem_unitária: R$ 66.25/un
margem_total: R$ 1,102,007.14
```

**Interpretação**:
1. Este SKU tinha 8,993 unidades em estoque
2. O modelo alocou 16,635 unidades (recebeu 7,642 unidades de outros SKUs)
3. A variação de +85% significa que recebeu 85% a mais que seu estoque original
4. Com margem de R$ 66.25/un, gerou R$ 1,102,007.14 de margem total
5. Esta realocação contribuiu significativamente para o ganho total de R$ 486,492.91

## Validação dos Resultados

Sempre verifique:
1. **Conservação de volume**: Soma de quantidade alocada por classe = estoque original da classe
2. **Margem positiva**: Todas as combinacoes devem ter margem_unitária > 0
3. **Variação total zero**: Soma de variações por classe deve ser zero
4. **Ganho positivo**: Margem otimizada deve ser maior que baseline


