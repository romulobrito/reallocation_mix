# Modelo de Otimização de Mix Diário com Realocação entre SKUs

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Conceito e Ideia do Modelo](#conceito-e-ideia-do-modelo)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Como Usar](#como-usar)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Funcionalidades](#funcionalidades)
- [Resultados](#resultados)
- [Troubleshooting](#troubleshooting)

## 🎯 Visão Geral

Este modelo utiliza **Programação Linear Inteira Mista (MILP)** com OR-Tools para otimizar o mix diário de produtos, permitindo **realocação de volume entre SKUs da mesma classe biológica** para maximizar a margem total ou minimizar custos.

### Diferencial Principal

**Realocação entre SKUs da mesma classe**: SKUs biologicamente equivalentes (mesma classe) compartilham o estoque total da classe, permitindo que o modelo mova volume de SKUs com menor margem para SKUs com maior margem, gerando ganhos significativos (tipicamente **24-28% de aumento de margem**).

## 💡 Conceito e Ideia do Modelo

### Problema de Negócio

Em uma operação de produção de ovos, existem diferentes SKUs (códigos de produto) que são biologicamente equivalentes, diferindo apenas em características como embalagem ou apresentação. O desafio é decidir como alocar o estoque disponível entre diferentes combinações de SKU e embalagem para maximizar a rentabilidade.

### Solução Proposta

O modelo resolve este problema através de:

1. **Realocação Inteligente**: Permite que SKUs da mesma classe biológica compartilhem estoque, movendo volume de produtos menos rentáveis para mais rentáveis.

2. **Otimização Matemática**: Utiliza programação linear para encontrar a solução ótima que maximiza margem ou minimiza custos, respeitando restrições operacionais e comerciais.

3. **Flexibilidade Operacional**: Suporta diferentes modos de operação:
   - Atendimento prioritário de pedidos de clientes
   - Otimização apenas do excedente ou do estoque total
   - Maximização de margem (operação normal) ou minimização de custos (desova de estoque)

### Exemplo Prático

**Cenário**: Classe `BRANCO_GRANDE_MTQ` tem 3 SKUs no estoque:
- SKU A: 1000 unidades (margem R$ 0.50/un)
- SKU B: 500 unidades (margem R$ 0.30/un)
- SKU C: 300 unidades (margem R$ 0.20/un)
- **Estoque total da classe**: 1800 unidades

**Sem realocação** (modelo tradicional):
- Margem = 1000×0.50 + 500×0.30 + 300×0.20 = **R$ 710**

**Com realocação** (este modelo):
- O modelo pode alocar mais de 1000 unidades para SKU A (ex: 1500 un), desde que o total não ultrapasse 1800 unidades
- Margem = 1500×0.50 + 300×0.30 = **R$ 840** (ganho de **18%**)

## 🚀 Instalação

### Pré-requisitos

- Python 3.8 ou superior
- Git (para clonar o repositório)
- Acesso aos datasets da empresa (não versionados no Git)

### Passo 1: Clonar o Repositório

```bash
# Se ainda não tiver o repositório
git clone <url-do-repositorio>
cd mantiqueira/otimizacao_mix_diario
```

### Passo 2: Criar Ambiente Virtual (Recomendado)

```bash
# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
# No Linux/Mac:
source venv/bin/activate
# No Windows:
venv\Scripts\activate
```

### Passo 3: Instalar Dependências

```bash
# Instalar todas as dependências
pip install -r requirements.txt
```

Ou instalar manualmente:

```bash
pip install pandas>=1.5.0 numpy>=1.23.0 ortools>=9.0 pyyaml>=6.0 pyarrow>=10.0.0 openpyxl>=3.0.0
```

### Passo 4: Verificar Instalação

```bash
python3 -c "import pandas, numpy, ortools, yaml; print('Dependências instaladas com sucesso!')"
```

## ⚙️ Configuração

### Arquivos de Configuração

O modelo utiliza o arquivo `config.yaml` para todas as configurações. Principais seções:

#### 1. Caminhos dos Arquivos (`paths`)

```yaml
paths:
  estoque: "../manti_estoque.parquet"
  classes: "../base_skus_classes.xlsx"
  pedidos: "inputs/pedidos_clientes.csv"
  compatibilidade: "inputs/compatibilidade_sku_embalagem.csv"
  precos: "inputs/precos_sku_embalagem.csv"
  custos: "../CUSTO ITEM.csv"
  faturamento: "../manti_fat_2024.parquet"
```

#### 2. Parâmetros de Dados (`dados`)

```yaml
dados:
  data_estoque: "2025-08-19"  # Data do estoque a otimizar
  tipo_estoque: "DISPONIVEL PARA VENDA"
```

#### 3. Parâmetros do Modelo (`modelo`)

```yaml
modelo:
  # Tipo de função objetivo
  tipo_objetivo: maximizar_margem  # ou "minimizar_custos"
  
  # Controle de volume
  atender_pedidos: true  # true = atende pedidos, false = ignora
  usar_apenas_excedente: false  # true = só excedente, false = estoque total
  
  # Realocação
  limite_realocacao: 2.0  # SKU pode receber até 2x seu estoque original
  
  # Demanda histórica (opcional)
  considerar_demanda_historica: true
  granularidade_demanda: M  # M=Mensal, S=Semanal, D=Diária
  tipo_calculo_demanda: percentil  # "percentil" ou "maximo"
  percentil_demanda: 95
  fator_expansao_demanda: 5.0
  fator_percentual_maximo: 1.2
```

### Dados Necessários

Os seguintes arquivos devem estar disponíveis (não versionados no Git):

1. **Estoque diário**: `../manti_estoque.parquet`
   - Colunas: `DATA DA CONTAGEM`, `ITEM`, `TIPO DE ESTOQUE`, `QUANTIDADE`

2. **Faturamento histórico**: `../manti_fat_2024.parquet`
   - Usado para extrair compatibilidade, preços e calcular demanda histórica

3. **Custos**: `../CUSTO ITEM.csv`
   - Colunas: `ITEM - DESCRIÇÃO`, `CUSTO YTD`

4. **Classificação de SKUs**: `../base_skus_classes.xlsx`
   - Colunas: `item`, `Classe_Produto`

## 📖 Como Usar

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

# 4. (Opcional) Gerar pedidos fictícios de clientes
python gerar_pedidos_clientes.py
```

Isso criará os arquivos em `inputs/`:
- `compatibilidade_sku_embalagem.csv` (obrigatório)
- `precos_sku_embalagem.csv` (obrigatório)
- `compatibilidade_tecnica_sku_embalagem.csv` (opcional, mas recomendado)
- `pedidos_clientes.csv` (opcional)

### Passo 2: Configurar Modelo

Edite `config.yaml` para ajustar:
- **Data do estoque**: `dados.data_estoque`
- **Tipo de objetivo**: `modelo.tipo_objetivo` (maximizar_margem ou minimizar_custos)
- **Atender pedidos**: `modelo.atender_pedidos`
- **Limite de realocação**: `modelo.limite_realocacao`
- **Demanda histórica**: `modelo.considerar_demanda_historica` e parâmetros relacionados

### Passo 3: Executar Modelo

```bash
python modelo_otimizacao_com_realocacao.py
```

O modelo irá:
1. Carregar estoque do dia especificado
2. Carregar classificação de SKUs por classe
3. Carregar pedidos, compatibilidade e preços
4. Calcular estoque excedente (se aplicável)
5. Criar modelo MILP com restrições
6. Resolver e gerar resultados

### Passo 4: Analisar Resultados

Os resultados são salvos em `resultados/` com timestamp:
- `resultado_YYYYMMDD_HHMMSS.csv`: Alocação ótima detalhada
- `resultado_YYYYMMDD_HHMMSS.xlsx`: Excel com múltiplas abas
  - Aba "Alocação": Detalhamento completo
  - Aba "Estatísticas": Resumo de métricas, ganhos, tempos

O log no console mostra:
- Margem/custo baseline (sem otimização)
- Margem/custo otimizado (com otimização)
- Ganho absoluto e percentual
- Realocações significativas por SKU

## 📁 Estrutura do Projeto

```
otimizacao_mix_diario/
├── README.md                              # Este arquivo
├── FLUXO_MODELO.md                        # Diagrama de fluxo do modelo
├── requirements.txt                       # Dependências Python
├── .gitignore                             # Arquivos ignorados pelo Git
├── config.yaml                            # Configurações do modelo
│
├── modelo_otimizacao_com_realocacao.py   # Modelo principal ⭐
│
├── Scripts de Preparação de Dados:
│   ├── extrair_compatibilidade_embalagem.py
│   ├── extrair_precos_embalagem.py
│   ├── criar_compatibilidade_tecnica.py
│   ├── gerar_pedidos_clientes.py
│   └── criar_custo_embalagem.py
│
├── Scripts de Análise e Teste:
│   ├── testar_modos_operacao.py
│   ├── testar_com_demanda_historica.py
│   ├── testar_granularidade_mensal.py
│   ├── testar_maximo_historico.py
│   ├── verificar_custo_por_classe.py
│   └── analisar_potencial_ganho.py
│
├── inputs/                                 # Datasets gerados (não versionados)
│   ├── compatibilidade_sku_embalagem.csv
│   ├── precos_sku_embalagem.csv
│   ├── pedidos_clientes.csv
│   └── ...
│
├── resultados/                             # Resultados da otimização (não versionados)
│   ├── resultado_YYYYMMDD_HHMMSS.csv
│   └── resultado_YYYYMMDD_HHMMSS.xlsx
│
└── logs/                                   # Logs de execução (não versionados)
    └── modelo_YYYYMMDD_HHMMSS.log
```

## 🎛️ Funcionalidades

### 1. Modos de Operação

#### Atendimento de Pedidos
- **`atender_pedidos: true`**: Atende pedidos prioritariamente, otimiza apenas o excedente
- **`atender_pedidos: false`**: Ignora pedidos completamente, otimiza todo o estoque

#### Escopo de Otimização
- **`usar_apenas_excedente: true`**: Otimiza apenas estoque excedente (após pedidos)
- **`usar_apenas_excedente: false`**: Otimiza estoque total disponível

### 2. Tipos de Função Objetivo

#### Maximizar Margem (Padrão)
- **Uso**: Operação normal do dia a dia
- **Objetivo**: Maximizar margem total (preço - custo)
- **Configuração**: `tipo_objetivo: maximizar_margem`

#### Minimizar Custos
- **Uso**: Desova de estoque, fim de mês, preços fixos
- **Objetivo**: Minimizar custos totais mantendo receita
- **Configuração**: `tipo_objetivo: minimizar_custos`
- **Observação**: Ainda filtra combinações com margem positiva (ver README)

### 3. Restrições de Demanda Histórica (Opcional)

Limita a alocação baseada em padrões históricos de venda:

- **Granularidade**: Mensal (M), Semanal (S) ou Diária (D)
- **Método de Cálculo**:
  - **Percentil**: Usa percentil histórico (ex: 95%) × fator de expansão
  - **Máximo Histórico**: Usa máximo histórico × fator percentual

**Configuração**:
```yaml
modelo:
  considerar_demanda_historica: true
  granularidade_demanda: M  # M, S ou D
  tipo_calculo_demanda: percentil  # ou "maximo"
  percentil_demanda: 95
  fator_expansao_demanda: 5.0
  fator_percentual_maximo: 1.2
```

### 4. Realocação entre SKUs

- **Permite**: Mover volume entre SKUs da mesma classe biológica
- **Limite**: Cada SKU pode receber até `λ × estoque_original` (padrão: 2.0x)
- **Benefício**: Captura ganhos através de redistribuição inteligente

## 📊 Resultados

### Resultados Típicos

Com base em testes realizados sobre múltiplas datas:

- **Ganho percentual**: 24-28% de aumento de margem em relação ao baseline
- **Ganho absoluto**: R$ 1,0M - R$ 1,2M por dia em estoques de ~95.000 unidades
- **Realocação**: SKUs com maior margem recebem 50-100% mais volume
- **Tempo de resolução**: < 1 segundo para problemas com ~200-500 variáveis

### Arquivos de Saída

#### CSV Detalhado
- Alocação ótima por combinação (SKU, Embalagem)
- Separação entre PEDIDO e EXCEDENTE
- Métricas de realocação (variação de volume por SKU)
- Receita, custo e margem por combinação

#### Excel Completo
- **Aba "Alocação"**: Detalhamento completo (mesmo do CSV)
- **Aba "Estatísticas"**: 
  - Resumo de métricas (baseline vs otimizado)
  - Ganhos absolutos e percentuais
  - Tempos de execução
  - Estatísticas de restrições aplicadas

#### Log de Execução
- Processo completo passo a passo
- Informações de debug
- Métricas detalhadas de ganho

## 🔧 Troubleshooting

### Erro: "Arquivo não encontrado: inputs/compatibilidade_sku_embalagem.csv"
**Solução**: Execute primeiro `python extrair_compatibilidade_embalagem.py`

### Erro: "Coluna de descrição não encontrada"
**Solução**: Verifique se o faturamento tem coluna com "descrição" e "item" no nome. Os scripts detectam automaticamente, mas podem falhar se o formato for muito diferente.

### Modelo não resolve (INFEASIBLE)
**Solução**: 
- Verifique se há compatibilidade entre SKUs do estoque e embalagens
- Verifique se há preços para as combinações
- Verifique se há custos para todos os SKUs
- Tente aumentar `limite_realocacao` em `config.yaml`
- Verifique se restrições de demanda histórica não estão muito restritivas

### Ganho zero ou muito baixo
**Solução**:
- Verifique se há diferença de margem entre SKUs da mesma classe
- Verifique se o limite de realocação não está muito restritivo
- Execute `verificar_custo_por_classe.py` para verificar variação de custos
- Execute `analisar_potencial_ganho.py` para diagnosticar

### Erro: "ModuleNotFoundError: No module named 'ortools'"
**Solução**: 
- Ative o ambiente virtual: `source venv/bin/activate`
- Instale as dependências: `pip install -r requirements.txt`

## 📚 Documentação Adicional

- **Fluxo do Modelo**: Ver `FLUXO_MODELO.md` para diagramas de fluxo
- **Documentação Técnica**: Ver `../modelo_otimizacao_tecnico_v3.tex` para especificação matemática completa
- **Diferenças entre Modelos**: Ver `DIFERENCA_MODELOS.md`

## 🔗 Referências

- **OR-Tools**: https://developers.google.com/optimization
- **Documentação Técnica**: `../modelo_otimizacao_tecnico_v3.tex`

## ⚠️ Observações Importantes

### Filtro de Margem Positiva

**Mesmo em modo `minimizar_custos`**, o modelo mantém o filtro de margem positiva (`margem_unitaria > 0`). Isso significa que apenas combinações lucrativas são consideradas, garantindo que a minimização de custos não resulte em perdas operacionais.

**Justificativa**: Em cenários de desova de estoque, mesmo com preços abaixo do mercado, ainda é necessário garantir que a receita cubra os custos, evitando vendas com prejuízo.

### Compatibilidade

- O modelo mantém compatibilidade com código existente
- Default: `tipo_objetivo: maximizar_margem`
- Se `tipo_objetivo` não for `maximizar_margem`, assume `minimizar_custos`

## 📝 Licença

Este projeto é de uso interno da Mantiqueira.

## 👤 Autor

Romulo Brito - 2024

---

**Versão**: 3.0  
**Última atualização**: 2024-12-09
