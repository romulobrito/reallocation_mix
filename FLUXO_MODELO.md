# Fluxo do Modelo de Otimização de Mix Diário

## Diagrama de Fluxo Simplificado

```mermaid
flowchart TD
    Start([Início]) --> Config[Carregar Configuração]
    
    Config --> Carregar[Carregar Dados de Entrada]
    
    Carregar --> I1[Estoque]
    Carregar --> I2[Classes]
    Carregar --> I3[Pedidos]
    Carregar --> I4[Compatibilidade]
    Carregar --> I5[Preços]
    Carregar --> I6[Custos]
    Carregar --> I7[Faturamento Histórico]
    
    I1 --> Preparar[Preparar Dados]
    I2 --> Preparar
    I3 --> Preparar
    I4 --> Preparar
    I5 --> Preparar
    I6 --> Preparar
    I7 --> Preparar
    
    Preparar --> Criar[Criar Modelo MILP]
    
    Criar --> Objetivo{Tipo Objetivo?}
    Objetivo -->|maximizar_margem| Max[Maximizar Margem]
    Objetivo -->|minimizar_custos| Min[Minimizar Custos]
    
    Max --> Restricoes[Adicionar Restrições]
    Min --> Restricoes
    
    Restricoes --> Resolver[Resolver com OR-Tools]
    
    Resolver --> Status{Status?}
    Status -->|Sucesso| Resultados[Gerar Resultados]
    Status -->|Erro| Fim([Fim])
    
    Resultados --> CSV[CSV Detalhado]
    Resultados --> Excel[Excel com Estatísticas]
    Resultados --> Log[Log de Execução]
    
    CSV --> Fim
    Excel --> Fim
    Log --> Fim
    
    style Start fill:#90EE90
    style Fim fill:#FFB6C1
    style Carregar fill:#87CEEB
    style Preparar fill:#DDA0DD
    style Criar fill:#F0E68C
    style Resolver fill:#FFA07A
    style Resultados fill:#98FB98
```

## Diagrama de Fluxo Detalhado

```mermaid
flowchart TD
    Start([Início]) --> Config[Carregar Config YAML]
    
    Config --> Inputs[INPUTS - Carregamento de Dados]
    
    Inputs --> I1[Estoque Diário<br/>manti_estoque.parquet]
    Inputs --> I2[Classificação SKUs<br/>base_skus_classes.xlsx]
    Inputs --> I3[Pedidos Clientes<br/>pedidos_clientes.csv]
    Inputs --> I4[Compatibilidade SKU x Embalagem<br/>compatibilidade_sku_embalagem.csv]
    Inputs --> I5[Preços Históricos<br/>precos_sku_embalagem.csv]
    Inputs --> I6[Custos de Produção<br/>CUSTO ITEM.csv]
    Inputs --> I7[Faturamento Histórico<br/>manti_fat_2024.parquet<br/>Opcional: Demanda Histórica]
    
    I1 --> Prep[PREPARAÇÃO DE DADOS]
    I2 --> Prep
    I3 --> Prep
    I4 --> Prep
    I5 --> Prep
    I6 --> Prep
    I7 --> Prep
    
    Prep --> Prep1[Calcular Estoque Excedente<br/>Estoque - Pedidos]
    Prep --> Prep2[Calcular Margem Unitária<br/>Preço - Custo]
    Prep --> Prep3[Calcular Demanda Histórica<br/>Opcional: Percentil/Máximo]
    Prep --> Prep4[Filtrar Combinações Válidas<br/>Margem > 0]
    
    Prep1 --> Modelo[CRIAÇÃO DO MODELO MILP]
    Prep2 --> Modelo
    Prep3 --> Modelo
    Prep4 --> Modelo
    
    Modelo --> Vars[Criar Variáveis de Decisão<br/>x item,embalagem<br/>y item - Pedidos]
    
    Vars --> Obj[Definir Função Objetivo]
    
    Obj --> Obj1{Modo?}
    Obj1 -->|maximizar_margem| MaxMarg[Maximizar Margem Total<br/>Σ margem × quantidade]
    Obj1 -->|minimizar_custos| MinCust[Minimizar Custos Totais<br/>Σ custo × quantidade]
    
    MaxMarg --> Restr[Adicionar Restrições]
    MinCust --> Restr
    
    Restr --> R1[Restrição 1: Atendimento Pedidos<br/>y menor ou igual min pedido,estoque]
    Restr --> R2[Restrição 2: Estoque por Classe<br/>Soma alocações menor ou igual estoque_classe]
    Restr --> R3[Restrição 3: Limite Realocação<br/>alocação_sku menor ou igual lambda x estoque_sku]
    Restr --> R4[Restrição 4: Demanda Histórica<br/>Opcional: alocação menor ou igual demanda_max]
    Restr --> R5[Restrição 5: Não Negatividade<br/>x e y maior ou igual 0]
    
    R1 --> Solver[RESOLUÇÃO - OR-Tools SCIP]
    R2 --> Solver
    R3 --> Solver
    R4 --> Solver
    R5 --> Solver
    
    Solver --> Solver1[Resolver MILP]
    Solver1 --> Solver2{Status?}
    
    Solver2 -->|Ótimo| Extract[Extrair Solução]
    Solver2 -->|Viável| Extract
    Solver2 -->|Inviável| Error[Erro: Sem Solução]
    
    Extract --> Outputs[OUTPUTS - Resultados]
    
    Outputs --> O1[CSV: Alocação Detalhada<br/>resultado_YYYYMMDD_HHMMSS.csv]
    Outputs --> O2[Excel: Resultados Completos<br/>resultado_YYYYMMDD_HHMMSS.xlsx<br/>- Aba: Alocação<br/>- Aba: Estatísticas]
    Outputs --> O3[Log: Métricas e Ganhos<br/>logs/modelo_YYYYMMDD_HHMMSS.log]
    
    O1 --> End([Fim])
    O2 --> End
    O3 --> End
    Error --> End
    
    style Start fill:#90EE90
    style End fill:#FFB6C1
    style Inputs fill:#87CEEB
    style Prep fill:#DDA0DD
    style Modelo fill:#F0E68C
    style Solver fill:#FFA07A
    style Outputs fill:#98FB98
    style Error fill:#FF6B6B
```

