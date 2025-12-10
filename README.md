# Modelo de Otimização de Mix Diário com Realocação entre SKUs

## Descrição

Este modelo utiliza OR-Tools (MILP) para otimizar o mix diário de produtos, permitindo **realocação de volume entre SKUs da mesma classe biológica** para maximizar a margem total.

### Diferencial Principal

**Realocação entre SKUs da mesma classe**: SKUs biologicamente equivalentes (mesma classe) compartilham o estoque total da classe, permitindo que o modelo mova volume de SKUs com menor margem para SKUs com maior margem, gerando ganhos significativos (tipicamente 24-28% de aumento de margem).

### Exemplo

- Classe `BRANCO_GRANDE_MTQ` tem 3 SKUs no estoque:
  - SKU A: 1000 unidades (margem R$ 0.50/un)
  - SKU B: 500 unidades (margem R$ 0.30/un)
  - SKU C: 300 unidades (margem R$ 0.20/un)
- Estoque total da classe: 1800 unidades
- **Sem realocação**: Margem = 1000×0.50 + 500×0.30 + 300×0.20 = R$ 710
- **Com realocação**: O modelo pode alocar mais de 1000 unidades para SKU A (ex: 1500 un), desde que o total não ultrapasse 1800 unidades
- **Com realocação**: Margem = 1500×0.50 + 300×0.30 = R$ 840 (ganho de 18%)

## Estrutura do Projeto

```
otimizacao_mix_diario/
├── README.md                              # Este arquivo
├── requirements.txt                       # Dependências Python
├── config.yaml                            # Configurações do modelo
├── modelo_otimizacao_com_realocacao.py    # Modelo principal
├── extrair_compatibilidade_embalagem.py   # Script: extrair compatibilidade do histórico
├── extrair_precos_embalagem.py            # Script: extrair preços do histórico
├── criar_compatibilidade_tecnica.py        # Script: criar compatibilidade técnica
├── criar_custo_embalagem.py               # Script: criar custos de embalagem
├── inputs/                                 # Datasets gerados (criados pelos scripts)
│   ├── compatibilidade_sku_embalagem.csv
│   ├── compatibilidade_tecnica_sku_embalagem.csv
│   ├── precos_sku_embalagem.csv
│   └── custo_embalagem.csv
└── resultados/                             # Resultados da otimização (gerados)
    ├── resultado_realocacao.csv
    └── resumo_por_classe.csv
```

## Pré-requisitos

### Dados Necessários

Os seguintes arquivos devem estar disponíveis (não versionados no Git):

1. **Estoque diário**: `../manti_estoque.parquet`
   - Colunas: `DATA DA CONTAGEM`, `ITEM`, `TIPO DE ESTOQUE`, `QUANTIDADE`

2. **Faturamento histórico**: `../manti_fat_2024.parquet`
   - Usado para extrair compatibilidade e preços históricos

3. **Custos**: `../CUSTO ITEM.csv`
   - Colunas: `ITEM - DESCRIÇÃO`, `CUSTO YTD`

4. **Classificação de SKUs**: `../base_skus_classes.xlsx`
   - Colunas: `item`, `Classe_Produto` (ou similar)

### Dependências Python

```bash
pip install -r requirements.txt
```

Ou instalar manualmente:

```bash
pip install pandas numpy ortools pyyaml pyarrow openpyxl
```

## Como Usar

### Passo 1: Preparar Dados de Entrada

Execute os scripts para gerar os datasets necessários:

```bash
cd otimizacao_mix_diario

# 1. Extrair compatibilidade histórica SKU x Embalagem
python extrair_compatibilidade_embalagem.py

# 2. Extrair preços por (SKU, Embalagem)
python extrair_precos_embalagem.py

# 3. (Opcional) Criar compatibilidade técnica (expande opções)
python criar_compatibilidade_tecnica.py

# 4. (Opcional) Criar custos de embalagem
python criar_custo_embalagem.py
```

Isso criará os arquivos em `inputs/`:
- `compatibilidade_sku_embalagem.csv` (obrigatório)
- `precos_sku_embalagem.csv` (obrigatório)
- `compatibilidade_tecnica_sku_embalagem.csv` (opcional, mas recomendado)
- `custo_embalagem.csv` (opcional)

### Passo 2: Configurar

Edite `config.yaml` para ajustar:

- **Data do estoque**: `dados.data_estoque` (ex: "2025-08-19")
- **Tipo de estoque**: `dados.tipo_estoque` (ex: "DISPONIVEL PARA VENDA")
- **Limite de realocação**: `modelo.limite_realocacao` (ex: 2.0 = SKU pode receber até 2x seu estoque original)
- **Parâmetros do solver**: tempo limite, gap de otimalidade, etc.

