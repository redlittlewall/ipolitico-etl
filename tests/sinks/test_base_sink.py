import polars as pl
import pytest
from ipolitico.sinks.base import BaseSink


class DummySink(BaseSink):
    """Implementação vazia para testar a fundação da interface."""

    async def save(self, df: pl.DataFrame, table_name: str) -> None:
        # Aciona explicitamente o 'pass' da classe abstrata
        await super().save(df, table_name)


@pytest.mark.asyncio
async def test_base_sink_contract():
    """
     Garante que o contrato BaseSink pode ser
    herdado e executado sem efeitos colaterais. O método abstrato
    deve permanecer estéril (apenas 'pass').
    """
    sink = DummySink()
    df_vazio = pl.DataFrame()

    # Executa o contrato. Se houver qualquer lógica oculta na base,
    # ou se a assinatura do método mudar, o teste quebra.
    try:
        await sink.save(df_vazio, "tabela_qualquer")
    except Exception as e:
        pytest.fail(f"O contrato BaseSink falhou de forma inesperada: {e}")
