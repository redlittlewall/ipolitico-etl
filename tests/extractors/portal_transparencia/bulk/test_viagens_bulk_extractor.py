"""Testes do PortalViagensBulkExtractor — seleção do CSV da entidade-pai.

O ZIP anual de viagens tem 4 CSVs heterogêneos (``*_Pagamento.csv``,
``*_Passagem.csv``, ``*_Trecho.csv``, ``*_Viagem.csv``). O base
(``PortalTransparenciaBulkExtractor``) concatenaria TODOS via
``diagonal_relaxed`` — o que quebraria a unicidade da UK Silver
(``identificador_processo_viagem`` se repete por trecho/passagem/pagamento). A
subclasse seleciona apenas o ``*_Viagem.csv`` e o lê com o ``rename_map`` do
registry (colunas do CSV → snake_case do contrato).
"""

import zipfile
from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.portal_transparencia.bulk.bulk_extractor import (
    PortalTransparenciaBulkExtractor,
)
from ipolitico.extractors.portal_transparencia.bulk.viagens_bulk_extractor import (
    PortalViagensBulkExtractor,
)

HEADER_VIAGEM = (
    "Identificador do processo de viagem;Número da Proposta (PCDP);Situação;"
    "Viagem Urgente;Justificativa Urgência Viagem;Código do órgão superior;"
    "Nome do órgão superior;Código órgão solicitante;Nome órgão solicitante;"
    "CPF viajante;Nome;Cargo;Função;Descrição Função;Período - Data de início;"
    "Período - Data de fim;Destinos;Motivo;Valor diárias;Valor passagens;"
    "Valor devolução;Valor outros gastos"
)
ROW_VIAGEM = (
    "000000000001246317;009796/16;Realizada;NÃO;Sem informação;50000;"
    "MINISTERIO DA JUSTICA;52001;POLICIA FEDERAL;***.726.515-**;JOAO DA SILVA;"
    "DELEGADO;DAS-1016;Cargo de Assessoramento;04/01/2016;10/01/2016;BRASILIA;"
    "DILIGENCIA;8791,50;0,00;0,00;0,00"
)
# CSVs filhos referenciam o MESMO processo de viagem → não podem entrar na UK.
ROW_TECHO = "000000000001246317;10/01/2016;BRASILIA;RIO DE JANEIRO"
ROW_PASSAGEM = "000000000001246317;123456;8791,50"
ROW_PAGAMENTO = "000000000001246317;2024-01;PAGO"


@pytest.fixture(autouse=True)
def _clear_bulk_cache():
    """Limpa os caches do portal e da classe base antes de cada teste."""
    PortalTransparenciaBulkExtractor.clear_cache()
    BaseBulkExtractor.clear_cache()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.download_file = AsyncMock(return_value=True)
    return client


def _write_zip_with_4_csvs(dest) -> None:
    """Escreve o ZIP anual real: 4 CSVs heterogêneos (Viagem + 3 filhos).

    Os CSVs reais são latin-1 — o fixture escreve bytes latin-1 (o registry
    lê ``encoding="latin-1"``; UTF-8 produziria mojibake nos acentos do
    header, quebrando o ``rename_map``).
    """

    def lat(s: str) -> bytes:
        return s.encode("latin-1")

    with zipfile.ZipFile(dest, "w") as zf:
        zf.writestr(
            "2025_Pagamento.csv",
            lat("Identificador do processo de viagem;Situação;Valor\n" + ROW_PAGAMENTO + "\n"),
        )
        zf.writestr(
            "2025_Passagem.csv",
            lat("Identificador do processo de viagem;Número bilhete;Valor\n" + ROW_PASSAGEM + "\n"),
        )
        zf.writestr(
            "2025_Trecho.csv",
            lat("Identificador do processo de viagem;Data;Origem;Destino\n" + ROW_TECHO + "\n"),
        )
        zf.writestr("2025_Viagem.csv", lat(HEADER_VIAGEM + "\n" + ROW_VIAGEM + "\n"))


