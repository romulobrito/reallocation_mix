"""
Cria dataset de custo por embalagem.

Como não temos custo real de embalagem, vamos criar um proxy baseado em:
- Custo estimado por unidade de embalagem
- Ou usar valores padrão baseados no tipo de embalagem
"""
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent))
from extrair_compatibilidade_embalagem import calcular_qtd_embalagem

print("="*80)
print("CRIACAO DE CUSTO POR EMBALAGEM")
print("="*80)

# Carregar embalagens do histórico
df_comp = pd.read_csv('inputs/compatibilidade_sku_embalagem.csv')

# Extrair embalagens únicas
embalagens = df_comp['embalagem'].unique()

print(f"\n[1] Embalagens encontradas: {len(embalagens)}")

# Criar custo estimado por embalagem
# Estratégia: usar custo proporcional à quantidade de ovos na embalagem
# Custo base por ovo na embalagem: R$ 0.01 a R$ 0.05 (ajustar conforme necessário)

custos_embalagem = []

for emb in embalagens:
    if pd.isna(emb):
        continue
    
    # Usar função existente para calcular quantidade
    qtd_total = calcular_qtd_embalagem(emb)
    
    if qtd_total is None or qtd_total == 0:
        print(f"  [AVISO] Não foi possível calcular quantidade para: {emb}")
        continue
    
    # Custo estimado: proporcional ao tamanho
    # Embalagens maiores têm custo unitário menor
    if qtd_total >= 360:
        custo_unit = 0.01  # R$ 0.01 por ovo (embalagens grandes)
    elif qtd_total >= 240:
        custo_unit = 0.015  # R$ 0.015 por ovo
    elif qtd_total >= 180:
        custo_unit = 0.02  # R$ 0.02 por ovo
    else:
        custo_unit = 0.025  # R$ 0.025 por ovo (embalagens pequenas)
    
    custo_total_emb = qtd_total * custo_unit
    
    custos_embalagem.append({
        'embalagem': emb,
        'qtd_embalagem': qtd_total,
        'custo_unitario_embalagem': custo_unit,
        'custo_total_embalagem': custo_total_emb,
        'fonte': 'ESTIMADO',
        'observacao': 'Custo estimado - ajustar com valores reais quando disponivel'
    })

df_custo_emb = pd.DataFrame(custos_embalagem)

if len(df_custo_emb) > 0:
    print(f"\n[2] Custos criados: {len(df_custo_emb)} embalagens")
    print(df_custo_emb[['embalagem', 'qtd_embalagem', 'custo_unitario_embalagem', 'custo_total_embalagem']].to_string(index=False))
else:
    print("\n[ERRO] Nenhum custo foi criado. Verificar formato das embalagens.")

# Salvar
output_path = Path("inputs/custo_embalagem.csv")
df_custo_emb.to_csv(output_path, index=False, encoding='utf-8')
print(f"\n[OK] Dataset salvo: {output_path}")

print("\n" + "="*80)
print("OBSERVACAO:")
print("="*80)
print("  Os custos de embalagem sao ESTIMADOS.")
print("  Para valores reais, substitua este arquivo com custos reais de embalagem.")
print("  O modelo usara: custo_total = custo_sku + custo_embalagem")

