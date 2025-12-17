# Campos Necessarios para Operacao do Modelo

Este documento lista todos os campos (colunas) necessarios em cada arquivo de input para que o modelo de otimizacao funcione corretamente.

## 1. Estoque Diario (`manti_estoque.parquet`)

**Arquivo**: Parquet com estoque diario por SKU

**Colunas Obrigatorias**:
- `ITEM` ou `CODIGO ITEM`: Codigo numerico do SKU (integer)
- `DATA DA CONTAGEM`: Data da contagem do estoque (datetime)
- `TIPO DE ESTOQUE`: Tipo de estoque (string, ex: "DISPONIVEL PARA VENDA")
- `QUANTIDADE`: Quantidade disponivel em estoque (numeric, > 0)

**Observacoes**:
- O modelo filtra por data especificada em `config.yaml` (`dados.data_estoque`)
- O modelo filtra por tipo de estoque especificado em `config.yaml` (`dados.tipo_estoque`)
- Apenas registros com quantidade > 0 sao considerados

---

## 2. Classificacao de SKUs (`base_skus_classes.xlsx`)

**Arquivo**: Excel com classificacao de SKUs por classe biologica

**Colunas Obrigatorias**:
- `item`: Codigo numerico do SKU (integer)
- `Classe_Produto` (ou coluna com "classe" e "produto" no nome): Nome da classe biologica do produto (string)

**Observacoes**:
- SKUs sem classe sao automaticamente classificados como "OUTROS"
- A classe determina quais SKUs podem compartilhar estoque (realocacao)

---

## 3. Pedidos de Clientes (`inputs/pedidos_clientes.csv`)

**Arquivo**: CSV com pedidos de clientes (opcional)

**Colunas Obrigatorias**:
- `item`: Codigo numerico do SKU solicitado (integer)
- `quantidade_pedida`: Quantidade solicitada pelo cliente (numeric, > 0)

**Colunas Opcionais**:
- `cod_cliente`: Codigo do cliente (para informacao/auditoria)

**Observacoes**:
- Se o arquivo nao existir, o modelo continua sem pedidos
- Pedidos sao agregados por SKU (soma de todos os clientes)
- O modelo permite atendimento parcial se o estoque for insuficiente

---

## 4. Compatibilidade SKU x Embalagem (`inputs/compatibilidade_sku_embalagem.csv`)

**Arquivo**: CSV gerado por `extrair_compatibilidade_embalagem.py`

**Colunas Obrigatorias**:
- `item`: Codigo numerico do SKU (integer)
- `embalagem`: Tipo de embalagem (string, ex: "CX 12/1", "CX 30/1")

**Colunas Opcionais** (geradas pelo script):
- `qtd_embalagem`: Quantidade de unidades na embalagem (integer)
- `descricao_item`: Descricao completa do item (string)
- `volume_total`: Volume total vendido no historico (numeric)
- `receita_total`: Receita total no historico (numeric)

**Observacoes**:
- Este arquivo pode ser substituido por `compatibilidade_tecnica_sku_embalagem.csv` (compatibilidade expandida)
- Define quais combinacoes (SKU, Embalagem) sao validas para otimizacao

---

## 5. Precos por (SKU, Embalagem) (`inputs/precos_sku_embalagem.csv`)

**Arquivo**: CSV gerado por `extrair_precos_embalagem.py`

**Colunas Obrigatorias**:
- `item`: Codigo numerico do SKU (integer)
- `embalagem`: Tipo de embalagem (string)
- `preco`: Preco unitario da combinacao (numeric, > 0)

**Colunas Opcionais** (geradas pelo script):
- `preco_medio`: Preco medio historico (numeric)
- `preco_mediano`: Preco mediano historico (numeric)
- `preco_ponderado`: Preco ponderado por volume (numeric) - usado como `preco` se disponivel
- `preco_std`: Desvio padrao do preco (numeric)
- `num_transacoes`: Numero de transacoes historicas (integer)
- `volume_total`: Volume total vendido (numeric)
- `receita_total`: Receita total (numeric)
- `descricao_item`: Descricao do item (string)

**Observacoes**:
- O modelo aceita `preco`, `preco_ponderado` ou `preco_medio` como coluna de preco
- Apenas combinacoes com preco > 0 sao consideradas

---

## 6. Custos por SKU (`CUSTO ITEM.csv`)

**Arquivo**: CSV com custos de producao por SKU

**Colunas Obrigatorias**:
- Coluna com "item" e "descri" no nome (ex: `ITEM - DESCRIÇÃO`): Descricao do item com codigo numerico no inicio (string)
- Coluna com "custo" e "ytd" no nome (ex: `CUSTO YTD`): Custo YTD do item (string/numeric, formato brasileiro: "R$ 1.234,56" ou numerico)