### Passo 3: Executar Modelo

```bash
python modelo_otimizacao_com_realocacao.py
```

O modelo irá:
1. Carregar estoque do dia especificado
2. Carregar classificação de SKUs por classe
3. Carregar compatibilidade e preços
4. Criar modelo MILP com restrições de realocação
5. Resolver e gerar resultados

### Passo 4: Analisar Resultados

Os resultados são salvos em `resultados/`:
- `resultado_realocacao.csv`: Alocação ótima detalhada com variações de realocação
- `resumo_por_classe.csv`: Métricas agregadas por classe

O log no console mostra:
- Margem baseline (sem realocação)
- Margem otimizada (com realocação)
- Ganho absoluto e percentual
- Realocações significativas por SKU

## Modelo Matemático

### Variáveis de Decisão

```
x[sku, embalagem] = quantidade do SKU embalada na embalagem (unidades de ovo)
```

### Restrições

1. **Estoque total por CLASSE** (permite realocação):
   ```
   Σ_sku∈classe Σ_embalagem x[sku, embalagem] <= estoque_total_classe
   ```

2. **Limite de realocação por SKU** (evita soluções extremas):
   ```
   Σ_embalagem x[sku, embalagem] <= estoque_original_sku × limite_realocacao
   ```
   Onde `limite_realocacao` tipicamente é 2.0 (SKU pode receber até 2x seu estoque original).

3. **Compatibilidade**:
   ```
   x[sku, embalagem] = 0  se (sku, embalagem) não for compatível
   ```

### Função Objetivo

```
MAXIMIZAR: Σ_sku Σ_embalagem (margem[sku, embalagem] × x[sku, embalagem])

onde:
margem[sku, embalagem] = preco[sku, embalagem] - custo_sku[sku] - custo_embalagem[embalagem]
```

## Diferenças em Relação ao Modelo Sem Realocação

| Aspecto | Modelo Sem Realocação | Modelo Com Realocação |
|---------|----------------------|----------------------|
| **Restrição de estoque** | Por SKU individual | Por classe (compartilhado) |
| **Realocação** | Não permitida | Permitida entre SKUs da mesma classe |
| **Ganho típico** | 0-5% | 24-28% |
| **Complexidade** | Mais simples | Mais complexo (mais variáveis) |

## Resultados Típicos

Com base em testes realizados:

- **Ganho percentual**: 24-28% de aumento de margem em relação ao baseline
- **Ganho absoluto**: R$ 1,0M - R$ 1,2M por dia em estoques de ~95.000 unidades
- **Realocação**: SKUs com maior margem recebem 50-100% mais volume
- **Tempo de resolução**: < 1 segundo para problemas com ~200 variáveis

## Troubleshooting

### Erro: "Arquivo não encontrado: inputs/compatibilidade_sku_embalagem.csv"
**Solução**: Execute primeiro `extrair_compatibilidade_embalagem.py`

### Erro: "Coluna de descrição não encontrada"
**Solução**: Verifique se o faturamento tem coluna com "descrição" e "item" no nome. Os scripts detectam automaticamente, mas podem falhar se o formato for muito diferente.

### Modelo não resolve (INFEASIBLE)
**Solução**: 
- Verifique se há compatibilidade entre SKUs do estoque e embalagens
- Verifique se há preços para as combinações
- Verifique se há custos para todos os SKUs
- Tente aumentar `limite_realocacao` em `config.yaml`

### Ganho zero ou muito baixo
**Solução**:
- Verifique se há diferença de margem entre SKUs da mesma classe
- Verifique se o limite de realocação não está muito restritivo
- Execute `analisar_potencial_ganho.py` para diagnosticar

## Arquivos Auxiliares

- `testar_com_realocacao.py`: Script para testar o modelo em múltiplas datas
- `analisar_potencial_ganho.py`: Análise de potencial de ganho por classe
- `verificar_datas_estoque.py`: Verificar datas disponíveis no estoque
- `DIFERENCA_MODELOS.md`: Documentação detalhada das diferenças entre modelos

## Referências

- Documentação técnica: `../modelo_otimizacao_tecnico_v3.tex`
- OR-Tools: https://developers.google.com/optimization
- Modelo heurístico original: `../modelo_realocacao_completo.ipynb`

## Licença

Este projeto é de uso interno da Mantiqueira.

## Autor

Romulo Brito - 2024
