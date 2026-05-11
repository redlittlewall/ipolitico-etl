import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import DATA_DIR, DB_PATH
from ipolitico.core.constants import SinkType
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

    def __init__(self, client: CamaraClient):
        """
        Inicializa o construtor com as dependências de rede globais.

        Args:
            client (CamaraClient): Cliente HTTP compartilhado para injeção nos extratores.
        """
        self.client = client

    def _import_class(self, class_path: str) -> Any:
        """
        Carrega uma classe dinamicamente a partir do seu caminho em string.

        Args:
            class_path (str): Caminho completo (ex: "ipolitico.sinks.sqlite_sink.SQLiteSink").

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

    def build(self, domain_config: Dict[str, str], sink_type: SinkType) -> PipelineComponents:
        """
        Instancia Extractor, Transformer e Sink, injetando suas dependências.

        Args:
            domain_config (Dict[str, str]): Dicionário com os paths mapeados do YAML.
                Ex: {"extractor": "path.to.Ext", "transformer": "path.to.Trans"}
            sink_type (SinkType): O destino escolhido pelo usuário (SQLite ou DataLake).

        Returns:
            PipelineComponents: Objeto contendo as três instâncias acopladas e prontas.
        """
        logger.debug("Construindo blocos do pipeline via injeção dinâmica...")

        # Instancia o Extrator injetando o Client
        extractor_class = self._import_class(domain_config["extractor"])
        extractor_instance = extractor_class(client=self.client)

        # Instancia o Transformer (Puro, sem dependências de I/O)
        transformer_class = self._import_class(domain_config["transformer"])
        transformer_instance = transformer_class()

        # Instancia o Sink selecionado com os paths da configuração global
        sink_path_config = domain_config.get("sinks", {})
        sink_class_path = sink_path_config.get(sink_type.value)

        if not sink_class_path:
            raise ValueError(f"Sink '{sink_type.value}' não mapeado na configuração do domínio.")

        sink_class = self._import_class(sink_class_path)

        # Injeção de dependência de caminhos baseados no tipo do Sink
        if sink_type == SinkType.SQLITE:
            sink_instance = sink_class(db_path=str(DB_PATH))
        elif sink_type == SinkType.DATALAKE:
            sink_instance = sink_class(base_dir=str(DATA_DIR / "datalake"))
        else:
            sink_instance = sink_class()

        logger.info(
            f"Pipeline montado com sucesso: [{extractor_class.__name__} -> ",
            f"{transformer_class.__name__} -> {sink_class.__name__}]",
        )

        return PipelineComponents(
            extractor=extractor_instance, transformer=transformer_instance, sink=sink_instance
        )
