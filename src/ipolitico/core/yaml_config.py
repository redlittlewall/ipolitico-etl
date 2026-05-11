import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class PipelineConfigLoader:
    """
    Responsável por carregar e processar as configurações YAML do pipeline.

    Isola a leitura de arquivos físicos e a conversão de YAML para dicionários Python,
    permitindo que o Builder do pipeline seja agnóstico à origem da configuração.
    """

    def __init__(self, config_path: str = "configs/camara_pipeline.yaml"):
        """
        Inicializa o loader com o caminho do arquivo de configuração.

        Args:
            config_path (str): Caminho relativo ou absoluto para o arquivo YAML.
        """
        self.config_path = Path(config_path)

    def load(self) -> Dict[str, Any]:
        """
        Lê e retorna a configuração do pipeline mapeada no arquivo YAML.

        Returns:
            Dict[str, Any]: Dicionário contendo as configurações de domain,
                            extractor_class, transformer_class e sink_type.

        Raises:
            FileNotFoundError: Se o arquivo YAML não for encontrado.
            yaml.YAMLError: Se houver erro de sintaxe no arquivo.
        """
        if not self.config_path.exists():
            logger.error(f"Arquivo de configuração não encontrado: {self.config_path}")
            raise FileNotFoundError(f"Configuration file {self.config_path} not found.")

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                logger.debug(f"Configuração {self.config_path.name} carregada com sucesso.")
                return config
        except yaml.YAMLError as exc:
            logger.error(f"Erro ao fazer o parse do arquivo YAML: {exc}")
            raise
