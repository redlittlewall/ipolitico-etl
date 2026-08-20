"""Passo 0 do ticket 04 — capturar o header real do CSV de viagens (bulk anual).

Lê o ZIP do dump anual de viagens VIA RANGE (sem baixar os ~130 MB): o diretório
central do ZIP fica no fim do arquivo; com ele sabemos o offset do header local
do(s) membro(s) e lemos só os primeiros KB do CSV (encapsulado deflate, truncado
de propósito — o suficiente para o header e 2-3 linhas).

Imprime: schema real (nome das colunas), encoding, amostra de 2 linhas e o
nome(s) do(s) membro(s) do ZIP.
Uso: python .scratch/portal-transparencia/tools/_capture_viagens_header.py
"""

from __future__ import annotations

import struct
import zlib

import httpx

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# 2016 = 131 MB (menor ano substancial; 2013 tem 4 KB quase vazio)
URL = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/viagens/2016_20260816_Viagens.zip"


def _range_get(client: httpx.Client, start: int, end: int) -> bytes:
    """
    Baixa um intervalo de bytes do dump via Range header.

    Args:
        client: Cliente HTTP já configurado com User-Agent e redirects.
        start: Primeiro byte (inclusivo) do intervalo.
        end: Último byte (inclusivo) do intervalo.

    Returns:
        Conteúdo bruto do intervalo.

    Raises:
        RuntimeError: Se o host não responde 200/206 (Range não suportado
            ou falha de rede).
    """
    r = client.get(URL, headers={"Range": f"bytes={start}-{end}"})
    if r.status_code not in (200, 206):
        raise RuntimeError(f"Range {start}-{end} falhou: {r.status_code}")
    return r.content


def main() -> None:
    """
    Captura e imprime o header real do CSV de viagens via ZIP Range parcial.

    Lê o tamanho total via HEAD, localiza o EOCD/diretório central no tail e
    descompacta só os primeiros KB de cada membro (deflate truncado) para
    imprimir encoding e header. Não baixa o arquivo inteiro.
    """
    client = httpx.Client(
        timeout=60.0,
        headers={"User-Agent": BROWSER_UA},
        follow_redirects=True,
    )
    head = client.head(URL)
    total = int(head.headers.get("Content-Length", "0"))

    print(f"total_bytes={total}")

    tail = _range_get(client, max(0, total - 200_000), total - 1)
    # EOCD: PK\x05\x06
    eocd_idx = tail.rfind(b"\x50\x4b\x05\x06")
    if eocd_idx < 0:
        raise RuntimeError("EOCD não encontrado no tail")
    cd_size = struct.unpack_from("<I", tail, eocd_idx + 12)[0]
    cd_offset = struct.unpack_from("<I", tail, eocd_idx + 16)[0]

    # Garante o diretório central completo
    if cd_offset >= total - 200_000:
        cd = tail[eocd_idx - cd_size : eocd_idx]
    else:
        cd = _range_get(client, cd_offset, cd_offset + cd_size - 1)

    members = []
    pos = 0
    while pos + 46 <= len(cd):
        if cd[pos : pos + 4] != b"\x50\x4b\x01\x02":
            break
        method = struct.unpack_from("<H", cd, pos + 10)[0]
        name_len = struct.unpack_from("<H", cd, pos + 28)[0]
        extra_len = struct.unpack_from("<H", cd, pos + 30)[0]
        comment_len = struct.unpack_from("<H", cd, pos + 32)[0]
        local_offset = struct.unpack_from("<I", cd, pos + 42)[0]
        name = cd[pos + 46 : pos + 46 + name_len].decode("utf-8", "replace")
        members.append((name, method, local_offset))
        pos += 46 + name_len + extra_len + comment_len

    print(f"membros={members}")

    for name, method, local_offset in members:
        if name.endswith("/"):
            continue
        lh = _range_get(client, local_offset, local_offset + 30)
        if lh[:4] != b"\x50\x4b\x03\x04":
            raise RuntimeError(f"Header local inválido para {name}")
        name_len = struct.unpack_from("<H", lh, 26)[0]
        extra_len = struct.unpack_from("<H", lh, 28)[0]
        data_start = local_offset + 30 + name_len + extra_len
        chunk = _range_get(client, data_start, min(data_start + 200_000, total - 1))

        raw = chunk
        if method == 8:  # deflate: descompacta truncado, basta o início
            d = zlib.decompressobj(-zlib.MAX_WBITS)
            try:
                raw = d.decompress(chunk)
            except zlib.error as e:
                # fluxo truncado de propósito — o que já saiu é o bastante
                print(f"  (deflate truncado intencional: {e})")

        for enc in ("latin-1", "utf-8", "cp1252"):
            try:
                text = raw.decode(enc)
                print(f"  encoding={enc} bytes_decoded={len(raw)}")
                lines = text.split("\n")
                print(f"  header={lines[0]!r}")
                header = lines[0]
                sep = ";" if ";" in header else ","
                print(f"  n_cols={len(header.split(sep))}")
                for line in lines[1:4]:
                    if line.strip():
                        print(f"  linha={line[:400]!r}")
                break
            except UnicodeDecodeError:
                continue


if __name__ == "__main__":
    main()
