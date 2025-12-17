# Campos Necessários para Operação do Modelo

Este documento lista todos os campos (colunas) necessários em cada arquivo de input para que o modelo de otimização funcione corretamente.

## 1. Estoque Diario (`manti_estoque.parquet`)

**Arquivo**: Parquet com estoque diario por SKU

**Colunas Obrigatórias**:
- `ITEM` ou `CODIGO ITEM`: Código numérico do SKU (integer)
- `DATA DA CONTAGEM`: Data da contagem do estoque (datetime)
- `TIPO DE ESTOQUE`: Tipo de estoque (string, ex: "DISPONIVEL PARA VENDA")
- `QUANTIDADE`: Quantidade disponível em estoque (numeric, > 0)

**Observacoes**:
- O modelo filtra por data especificada em `config.yaml` (`dados.data_estoque`)
- O modelo filtra por tipo de estoque especificado em `config.yaml` (`dados.tipo_estoque`)
- Apenas registros com quantidade > 0 sao considerados

---

## 2. Classificação de SKUs (`base_skus_classes.xlsx`)

**Arquivo**: Excel com classificação de SKUs por classe biológica

**Colunas Obrigatórias**:
- `item`: Código numérico do SKU (integer)
- `Classe_Produto` (ou coluna com "classe" e "produto" no nome): Nome da classe biológica do produto (string)

**Observacoes**:
- SKUs sem classe sao automaticamente classificados como "OUTROS"
- A classe determina quais SKUs podem compartilhar estoque (realocacao)

---

## 3. Pedidos de Clientes (`inputs/pedidos_clientes.csv`)

**Arquivo**: CSV com pedidos de clientes (opcional)

**Colunas Obrigatórias**:
- `item`: Código numérico do SKU solicitado (integer)
- `quantidade_pedida`: Quantidade solicitada pelo cliente (numeric, > 0)

**Colunas Opcionais**:
- `cod_cliente`: Código do cliente (para informação/auditoria)

**Observações**:
- Se o arquivo não existir, o modelo continua sem pedidos
- Pedidos são agregados por SKU (soma de todos os clientes)
- O modelo permite atendimento parcial se o estoque for insuficiente

---

## 4. Compatibilidade SKU x Embalagem (`inputs/compatibilidade_sku_embalagem.csv`)

**Arquivo**: CSV gerado por `extrair_compatibilidade_embalagem.py`

**Colunas Obrigatórias**:
- `item`: Código numérico do SKU (integer)
- `embalagem`: Tipo de embalagem (string, ex: "CX 12/1", "CX 30/1")

**Colunas Opcionais** (geradas pelo script):
- `qtd_embalagem`: Quantidade de unidades na embalagem (integer)
- `descricao_item`: Descrição completa do item (string)
- `volume_total`: Volume total vendido no histórico (numeric)
- `receita_total`: Receita total no histórico (numeric)

**Observações**:
- Este arquivo pode ser substituído por `compatibilidade_tecnica_sku_embalagem.csv` (compatibilidade expandida)
- Define quais combinações (SKU, Embalagem) são válidas para otimização

---

## 5. Preços por (SKU, Embalagem) (`inputs/precos_sku_embalagem.csv`)

**Arquivo**: CSV gerado por `extrair_precos_embalagem.py`

**Colunas Obrigatórias**:
- `item`: Código numérico do SKU (integer)
- `embalagem`: Tipo de embalagem (string)
- `preco`: Preço unitário da combinação (numeric, > 0)

**Colunas Opcionais** (geradas pelo script):
- `preco_medio`: Preço médio histórico (numeric)
- `preco_mediano`: Preço mediano histórico (numeric)
- `preco_ponderado`: Preço ponderado por volume (numeric) - usado como `preco` se disponível
- `preco_std`: Desvio padrão do preço (numeric)
- `num_transacoes`: Número de transações históricas (integer)
- `volume_total`: Volume total vendido (numeric)
- `receita_total`: Receita total (numeric)
- `descricao_item`: Descrição do item (string)

**Observações**:
- O modelo aceita `preco`, `preco_ponderado` ou `preco_medio` como coluna de preço
- Apenas combinações com preço > 0 são consideradas

---

## 6. Custos por SKU (`CUSTO ITEM.csv`)

**Arquivo**: CSV com custos de producao por SKU

**Colunas Obrigatórias**:
- Coluna com "item" e "descri" no nome (ex: `ITEM - DESCRIÇÃO`): Descrição do item com código numérico no início (string)
- Coluna com "custo" e "ytd" no nome (ex: `CUSTO YTD`): Custo YTD do item (string/numeric, formato brasileiro: "R$ 1.234,56" ou numérico)

