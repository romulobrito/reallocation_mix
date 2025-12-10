"""Verifica range de datas no arquivo de estoque."""
import pandas as pd
from datetime import datetime

df_estoque = pd.read_parquet('../manti_estoque.parquet')
df_estoque['DATA DA CONTAGEM'] = pd.to_datetime(df_estoque['DATA DA CONTAGEM'], errors='coerce')

df_filtrado = df_estoque[
    (df_estoque['TIPO DE ESTOQUE'] == 'DISPONIVEL PARA VENDA') &
    (df_estoque['DATA DA CONTAGEM'].notna())
]

datas_unicas = sorted(df_filtrado['DATA DA CONTAGEM'].dropna().unique())

print('='*80)
print('DATAS NO ARQUIVO DE ESTOQUE')
print('='*80)
print(f'\nTotal de datas: {len(datas_unicas)}')
print(f'Primeira data: {datas_unicas[0].strftime("%Y-%m-%d")}')
print(f'Ultima data: {datas_unicas[-1].strftime("%Y-%m-%d")}')

# Distribuicao por ano
df_filtrado['ano'] = df_filtrado['DATA DA CONTAGEM'].dt.year
dist_ano = df_filtrado.groupby('ano').agg({
    'DATA DA CONTAGEM': 'nunique',
    'QUANTIDADE': 'sum'
}).reset_index()
dist_ano.columns = ['ano', 'num_datas', 'estoque_total']

print(f'\nDistribuicao por ano:')
for _, row in dist_ano.iterrows():
    print(f'  {row["ano"]}: {row["num_datas"]} datas, {row["estoque_total"]:,.0f} unidades')

# Verificar datas futuras
hoje = datetime.now()
datas_futuras = [d for d in datas_unicas if d > hoje]

if len(datas_futuras) > 0:
    print(f'\n[ATENCAO] {len(datas_futuras)} datas FUTURAS encontradas!')
    print(f'Primeiras 5 datas futuras:')
    for d in datas_futuras[:5]:
        print(f'  {d.strftime("%Y-%m-%d")}')
else:
    print(f'\n[OK] Nenhuma data futura')

