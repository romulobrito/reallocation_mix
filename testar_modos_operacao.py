"""
Script para testar diferentes modos de operacao do modelo de otimizacao.

Testa:
1. Modo 1: atender_pedidos=true (sempre usa excedente)
2. Modo 2: atender_pedidos=false (otimiza tudo, ignora pedidos)
"""

import yaml
import pandas as pd
from pathlib import Path
from modelo_otimizacao_com_realocacao import ModeloOtimizacaoComRealocacao
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def testar_modo(config_path: str, modo: str, atender_pedidos: bool):
    """Testa um modo especifico de operacao."""
    logger.info("\n" + "="*80)
    logger.info(f"TESTE: {modo}")
    logger.info("="*80)
    
    # Carregar config
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Ajustar flags
    config['modelo']['atender_pedidos'] = atender_pedidos
    config['modelo']['usar_apenas_excedente'] = True  # Será ajustado automaticamente se necessário
    
    # Salvar config temporario
    config_temp_path = Path('config_temp.yaml')
    with open(config_temp_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    try:
        # Criar e executar modelo
        modelo = ModeloOtimizacaoComRealocacao(config_path=str(config_temp_path))
        modelo.carregar_dados()
        modelo.criar_modelo()
        
        if modelo.resolver():
            comparativo = modelo.calcular_comparativo()
            
            # Extrair resultados
            resultado = modelo.resultado
            if resultado is not None and len(resultado) > 0:
                # Separar pedidos e excedente
                if 'tipo' in resultado.columns:
                    df_pedidos = resultado[resultado['tipo'] == 'PEDIDO']
                    df_excedente = resultado[resultado['tipo'] == 'EXCEDENTE']
                else:
                    df_pedidos = pd.DataFrame()
                    df_excedente = resultado
                
                # Estatisticas
                stats = {
                    'modo': modo,
                    'atender_pedidos': atender_pedidos,
                    'qtd_pedidos': df_pedidos['quantidade'].sum() if len(df_pedidos) > 0 else 0,
                    'qtd_excedente': df_excedente['quantidade'].sum() if len(df_excedente) > 0 else 0,
                    'qtd_total': resultado['quantidade'].sum(),
                    'margem_pedidos': df_pedidos['margem_total'].sum() if len(df_pedidos) > 0 else 0,
                    'margem_excedente': df_excedente['margem_total'].sum() if len(df_excedente) > 0 else 0,
                    'margem_total': resultado['margem_total'].sum(),
                    'margem_baseline': comparativo['margem_baseline'] if comparativo else 0,
                    'ganho_absoluto': comparativo['ganho_absoluto'] if comparativo else 0,
                    'ganho_percentual': comparativo['ganho_percentual'] if comparativo else 0,
                }
                
                return stats
            else:
                logger.warning("  Nenhum resultado encontrado!")
                return None
        else:
            logger.error("  Modelo nao encontrou solucao!")
            return None
            
    except Exception as e:
        logger.error(f"  ERRO: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Limpar config temporario
        if config_temp_path.exists():
            config_temp_path.unlink()

def main():
    """Executa testes de todos os modos."""
    logger.info("\n" + "="*80)
    logger.info("TESTE DE MODOS DE OPERACAO")
    logger.info("="*80)
    
    config_path = 'config.yaml'
    
    # Teste 1: Atender pedidos (usa excedente)
    stats1 = testar_modo(config_path, "MODO 1: Atender Pedidos + Otimizar Excedente", atender_pedidos=True)
    
    # Teste 2: Ignorar pedidos (otimiza tudo)
    stats2 = testar_modo(config_path, "MODO 2: Ignorar Pedidos + Otimizar Tudo", atender_pedidos=False)
    
    # Comparacao
    logger.info("\n" + "="*80)
    logger.info("COMPARACAO DOS MODOS")
    logger.info("="*80)
    
    if stats1 and stats2:
        df_comparacao = pd.DataFrame([stats1, stats2])
        
        logger.info("\nRESUMO:")
        logger.info(df_comparacao.to_string(index=False))
        
        logger.info("\n" + "-"*80)
        logger.info("DIFERENCAS:")
        logger.info("-"*80)
        
        diff_qtd = stats2['qtd_total'] - stats1['qtd_total']
        diff_margem = stats2['margem_total'] - stats1['margem_total']
        diff_ganho = stats2['ganho_absoluto'] - stats1['ganho_absoluto']
        
        logger.info(f"  Quantidade total (Modo 2 - Modo 1): {diff_qtd:,.0f} unidades")
        logger.info(f"  Margem total (Modo 2 - Modo 1): R$ {diff_margem:,.2f}")
        logger.info(f"  Ganho absoluto (Modo 2 - Modo 1): R$ {diff_ganho:,.2f}")
        
        logger.info("\n" + "-"*80)
        logger.info("ANALISE:")
        logger.info("-"*80)
        logger.info(f"  Modo 1 atendeu {stats1['qtd_pedidos']:,.0f} unidades de pedidos")
        logger.info(f"  Modo 2 ignorou pedidos e otimizou {stats2['qtd_total']:,.0f} unidades")
        
        if diff_margem > 0:
            logger.info(f"  Modo 2 gerou R$ {diff_margem:,.2f} a mais de margem")
            logger.info("  (Isso e esperado, pois ignora pedidos e otimiza tudo)")
        else:
            logger.info(f"  Modo 1 gerou R$ {abs(diff_margem):,.2f} a mais de margem")
            logger.info("  (Isso pode ocorrer se os pedidos tem margem melhor que o excedente)")
        
        # Salvar comparacao
        output_dir = Path('resultados')
        output_dir.mkdir(exist_ok=True)
        arquivo_comparacao = output_dir / 'comparacao_modos_operacao.csv'
        df_comparacao.to_csv(arquivo_comparacao, index=False, encoding='utf-8')
        logger.info(f"\n[OK] Comparacao salva em: {arquivo_comparacao}")
    else:
        logger.error("\n[ERRO] Nao foi possivel comparar os modos!")

if __name__ == '__main__':
    main()

