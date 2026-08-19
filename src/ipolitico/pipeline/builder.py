import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict

from ipolitico.core.config import DATA_DIR
from ipolitico.core.constants import SinkType, SourceType
from ipolitico.extractors.base import BaseExtractor
from ipolitico.sinks.base import BaseSink
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineComponents:
    """
    Contêiner de dados imutável que transporta os componentes instanciados
    e prontos para execução pelo PipelineRunner.
    """

    extractor: BaseExtractor
    transformer: BaseTransformer
    sink: BaseSink


class PipelineBuilder:
    """
    Construtor de Pipeline orientado a configuração (Config-Driven).

    Substitui fábricas engessadas por importações dinâmicas (Reflection).
    Lê os caminhos das classes a partir do YAML e injeta as dependências
    corretas em tempo de execução.
    """

    def __init__(self, client: Any):
        """
        Inicializa o construtor com as dependências de rede (cliente HTTP).

        Args:
            client: Cliente HTTP compartilhado para injeção nos extratores
                    (CamaraClient, SenadoClient ou similar).
        """
        self.client = client

    def _import_class(self, class_path: str) -> Any:
        """
        Carrega uma classe dinamicamente a partir do seu caminho em string.

        Args:
            class_path (str): Caminho completo (ex: "ipolitico.sinks.datalake_sink.DataLakeSink").

        Returns:
            Any: A referência da classe pronta para ser instanciada.

        Raises:
            ImportError: Se o módulo ou classe não for encontrado.
        """
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as e:
            logger.error(f"Falha catastrófica ao carregar classe dinamicamente: {class_path}")
            raise ImportError(f"Não foi possível importar {class_path}: {e}")

    def build(
        self,
        domain_config: Dict[str, Any],
        sink_type: SinkType,
        source_type: SourceType = SourceType.API,
        domain_name: str | None = None,
    ) -> PipelineComponents:
        """
        Instancia Extractor, Transformer e Sink, injetando suas dependências.

        Args:
            domain_config (Dict[str, str]): Dicionário com os paths mapeados do YAML.
                Ex: {"extractor": "path.to.Ext", "transformer": "path.to.Trans"}.
                Pode conter ``extractor_kwargs`` (dict opcional de kwargs do
                construtor do extrator — ex: ``{"module": "servidores"}`` no
                portal da transparência, onde o segmento da URL difere do
                domain_name do pipeline).
            sink_type (SinkType): O destino escolhido pelo usuário (DataLake).
            source_type (SourceType): Fonte de extração (API ou Bulk).
            domain_name (str, optional): Nome do domínio para extratores Bulk.

        Returns:
            PipelineComponents: Objeto contendo as três instâncias acopladas e prontas.
        """
        logger.debug("Construindo blocos do pipeline via injeção dinâmica...")

        extractor_path_key = (
            "extractor_bulk"
            if source_type == SourceType.BULK and domain_config.get("extractor_bulk")
            else "extractor"
        )
        extractor_class = self._import_class(domain_config[extractor_path_key])

        extractor_kwargs: dict[str, Any] = {"client": self.client}
        if domain_name and source_type == SourceType.BULK:
            extractor_kwargs["domain_name"] = domain_name
        # Merge dos kwargs declarados no YAML (ex: ``extractor_kwargs: {module: servidores}``
        # no portal da transparência — o segmento da URL difere do domain_name do
        # pipeline, ex: ``cg_imoveis_funcionais`` → ``imoveis-funcionais``).
        extractor_kwargs.update(domain_config.get("extractor_kwargs", {}))
        extractor_instance = extractor_class(**extractor_kwargs)

        # Instancia o Transformer (Puro, sem dependências de I/O)
        transformer_class = self._import_class(domain_config["transformer"])
        transformer_instance = transformer_class()

        # Instancia o Sink selecionado com os paths da configuração global
        sink_path_config = domain_config.get("sinks", {})
        sink_class_path = sink_path_config.get(sink_type.value)

        if not sink_class_path:
            from ipolitico.sinks.datalake_sink import DataLakeSink

            sink_class = DataLakeSink
        else:
            sink_class = self._import_class(sink_class_path)

        sink_instance = sink_class(base_dir=str(DATA_DIR / "datalake"))

        logger.info(
            f"Pipeline montado com sucesso: [{extractor_class.__name__} -> "
            f"{transformer_class.__name__} -> {sink_class.__name__}]",
        )

        return PipelineComponents(
            extractor=extractor_instance, transformer=transformer_instance, sink=sink_instance
        )