## Descrição dos Componentes

### INPUTS (Entradas)

1. **Estoque Diário** (`manti_estoque.parquet`)
   - Estoque disponível por SKU em uma data específica
   - Filtrado por tipo de estoque (ex: "DISPONIVEL PARA VENDA")

2. **Classificação SKUs** (`base_skus_classes.xlsx`)
   - Mapeamento de SKU → Classe de Produto
   - Define agrupamentos para realocação

3. **Pedidos Clientes** (`pedidos_clientes.csv`)
   - Demandas específicas por SKU
   - Podem ser atendidos parcialmente

4. **Compatibilidade** (`compatibilidade_sku_embalagem.csv`)
   - Combinações viáveis de SKU x Embalagem
   - Histórica (vendidas) + Técnica (viáveis)

5. **Preços Históricos** (`precos_sku_embalagem.csv`)
   - Preço médio por combinação (SKU, Embalagem)
   - Calculado a partir do faturamento histórico

6. **Custos de Produção** (`CUSTO ITEM.csv`)
   - Custo de produção por SKU
   - Obtido do sistema de custeio

7. **Faturamento Histórico** (`manti_fat_2024.parquet`)
   - Opcional: usado para calcular limites de demanda histórica
   - Suporta granularidade mensal/semanal/diária

### PROCESSAMENTO

1. **Preparação de Dados**
   - Merge de todos os datasets
   - Cálculo de estoque excedente (estoque - pedidos)
   - Cálculo de margem unitária (preço - custo)
   - Cálculo de demanda histórica (se habilitado)
   - Filtragem de combinações válidas

2. **Criação do Modelo MILP**
   - Variáveis de decisão: `x[item, embalagem]` e `y[item]`
   - Função objetivo: Maximizar margem OU Minimizar custos
   - Restrições operacionais e comerciais

3. **Resolução**
   - OR-Tools com solver SCIP
   - Busca solução ótima ou viável
   - Limite de tempo configurável

### OUTPUTS (Saídas)

1. **CSV Detalhado** (`resultado_YYYYMMDD_HHMMSS.csv`)
   - Alocação ótima por combinação (SKU, Embalagem)
   - Separação entre PEDIDO e EXCEDENTE
   - Métricas de realocação

2. **Excel Completo** (`resultado_YYYYMMDD_HHMMSS.xlsx`)
   - Aba "Alocação": Detalhamento completo
   - Aba "Estatísticas": Resumo de métricas, ganhos, tempos

3. **Log Detalhado** (`logs/modelo_YYYYMMDD_HHMMSS.log`)
   - Processo completo de execução
   - Métricas de ganho (baseline vs otimizado)
   - Informações de debug

## Fluxo de Decisão

### Modo de Operação

O modelo pode operar em diferentes modos conforme configuração:

- **Atender Pedidos**: `true` = prioriza pedidos, otimiza excedente | `false` = ignora pedidos
- **Usar Apenas Excedente**: `true` = otimiza só excedente | `false` = otimiza estoque total
- **Tipo Objetivo**: `maximizar_margem` (padrão) | `minimizar_custos` (desova de estoque)

### Restrições Opcionais

- **Demanda Histórica**: Limita alocação baseada em padrões históricos de venda
  - Granularidade: Mensal (M), Semanal (S), Diária (D)
  - Método: Percentil ou Máximo Histórico

