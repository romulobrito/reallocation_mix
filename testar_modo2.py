"""Testa apenas o Modo 2: Ignorar Pedidos + Otimizar Tudo"""

import yaml
from pathlib import Path
from modelo_otimizacao_com_realocacao import ModeloOtimizacaoComRealocacao

# Carregar config
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Ajustar para Modo 2
config['modelo']['atender_pedidos'] = False
config['modelo']['usar_apenas_excedente'] = False

# Salvar config temporario
config_temp_path = Path('config_temp.yaml')
with open(config_temp_path, 'w', encoding='utf-8') as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

try:
    modelo = ModeloOtimizacaoComRealocacao(config_path=str(config_temp_path))
    modelo.carregar_dados()
    modelo.criar_modelo()
    
    if modelo.resolver():
        comparativo = modelo.calcular_comparativo()
        modelo.salvar_resultados()
        
        print("\n" + "="*80)
        print("RESULTADOS FINAIS - MODO 2")
        print("="*80)
        if comparativo:
            print(f"Margem Baseline: R$ {comparativo['margem_baseline']:,.2f}")
            print(f"Margem Otimizada: R$ {comparativo['margem_otimizada']:,.2f}")
            print(f"Ganho Absoluto: R$ {comparativo['ganho_absoluto']:,.2f}")
            print(f"Ganho Percentual: {comparativo['ganho_percentual']:.2f}%")
finally:
    if config_temp_path.exists():
        config_temp_path.unlink()