**Observacoes**:
- O codigo do item e extraido do inicio da descricao usando regex `^(\d+)`
- O custo e convertido de formato brasileiro para numerico (remove "R$", pontos e virgulas)
- Apenas SKUs com custo valido sao considerados
- O custo e por SKU, nao varia por embalagem

---

## 7. Faturamento Historico (`manti_fat_2024.parquet`)

**Arquivo**: Parquet com historico de faturamento (usado para demanda historica e scripts de preparacao)

**Colunas Necessarias para Demanda Historica**:
- Coluna com "item" no nome (ex: `ITEM`): Codigo numerico do SKU (integer)
- Coluna com "quantidade" no nome (ex: `QUANTIDADE`): Quantidade vendida (numeric, > 0)
- Coluna com "emiss" ou "data" no nome (ex: `DT.EMISSÃO`, `DT EMISSÃO`, `DATA EMISSAO`): Data da venda (datetime)

**Colunas Necessarias para Scripts de Preparacao**:

### Para `extrair_compatibilidade_embalagem.py`:
- `ITEM`: Codigo numerico do SKU (integer)
- `ITEM - DESCRIÇÃO` ou coluna com "descri" e "item" no nome: Descricao completa do item (string)
- `Quantidade`: Quantidade vendida (numeric, > 0)
- `Receita Liquida`: Receita liquida da venda (numeric, > 0)

### Para `extrair_precos_embalagem.py`:
- `ITEM`: Codigo numerico do SKU (integer)
- `ITEM - DESCRIÇÃO` ou coluna com "descri" e "item" no nome: Descricao completa do item (string)
- `Quantidade`: Quantidade vendida (numeric, > 0)
- `Receita Liquida`: Receita liquida da venda (numeric, > 0)

### Para `gerar_pedidos_clientes.py`:
- `COD.EMITENTE` ou `COD EMITENTE` ou `CODIGO EMITENTE` ou `CLIENTE`: Codigo do cliente (string/integer)
- `ITEM`: Codigo numerico do SKU (integer)
- `QUANTIDADE` ou `QTD`: Quantidade vendida (numeric, > 0)
- `DT.EMISSÃO` ou `DT EMISSÃO` ou `DT.EMISSAO` ou coluna com "data" e "emissao": Data da venda (datetime)
- (Opcional) `NOME` ou coluna com "nome" e "cliente": Nome do cliente (string)

**Observacoes**:
- O faturamento historico e usado para:
  1. Calcular demanda historica (se `considerar_demanda_historica: true`)
  2. Extrair compatibilidade SKU x Embalagem
  3. Extrair precos historicos
  4. Gerar pedidos ficticios de clientes
- O periodo historico considerado e configurado em `config.yaml` (`modelo.periodo_historico_meses`)

---

## Resumo por Arquivo

| Arquivo | Formato | Colunas Obrigatorias | Gerado por Script? |
|---------|---------|---------------------|-------------------|
| `manti_estoque.parquet` | Parquet | ITEM, DATA DA CONTAGEM, TIPO DE ESTOQUE, QUANTIDADE | Nao |
| `base_skus_classes.xlsx` | Excel | item, Classe_Produto | Nao |
| `inputs/pedidos_clientes.csv` | CSV | item, quantidade_pedida | `gerar_pedidos_clientes.py` (opcional) |
| `inputs/compatibilidade_sku_embalagem.csv` | CSV | item, embalagem | `extrair_compatibilidade_embalagem.py` |
| `inputs/precos_sku_embalagem.csv` | CSV | item, embalagem, preco | `extrair_precos_embalagem.py` |
| `CUSTO ITEM.csv` | CSV | ITEM - DESCRIÇÃO, CUSTO YTD | Nao |
| `manti_fat_2024.parquet` | Parquet | ITEM, Quantidade, DT.EMISSÃO, ITEM - DESCRIÇÃO, Receita Liquida | Nao |

---

## Deteccao Automatica de Colunas

O modelo possui deteccao automatica de colunas para maior flexibilidade:

- **Estoque**: Detecta variacoes de nome como "CODIGO ITEM", "ITEM", "QUANTIDADE", "QTD"
- **Classes**: Procura coluna com "classe" e "produto" no nome
- **Custos**: Procura coluna com "custo" e "ytd" no nome, e coluna com "item" e "descri" no nome
- **Faturamento**: Detecta variacoes como "DT.EMISSÃO", "DT EMISSÃO", "DATA EMISSAO", "QUANTIDADE", "QTD"

---

## Validacao de Dados

O modelo valida automaticamente:
- Tipos de dados (integers para SKUs, numericos para quantidades/precos)
- Valores positivos (quantidades, precos > 0)
- Datas validas (formato datetime)
- Existencia de colunas obrigatorias

Se alguma validacao falhar, o modelo exibira mensagens de erro detalhadas indicando qual arquivo e qual coluna esta faltando ou invalida.

