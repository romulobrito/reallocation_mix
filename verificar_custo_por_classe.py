#!/usr/bin/env python3
"""Verifica se custos variam entre SKUs da mesma classe usando o código do modelo."""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Carregar config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Carregar custos usando o mesmo método do modelo
print("Carregando custos...")
path_custo = Path(config['paths']['custos'])

# Tentar diferentes métodos de leitura (arquivo pode ter BOM)
try:
    df_custo = pd.read_csv(path_custo, encoding='utf-8-sig', engine='python')
except:
    try:
        df_custo = pd.read_csv(path_custo, encoding='utf-8-sig')
    except:
        df_custo = pd.read_csv(path_custo, encoding='latin-1', engine='python')

# Extrair codigo do item
col_item_desc = None
for col in df_custo.columns:
    if 'item' in col.lower() and 'descri' in col.lower():
        col_item_desc = col
        break

if col_item_desc is None:
    col_item_desc = df_custo.columns[0]

df_custo['item'] = pd.to_numeric(
    df_custo[col_item_desc].str.extract(r'^(\d+)')[0],
    errors='coerce'
)

# Converter custo
def parse_currency(valor):
    if pd.isna(valor):
        return np.nan
    limpo = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(limpo) if limpo else np.nan
    except:
        return np.nan

col_custo = None
for col in df_custo.columns:
    if 'custo' in col.lower() and 'ytd' in col.lower():
        col_custo = col
        break

df_custo['custo_ytd'] = df_custo[col_custo].apply(parse_currency)
df_custo = df_custo[df_custo['item'].notna() & df_custo['custo_ytd'].notna()]
df_custo['item'] = df_custo['item'].astype(int)
df_custo = df_custo[['item', 'custo_ytd']].drop_duplicates('item')

print(f"  SKUs com custo carregados: {len(df_custo)}")

# Carregar classes
print("Carregando classes...")
df_classes = pd.read_excel(config['paths']['classes'])
df_classes['item'] = df_classes['item'].astype(int)

# Juntar
df = df_custo.merge(df_classes, on='item', how='inner')
print(f"  SKUs com custo e classe: {len(df)}")

# Normalizar nome da coluna de classe
if 'Classe_Produto' in df.columns:
    df['classe'] = df['Classe_Produto']
elif 'classe' not in df.columns:
    print("ERRO: Coluna de classe não encontrada")
    print("Colunas disponíveis:", df.columns.tolist())
    exit(1)

# Verificar variação de custo por classe
print('\n' + '='*80)
print('ANÁLISE: VARIAÇÃO DE CUSTO POR CLASSE DE PRODUTO')
print('='*80)
print()

variacao_por_classe = df.groupby('classe')['custo_ytd'].agg(['min', 'max', 'mean', 'std', 'count']).reset_index()
variacao_por_classe['variacao_abs'] = variacao_por_classe['max'] - variacao_por_classe['min']
variacao_por_classe['variacao_pct'] = (variacao_por_classe['variacao_abs'] / variacao_por_classe['min'] * 100).round(1)
variacao_por_classe = variacao_por_classe.sort_values('variacao_abs', ascending=False)

print(f'Total de classes analisadas: {len(variacao_por_classe)}')
print(f'Classes com custos variando (> R$ 0,01): {len(variacao_por_classe[variacao_por_classe["variacao_abs"] > 0.01])}')
print(f'Classes com custos constantes: {len(variacao_por_classe[variacao_por_classe["variacao_abs"] <= 0.01])}')
print()

classes_com_variacao = variacao_por_classe[variacao_por_classe['variacao_abs'] > 0.01]
if len(classes_com_variacao) > 0:
    print('Top 15 classes com maior variação de custo entre SKUs:')
    print('-'*80)
    print(classes_com_variacao.head(15)[['classe', 'count', 'min', 'max', 'variacao_abs', 'variacao_pct']].to_string(index=False))
    print()
    
    # Exemplos detalhados
    print('Exemplos detalhados (3 primeiras classes):')
    print('-'*80)
    for idx, row in classes_com_variacao.head(3).iterrows():
        classe = row['classe']
        df_classe = df[df['classe'] == classe].sort_values('custo_ytd')
        print(f'\nClasse: {classe}')
        print(f'  SKUs: {len(df_classe)}')
        print(f'  Custo mínimo: R$ {row["min"]:.2f}')
        print(f'  Custo máximo: R$ {row["max"]:.2f}')
        print(f'  Variação: R$ {row["variacao_abs"]:.2f} ({row["variacao_pct"]:.1f}%)')
        print(f'  Exemplos de SKUs:')
        for _, sku_row in df_classe.head(3).iterrows():
            print(f'    - SKU {sku_row["item"]}: R$ {sku_row["custo_ytd"]:.2f}')
        if len(df_classe) > 3:
            print(f'    ... e mais {len(df_classe) - 3} SKUs')
else:
    print('Nenhuma classe tem variação significativa de custo (> R$ 0,01)')
    print('Isso significa que SKUs da mesma classe têm custos muito similares.')

print()
print('='*80)
print('CONCLUSÃO:')
print('='*80)
if len(classes_com_variacao) > 0:
    print(f'✓ Custos VARIAM entre SKUs da mesma classe em {len(classes_com_variacao)} classes')
    print('✓ Minimizar custos pode ser estratégico quando:')
    print('  - Preços são fixos ou abaixo do mercado (desova de estoque)')
    print('  - Objetivo é reduzir custos totais mantendo receita constante')
    print('  - Fim de mês: objetivo é não ter estoque com menor custo possível')
    print()
    print('  Exemplo prático:')
    print('  - Se SKU A tem custo R$ 100 e SKU B tem custo R$ 110 (mesma classe)')
    print('  - E ambos têm preço fixo de R$ 150 (desova)')
    print('  - Minimizar custos escolheria SKU A, gerando margem R$ 50 vs R$ 40')
else:
    print('✗ Custos são praticamente constantes por classe')
    print('✗ Minimizar custos não teria efeito prático significativo')
    print('✗ Maximizar margem continua sendo a melhor estratégia')
