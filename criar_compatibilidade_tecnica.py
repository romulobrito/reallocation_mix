"""
Cria dataset de compatibilidade técnica SKU x Embalagem.

Baseado no histórico, mas expande para incluir embalagens compatíveis
mesmo que não tenham sido vendidas no histórico.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))
from extrair_compatibilidade_embalagem import extrair_embalagem_descricao, calcular_qtd_embalagem

print("="*80)
print("CRIACAO DE COMPATIBILIDADE TECNICA SKU x EMBALAGEM")
print("="*80)

# Carregar dados
print("\n[1] Carregando dados...")
df_fat = pd.read_parquet('../manti_fat_2024.parquet')
df_comp_historico = pd.read_csv('inputs/compatibilidade_sku_embalagem.csv')

# Detectar coluna de descrição
col_desc = None
for col in df_fat.columns:
    if col == 'ITEM -  DESCRIÇÃO' or col == 'ITEM - DESCRIÇÃO':
        col_desc = col
        break

if col_desc is None:
    for col in df_fat.columns:
        if 'descri' in col.lower() and 'item' in col.lower():
            col_desc = col
            break

# Extrair características dos SKUs
print("\n[2] Extraindo características dos SKUs...")
df_fat['embalagem_historico'] = df_fat[col_desc].apply(extrair_embalagem_descricao)

# Agregar por SKU para identificar tipo de ovo
df_skus = df_fat.groupby('item').agg({
    col_desc: 'first',
    'embalagem_historico': lambda x: x.dropna().unique().tolist() if x.dropna().any() else []
}).reset_index()

# Função para identificar tipo de ovo da descrição
def identificar_tipo_ovo(descricao):
    """Identifica tipo de ovo (GRANDE, EXTRA, JUMBO, etc.)"""
    if pd.isna(descricao):
        return None
    desc_upper = str(descricao).upper()
    
    if 'JUMBO' in desc_upper:
        return 'JUMBO'
    elif 'EXTRA' in desc_upper:
        return 'EXTRA'
    elif 'GRANDE' in desc_upper or ' GR ' in desc_upper:
        return 'GRANDE'
    elif 'MEDIO' in desc_upper or ' MD ' in desc_upper:
        return 'MEDIO'
    elif 'PEQUENO' in desc_upper or ' PQ ' in desc_upper:
        return 'PEQUENO'
    else:
        return 'OUTROS'

df_skus['tipo_ovo'] = df_skus[col_desc].apply(identificar_tipo_ovo)

# Lista de embalagens disponíveis (do histórico)
embalagens_disponiveis = df_comp_historico['embalagem'].unique()

print(f"  SKUs únicos: {len(df_skus)}")
print(f"  Embalagens disponíveis: {len(embalagens_disponiveis)}")
print(f"  Tipos de ovo: {df_skus['tipo_ovo'].value_counts().to_dict()}")

# Criar compatibilidade técnica
# Regra: SKUs do mesmo tipo de ovo podem usar embalagens compatíveis
print("\n[3] Criando compatibilidade técnica...")

compatibilidade_tecnica = []

for idx, row in df_skus.iterrows():
    item = int(row['item'])
    tipo_ovo = row['tipo_ovo']
    embalagens_historicas = row['embalagem_historico']
    
    # Embalagens já usadas no histórico (sempre compatíveis)
    for emb in embalagens_historicas:
        if emb:
            qtd = calcular_qtd_embalagem(emb)
            compatibilidade_tecnica.append({
                'item': item,
                'embalagem': emb,
                'qtd_embalagem': qtd,
                'fonte': 'HISTORICO',
                'tipo_ovo': tipo_ovo
            })
    
    # Para embalagens não usadas no histórico, aplicar regras de compatibilidade
    # Regra simples: se o tipo de ovo é compatível com a capacidade da embalagem
    for emb in embalagens_disponiveis:
        if emb not in embalagens_historicas:
            qtd = calcular_qtd_embalagem(emb)
            
            # Regra de compatibilidade básica (pode ser refinada)
            # JUMBO precisa de embalagens maiores (mais unidades)
            # PEQUENO pode ir em embalagens menores
            # Por enquanto, vamos ser conservadores: só adicionar se for do mesmo tipo de capacidade
            
            # Extrair capacidade da embalagem histórica mais comum
            if len(embalagens_historicas) > 0 and embalagens_historicas[0]:
                qtd_historica = calcular_qtd_embalagem(embalagens_historicas[0])
                
                # Se a capacidade for similar (±20%), considerar compatível
                if qtd_historica and qtd:
                    diferenca_pct = abs(qtd - qtd_historica) / qtd_historica
                    if diferenca_pct <= 0.2:  # 20% de tolerância
                        compatibilidade_tecnica.append({
                            'item': item,
                            'embalagem': emb,
                            'qtd_embalagem': qtd,
                            'fonte': 'TECNICA',
                            'tipo_ovo': tipo_ovo
                        })

df_comp_tecnica = pd.DataFrame(compatibilidade_tecnica)
df_comp_tecnica = df_comp_tecnica.drop_duplicates(['item', 'embalagem'])

print(f"  Combinações criadas: {len(df_comp_tecnica)}")
print(f"  Do histórico: {len(df_comp_tecnica[df_comp_tecnica['fonte'] == 'HISTORICO'])}")
print(f"  Técnicas (novas): {len(df_comp_tecnica[df_comp_tecnica['fonte'] == 'TECNICA'])}")

# Salvar
output_path = Path("inputs/compatibilidade_tecnica_sku_embalagem.csv")
df_comp_tecnica.to_csv(output_path, index=False, encoding='utf-8')
print(f"\n[OK] Dataset salvo: {output_path}")

print("\n" + "="*80)
print("ESTATISTICAS:")
print("="*80)
print(f"\nSKUs com múltiplas embalagens:")
skus_multiplas = df_comp_tecnica.groupby('item').size()
print(f"  {len(skus_multiplas[skus_multiplas > 1])} SKUs têm 2+ embalagens")
print(f"  {len(skus_multiplas[skus_multiplas == 1])} SKUs têm apenas 1 embalagem")

