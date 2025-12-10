# DIFERENCA ENTRE MODELO DE REALOCACAO E MODELO DE MIX DIARIO

## RESUMO EXECUTIVO

O **Modelo de Realocacao** (`modelo_realocacao_completo.ipynb`) gera ganho porque **realoca volume entre SKUs diferentes** dentro da mesma classe, enquanto o **Modelo de Mix Diario** (`modelo_otimizacao_mix_diario.py`) apenas escolhe embalagens para SKUs individuais, sem realocar volume entre SKUs.

## MODELO DE REALOCACAO (Gera Ganho)

### O que faz:
1. **Agrega dados historicos** por SKU dentro de cada classe de produtos
2. **Calcula margem unitaria** para cada SKU: `margem_unitaria = preco_medio - custo_unitario`
3. **Realoca VOLUME entre SKUs diferentes** da mesma classe:
   - Identifica SKUs com maior margem (top_k)
   - Identifica SKUs com menor margem (bottom_k)
   - Move 3% do volume dos SKUs de menor margem para os de maior margem
4. **Mantem volume total da classe fixo** (restricao biologica)

### Exemplo de ganho:
```
Classe: BRANCO_GRANDE_MTQ (mesmo tipo de ovo, diferentes embalagens)

SKU A (CX 12 BJ 30 UN): margem = R$ 10,00/unidade
SKU B (CX 6 BJ 30 UN):  margem = R$ 8,00/unidade
SKU C (CX 12 BJ 12 UN): margem = R$ 9,50/unidade

Volume historico:
- SKU A: 1.000.000 unidades
- SKU B: 500.000 unidades  
- SKU C: 300.000 unidades
Total: 1.800.000 unidades (FIXO)

Realocacao (3%):
- Move 3% de B (15.000 unidades) para A
- Move 3% de C (9.000 unidades) para A

Ganho = (15.000 * (10,00 - 8,00)) + (9.000 * (10,00 - 9,50))
      = 30.000 + 4.500
      = R$ 34.500
```

### Por que gera ganho:
- **Diferenca de margem entre SKUs diferentes** e significativa (R$ 1-2/unidade)
- **Volume realocado** e grande (milhares de unidades)
- **Ganho = diferenca_margem * volume_realocado**

### Resultados:
- Ganho total: R$ 2,94M/ano (0,50% do lucro baseline)
- Classes com maior ganho: BRANCO_ORGANICO_TC (R$ 0,63M), VERMELHO_EXTRA_MTQ (R$ 0,54M)

## MODELO DE MIX DIARIO (Nao Gera Ganho)

### O que faz:
1. **Olha para estoque do dia** (SKUs especificos disponiveis)
2. **Para cada SKU no estoque**, escolhe a melhor embalagem disponivel
3. **NAO realoca volume entre SKUs diferentes**
4. Apenas decide: "Para o SKU X que esta no estoque, qual embalagem usar?"

### Exemplo:
```
Estoque do dia:
- SKU 2000211: 10.000 unidades disponiveis
- SKU 2000218: 5.000 unidades disponiveis

Opcoes de embalagem para SKU 2000211:
- CX 12 BJ 30 UN: margem = R$ 83,68/unidade
- CX 6 BJ 30 UN:  margem = R$ 83,67/unidade
- CX 12 BJ 12 UN: margem = R$ 83,66/unidade

Modelo escolhe: CX 12 BJ 30 UN (melhor margem)
```

### Por que NAO gera ganho:
- **Diferenca de margem entre embalagens do mesmo SKU** e muito pequena (R$ 0,004-0,005/unidade)
- **Volume e fixo** (nao realoca entre SKUs)
- **Ganho = diferenca_margem * volume** = 0,004 * 10.000 = R$ 40 (desprezivel)

### Resultados:
- Ganho total: R$ 0,00 a R$ 0,18 (desprezivel)
- Diferenca media de margem entre embalagens: R$ 0,004-0,005

## DIFERENCA FUNDAMENTAL

| Aspecto | Modelo Realocacao | Modelo Mix Diario |
|--------|------------------|-------------------|
| **Escopo** | Dados historicos agregados | Estoque do dia |
| **Decisao** | Realoca volume entre SKUs diferentes | Escolhe embalagem para SKU individual |
| **Volume** | Volume total da classe e fixo | Volume de cada SKU e fixo |
| **Diferenca de margem** | Entre SKUs diferentes (R$ 1-2/unidade) | Entre embalagens do mesmo SKU (R$ 0,004/unidade) |
| **Ganho** | R$ 2,94M/ano | R$ 0,00 |
| **Por que funciona** | Realoca volume de SKUs de baixa margem para alta margem | Apenas escolhe melhor opcao disponivel |

## COMO FAZER O MODELO DE MIX DIARIO GERAR GANHO

Para o modelo de mix diario gerar ganho significativo, seria necessario:

1. **Realocar volume entre SKUs diferentes** (nao apenas escolher embalagens):
   - Se SKU A tem margem maior que SKU B, mover parte do estoque de B para A
   - Mas isso requer que os SKUs sejam da mesma classe (mesmo tipo de ovo)

2. **Precos diferentes por embalagem** (nao apenas media do SKU):
   - Embalagens maiores podem ter preco unitario menor
   - Criar estrategia de precificacao por embalagem

3. **Custos de embalagem mais significativos**:
   - Atualmente custo medio e R$ 0,01 (muito baixo)
   - Revisar custos reais de producao/logistica por embalagem

4. **Analise de demanda**:
   - Priorizar embalagens com maior demanda/giro
   - Considerar elasticidade de preco

## CONCLUSÃO

O modelo de realocacao gera ganho porque **realoca volume entre SKUs diferentes**, aproveitando diferencas significativas de margem (R$ 1-2/unidade). O modelo de mix diario nao gera ganho porque apenas escolhe embalagens para SKUs individuais, onde as diferencas de margem sao muito pequenas (R$ 0,004/unidade).

Para o modelo de mix diario gerar ganho, seria necessario implementar logica de realocacao de volume entre SKUs, similar ao modelo de realocacao, mas adaptado para o contexto de estoque diario.

