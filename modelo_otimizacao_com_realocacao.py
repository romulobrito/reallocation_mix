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
        self.logger.info("\n[6/6] Preparando dados para otimizacao...")
        
        df_estoque = self.dados['estoque']
        df_comp = self.dados['compatibilidade']
        df_precos = self.dados['precos']
        df_custos = self.dados['custos']
        
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
        
        # Calcular estoque total por classe (para restricao de realocacao)
        estoque_por_classe = df_estoque.groupby('classe')['estoque_disponivel'].sum()
        df_base['estoque_classe'] = df_base['classe'].map(estoque_por_classe)
        
        self.logger.info(f"  Combinacoes validas: {len(df_base)}")
        self.logger.info(f"  SKUs validos: {df_base['item'].nunique()}")
        self.logger.info(f"  Classes validas: {df_base['classe'].nunique()}")
        self.logger.info(f"  Margem unitaria media: R$ {df_base['margem_unitaria'].mean():.2f}")
        
        # Mostrar top classes por potencial de ganho
        potencial_classe = df_base.groupby('classe').agg({
            'item': 'nunique',
            'estoque_classe': 'first',
            'margem_unitaria': ['min', 'max', 'mean']
        })
        potencial_classe.columns = ['num_skus', 'estoque', 'margem_min', 'margem_max', 'margem_media']
        potencial_classe['diff_margem'] = potencial_classe['margem_max'] - potencial_classe['margem_min']
        potencial_classe['potencial_ganho'] = potencial_classe['diff_margem'] * potencial_classe['estoque'] * 0.03
        potencial_classe = potencial_classe.sort_values('potencial_ganho', ascending=False)
        
        self.logger.info(f"\n  Classes com maior potencial de ganho (diff_margem * estoque * 3%):")
        for classe, row in potencial_classe.head(5).iterrows():
            if row['num_skus'] >= 2:
                self.logger.info(f"    {classe}: {row['num_skus']} SKUs, "
                               f"diff margem R$ {row['diff_margem']:.2f}, "
                               f"potencial R$ {row['potencial_ganho']:,.0f}")
        
        self.dados['base_otimizacao'] = df_base
        self.dados['estoque_por_classe'] = estoque_por_classe
    
    def criar_modelo(self):
        """Cria o modelo de otimizacao com realocacao."""
        self.logger.info("\n" + "="*80)
        self.logger.info("ETAPA 2: CRIACAO DO MODELO COM REALOCACAO")
        self.logger.info("="*80)
        
        # Criar solver
        solver_type = getattr(pywraplp.Solver, self.config['solver']['solver_type'])
        self.solver = pywraplp.Solver('MixDiarioComRealocacao', solver_type)
        
        df_base = self.dados['base_otimizacao']
        
        # Criar variaveis: x[item, embalagem] = quantidade alocada
        self.logger.info("\n[1/3] Criando variaveis de decisao...")
        
        self.variaveis = {}
        for idx, row in df_base.iterrows():
            item = row['item']
            emb = row['embalagem']
            var_name = f"x_{item}_{emb}"
            
            # Limite superior: estoque total da CLASSE (permite realocacao!)
            estoque_classe = row['estoque_classe']
            
            self.variaveis[(item, emb)] = self.solver.NumVar(
                0,
                estoque_classe,  # IMPORTANTE: limite e o estoque da classe, nao do SKU
                var_name
            )
        
        self.logger.info(f"  Variaveis criadas: {len(self.variaveis)}")
        
        # Adicionar restricoes
        self._adicionar_restricoes(df_base)
        
        # Definir objetivo
        self._definir_objetivo(df_base)
        
        self.logger.info("\n[OK] Modelo criado com sucesso!")
    
    def _adicionar_restricoes(self, df_base: pd.DataFrame):
        """Adiciona restricoes ao modelo."""
        self.logger.info("\n[2/3] Adicionando restricoes...")
        
        num_restricoes = 0
        
        # RESTRICAO 1: Volume total por CLASSE <= estoque total da classe
        # Esta e a restricao que permite realocacao entre SKUs!
        classes = df_base['classe'].unique()
        
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
            
            # Estoque total da classe
            estoque_classe = self.dados['estoque_por_classe'].get(classe, 0)
            
            if estoque_classe > 0:
                self.solver.Add(soma_classe <= estoque_classe)
                num_restricoes += 1
        
        self.logger.info(f"  Restricoes de estoque por CLASSE: {num_restricoes}")
        
        # RESTRICAO 2: Para cada SKU, escolher no maximo uma embalagem
        # (opcional - pode ser removida se quiser permitir multiplas embalagens)
        items_unicos = df_base['item'].unique()
        
        for item in items_unicos:
            # Todas as embalagens deste item
            embalagens_item = df_base[df_base['item'] == item]['embalagem'].unique()
            
            if len(embalagens_item) <= 1:
                continue
            
            # Para cada item, a quantidade total alocada nao pode exceder
            # o estoque original do item (limita a "absorcao" de volume)
            estoque_item = df_base[df_base['item'] == item]['estoque_disponivel'].iloc[0]
            
            soma_item = sum(
                self.variaveis.get((item, emb), 0)
                for emb in embalagens_item
                if (item, emb) in self.variaveis
            )
            
            # Permite receber ate 2x o estoque original (realocacao moderada)
            # Ou pode remover este limite para realocacao total
            limite_realocacao = self.config.get('modelo', {}).get('limite_realocacao', 2.0)
            self.solver.Add(soma_item <= estoque_item * limite_realocacao)
            num_restricoes += 1
        
        self.logger.info(f"  Restricoes de limite por SKU: {num_restricoes - len(classes)}")
        self.logger.info(f"  Total de restricoes: {num_restricoes}")
    
    def _definir_objetivo(self, df_base: pd.DataFrame):
        """Define funcao objetivo: maximizar margem total."""
        self.logger.info("\n[3/3] Definindo funcao objetivo...")
        
        # Objetivo: maximizar soma(margem_unitaria * quantidade)
        objetivo = sum(
            row['margem_unitaria'] * self.variaveis.get((row['item'], row['embalagem']), 0)
            for _, row in df_base.iterrows()
            if (row['item'], row['embalagem']) in self.variaveis
        )
        
        self.solver.Maximize(objetivo)
        
        # Estimar margem potencial
        margem_potencial = (df_base['margem_unitaria'] * df_base['estoque_disponivel']).sum()
        self.logger.info(f"  Margem potencial (sem realocacao): R$ {margem_potencial:,.2f}")
    
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
                        'estoque_original': row['estoque_disponivel'],
                        'preco': row['preco'],
                        'custo_ytd': row['custo_ytd'],
                        'margem_unitaria': row['margem_unitaria'],
                        'receita_total': qtd * row['preco'],
                        'custo_total': qtd * row['custo_ytd'],
                        'margem_total': qtd * row['margem_unitaria']
                    })
        
        self.resultado = pd.DataFrame(resultados)
        
        if len(self.resultado) > 0:
            # Adicionar coluna de variacao (realocacao)
            self.resultado['variacao_qtd'] = (
                self.resultado['quantidade'] - self.resultado['estoque_original']
            )
            self.resultado['variacao_pct'] = (
                self.resultado['variacao_qtd'] / self.resultado['estoque_original'] * 100
            )
            
            self.logger.info("\nRESULTADOS:")
            self.logger.info(f"  Combinacoes escolhidas: {len(self.resultado)}")
            self.logger.info(f"  Quantidade total alocada: {self.resultado['quantidade'].sum():,.0f} unidades")
            self.logger.info(f"  Receita total: R$ {self.resultado['receita_total'].sum():,.2f}")
            self.logger.info(f"  Custo total: R$ {self.resultado['custo_total'].sum():,.2f}")
            self.logger.info(f"  Margem total: R$ {self.resultado['margem_total'].sum():,.2f}")
            self.logger.info(f"  Margem %: {self.resultado['margem_total'].sum() / self.resultado['receita_total'].sum() * 100:.2f}%")
            
            # Mostrar realocacoes significativas
            realocacoes = self.resultado[abs(self.resultado['variacao_pct']) > 5].sort_values('variacao_qtd', ascending=False)
            if len(realocacoes) > 0:
                self.logger.info(f"\n  REALOCACOES SIGNIFICATIVAS (>5%):")
                for _, row in realocacoes.head(10).iterrows():
                    sinal = '+' if row['variacao_qtd'] > 0 else ''
                    self.logger.info(f"    SKU {row['item']} ({row['classe']}): "
                                   f"{row['estoque_original']:,.0f} -> {row['quantidade']:,.0f} "
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
        """Salva resultados em CSV."""
        if self.resultado is None:
            return
        
        output_dir = Path('resultados')
        output_dir.mkdir(exist_ok=True)
        
        # Resultado detalhado
        self.resultado.to_csv(output_dir / 'resultado_realocacao.csv', index=False)
        
        # Resumo por classe
        resumo_classe = self.resultado.groupby('classe').agg({
            'item': 'nunique',
            'quantidade': 'sum',
            'estoque_original': 'sum',
            'margem_total': 'sum'
        }).reset_index()
        resumo_classe.columns = ['classe', 'num_skus', 'quantidade_alocada', 'estoque_original', 'margem_total']
        resumo_classe.to_csv(output_dir / 'resumo_por_classe.csv', index=False)
        
        self.logger.info(f"\n[OK] Resultados salvos em {output_dir}/")


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

