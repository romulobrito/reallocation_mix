"""
Gera dataset de pedidos de clientes a partir do faturamento histórico.

Este script cria pedidos fictícios baseados em padrões históricos de compra,
que podem ser usados como input para o modelo de otimização com restrições de pedidos.

Estratégias disponíveis:
1. MEDIA_MENSAL: Média mensal de compra por cliente/SKU
2. ULTIMO_PEDIDO: Último pedido histórico de cada cliente/SKU
3. DEMANDA_PROJETADA: Projeção baseada em tendência histórica
4. ALEATORIO_PONDERADO: Pedidos aleatórios ponderados pelo histórico
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

def detectar_colunas(df_fat):
    """Detecta automaticamente as colunas relevantes do faturamento."""
    colunas = {}
    
    # Cliente
    for col in df_fat.columns:
        if col.upper() in ['COD.EMITENTE', 'COD EMITENTE', 'CODIGO EMITENTE', 'CLIENTE']:
            colunas['cliente'] = col
            break
    
    # Item/SKU
    for col in df_fat.columns:
        if col.upper() == 'ITEM' or (col.upper().startswith('ITEM') and 'DESCRI' not in col.upper()):
            colunas['item'] = col
            break
    
    # Quantidade
    for col in df_fat.columns:
        if 'QUANTIDADE' in col.upper() or 'QTD' in col.upper():
            colunas['quantidade'] = col
            break
    
    # Data
    for col in df_fat.columns:
        col_upper = col.upper()
        if ('DATA' in col_upper or 'DT' in col_upper) and 'EMISSAO' in col_upper:
            colunas['data'] = col
            break
        elif col_upper == 'DT.EMISSÃO' or col_upper == 'DT EMISSÃO' or col_upper == 'DT.EMISSAO':
            colunas['data'] = col
            break
    
    # Nome do cliente (opcional)
    for col in df_fat.columns:
        if col.upper() == 'NOME' or 'NOME' in col.upper() and 'CLIENTE' in col.upper():
            colunas['nome_cliente'] = col
            break
    
    return colunas

def estrategia_media_mensal(df_fat, colunas, meses_considerados=3):
    """
    Cria pedidos baseados na média mensal dos últimos N meses.
    
    Estratégia: Para cada cliente/SKU, calcula a média mensal de compra
    nos últimos N meses e usa isso como quantidade pedida.
    """
    print(f"\n[Estratégia: MÉDIA MENSAL dos últimos {meses_considerados} meses]")
    
    # Converter data
    df_fat[colunas['data']] = pd.to_datetime(df_fat[colunas['data']], errors='coerce')
    df_fat = df_fat[df_fat[colunas['data']].notna()]
    
    # Filtrar últimos N meses
    data_max = df_fat[colunas['data']].max()
    data_min = data_max - timedelta(days=meses_considerados * 30)
    df_recente = df_fat[df_fat[colunas['data']] >= data_min].copy()
    
    # Agrupar por cliente e SKU
    pedidos = df_recente.groupby([colunas['cliente'], colunas['item']]).agg({
        colunas['quantidade']: 'sum',
        colunas['data']: 'max'  # Data do último pedido
    }).reset_index()
    
    # Calcular média mensal
    num_meses = meses_considerados
    pedidos['quantidade_pedida'] = pedidos[colunas['quantidade']] / num_meses
    
    # Arredondar para inteiro
    pedidos['quantidade_pedida'] = pedidos['quantidade_pedida'].round().astype(int)
    
    # Remover pedidos muito pequenos (menos de 10 unidades)
    pedidos = pedidos[pedidos['quantidade_pedida'] >= 10]
    
    return pedidos

def estrategia_ultimo_pedido(df_fat, colunas):
    """
    Cria pedidos baseados no último pedido histórico de cada cliente/SKU.
    
    Estratégia: Para cada cliente/SKU, pega a quantidade do último pedido histórico.
    """
    print("\n[Estratégia: ÚLTIMO PEDIDO histórico]")
    
    # Converter data
    df_fat[colunas['data']] = pd.to_datetime(df_fat[colunas['data']], errors='coerce')
    df_fat = df_fat[df_fat[colunas['data']].notna()]
    
    # Agrupar por cliente, SKU e data (agrupar transações do mesmo dia)
    df_agrupado = df_fat.groupby([
        colunas['cliente'],
        colunas['item'],
        df_fat[colunas['data']].dt.date
    ]).agg({
        colunas['quantidade']: 'sum'
    }).reset_index()
    
    # Pegar último pedido de cada cliente/SKU
    pedidos = df_agrupado.sort_values(colunas['data']).groupby([
        colunas['cliente'],
        colunas['item']
    ]).last().reset_index()
    
    pedidos['quantidade_pedida'] = pedidos[colunas['quantidade']].astype(int)
    
    return pedidos

def estrategia_demanda_projetada(df_fat, colunas, fator_crescimento=1.0):
    """
    Cria pedidos baseados em projeção de demanda com tendência.
    
    Estratégia: Calcula média mensal e aplica fator de crescimento.
    """
    print(f"\n[Estratégia: DEMANDA PROJETADA (fator: {fator_crescimento})]")
    
    # Converter data
    df_fat[colunas['data']] = pd.to_datetime(df_fat[colunas['data']], errors='coerce')
    df_fat = df_fat[df_fat[colunas['data']].notna()]
    
    # Agrupar por mês, cliente e SKU
    df_fat['ano_mes'] = df_fat[colunas['data']].dt.to_period('M')
    
    demanda_mensal = df_fat.groupby([
        colunas['cliente'],
        colunas['item'],
        'ano_mes'
    ]).agg({
        colunas['quantidade']: 'sum'
    }).reset_index()
    
    # Calcular média mensal por cliente/SKU
    pedidos = demanda_mensal.groupby([
        colunas['cliente'],
        colunas['item']
    ]).agg({
        colunas['quantidade']: 'mean'
    }).reset_index()
    
    # Aplicar fator de crescimento
    pedidos['quantidade_pedida'] = (pedidos[colunas['quantidade']] * fator_crescimento).round().astype(int)
    
    # Remover pedidos muito pequenos
    pedidos = pedidos[pedidos['quantidade_pedida'] >= 10]
    
    return pedidos

def main():
    print("="*80)
    print("GERAÇÃO DE PEDIDOS DE CLIENTES (FICTÍCIOS)")
    print("="*80)
    
    # Configurações
    path_fat = Path("../manti_fat_2024.parquet")
    output_path = Path("inputs/pedidos_clientes.csv")
    
    estrategia = "MEDIA_MENSAL"  # Opções: MEDIA_MENSAL, ULTIMO_PEDIDO, DEMANDA_PROJETADA
    
    # Carregar faturamento
    print("\n[1/4] Carregando faturamento histórico...")
    if not path_fat.exists():
        print(f"[ERRO] Arquivo não encontrado: {path_fat}")
        return
    
    df_fat = pd.read_parquet(path_fat)
    print(f"  Registros: {len(df_fat):,}")
    
    # Detectar colunas
    print("\n[2/4] Detectando colunas...")
    colunas = detectar_colunas(df_fat)
    
    if not all(k in colunas for k in ['cliente', 'item', 'quantidade', 'data']):
        print("[ERRO] Não foi possível detectar todas as colunas necessárias")
        print(f"  Colunas detectadas: {colunas}")
        print(f"  Colunas disponíveis: {list(df_fat.columns)}")
        return
    
    print(f"  Cliente: {colunas['cliente']}")
    print(f"  Item: {colunas['item']}")
    print(f"  Quantidade: {colunas['quantidade']}")
    print(f"  Data: {colunas['data']}")
    
    # Filtrar dados válidos
    df_fat = df_fat[
        (df_fat[colunas['cliente']].notna()) &
        (df_fat[colunas['item']].notna()) &
        (df_fat[colunas['quantidade']] > 0)
    ].copy()
    
    # Converter item para int
    df_fat[colunas['item']] = pd.to_numeric(df_fat[colunas['item']], errors='coerce')
    df_fat = df_fat[df_fat[colunas['item']].notna()]
    df_fat[colunas['item']] = df_fat[colunas['item']].astype(int)
    
    print(f"  Registros válidos: {len(df_fat):,}")
    
    # Gerar pedidos conforme estratégia
    print(f"\n[3/4] Gerando pedidos (estratégia: {estrategia})...")
    
    if estrategia == "MEDIA_MENSAL":
        pedidos = estrategia_media_mensal(df_fat, colunas, meses_considerados=3)
    elif estrategia == "ULTIMO_PEDIDO":
        pedidos = estrategia_ultimo_pedido(df_fat, colunas)
    elif estrategia == "DEMANDA_PROJETADA":
        pedidos = estrategia_demanda_projetada(df_fat, colunas, fator_crescimento=1.0)
    else:
        print(f"[ERRO] Estratégia desconhecida: {estrategia}")
        return
    
    # Renomear colunas para formato padrão
    df_pedidos = pd.DataFrame({
        'cod_cliente': pedidos[colunas['cliente']],
        'item': pedidos[colunas['item']],
        'quantidade_pedida': pedidos['quantidade_pedida']
    })
    
    # Adicionar nome do cliente se disponível
    if 'nome_cliente' in colunas:
        df_clientes = df_fat[[colunas['cliente'], colunas['nome_cliente']]].drop_duplicates()
        df_pedidos = df_pedidos.merge(
            df_clientes,
            left_on='cod_cliente',
            right_on=colunas['cliente'],
            how='left'
        )
        df_pedidos = df_pedidos.rename(columns={colunas['nome_cliente']: 'nome_cliente'})
        df_pedidos = df_pedidos[['cod_cliente', 'nome_cliente', 'item', 'quantidade_pedida']]
    
    # Ordenar
    df_pedidos = df_pedidos.sort_values(['cod_cliente', 'item'])
    
    # Salvar
    print(f"\n[4/4] Salvando pedidos...")
    output_path.parent.mkdir(exist_ok=True)
    df_pedidos.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"\n[OK] Dataset salvo: {output_path}")
    print(f"  Total de pedidos: {len(df_pedidos):,}")
    print(f"  Clientes únicos: {df_pedidos['cod_cliente'].nunique():,}")
    print(f"  SKUs únicos: {df_pedidos['item'].nunique():,}")
    print(f"  Quantidade total pedida: {df_pedidos['quantidade_pedida'].sum():,.0f} unidades")
    
    # Estatísticas
    print("\n" + "="*80)
    print("ESTATÍSTICAS")
    print("="*80)
    print(f"\nTop 10 clientes por volume pedido:")
    top_clientes = df_pedidos.groupby('cod_cliente')['quantidade_pedida'].sum().sort_values(ascending=False).head(10)
    for cliente, qtd in top_clientes.items():
        print(f"  Cliente {cliente}: {qtd:,.0f} unidades")
    
    print(f"\nTop 10 SKUs mais pedidos:")
    top_skus = df_pedidos.groupby('item')['quantidade_pedida'].sum().sort_values(ascending=False).head(10)
    for sku, qtd in top_skus.items():
        print(f"  SKU {sku}: {qtd:,.0f} unidades")
    
    print(f"\nDistribuição de pedidos por cliente:")
    dist = df_pedidos.groupby('cod_cliente').size()
    print(f"  Média de SKUs por cliente: {dist.mean():.1f}")
    print(f"  Mediana de SKUs por cliente: {dist.median():.1f}")
    print(f"  Máximo de SKUs por cliente: {dist.max()}")

if __name__ == "__main__":
    main()

