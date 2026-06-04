import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import MedallionLayer
from ipolitico.pipeline.builder import PipelineComponents

logger = logging.getLogger(__name__)


class PipelineRunner:
    """
    Orquestrador de Execução do Pipeline (Motor Assíncrono).

    Implementa o padrão Producer-Consumer com backpressure. Recebe os componentes
    já instanciados (Extractor, Transformer, Sink) e executa o fluxo completo:
    Extração (Bronze) -> Transformação -> Carga (Silver/Gold).
    """

    def __init__(self, max_workers: int = MAX_CONCURRENT_REQUESTS):
        """
        Inicializa o motor de execução do pipeline.

        Args:
            max_workers (int): Número máximo de tarefas concorrentes consumindo a API.
        """
        self.max_workers = max_workers

    async def execute(
        self,
        components: PipelineComponents,
        items: List[Any],
        extract_kwargs_mapper: Callable[[Any], Dict[str, Any]],
        table_name: str,
        unique_keys: Optional[Union[str, List[str]]] = None,
        layer: MedallionLayer = MedallionLayer.SILVER,
        transform_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Executa o pipeline assíncrono para uma lista de itens (jobs).

        Args:
            components (PipelineComponents): Contêiner com as instâncias do Extractor,
                                             Transformer e Sink.
            items (List[Any]): Lista de itens a processar (ex: IDs de deputados, anos).
            extract_kwargs_mapper (Callable): Função que converte um item da lista
                                              nos parâmetros (kwargs) exigidos pelo Extractor.
            table_name (str): Nome da tabela/entidade de destino.
            unique_keys (str | List[str], optional): Chaves primárias para UPSERT no banco.
            layer (MedallionLayer): Camada de destino para o salvamento.
            transform_kwargs (Dict[str, Any], optional): Parâmetros de contexto adicionais
                                                         para o Transformer.
        """
        total_items = len(items)
        if total_items == 0:
            logger.info(f"[{table_name.upper()}] Nenhum item para processar nesta etapa.")
            return

        # Fila de Jobs (Producer)
        job_queue = asyncio.Queue()
        for item in items:
            job_queue.put_nowait(item)

        # [BLINDAGEM ANTI-OOM] Fila de DataFrames com Backpressure.
        # Se o banco (Sink) ficar lento, a fila lota (maxsize=10) e os workers
        # suspendem as chamadas à API automaticamente até o banco esvaziar a fila.
        df_queue = asyncio.Queue(maxsize=10)

        processed_count = 0
        log_threshold = max(1, total_items // 10)
        t_kwargs = transform_kwargs or {}

        async def _extract_with_retry(extract_args, t_kwargs):
            """Wrapper do extract+transform com retry exponencial."""
            for attempt in range(5):
                try:
                    raw_df = await components.extractor.extract(**extract_args)
                    if raw_df is not None and not raw_df.is_empty():
                        clean_df = components.transformer.transform(raw_df, **t_kwargs)
                        if clean_df is None or clean_df.is_empty():
                            logger.warning(
                                "[%s] %s linhas brutas descartadas na transformação "
                                "(contrato Silver ou filtro temporal).",
                                table_name,
                                raw_df.height,
                            )
                            return None
                        return clean_df
                    return None
                except Exception as e:
                    if attempt < 4:
                        wait = min(16, 2**attempt)
                        logger.warning(
                            "[%s] Retry %d/5 para job %s: %s",
                            table_name,
                            attempt + 1,
                            extract_args,
                            e,
                        )
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            "Erro fatal processando job %s em %s (5 tentativas): %s",
                            extract_args,
                            table_name,
                            e,
                        )
                        return None

        async def worker():
            nonlocal processed_count
            while True:
                try:
                    job_item = job_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                extract_args = extract_kwargs_mapper(job_item)
                clean_df = await _extract_with_retry(extract_args, t_kwargs)

                if clean_df is not None:
                    await df_queue.put(clean_df)

                processed_count += 1
                if processed_count % log_threshold == 0 or processed_count == total_items:
                    percent = (processed_count / total_items) * 100
                    logger.info(
                        f"       [Progresso - {table_name}] {processed_count}/{total_items} "
                        f"({percent:.1f}%) concluído."
                    )
                job_queue.task_done()

        async def consumer():
            while True:
                df = await df_queue.get()
                if df is None:  # Poison pill para encerrar o consumidor
                    df_queue.task_done()
                    break

                try:
                    # CARGA (I/O de Gravação Append-Only)
                    await components.sink.save(
                        df=df, table_name=table_name, layer=layer.value, unique_keys=unique_keys
                    )
                except Exception as e:
                    logger.error(f"Erro ao salvar dados no Sink da tabela {table_name}: {e}")
                finally:
                    df_queue.task_done()

        # Inicia a Orquestração
        consumer_task = asyncio.create_task(consumer())
        workers = [asyncio.create_task(worker()) for _ in range(self.max_workers)]

        # Aguarda todos os workers finalizarem as extrações
        await asyncio.gather(*workers)

        # Envia a poison pill para desligar o consumidor com segurança
        await df_queue.put(None)
        await consumer_task

        # Garante que todo buffer residual seja descarregado
        await components.sink.flush(table_name=table_name, layer=layer.value)