**Observações**:
- O código do item é extraído do início da descrição usando regex `^(\d+)`
- O custo é convertido de formato brasileiro para numérico (remove "R$", pontos e vírgulas)
- Apenas SKUs com custo válido são considerados
- O custo é por SKU, não varia por embalagem

---

## 7. Faturamento Histórico (`manti_fat_2024.parquet`)

**Arquivo**: Parquet com histórico de faturamento (usado para demanda histórica e scripts de preparação)

**Colunas Necessárias para Demanda Histórica**:
- Coluna com "item" no nome (ex: `ITEM`): Código numérico do SKU (integer)
- Coluna com "quantidade" no nome (ex: `QUANTIDADE`): Quantidade vendida (numeric, > 0)
- Coluna com "emiss" ou "data" no nome (ex: `DT.EMISSÃO`, `DT EMISSÃO`, `DATA EMISSAO`): Data da venda (datetime)

**Colunas Necessárias para Scripts de Preparação**:

### Para `extrair_compatibilidade_embalagem.py`:
- `ITEM`: Código numérico do SKU (integer)
- `ITEM - DESCRIÇÃO` ou coluna com "descri" e "item" no nome: Descrição completa do item (string)
- `Quantidade`: Quantidade vendida (numeric, > 0)
- `Receita Liquida`: Receita líquida da venda (numeric, > 0)

### Para `extrair_precos_embalagem.py`:
- `ITEM`: Código numérico do SKU (integer)
- `ITEM - DESCRIÇÃO` ou coluna com "descri" e "item" no nome: Descrição completa do item (string)
- `Quantidade`: Quantidade vendida (numeric, > 0)
- `Receita Liquida`: Receita líquida da venda (numeric, > 0)

### Para `gerar_pedidos_clientes.py`:
- `COD.EMITENTE` ou `COD EMITENTE` ou `CODIGO EMITENTE` ou `CLIENTE`: Código do cliente (string/integer)
- `ITEM`: Código numérico do SKU (integer)
- `QUANTIDADE` ou `QTD`: Quantidade vendida (numeric, > 0)
- `DT.EMISSÃO` ou `DT EMISSÃO` ou `DT.EMISSAO` ou coluna com "data" e "emissao": Data da venda (datetime)
- (Opcional) `NOME` ou coluna com "nome" e "cliente": Nome do cliente (string)

**Observações**:
- O faturamento histórico é usado para:
  1. Calcular demanda histórica (se `considerar_demanda_historica: true`)
  2. Extrair compatibilidade SKU x Embalagem
  3. Extrair preços históricos
  4. Gerar pedidos fictícios de clientes
- O período histórico considerado é configurado em `config.yaml` (`modelo.periodo_historico_meses`)

---

## Resumo por Arquivo

| Arquivo | Formato | Colunas Obrigatórias | Gerado por Script? |
|---------|---------|---------------------|-------------------|
| `manti_estoque.parquet` | Parquet | ITEM, DATA DA CONTAGEM, TIPO DE ESTOQUE, QUANTIDADE | Não |
| `base_skus_classes.xlsx` | Excel | item, Classe_Produto | Não |
| `inputs/pedidos_clientes.csv` | CSV | item, quantidade_pedida | `gerar_pedidos_clientes.py` (opcional) |
| `inputs/compatibilidade_sku_embalagem.csv` | CSV | item, embalagem | `extrair_compatibilidade_embalagem.py` |
| `inputs/precos_sku_embalagem.csv` | CSV | item, embalagem, preco | `extrair_precos_embalagem.py` |
| `CUSTO ITEM.csv` | CSV | ITEM - DESCRIÇÃO, CUSTO YTD | Não |
| `manti_fat_2024.parquet` | Parquet | ITEM, Quantidade, DT.EMISSÃO, ITEM - DESCRIÇÃO, Receita Liquida | Não |

---

## Detecção Automática de Colunas

O modelo possui detecção automática de colunas para maior flexibilidade:

- **Estoque**: Detecta variações de nome como "CODIGO ITEM", "ITEM", "QUANTIDADE", "QTD"
- **Classes**: Procura coluna com "classe" e "produto" no nome
- **Custos**: Procura coluna com "custo" e "ytd" no nome, e coluna com "item" e "descri" no nome
- **Faturamento**: Detecta variações como "DT.EMISSÃO", "DT EMISSÃO", "DATA EMISSAO", "QUANTIDADE", "QTD"

---

## Validação de Dados

O modelo valida automaticamente:
- Tipos de dados (integers para SKUs, numéricos para quantidades/preços)
- Valores positivos (quantidades, preços > 0)
- Datas válidas (formato datetime)
- Existência de colunas obrigatórias

Se alguma validação falhar, o modelo exibirá mensagens de erro detalhadas indicando qual arquivo e qual coluna está faltando ou inválida.

