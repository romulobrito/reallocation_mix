"""
Script para testar o modelo com calculo de demanda usando MAXIMO HISTORICO.
"""

import yaml
from pathlib import Path
from modelo_otimizacao_com_realocacao import ModeloOtimizacaoComRealocacao
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    """Executa modelo com maximo historico."""
    config_path = 'config.yaml'
    
    # Carregar config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Configurar para usar maximo historico
    config['modelo']['tipo_calculo_demanda'] = 'maximo'
    config['modelo']['fator_percentual_maximo'] = 1.2  # 20% acima do maximo
    config['modelo']['considerar_demanda_historica'] = True
    config['modelo']['granularidade_demanda'] = 'S'  # Semanal
    
    # Salvar config temporario
    config_temp_path = Path('config_temp.yaml')
    with open(config_temp_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    try:
        logger.info("\n" + "="*80)
        logger.info("TESTE: MAXIMO HISTORICO (Granularidade SEMANAL)")
        logger.info("="*80)
        logger.info("Configuracao:")
        logger.info(f"  Tipo: MAXIMO HISTORICO")
        logger.info(f"  Fator percentual: 1.2x (20% acima do maximo)")
        logger.info(f"  Granularidade: SEMANAL")
        logger.info("="*80)
        
        modelo = ModeloOtimizacaoComRealocacao(config_path=str(config_temp_path))
        modelo.carregar_dados()
        modelo.criar_modelo()
        
        if modelo.resolver():
            comparativo = modelo.calcular_comparativo()
            modelo.salvar_resultados()
            
            logger.info("\n" + "="*80)
            logger.info("RESUMO DO TESTE COM MAXIMO HISTORICO")
            logger.info("="*80)
            if comparativo:
                logger.info(f"  Margem Baseline: R$ {comparativo['margem_baseline']:,.2f}")
                logger.info(f"  Margem Otimizada: R$ {comparativo['margem_otimizada']:,.2f}")
                logger.info(f"  Ganho Absoluto: R$ {comparativo['ganho_absoluto']:,.2f}")
                logger.info(f"  Ganho Percentual: {comparativo['ganho_percentual']:.2f}%")
        else:
            logger.error("Modelo nao encontrou solucao!")
    
    finally:
        # Limpar config temporario
        if config_temp_path.exists():
            config_temp_path.unlink()

if __name__ == '__main__':
    main()

