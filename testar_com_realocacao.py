"""
Testa o modelo com realocacao em multiplas datas para encontrar maior ganho.
"""
import pandas as pd
from pathlib import Path
import yaml
from modelo_otimizacao_com_realocacao import ModeloOtimizacaoComRealocacao

print("="*80)
print("TESTE DO MODELO COM REALOCACAO - MULTIPLAS DATAS")
print("="*80)

# 1. Encontrar datas com maior estoque
print("\n[1] Analisando datas disponiveis...")
df_estoque = pd.read_parquet('../manti_estoque.parquet')
df_estoque['DATA DA CONTAGEM'] = pd.to_datetime(df_estoque['DATA DA CONTAGEM'], errors='coerce')
df_filtrado = df_estoque[
    (df_estoque['TIPO DE ESTOQUE'] == 'DISPONIVEL PARA VENDA') &
    (df_estoque['DATA DA CONTAGEM'].notna())
]

df_datas = df_filtrado.groupby('DATA DA CONTAGEM').agg({
    'ITEM': 'nunique',
    'QUANTIDADE': 'sum'
}).reset_index()
df_datas.columns = ['data', 'num_skus', 'estoque_total']
df_datas = df_datas.sort_values('estoque_total', ascending=False)

print(f"\nTop 5 datas com maior estoque:")
for idx, row in df_datas.head(5).iterrows():
    print(f"  {row['data'].strftime('%Y-%m-%d')}: {row['num_skus']:>3} SKUs, {row['estoque_total']:>12,.0f} unidades")

# 2. Testar com as top 3 datas
datas_teste = df_datas.head(3)['data'].tolist()

print(f"\n[2] Testando modelo com realocacao nas top 3 datas...")
print("="*80)

resultados = []

for data_teste in datas_teste:
    data_str = data_teste.strftime('%Y-%m-%d')
    print(f"\n{'='*80}")
    print(f"DATA: {data_str}")
    print(f"{'='*80}")
    
    # Atualizar config
    config_path = Path('config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    config['dados']['data_estoque'] = data_str
    
    # Salvar config temporario
    config_temp = Path('config_temp.yaml')
    with open(config_temp, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    try:
        # Executar modelo
        modelo = ModeloOtimizacaoComRealocacao(config_path=str(config_temp))
        modelo.carregar_dados()
        modelo.criar_modelo()
        
        if modelo.resolver():
            comparativo = modelo.calcular_comparativo()
            
            if comparativo:
                resultados.append({
                    'data': data_str,
                    'skus_estoque': modelo.dados['estoque']['item'].nunique(),
                    'estoque_total': modelo.dados['estoque']['estoque_disponivel'].sum(),
                    'classes': modelo.dados['estoque']['classe'].nunique(),
                    'margem_baseline': comparativo['margem_baseline'],
                    'margem_otimizada': comparativo['margem_otimizada'],
                    'ganho_absoluto': comparativo['ganho_absoluto'],
                    'ganho_percentual': comparativo['ganho_percentual']
                })
        
    except Exception as e:
        print(f"\n[ERRO] Falha ao processar {data_str}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if config_temp.exists():
            config_temp.unlink()

# 3. Resumo final
if len(resultados) > 0:
    df_resultados = pd.DataFrame(resultados)
    
    print("\n" + "="*80)
    print("RESUMO DOS RESULTADOS")
    print("="*80)
    print(df_resultados.to_string(index=False))
    
    # Melhor resultado
    melhor = df_resultados.loc[df_resultados['ganho_absoluto'].idxmax()]
    
    print("\n" + "="*80)
    print("MELHOR RESULTADO:")
    print("="*80)
    print(f"  Data: {melhor['data']}")
    print(f"  SKUs: {melhor['skus_estoque']}")
    print(f"  Estoque: {melhor['estoque_total']:,.0f} unidades")
    print(f"  Classes: {melhor['classes']}")
    print(f"  Margem Baseline: R$ {melhor['margem_baseline']:,.2f}")
    print(f"  Margem Otimizada: R$ {melhor['margem_otimizada']:,.2f}")
    print(f"  GANHO ABSOLUTO: R$ {melhor['ganho_absoluto']:,.2f}")
    print(f"  GANHO PERCENTUAL: {melhor['ganho_percentual']:.2f}%")
    
    # Salvar resultados
    output_path = Path('resultados/comparacao_realocacao_multiplas_datas.csv')
    output_path.parent.mkdir(exist_ok=True)
    df_resultados.to_csv(output_path, index=False)
    print(f"\n[OK] Resultados salvos: {output_path}")

