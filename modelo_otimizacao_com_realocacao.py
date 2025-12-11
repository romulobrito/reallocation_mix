"""
MODELO DE OTIMIZACAO DE MIX DIARIO COM REALOCACAO ENTRE SKUs

Este modelo combina:
1. A estrutura do modelo_otimizacao_mix_diario.py (OR-Tools, estoque diario)
2. A logica do modelo_realocacao_completo.ipynb (realocacao entre SKUs da mesma classe)

DIFERENCA FUNDAMENTAL:
- Modelo antigo: cada SKU usa no maximo seu estoque
- Este modelo: SKUs da mesma classe COMPARTILHAM o estoque total da classe

Isso permite mover volume de SKUs com menor margem para SKUs com maior margem,
gerando ganho significativo.

Autor: Romulo Brito
Data: 2024-12-09
"""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import logging
from typing import Dict, Optional
from ortools.linear_solver import pywraplp


class ModeloOtimizacaoComRealocacao:
    """
    Modelo de otimizacao que permite realocacao de volume entre SKUs da mesma classe.
    
    Exemplo:
    - Classe BRANCO_GRANDE_MTQ tem 3 SKUs no estoque: A (1000 un), B (500 un), C (300 un)
    - Estoque total da classe: 1800 unidades
    - Se SKU A tem margem maior, o modelo pode alocar mais que 1000 un para A
    - Desde que o total alocado nao ultrapasse 1800 unidades
    """
    
    def __init__(self, config_path: str = 'config.yaml'):
        """Inicializa o modelo."""
        self.config = self._carregar_config(config_path)
        self._setup_logging()
        self.dados: Dict = {}
        self.solver: Optional[pywraplp.Solver] = None
        self.variaveis: Dict = {}
        self.resultado: Optional[pd.DataFrame] = None
        
        self.logger.info("="*80)
        self.logger.info("MODELO DE OTIMIZACAO COM REALOCACAO ENTRE SKUs")
        self.logger.info("="*80)
    
    def _carregar_config(self, config_path: str) -> Dict:
        """Carrega configuracoes do YAML."""
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self):
        """Configura logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def carregar_dados(self):
        """Carrega todos os dados necessarios."""
        self.logger.info("\n" + "="*80)
        self.logger.info("ETAPA 1: CARREGAMENTO DE DADOS")
        self.logger.info("="*80)
        
        self._carregar_estoque()
        self._carregar_classes()
        self._carregar_pedidos()
        self._carregar_compatibilidade()
        self._carregar_precos()
        self._carregar_custos()
        self._preparar_dados_otimizacao()
        
        self.logger.info("\n[OK] Dados carregados com sucesso!")
    
    def _carregar_estoque(self):
        """Carrega estoque do dia."""
        self.logger.info("\n[1/6] Carregando estoque do dia...")
        
        path = Path(self.config['paths']['estoque'])
        df_estoque = pd.read_parquet(path)
        
        # Detectar colunas
        col_item = 'ITEM' if 'ITEM' in df_estoque.columns else 'CODIGO ITEM'
        col_data = 'DATA DA CONTAGEM'
        col_tipo = 'TIPO DE ESTOQUE'
        col_qtd = 'QUANTIDADE'
        
        # Converter data
        df_estoque[col_data] = pd.to_datetime(df_estoque[col_data], errors='coerce')
        
        # Filtrar por data e tipo
        data_estoque = pd.to_datetime(self.config['dados']['data_estoque'])
        df_filtrado = df_estoque[
            (df_estoque[col_data] == data_estoque) &
            (df_estoque[col_tipo] == self.config['dados']['tipo_estoque'])
        ].copy()
        
        # Agregar por item
        df_estoque_agg = df_filtrado.groupby(col_item).agg({
            col_qtd: 'sum'
        }).reset_index()
        df_estoque_agg.columns = ['item', 'estoque_disponivel']
        df_estoque_agg = df_estoque_agg[df_estoque_agg['estoque_disponivel'] > 0]
        
        self.logger.info(f"  SKUs com estoque: {len(df_estoque_agg)}")
        self.logger.info(f"  Estoque total: {df_estoque_agg['estoque_disponivel'].sum():,.0f} unidades")
        
        self.dados['estoque'] = df_estoque_agg
    
    def _carregar_classes(self):
        """Carrega classificacao de SKUs por classe."""
        self.logger.info("\n[2/6] Carregando classificacao de SKUs...")
        
        path = Path(self.config['paths'].get('classes', '../base_skus_classes.xlsx'))
        df_classes = pd.read_excel(path)
        
        # Detectar coluna de classe
        col_classe = None
        for col in df_classes.columns:
            if 'classe' in col.lower() and 'produto' in col.lower():
                col_classe = col
                break
        
        if col_classe is None:
            raise ValueError("Coluna de classe nao encontrada em base_skus_classes.xlsx")
        
        df_classes = df_classes[['item', col_classe]].copy()
        df_classes.columns = ['item', 'classe']
        
        # Merge com estoque para ver quantos SKUs tem classe
        df_estoque_com_classe = self.dados['estoque'].merge(df_classes, on='item', how='left')
        
        skus_com_classe = df_estoque_com_classe['classe'].notna().sum()
        skus_sem_classe = df_estoque_com_classe['classe'].isna().sum()
        
        # Atribuir classe OUTROS para SKUs sem classificacao
        df_estoque_com_classe['classe'] = df_estoque_com_classe['classe'].fillna('OUTROS')
        
        self.logger.info(f"  SKUs com classe: {skus_com_classe}")
        self.logger.info(f"  SKUs sem classe (-> OUTROS): {skus_sem_classe}")
        self.logger.info(f"  Classes unicas: {df_estoque_com_classe['classe'].nunique()}")
        
        # Mostrar distribuicao por classe
        dist_classes = df_estoque_com_classe.groupby('classe').agg({
            'item': 'count',
            'estoque_disponivel': 'sum'
        }).sort_values('estoque_disponivel', ascending=False)
        
        self.logger.info(f"\n  Distribuicao por classe:")
        for classe, row in dist_classes.head(10).iterrows():
            self.logger.info(f"    {classe}: {row['item']} SKUs, {row['estoque_disponivel']:,.0f} un")
        
        self.dados['estoque'] = df_estoque_com_classe
        self.dados['classes'] = df_classes
    
    def _carregar_pedidos(self):
        """Carrega pedidos de clientes."""
        self.logger.info("\n[3/7] Carregando pedidos de clientes...")
        
        path = Path(self.config['paths'].get('pedidos', 'inputs/pedidos_clientes.csv'))
        
        if not path.exists():
            self.logger.warning("  Arquivo de pedidos nao encontrado! Continuando sem pedidos.")
            self.dados['pedidos'] = pd.DataFrame(columns=['cod_cliente', 'item', 'quantidade_pedida'])
            return
        
        df_pedidos = pd.read_csv(path)
        
        # Validar colunas
        if 'item' not in df_pedidos.columns or 'quantidade_pedida' not in df_pedidos.columns:
            raise ValueError("Arquivo de pedidos deve conter colunas 'item' e 'quantidade_pedida'")
        
        df_pedidos['item'] = pd.to_numeric(df_pedidos['item'], errors='coerce')
        df_pedidos = df_pedidos[df_pedidos['item'].notna()]
        df_pedidos['item'] = df_pedidos['item'].astype(int)
        df_pedidos = df_pedidos[df_pedidos['quantidade_pedida'] > 0]
        
        # Agregar pedidos por SKU (soma de todos os clientes)
        pedidos_por_sku = df_pedidos.groupby('item')['quantidade_pedida'].sum().reset_index()
        pedidos_por_sku.columns = ['item', 'quantidade_total_pedida']
        
        self.logger.info(f"  Pedidos carregados: {len(df_pedidos):,}")
        self.logger.info(f"  Clientes unicos: {df_pedidos['cod_cliente'].nunique() if 'cod_cliente' in df_pedidos.columns else 'N/A'}")
        self.logger.info(f"  SKUs com pedidos: {len(pedidos_por_sku)}")
        self.logger.info(f"  Quantidade total pedida: {pedidos_por_sku['quantidade_total_pedida'].sum():,.0f} unidades")
        
        self.dados['pedidos'] = df_pedidos
        self.dados['pedidos_por_sku'] = pedidos_por_sku
    
    def _carregar_compatibilidade(self):
        """Carrega compatibilidade SKU x Embalagem."""
        self.logger.info("\n[3/6] Carregando compatibilidade SKU x Embalagem...")
        
        # Tentar compatibilidade tecnica primeiro
        path_tecnica = Path("inputs/compatibilidade_tecnica_sku_embalagem.csv")
        path_historica = Path(self.config['paths'].get('compatibilidade', 'inputs/compatibilidade_sku_embalagem.csv'))
        
        if path_tecnica.exists():
            self.logger.info("  Usando compatibilidade tecnica")
            df_comp = pd.read_csv(path_tecnica)
        elif path_historica.exists():
            self.logger.info("  Usando compatibilidade historica")
            df_comp = pd.read_csv(path_historica)
        else:
            raise FileNotFoundError("Nenhum arquivo de compatibilidade encontrado")
        
        self.logger.info(f"  Combinacoes compativeis: {len(df_comp)}")
        
        self.dados['compatibilidade'] = df_comp
    
    def _carregar_precos(self):
        """Carrega precos por (SKU, Embalagem)."""
        self.logger.info("\n[4/6] Carregando precos...")
        
        path = Path(self.config['paths'].get('precos', 'inputs/precos_sku_embalagem.csv'))
        
        if not path.exists():
            self.logger.warning("  Arquivo de precos nao encontrado!")
            self.dados['precos'] = pd.DataFrame(columns=['item', 'embalagem', 'preco'])
            return
        
        df_precos = pd.read_csv(path)
        
        # Detectar coluna de preco
        if 'preco' not in df_precos.columns:
            if 'preco_ponderado' in df_precos.columns:
                df_precos['preco'] = df_precos['preco_ponderado']
            elif 'preco_medio' in df_precos.columns:
                df_precos['preco'] = df_precos['preco_medio']
        
        df_precos = df_precos[['item', 'embalagem', 'preco']].copy()
        df_precos['item'] = df_precos['item'].astype(int)
        df_precos = df_precos[df_precos['preco'] > 0]
        
        self.logger.info(f"  Combinacoes com preco: {len(df_precos)}")
        self.logger.info(f"  Preco medio: R$ {df_precos['preco'].mean():.2f}")
        
        self.dados['precos'] = df_precos
    
    def _carregar_custos(self):
        """Carrega custos por SKU."""
        self.logger.info("\n[5/6] Carregando custos...")
        
        path = Path(self.config['paths']['custos'])
        df_custo = pd.read_csv(path)
        
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
        
        self.logger.info(f"  SKUs com custo: {len(df_custo)}")
        self.logger.info(f"  Custo medio: R$ {df_custo['custo_ytd'].mean():.2f}")
        
        self.dados['custos'] = df_custo[['item', 'custo_ytd']].drop_duplicates('item')
    
    def _preparar_dados_otimizacao(self):
        """Prepara dados para otimizacao."""
        self.logger.info("\n[7/7] Preparando dados para otimizacao...")
        
        df_estoque = self.dados['estoque']
        df_comp = self.dados['compatibilidade']
        df_precos = self.dados['precos']
        df_custos = self.dados['custos']
        df_pedidos_sku = self.dados.get('pedidos_por_sku', pd.DataFrame(columns=['item', 'quantidade_total_pedida']))
        
        # Juntar tudo
        df_base = df_comp.merge(df_estoque[['item', 'classe']], on='item', how='inner')
        df_base = df_base.merge(df_precos, on=['item', 'embalagem'], how='left')
        df_base = df_base.merge(df_custos, on='item', how='inner')
        
        # Preencher precos faltantes com media do SKU
        preco_medio_sku = df_precos.groupby('item')['preco'].mean()
        df_base['preco'] = df_base['preco'].fillna(df_base['item'].map(preco_medio_sku))
        
        # Se ainda nao tiver preco, usar media geral
        if df_base['preco'].isna().any():
            preco_medio_geral = df_precos['preco'].mean()
            df_base['preco'] = df_base['preco'].fillna(preco_medio_geral)
        
        # Calcular margem unitaria
        df_base['margem_unitaria'] = df_base['preco'] - df_base['custo_ytd']
        
        # Filtrar combinacoes validas
        df_base = df_base[
            (df_base['margem_unitaria'] > 0) &
            (df_base['preco'] > 0)
        ]
        
        # Adicionar estoque disponivel para cada item
        df_base = df_base.merge(
            df_estoque[['item', 'estoque_disponivel']],
            on='item',
            how='left'
        )
        
        # Adicionar pedidos por SKU
        df_base = df_base.merge(
            df_pedidos_sku,
            on='item',
            how='left'
        )
        df_base['quantidade_total_pedida'] = df_base['quantidade_total_pedida'].fillna(0)
        
        # Ler flags de configuracao
        usar_apenas_excedente = self.config.get('modelo', {}).get('usar_apenas_excedente', True)
        atender_pedidos = self.config.get('modelo', {}).get('atender_pedidos', True)
        
        # Validacao e ajuste de flags
        # Se atender_pedidos = True, SEMPRE usa excedente (nao pode "roubar" dos pedidos)
        # A flag usar_apenas_excedente so faz diferenca quando atender_pedidos = False
        if atender_pedidos:
            # Quando atende pedidos, excedente = estoque - pedidos (ja calculado acima)
            # Nao faz sentido usar estoque total, pois isso permitiria "roubar" dos pedidos
            usar_apenas_excedente = True
            self.logger.info("\n[INFO] Como atender_pedidos=true, usando apenas excedente (estoque - pedidos)")
        elif not atender_pedidos and usar_apenas_excedente:
            # Se nao atender pedidos e usar_apenas_excedente=true, nao faz sentido
            # (excedente = estoque - pedidos, se nao ha pedidos, excedente = estoque total)
            self.logger.warning("\n[AVISO] Combinacao invalida detectada:")
            self.logger.warning("  usar_apenas_excedente=true + atender_pedidos=false")
            self.logger.warning("  Se nao ha pedidos, excedente = estoque total.")
            self.logger.warning("  Ajustando para usar_apenas_excedente=false automaticamente.")
            usar_apenas_excedente = False
        
        # Calcular estoque excedente por SKU (apos atender pedidos)
        # O atendimento pode ser parcial, entao: excedente = estoque - min(pedido, estoque)
        # Se nao atender pedidos, excedente = estoque total
        if atender_pedidos:
            df_base['estoque_excedente_sku'] = df_base.apply(
                lambda row: max(0, row['estoque_disponivel'] - min(row['quantidade_total_pedida'], row['estoque_disponivel'])),
                axis=1
            )
        else:
            # Se nao atender pedidos, todo estoque esta disponivel para otimizacao
            df_base['estoque_excedente_sku'] = df_base['estoque_disponivel']
        
        # Calcular estoque total por classe (para restricao de realocacao)
        estoque_por_classe = df_estoque.groupby('classe')['estoque_disponivel'].sum()
        df_base['estoque_classe'] = df_base['classe'].map(estoque_por_classe)
        
        # Calcular estoque disponivel para otimizacao por classe
        # IMPORTANTE: Se atender_pedidos = True, SEMPRE usa excedente (estoque - pedidos)
        # A flag usar_apenas_excedente so faz diferenca quando atender_pedidos = False
        if atender_pedidos:
            # Se atende pedidos, SEMPRE usa excedente (nao pode "roubar" dos pedidos)
            # Excedente = estoque - pedidos (ja calculado acima)
            estoque_excedente_por_item = df_base.groupby(['classe', 'item'])['estoque_excedente_sku'].first()
            estoque_excedente_por_classe = estoque_excedente_por_item.groupby(level=0).sum()
            df_base['estoque_disponivel_otimizacao_classe'] = df_base['classe'].map(estoque_excedente_por_classe).fillna(0)
        else:
            # Se NAO atende pedidos, pode escolher entre excedente ou total
            # Mas se nao ha pedidos, excedente = estoque total (ja ajustado acima)
            if usar_apenas_excedente:
                # Usar excedente (que e igual ao estoque total quando nao ha pedidos)
                estoque_excedente_por_item = df_base.groupby(['classe', 'item'])['estoque_excedente_sku'].first()
                estoque_excedente_por_classe = estoque_excedente_por_item.groupby(level=0).sum()
                df_base['estoque_disponivel_otimizacao_classe'] = df_base['classe'].map(estoque_excedente_por_classe).fillna(0)
            else:
                # Usar estoque TOTAL da classe para otimizacao
                df_base['estoque_disponivel_otimizacao_classe'] = df_base['estoque_classe']
                # Criar estoque_excedente_por_classe baseado no estoque total (para compatibilidade)
                estoque_total_por_item = df_base.groupby(['classe', 'item'])['estoque_disponivel'].first()
                estoque_excedente_por_classe = estoque_total_por_item.groupby(level=0).sum()
        
        # Manter compatibilidade com codigo antigo
        df_base['estoque_excedente_classe'] = df_base['estoque_disponivel_otimizacao_classe']
        
        self.logger.info(f"  Combinacoes validas: {len(df_base)}")
        self.logger.info(f"  SKUs validos: {df_base['item'].nunique()}")
        self.logger.info(f"  Classes validas: {df_base['classe'].nunique()}")
        self.logger.info(f"  Margem unitaria media: R$ {df_base['margem_unitaria'].mean():.2f}")
        
        # Estatisticas de pedidos
        if len(df_pedidos_sku) > 0:
            total_pedido = df_pedidos_sku['quantidade_total_pedida'].sum()
            total_estoque = df_estoque['estoque_disponivel'].sum()
            total_excedente = df_base.groupby('item')['estoque_excedente_sku'].first().sum()
            
            self.logger.info(f"\n  ESTOQUE vs PEDIDOS:")
            self.logger.info(f"    Estoque total: {total_estoque:,.0f} unidades")
            self.logger.info(f"    Pedidos totais: {total_pedido:,.0f} unidades")
            self.logger.info(f"    Estoque excedente (apos pedidos): {total_excedente:,.0f} unidades")
            self.logger.info(f"    Percentual excedente: {total_excedente/total_estoque*100:.1f}%")
        
        # Mostrar top classes por potencial de ganho
        potencial_classe = df_base.groupby('classe').agg({
            'item': 'nunique',
            'estoque_excedente_classe': 'first',
            'margem_unitaria': ['min', 'max', 'mean']
        })
        potencial_classe.columns = ['num_skus', 'estoque_excedente', 'margem_min', 'margem_max', 'margem_media']
        potencial_classe['diff_margem'] = potencial_classe['margem_max'] - potencial_classe['margem_min']
        potencial_classe['potencial_ganho'] = potencial_classe['diff_margem'] * potencial_classe['estoque_excedente'] * 0.03
        potencial_classe = potencial_classe.sort_values('potencial_ganho', ascending=False)
        
        self.logger.info(f"\n  Classes com maior potencial de ganho (no excedente):")
        for classe, row in potencial_classe.head(5).iterrows():
            if row['num_skus'] >= 2 and row['estoque_excedente'] > 0:
                self.logger.info(f"    {classe}: {row['num_skus']} SKUs, "
                               f"excedente {row['estoque_excedente']:,.0f} un, "
                               f"diff margem R$ {row['diff_margem']:.2f}, "
                               f"potencial R$ {row['potencial_ganho']:,.0f}")
        
        # Log do modo de operacao
        modo_operacao = []
        if atender_pedidos:
            modo_operacao.append("ATENDE PEDIDOS")
        else:
            modo_operacao.append("IGNORA PEDIDOS")
        
        if usar_apenas_excedente:
            modo_operacao.append("OTIMIZA APENAS EXCEDENTE")
        else:
            modo_operacao.append("OTIMIZA TODO ESTOQUE")
        
        self.logger.info(f"\n  MODO DE OPERACAO: {' + '.join(modo_operacao)}")
        
        self.dados['base_otimizacao'] = df_base
        self.dados['estoque_por_classe'] = estoque_por_classe
        self.dados['estoque_excedente_por_classe'] = estoque_excedente_por_classe
        self.dados['usar_apenas_excedente'] = usar_apenas_excedente
        self.dados['atender_pedidos'] = atender_pedidos
    
    def criar_modelo(self):
        """Cria o modelo de otimizacao com realocacao."""
        self.logger.info("\n" + "="*80)
        self.logger.info("ETAPA 2: CRIACAO DO MODELO COM REALOCACAO")
        self.logger.info("="*80)
        
        # Criar solver
        solver_type = getattr(pywraplp.Solver, self.config['solver']['solver_type'])
        self.solver = pywraplp.Solver('MixDiarioComRealocacao', solver_type)
        
        df_base = self.dados['base_otimizacao']
        
        # Criar variaveis: 
        # 1. y[item] = quantidade atendida do pedido (pode ser parcial)
        # 2. x[item, embalagem] = quantidade alocada no excedente (para otimizacao)
        self.logger.info("\n[1/4] Criando variaveis de decisao...")
        
        # Variaveis de atendimento aos pedidos (apenas se atender_pedidos = True)
        self.variaveis_pedidos = {}
        atender_pedidos = self.dados.get('atender_pedidos', True)
        df_pedidos_sku = self.dados.get('pedidos_por_sku', pd.DataFrame(columns=['item', 'quantidade_total_pedida']))
        
        if atender_pedidos and len(df_pedidos_sku) > 0:
            for _, row in df_pedidos_sku.iterrows():
                item = int(row['item'])
                qtd_pedida = float(row['quantidade_total_pedida'])
                estoque_item = float(df_base[df_base['item'] == item]['estoque_disponivel'].iloc[0]) if len(df_base[df_base['item'] == item]) > 0 else 0.0
                
                # Atendimento pode ser no maximo o minimo entre pedido e estoque (pode ser parcial)
                limite_atendimento = min(qtd_pedida, estoque_item)
                
                if limite_atendimento > 0:
                    self.variaveis_pedidos[item] = self.solver.NumVar(
                        0.0,
                        float(limite_atendimento),
                        f"y_pedido_{item}"
                    )
        
        if atender_pedidos:
            self.logger.info(f"  Variaveis de atendimento aos pedidos: {len(self.variaveis_pedidos)}")
        else:
            self.logger.info(f"  Variaveis de atendimento aos pedidos: 0 (pedidos ignorados)")
        
        # Variaveis de alocacao (para otimizacao com realocacao)
        # Limite superior depende da flag usar_apenas_excedente
        usar_apenas_excedente = self.dados.get('usar_apenas_excedente', True)
        self.variaveis = {}
        
        for idx, row in df_base.iterrows():
            item = row['item']
            emb = row['embalagem']
            var_name = f"x_{item}_{emb}"
            
            # Limite superior: estoque disponivel para otimizacao da CLASSE
            estoque_disponivel_classe = row['estoque_disponivel_otimizacao_classe']
            
            if estoque_disponivel_classe > 0:
                self.variaveis[(item, emb)] = self.solver.NumVar(
                    0,
                    estoque_disponivel_classe,
                    var_name
                )
        
        modo_desc = "excedente" if usar_apenas_excedente else "todo estoque"
        self.logger.info(f"  Variaveis de alocacao (otimizacao do {modo_desc}): {len(self.variaveis)}")
        
        # Adicionar restricoes
        self._adicionar_restricoes(df_base)
        
        # Definir objetivo
        self._definir_objetivo(df_base)
        
        self.logger.info("\n[OK] Modelo criado com sucesso!")
    
    def _adicionar_restricoes(self, df_base: pd.DataFrame):
        """Adiciona restricoes ao modelo."""
        self.logger.info("\n[2/4] Adicionando restricoes...")
        
        num_restricoes = 0
        
        # RESTRICAO 1: Atendimento aos pedidos (apenas se atender_pedidos = True)
        atender_pedidos = self.dados.get('atender_pedidos', True)
        df_pedidos_sku = self.dados.get('pedidos_por_sku', pd.DataFrame(columns=['item', 'quantidade_total_pedida']))
        
        if atender_pedidos and len(df_pedidos_sku) > 0:
            for _, row in df_pedidos_sku.iterrows():
                item = row['item']
                qtd_pedida = row['quantidade_total_pedida']
                
                if item in self.variaveis_pedidos:
                    # Atendimento nao pode exceder o pedido nem o estoque disponivel
                    estoque_item = df_base[df_base['item'] == item]['estoque_disponivel'].iloc[0] if len(df_base[df_base['item'] == item]) > 0 else 0
                    limite_atendimento = min(qtd_pedida, estoque_item)
                    
                    # A restricao ja esta no limite da variavel, mas vamos adicionar explicitamente
                    self.solver.Add(self.variaveis_pedidos[item] <= limite_atendimento)
                    num_restricoes += 1
        
        if atender_pedidos:
            self.logger.info(f"  Restricoes de atendimento aos pedidos: {num_restricoes}")
        else:
            self.logger.info(f"  Restricoes de atendimento aos pedidos: 0 (pedidos ignorados)")
        
        # RESTRICAO 2: Volume total por CLASSE <= estoque disponivel da classe
        # Esta e a restricao que permite realocacao entre SKUs!
        usar_apenas_excedente = self.dados.get('usar_apenas_excedente', True)
        classes = df_base['classe'].unique()
        
        num_restricoes_classe = 0
        for classe in classes:
            # Todas as variaveis de SKUs desta classe
            items_classe = df_base[df_base['classe'] == classe][['item', 'embalagem']].drop_duplicates()
            
            if len(items_classe) == 0:
                continue
            
            # Soma de todas as alocacoes da classe
            soma_classe = sum(
                self.variaveis.get((row['item'], row['embalagem']), 0)
                for _, row in items_classe.iterrows()
                if (row['item'], row['embalagem']) in self.variaveis
            )
            
            # Estoque disponivel para otimizacao da classe
            estoque_disponivel_classe = df_base[df_base['classe'] == classe]['estoque_disponivel_otimizacao_classe'].iloc[0] if len(df_base[df_base['classe'] == classe]) > 0 else 0
            
            if estoque_disponivel_classe > 0:
                self.solver.Add(soma_classe <= estoque_disponivel_classe)
                num_restricoes_classe += 1
        
        num_restricoes += num_restricoes_classe
        modo_desc = "EXCEDENTE" if usar_apenas_excedente else "TOTAL"
        self.logger.info(f"  Restricoes de estoque {modo_desc} por CLASSE: {num_restricoes_classe}")
        
        # RESTRICAO 3: Para cada SKU, limite de alocacao
        # Limita a "absorcao" de volume de outros SKUs
        usar_apenas_excedente = self.dados.get('usar_apenas_excedente', True)
        items_unicos = df_base['item'].unique()
        
        num_restricoes_sku = 0
        for item in items_unicos:
            # Todas as embalagens deste item
            embalagens_item = df_base[df_base['item'] == item]['embalagem'].unique()
            
            if len(embalagens_item) <= 1:
                continue
            
            # Estoque base do item (excedente ou total, dependendo da flag)
            estoque_base_item = df_base[df_base['item'] == item]['estoque_excedente_sku'].iloc[0] if len(df_base[df_base['item'] == item]) > 0 else 0
            
            if estoque_base_item <= 0:
                continue
            
            soma_item = sum(
                self.variaveis.get((item, emb), 0)
                for emb in embalagens_item
                if (item, emb) in self.variaveis
            )
            
            # Permite receber ate 2x o estoque base original (realocacao moderada)
            limite_realocacao = self.config.get('modelo', {}).get('limite_realocacao', 2.0)
            self.solver.Add(soma_item <= estoque_base_item * limite_realocacao)
            num_restricoes_sku += 1
        
        num_restricoes += num_restricoes_sku
        modo_desc = "excedente" if usar_apenas_excedente else "total"
        self.logger.info(f"  Restricoes de limite por SKU (no {modo_desc}): {num_restricoes_sku}")
        self.logger.info(f"  Total de restricoes: {num_restricoes}")
    
    def _definir_objetivo(self, df_base: pd.DataFrame):
        """Define funcao objetivo: maximizar margem total (pedidos + excedente)."""
        self.logger.info("\n[3/4] Definindo funcao objetivo...")
        
        # Objetivo tem duas partes:
        # 1. Margem dos pedidos atendidos
        # 2. Margem da otimizacao no excedente
        
        objetivo_pedidos = 0.0
        atender_pedidos = self.dados.get('atender_pedidos', True)
        df_pedidos_sku = self.dados.get('pedidos_por_sku', pd.DataFrame(columns=['item', 'quantidade_total_pedida']))
        
        if atender_pedidos and len(df_pedidos_sku) > 0:
            for _, row in df_pedidos_sku.iterrows():
                item = row['item']
                if item in self.variaveis_pedidos:
                    # Buscar margem unitaria do item (usar primeira embalagem disponivel)
                    margem_item = df_base[df_base['item'] == item]['margem_unitaria'].iloc[0] if len(df_base[df_base['item'] == item]) > 0 else 0
                    objetivo_pedidos += margem_item * self.variaveis_pedidos[item]
        
        # Objetivo da otimizacao no excedente
        objetivo_excedente = sum(
            row['margem_unitaria'] * self.variaveis.get((row['item'], row['embalagem']), 0)
            for _, row in df_base.iterrows()
            if (row['item'], row['embalagem']) in self.variaveis
        )
        
        objetivo_total = objetivo_pedidos + objetivo_excedente
        self.solver.Maximize(objetivo_total)
        
        # Estimar margem potencial
        atender_pedidos = self.dados.get('atender_pedidos', True)
        usar_apenas_excedente = self.dados.get('usar_apenas_excedente', True)
        
        margem_potencial_pedidos = 0.0
        if atender_pedidos and len(df_pedidos_sku) > 0:
            for _, row in df_pedidos_sku.iterrows():
                item = row['item']
                qtd_pedida = row['quantidade_total_pedida']
                estoque_item = df_base[df_base['item'] == item]['estoque_disponivel'].iloc[0] if len(df_base[df_base['item'] == item]) > 0 else 0
                margem_item = df_base[df_base['item'] == item]['margem_unitaria'].iloc[0] if len(df_base[df_base['item'] == item]) > 0 else 0
                margem_potencial_pedidos += margem_item * min(qtd_pedida, estoque_item)
        
        # Calcular margem potencial da otimizacao
        if usar_apenas_excedente:
            estoque_otimizacao = df_base['estoque_excedente_sku']
            modo_desc = "excedente"
        else:
            estoque_otimizacao = df_base['estoque_disponivel']
            modo_desc = "total"
        
        margem_potencial_otimizacao = (df_base['margem_unitaria'] * estoque_otimizacao).sum()
        margem_potencial_total = margem_potencial_pedidos + margem_potencial_otimizacao
        
        if atender_pedidos:
            self.logger.info(f"  Margem potencial pedidos: R$ {margem_potencial_pedidos:,.2f}")
        self.logger.info(f"  Margem potencial {modo_desc} (sem realocacao): R$ {margem_potencial_otimizacao:,.2f}")
        self.logger.info(f"  Margem potencial total: R$ {margem_potencial_total:,.2f}")
    
    def resolver(self):
        """Resolve o modelo de otimizacao."""
        self.logger.info("\n" + "="*80)
        self.logger.info("ETAPA 3: RESOLUCAO DO MODELO")
        self.logger.info("="*80)
        
        # Configurar tempo limite
        self.solver.SetTimeLimit(self.config['solver']['time_limit_ms'])
        
        # Resolver
        status = self.solver.Solve()
        
        if status == pywraplp.Solver.OPTIMAL:
            self.logger.info("\n[OK] Solucao otima encontrada!")
            self._extrair_resultado()
            return True
        elif status == pywraplp.Solver.FEASIBLE:
            self.logger.warning("\n[AVISO] Solucao viavel (nao otima) encontrada")
            self._extrair_resultado()
            return True
        else:
            self.logger.error("\n[ERRO] Nenhuma solucao encontrada")
            return False
    
    def _extrair_resultado(self):
        """Extrai resultado da otimizacao."""
        df_base = self.dados['base_otimizacao']
        
        # Resultados da otimizacao no excedente
        resultados = []
        for (item, emb), var in self.variaveis.items():
            qtd = var.solution_value()
            if qtd > 0.01:
                # Buscar dados desta combinacao
                row_base = df_base[(df_base['item'] == item) & (df_base['embalagem'] == emb)]
                if len(row_base) > 0:
                    row = row_base.iloc[0]
                    resultados.append({
                        'item': item,
                        'embalagem': emb,
                        'classe': row['classe'],
                        'quantidade': qtd,
                        'tipo': 'EXCEDENTE',
                        'estoque_original': row['estoque_disponivel'],
                        'estoque_excedente': row['estoque_excedente_sku'],
                        'preco': row['preco'],
                        'custo_ytd': row['custo_ytd'],
                        'margem_unitaria': row['margem_unitaria'],
                        'receita_total': qtd * row['preco'],
                        'custo_total': qtd * row['custo_ytd'],
                        'margem_total': qtd * row['margem_unitaria']
                    })
        
        # Resultados dos pedidos atendidos
        df_pedidos_sku = self.dados.get('pedidos_por_sku', pd.DataFrame(columns=['item', 'quantidade_total_pedida']))
        if len(df_pedidos_sku) > 0:
            for _, row_pedido in df_pedidos_sku.iterrows():
                item = row_pedido['item']
                if item in self.variaveis_pedidos:
                    qtd_atendida = self.variaveis_pedidos[item].solution_value()
                    if qtd_atendida > 0.01:
                        # Buscar dados do item
                        row_base = df_base[df_base['item'] == item]
                        if len(row_base) > 0:
                            row = row_base.iloc[0]
                            resultados.append({
                                'item': item,
                                'embalagem': 'PEDIDO',  # Pedidos nao especificam embalagem
                                'classe': row['classe'],
                                'quantidade': qtd_atendida,
                                'tipo': 'PEDIDO',
                                'estoque_original': row['estoque_disponivel'],
                                'estoque_excedente': row['estoque_excedente_sku'],
                                'quantidade_pedida': row_pedido['quantidade_total_pedida'],
                                'percentual_atendido': (qtd_atendida / row_pedido['quantidade_total_pedida'] * 100) if row_pedido['quantidade_total_pedida'] > 0 else 0,
                                'preco': row['preco'],
                                'custo_ytd': row['custo_ytd'],
                                'margem_unitaria': row['margem_unitaria'],
                                'receita_total': qtd_atendida * row['preco'],
                                'custo_total': qtd_atendida * row['custo_ytd'],
                                'margem_total': qtd_atendida * row['margem_unitaria']
                            })
        
        self.resultado = pd.DataFrame(resultados)
        
        if len(self.resultado) > 0:
            # Adicionar coluna de variacao (realocacao) apenas para excedente
            if 'tipo' in self.resultado.columns:
                # Para excedente: comparar com estoque excedente original
                mask_excedente = self.resultado['tipo'] == 'EXCEDENTE'
                self.resultado.loc[mask_excedente, 'variacao_qtd'] = (
                    self.resultado.loc[mask_excedente, 'quantidade'] - 
                    self.resultado.loc[mask_excedente, 'estoque_excedente']
                )
                self.resultado.loc[mask_excedente, 'variacao_pct'] = (
                    self.resultado.loc[mask_excedente, 'variacao_qtd'] / 
                    self.resultado.loc[mask_excedente, 'estoque_excedente'].replace(0, 1) * 100
                )
            else:
                # Fallback para compatibilidade
                self.resultado['variacao_qtd'] = (
                    self.resultado['quantidade'] - self.resultado['estoque_original']
                )
                self.resultado['variacao_pct'] = (
                    self.resultado['variacao_qtd'] / self.resultado['estoque_original'].replace(0, 1) * 100
                )
            
            self.logger.info("\nRESULTADOS:")
            
            # Separar pedidos e excedente
            if 'tipo' in self.resultado.columns:
                df_pedidos = self.resultado[self.resultado['tipo'] == 'PEDIDO']
                df_excedente = self.resultado[self.resultado['tipo'] == 'EXCEDENTE']
                
                if len(df_pedidos) > 0:
                    self.logger.info(f"\n  PEDIDOS ATENDIDOS:")
                    self.logger.info(f"    SKUs atendidos: {len(df_pedidos)}")
                    self.logger.info(f"    Quantidade atendida: {df_pedidos['quantidade'].sum():,.0f} unidades")
                    self.logger.info(f"    Margem dos pedidos: R$ {df_pedidos['margem_total'].sum():,.2f}")
                    if 'percentual_atendido' in df_pedidos.columns:
                        self.logger.info(f"    Percentual medio atendido: {df_pedidos['percentual_atendido'].mean():.1f}%")
                
                if len(df_excedente) > 0:
                    self.logger.info(f"\n  OTIMIZACAO NO EXCEDENTE:")
                    self.logger.info(f"    Combinacoes escolhidas: {len(df_excedente)}")
                    self.logger.info(f"    Quantidade alocada: {df_excedente['quantidade'].sum():,.0f} unidades")
                    self.logger.info(f"    Margem do excedente: R$ {df_excedente['margem_total'].sum():,.2f}")
            else:
                self.logger.info(f"  Combinacoes escolhidas: {len(self.resultado)}")
            
            self.logger.info(f"\n  TOTAIS:")
            self.logger.info(f"    Quantidade total alocada: {self.resultado['quantidade'].sum():,.0f} unidades")
            self.logger.info(f"    Receita total: R$ {self.resultado['receita_total'].sum():,.2f}")
            self.logger.info(f"    Custo total: R$ {self.resultado['custo_total'].sum():,.2f}")
            self.logger.info(f"    Margem total: R$ {self.resultado['margem_total'].sum():,.2f}")
            if self.resultado['receita_total'].sum() > 0:
                self.logger.info(f"    Margem %: {self.resultado['margem_total'].sum() / self.resultado['receita_total'].sum() * 100:.2f}%")
            
            # Mostrar realocacoes significativas (apenas no excedente)
            if 'tipo' in self.resultado.columns and 'variacao_pct' in self.resultado.columns:
                df_excedente = self.resultado[self.resultado['tipo'] == 'EXCEDENTE']
                if len(df_excedente) > 0 and 'variacao_pct' in df_excedente.columns:
                    realocacoes = df_excedente[abs(df_excedente['variacao_pct']) > 5].sort_values('variacao_qtd', ascending=False)
                    if len(realocacoes) > 0:
                        self.logger.info(f"\n  REALOCACOES SIGNIFICATIVAS NO EXCEDENTE (>5%):")
                        for _, row in realocacoes.head(10).iterrows():
                            sinal = '+' if row['variacao_qtd'] > 0 else ''
                            self.logger.info(f"    SKU {row['item']} ({row['classe']}): "
                                           f"excedente {row['estoque_excedente']:,.0f} -> alocado {row['quantidade']:,.0f} "
                                           f"({sinal}{row['variacao_pct']:.1f}%)")
    
    def calcular_comparativo(self):
        """Calcula margem baseline vs otimizada."""
        if self.resultado is None or len(self.resultado) == 0:
            return None
        
        df_estoque = self.dados['estoque']
        df_base = self.dados['base_otimizacao']
        
        # Margem otimizada
        margem_otimizada = self.resultado['margem_total'].sum()
        
        # Margem baseline: para cada SKU, usar a embalagem mais comum historicamente
        margem_baseline = 0.0
        
        for _, row in df_estoque.iterrows():
            item = row['item']
            qtd_estoque = row['estoque_disponivel']
            
            # Buscar combinacoes para este item
            combinacoes_item = df_base[df_base['item'] == item]
            
            if len(combinacoes_item) == 0:
                continue
            
            # Usar margem media das embalagens disponiveis como baseline
            margem_media = combinacoes_item['margem_unitaria'].mean()
            margem_baseline += qtd_estoque * margem_media
        
        ganho = margem_otimizada - margem_baseline
        ganho_pct = (ganho / margem_baseline * 100) if margem_baseline > 0 else 0
        
        self.logger.info("\n" + "="*80)
        self.logger.info("COMPARATIVO: BASELINE vs OTIMIZADO")
        self.logger.info("="*80)
        self.logger.info(f"  Margem Baseline (sem realocacao): R$ {margem_baseline:,.2f}")
        self.logger.info(f"  Margem Otimizada (com realocacao): R$ {margem_otimizada:,.2f}")
        self.logger.info(f"  GANHO ABSOLUTO: R$ {ganho:,.2f}")
        self.logger.info(f"  GANHO PERCENTUAL: {ganho_pct:.2f}%")
        
        return {
            'margem_baseline': margem_baseline,
            'margem_otimizada': margem_otimizada,
            'ganho_absoluto': ganho,
            'ganho_percentual': ganho_pct
        }
    
    def salvar_resultados(self):
        """Salva resultados em CSV e Excel com timestamp e modo de operacao."""
        if self.resultado is None:
            return
        
        from datetime import datetime
        
        output_dir = Path('resultados')
        output_dir.mkdir(exist_ok=True)
        
        # Gerar timestamp no formato YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Determinar sufixo do modo de operacao
        atender_pedidos = self.dados.get('atender_pedidos', True)
        usar_apenas_excedente = self.dados.get('usar_apenas_excedente', True)
        
        if atender_pedidos:
            modo_sufixo = 'excedente'  # Sempre usa excedente quando atende pedidos
        else:
            if usar_apenas_excedente:
                modo_sufixo = 'excedente'  # Ajustado automaticamente, mas mantem para compatibilidade
            else:
                modo_sufixo = 'completo'  # Otimiza todo estoque
        
        # Resultado detalhado com timestamp e modo
        arquivo_resultado_csv = output_dir / f'resultado_realocacao_{modo_sufixo}_{timestamp}.csv'
        arquivo_resultado_xlsx = output_dir / f'resultado_realocacao_{modo_sufixo}_{timestamp}.xlsx'
        
        self.resultado.to_csv(arquivo_resultado_csv, index=False, encoding='utf-8')
        
        # Resumo por classe com timestamp e modo
        resumo_classe = self.resultado.groupby('classe').agg({
            'item': 'nunique',
            'quantidade': 'sum',
            'estoque_original': 'sum',
            'margem_total': 'sum'
        }).reset_index()
        resumo_classe.columns = ['classe', 'num_skus', 'quantidade_alocada', 'estoque_original', 'margem_total']
        
        arquivo_resumo_csv = output_dir / f'resumo_por_classe_{modo_sufixo}_{timestamp}.csv'
        resumo_classe.to_csv(arquivo_resumo_csv, index=False, encoding='utf-8')
        
        # Criar Excel com multiplas abas
        with pd.ExcelWriter(arquivo_resultado_xlsx, engine='openpyxl') as writer:
            # Aba 1: Resultado detalhado
            self.resultado.to_excel(writer, sheet_name='Resultado Detalhado', index=False)
            
            # Aba 2: Resumo por classe
            resumo_classe.to_excel(writer, sheet_name='Resumo por Classe', index=False)
            
            # Aba 3: Estatisticas e Resumo Executivo
            df_estatisticas = self._criar_aba_estatisticas(resumo_classe)
            df_estatisticas.to_excel(writer, sheet_name='Estatisticas', index=False)
        
        # Salvar resumo por classe separado (para compatibilidade)
        arquivo_resumo_xlsx = output_dir / f'resumo_por_classe_{modo_sufixo}_{timestamp}.xlsx'
        resumo_classe.to_excel(arquivo_resumo_xlsx, index=False, engine='openpyxl')
        
        self.logger.info(f"\n[OK] Resultados salvos em {output_dir}/")
        self.logger.info(f"  CSV:")
        self.logger.info(f"    - {arquivo_resultado_csv.name}")
        self.logger.info(f"    - {arquivo_resumo_csv.name}")
        self.logger.info(f"  Excel:")
        self.logger.info(f"    - {arquivo_resultado_xlsx.name} (com 3 abas: Detalhado, Resumo, Estatisticas)")
        self.logger.info(f"    - {arquivo_resumo_xlsx.name}")
    
    def _criar_aba_estatisticas(self, resumo_classe: pd.DataFrame):
        """Cria DataFrame com estatisticas e resumo executivo."""
        estatisticas = []
        
        # Separar pedidos e excedente
        if 'tipo' in self.resultado.columns:
            df_pedidos = self.resultado[self.resultado['tipo'] == 'PEDIDO']
            df_excedente = self.resultado[self.resultado['tipo'] == 'EXCEDENTE']
        else:
            df_pedidos = pd.DataFrame()
            df_excedente = self.resultado
        
        # 1. ESTOQUE vs PEDIDOS
        df_estoque = self.dados['estoque']
        df_pedidos_sku = self.dados.get('pedidos_por_sku', pd.DataFrame(columns=['item', 'quantidade_total_pedida']))
        
        total_estoque = df_estoque['estoque_disponivel'].sum()
        total_pedido = df_pedidos_sku['quantidade_total_pedida'].sum() if len(df_pedidos_sku) > 0 else 0
        total_excedente = df_estoque['estoque_disponivel'].sum() - df_pedidos['quantidade'].sum() if len(df_pedidos) > 0 else total_estoque
        
        estatisticas.append({'Categoria': 'ESTOQUE vs PEDIDOS', 'Metrica': 'Estoque Total', 'Valor': f'{total_estoque:,.0f}', 'Unidade': 'unidades'})
        estatisticas.append({'Categoria': 'ESTOQUE vs PEDIDOS', 'Metrica': 'Pedidos Totais', 'Valor': f'{total_pedido:,.0f}', 'Unidade': 'unidades'})
        estatisticas.append({'Categoria': 'ESTOQUE vs PEDIDOS', 'Metrica': 'Estoque Excedente', 'Valor': f'{total_excedente:,.0f}', 'Unidade': 'unidades'})
        estatisticas.append({'Categoria': 'ESTOQUE vs PEDIDOS', 'Metrica': 'Percentual Excedente', 'Valor': f'{total_excedente/total_estoque*100:.1f}', 'Unidade': '%'})
        
        # 2. PEDIDOS ATENDIDOS
        if len(df_pedidos) > 0:
            qtd_atendida = df_pedidos['quantidade'].sum()
            margem_pedidos = df_pedidos['margem_total'].sum()
            pct_medio = df_pedidos['percentual_atendido'].mean() if 'percentual_atendido' in df_pedidos.columns else 0
            
            estatisticas.append({'Categoria': 'PEDIDOS ATENDIDOS', 'Metrica': 'SKUs Atendidos', 'Valor': f'{len(df_pedidos)}', 'Unidade': 'SKUs'})
            estatisticas.append({'Categoria': 'PEDIDOS ATENDIDOS', 'Metrica': 'Quantidade Atendida', 'Valor': f'{qtd_atendida:,.0f}', 'Unidade': 'unidades'})
            estatisticas.append({'Categoria': 'PEDIDOS ATENDIDOS', 'Metrica': 'Percentual Medio Atendido', 'Valor': f'{pct_medio:.1f}', 'Unidade': '%'})
            estatisticas.append({'Categoria': 'PEDIDOS ATENDIDOS', 'Metrica': 'Margem dos Pedidos', 'Valor': f'R$ {margem_pedidos:,.2f}', 'Unidade': 'R$'})
        
        # 3. OTIMIZACAO NO EXCEDENTE
        if len(df_excedente) > 0:
            qtd_excedente = df_excedente['quantidade'].sum()
            margem_excedente = df_excedente['margem_total'].sum()
            
            estatisticas.append({'Categoria': 'OTIMIZACAO NO EXCEDENTE', 'Metrica': 'Combinacoes Escolhidas', 'Valor': f'{len(df_excedente)}', 'Unidade': 'combinacoes'})
            estatisticas.append({'Categoria': 'OTIMIZACAO NO EXCEDENTE', 'Metrica': 'Quantidade Alocada', 'Valor': f'{qtd_excedente:,.0f}', 'Unidade': 'unidades'})
            estatisticas.append({'Categoria': 'OTIMIZACAO NO EXCEDENTE', 'Metrica': 'Margem do Excedente', 'Valor': f'R$ {margem_excedente:,.2f}', 'Unidade': 'R$'})
        
        # 4. TOTAIS
        qtd_total = self.resultado['quantidade'].sum()
        receita_total = self.resultado['receita_total'].sum()
        custo_total = self.resultado['custo_total'].sum()
        margem_total = self.resultado['margem_total'].sum()
        margem_pct = (margem_total / receita_total * 100) if receita_total > 0 else 0
        
        estatisticas.append({'Categoria': 'TOTAIS', 'Metrica': 'Quantidade Total Alocada', 'Valor': f'{qtd_total:,.0f}', 'Unidade': 'unidades'})
        estatisticas.append({'Categoria': 'TOTAIS', 'Metrica': 'Receita Total', 'Valor': f'R$ {receita_total:,.2f}', 'Unidade': 'R$'})
        estatisticas.append({'Categoria': 'TOTAIS', 'Metrica': 'Custo Total', 'Valor': f'R$ {custo_total:,.2f}', 'Unidade': 'R$'})
        estatisticas.append({'Categoria': 'TOTAIS', 'Metrica': 'Margem Total', 'Valor': f'R$ {margem_total:,.2f}', 'Unidade': 'R$'})
        estatisticas.append({'Categoria': 'TOTAIS', 'Metrica': 'Margem Percentual', 'Valor': f'{margem_pct:.2f}', 'Unidade': '%'})
        
        # 5. COMPARATIVO BASELINE vs OTIMIZADO
        comparativo = self.calcular_comparativo()
        if comparativo:
            estatisticas.append({'Categoria': 'COMPARATIVO', 'Metrica': 'Margem Baseline', 'Valor': f'R$ {comparativo["margem_baseline"]:,.2f}', 'Unidade': 'R$'})
            estatisticas.append({'Categoria': 'COMPARATIVO', 'Metrica': 'Margem Otimizada', 'Valor': f'R$ {comparativo["margem_otimizada"]:,.2f}', 'Unidade': 'R$'})
            estatisticas.append({'Categoria': 'COMPARATIVO', 'Metrica': 'Ganho Absoluto', 'Valor': f'R$ {comparativo["ganho_absoluto"]:,.2f}', 'Unidade': 'R$'})
            estatisticas.append({'Categoria': 'COMPARATIVO', 'Metrica': 'Ganho Percentual', 'Valor': f'{comparativo["ganho_percentual"]:.2f}', 'Unidade': '%'})
        
        # 6. REALOCACOES SIGNIFICATIVAS (top 10)
        if 'tipo' in self.resultado.columns and 'variacao_pct' in self.resultado.columns:
            df_excedente = self.resultado[self.resultado['tipo'] == 'EXCEDENTE']
            if len(df_excedente) > 0 and 'variacao_pct' in df_excedente.columns:
                realocacoes = df_excedente[abs(df_excedente['variacao_pct']) > 5].sort_values('variacao_qtd', ascending=False).head(10)
                if len(realocacoes) > 0:
                    estatisticas.append({'Categoria': 'REALOCACOES', 'Metrica': 'Numero de Realocacoes Significativas', 'Valor': f'{len(realocacoes)}', 'Unidade': 'SKUs'})
                    for idx, row in realocacoes.iterrows():
                        sinal = '+' if row['variacao_qtd'] > 0 else ''
                        estatisticas.append({
                            'Categoria': 'REALOCACOES',
                            'Metrica': f'SKU {int(row["item"])} ({row["classe"]})',
                            'Valor': f'Excedente: {row["estoque_excedente"]:,.0f} -> Alocado: {row["quantidade"]:,.0f} ({sinal}{row["variacao_pct"]:.1f}%)',
                            'Unidade': ''
                        })
        
        # 7. CLASSES COM MAIOR POTENCIAL
        if len(resumo_classe) > 0:
            top_classes = resumo_classe.nlargest(5, 'margem_total')
            estatisticas.append({'Categoria': 'TOP CLASSES', 'Metrica': 'Numero de Classes Analisadas', 'Valor': f'{len(resumo_classe)}', 'Unidade': 'classes'})
            for _, row in top_classes.iterrows():
                estatisticas.append({
                    'Categoria': 'TOP CLASSES',
                    'Metrica': row['classe'],
                    'Valor': f'Margem: R$ {row["margem_total"]:,.2f} | {int(row["num_skus"])} SKUs | {row["quantidade_alocada"]:,.0f} un',
                    'Unidade': ''
                })
        
        return pd.DataFrame(estatisticas)


def main():
    """Funcao principal."""
    modelo = ModeloOtimizacaoComRealocacao()
    modelo.carregar_dados()
    modelo.criar_modelo()
    
    if modelo.resolver():
        modelo.calcular_comparativo()
        modelo.salvar_resultados()


if __name__ == '__main__':
    main()