@pytest.mark.asyncio
async def test_extract_seleciona_apenas_o_viagem_csv(tmp_path, mock_client):
    """Só as linhas do *_Viagem.csv entram; os 3 CSVs filhos ficam de fora."""
    url = "https://portaldatransparencia.gov.br/download-de-dados/viagens/2025"

    async def fake_download(dest_url, dest):
        _write_zip_with_4_csvs(dest)
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalViagensBulkExtractor(
        mock_client, module="viagens", domain_name="cg_viagens", bulk_dir=tmp_path
    )

    result = await ext.extract(year=2025)

    # 1 linha (o *_Viagem.csv), não 4 (o base concatenaria os 4 CSVs).
    assert result.height == 1
    assert result["identificador_processo_viagem"][0] == "000000000001246317"
    assert result["nome_viajante"][0] == "JOAO DA SILVA"
    # rename_map aplicado: colunas do CSV já em snake_case do contrato.
    assert result.columns[0] == "_source_url"
    assert "identificador_processo_viagem" in result.columns
    assert "Cargo" not in result.columns
    assert "valor_diarias" in result.columns
    assert result["valor_diarias"][0] == "8791,50"
    assert result["_source_url"][0] == url


@pytest.mark.asyncio
async def test_extract_zip_sem_viagem_csv_retorna_vazio(tmp_path, mock_client):
    """ZIP sem o membro *_Viagem.csv → DataFrame vazio, sem crash."""

    async def fake_download(dest_url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("2025_Pagamento.csv", "A;B\n1;2\n")
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalViagensBulkExtractor(
        mock_client, module="viagens", domain_name="cg_viagens", bulk_dir=tmp_path
    )

    result = await ext.extract(year=2025)

    assert result.is_empty()


@pytest.mark.asyncio
async def test_extract_motivo_com_ponto_e_virgula_entre_aspas_nao_desalinha(tmp_path, mock_client):
    """Motivo com ``;`` entre aspas → parse quote-aware; monetárias não desalinham.

    Correção da validação real (ticket 04): o campo Motivo do dump real contém
    ``;`` dentro de aspas (ex: prosa citando vários números de PCDP). Com
    ``quote_char=None`` (padrão do base), a linha vira 26 campos e o
    ``truncate_ragged_lines`` corta os valores monetários reais, deixando
    fragmentos do Motivo nas colunas de valor (soma absurda 2e18 no Silver).
    """
    # Motivo QUOTADO contendo ";" (reproduz a linha real: "…Nota 00217224420138130084;
    # e 00126437020158130084…"). O parse quote-aware mantém o Motivo como UM campo.
    motivo_quoted = (
        '"Viagem de Pocoos de Caldas a Botelhos; autorizado pela Nota '
        '00217224420138130084; e 00126437020158130084"'
    )
    row = ROW_VIAGEM.replace("DILIGENCIA", motivo_quoted)

    async def fake_download(dest_url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("2025_Viagem.csv", (HEADER_VIAGEM + "\n" + row + "\n").encode("latin-1"))
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalViagensBulkExtractor(
        mock_client, module="viagens", domain_name="cg_viagens", bulk_dir=tmp_path
    )

    result = await ext.extract(year=2025)

    assert result.height == 1
    assert result["identificador_processo_viagem"][0] == "000000000001246317"
    # valor_diarias mantém o valor REAL (8791,50), não fragmento do Motivo.
    assert result["valor_diarias"][0] == "8791,50"
    assert result["valor_passagens"][0] == "0,00"
    assert result["motivo"][0].startswith("Viagem de Pocoos de Caldas a Botelhos")


@pytest.mark.asyncio
async def test_identificador_unicidade_preservada(tmp_path, mock_client):
    """Duas viagens no *_Viagem.csv → 2 linhas, UK deduplica sem colisão."""

    async def fake_download(dest_url, dest):
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr(
                "2025_Viagem.csv",
                (
                    HEADER_VIAGEM
                    + "\n"
                    + ROW_VIAGEM
                    + "\n"
                    + ROW_VIAGEM.replace("000000000001246317", "000000000001246318")
                    .replace("009796/16", "009797/16")
                    .replace("JOAO DA SILVA", "MARIA DA SILVA")
                    + "\n"
                ).encode("latin-1"),
            )
        return True

    mock_client.download_file.side_effect = fake_download
    ext = PortalViagensBulkExtractor(
        mock_client, module="viagens", domain_name="cg_viagens", bulk_dir=tmp_path
    )

    result = await ext.extract(year=2025)

    assert result.height == 2
    assert result["identificador_processo_viagem"].n_unique() == 2
