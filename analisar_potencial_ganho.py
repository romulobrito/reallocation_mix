"""
Analisa o potencial de ganho (margem) em cada data testada.
Verifica oportunidades não exploradas e diferenças de margem entre embalagens.
"""
import pandas as pd
from pathlib import Path
import sys
import yaml
from datetime import datetime

# Importar classe do modelo
sys.path.append(str(Path(__file__).parent))
from modelo_otimizacao_mix_diario import ModeloOtimizacaoMixDiario

print("="*80)
print("ANALISE DE POTENCIAL DE GANHO POR DATA")
print("="*80)

# Carregar resultados da comparacao
df_comparacao = pd.read_csv('resultados/comparacao_multiplas_datas.csv')
df_comparacao['data'] = pd.to_datetime(df_comparacao['data'])

# Carregar config
config_path = Path('config.yaml')
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

print(f"\n[INFO] Analisando {len(df_comparacao)} datas...\n")

resultados_analise = []

for idx, row in df_comparacao.iterrows():
    data_str = row['data'].strftime('%Y-%m-%d') if isinstance(row['data'], pd.Timestamp) else str(row['data'])
    print(f"\n{'='*80}")
    print(f"DATA: {data_str}")
    print(f"{'='*80}")
    
    # Atualizar config
    config['dados']['data_estoque'] = data_str
    config_temp_path = Path('config_temp.yaml')
    with open(config_temp_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    try:
        # Carregar modelo e dados
        modelo = ModeloOtimizacaoMixDiario(config_path=str(config_temp_path))
        modelo.carregar_dados()
        modelo.criar_modelo()
        modelo.resolver()  # Resolver para ter resultado
        
        # Acessar dados de otimizacao (ja preparados em carregar_dados)
        df_base = modelo.dados.get('base_otimizacao')
        if df_base is None or len(df_base) == 0:
            print(f"  [AVISO] Nenhum dado de otimizacao disponivel para {data_str}")
            continue
        
        # Analisar oportunidades
        # 1. Para cada SKU no estoque, verificar todas as embalagens disponiveis
        df_estoque = modelo.dados['estoque']
        skus_estoque = df_estoque['item'].unique()
        
        oportunidades = []
        
        for sku in skus_estoque:
            # Todas as combinacoes disponiveis para este SKU
            df_sku = df_base[df_base['item'] == sku].copy()
            
            if len(df_sku) == 0:
                continue
            
            # Ordenar por margem unitaria (decrescente)
            df_sku = df_sku.sort_values('margem_unitaria', ascending=False)
            
            # Verificar se ha diferenca significativa entre embalagens
            margem_max = df_sku['margem_unitaria'].max()
            margem_min = df_sku['margem_unitaria'].min()
            margem_media = df_sku['margem_unitaria'].mean()
            diff_max_min = margem_max - margem_min
            
            # Verificar qual embalagem foi escolhida (se houver resultado)
            embalagem_escolhida = None
            if modelo.resultado is not None and len(modelo.resultado) > 0:
                df_resultado_sku = modelo.resultado[modelo.resultado['item'] == sku]
                if len(df_resultado_sku) > 0:
                    embalagem_escolhida = df_resultado_sku.iloc[0]['embalagem']
            
            # Verificar se a melhor embalagem foi escolhida
            melhor_embalagem = df_sku.iloc[0]['embalagem']
            melhor_margem = df_sku.iloc[0]['margem_unitaria']
            
            # Calcular potencial de ganho se mudar para melhor embalagem
            estoque_sku = df_estoque[df_estoque['item'] == sku]['estoque_disponivel'].sum()
            
            if embalagem_escolhida and embalagem_escolhida != melhor_embalagem:
                # Encontrar margem da embalagem escolhida
                margem_escolhida = df_sku[df_sku['embalagem'] == embalagem_escolhida]['margem_unitaria'].values[0]
                ganho_potencial = (melhor_margem - margem_escolhida) * estoque_sku
            else:
                ganho_potencial = 0
            
            oportunidades.append({
                'item': sku,
                'estoque': estoque_sku,
                'num_embalagens_disponiveis': len(df_sku),
                'margem_max': margem_max,
                'margem_min': margem_min,
                'margem_media': margem_media,
                'diff_max_min': diff_max_min,
                'melhor_embalagem': melhor_embalagem,
                'melhor_margem': melhor_margem,
                'embalagem_escolhida': embalagem_escolhida if embalagem_escolhida else 'NENHUMA',
                'ganho_potencial': ganho_potencial
            })
        
        df_oportunidades = pd.DataFrame(oportunidades)
        
        # Metricas agregadas
        total_ganho_potencial = df_oportunidades['ganho_potencial'].sum()
        skus_com_multiplas_opcoes = len(df_oportunidades[df_oportunidades['num_embalagens_disponiveis'] > 1])
        skus_com_diferenca_significativa = len(df_oportunidades[df_oportunidades['diff_max_min'] > 0.01])  # > R$ 0.01 de diferenca
        skus_nao_otimizados = len(df_oportunidades[df_oportunidades['ganho_potencial'] > 0])
        
        # Diferenca media de margem entre embalagens (para SKUs com multiplas opcoes)
        diff_media = df_oportunidades[df_oportunidades['num_embalagens_disponiveis'] > 1]['diff_max_min'].mean() if skus_com_multiplas_opcoes > 0 else 0
        
        resultados_analise.append({
            'data': data_str,
            'skus_estoque': len(skus_estoque),
            'skus_com_multiplas_embalagens': skus_com_multiplas_opcoes,
            'skus_com_diferenca_margem': skus_com_diferenca_significativa,
            'skus_nao_otimizados': skus_nao_otimizados,
            'diff_margem_media': diff_media,
            'ganho_potencial_total': total_ganho_potencial,
            'ganho_potencial_por_sku_medio': total_ganho_potencial / len(skus_estoque) if len(skus_estoque) > 0 else 0
        })
        
        print(f"\n[ANALISE]")
        print(f"  SKUs no estoque: {len(skus_estoque)}")
        print(f"  SKUs com multiplas embalagens: {skus_com_multiplas_opcoes}")
        print(f"  SKUs com diferenca significativa de margem: {skus_com_diferenca_significativa}")
        print(f"  SKUs nao otimizados (ganho potencial > 0): {skus_nao_otimizados}")
        print(f"  Diferenca media de margem entre embalagens: R$ {diff_media:.4f}")
        print(f"  GANHO POTENCIAL TOTAL: R$ {total_ganho_potencial:,.2f}")
        
        # Top 5 oportunidades
        if len(df_oportunidades) > 0:
            df_top = df_oportunidades.nlargest(5, 'ganho_potencial')
            print(f"\n  TOP 5 OPORTUNIDADES:")
            for _, op in df_top.iterrows():
                if op['ganho_potencial'] > 0:
                    print(f"    SKU {op['item']}: Ganho potencial R$ {op['ganho_potencial']:,.2f} "
                          f"(mudar de '{op['embalagem_escolhida']}' para '{op['melhor_embalagem']}')")
        
    except Exception as e:
        print(f"\n[ERRO] Falha ao analisar {data_str}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if config_temp_path.exists():
            config_temp_path.unlink()

# Salvar analise
if len(resultados_analise) > 0:
    df_analise = pd.DataFrame(resultados_analise)
    
    output_path = Path('resultados/analise_potencial_ganho.csv')
    output_path.parent.mkdir(exist_ok=True)
    df_analise.to_csv(output_path, index=False, encoding='utf-8')
    
    print("\n" + "="*80)
    print("RESUMO DA ANALISE DE POTENCIAL")
    print("="*80)
    print(df_analise.to_string(index=False))
    
    # Identificar data com maior potencial
    if df_analise['ganho_potencial_total'].max() > 0:
        idx_max = df_analise['ganho_potencial_total'].idxmax()
        data_max = df_analise.loc[idx_max, 'data']
        ganho_max = df_analise.loc[idx_max, 'ganho_potencial_total']
        
        print(f"\n{'='*80}")
        print("DATA COM MAIOR POTENCIAL DE GANHO:")
        print(f"{'='*80}")
        print(f"  Data: {data_max}")
        print(f"  Ganho Potencial: R$ {ganho_max:,.2f}")
        print(f"  SKUs com multiplas embalagens: {df_analise.loc[idx_max, 'skus_com_multiplas_embalagens']}")
        print(f"  SKUs nao otimizados: {df_analise.loc[idx_max, 'skus_nao_otimizados']}")
    else:
        print(f"\n{'='*80}")
        print("CONCLUSAO:")
        print(f"{'='*80}")
        print("  Nenhuma data apresenta ganho potencial significativo.")
        print("  Isso indica que o modelo ja esta escolhendo as melhores embalagens disponiveis.")
    
    print(f"\n[OK] Analise salva: {output_path}")

