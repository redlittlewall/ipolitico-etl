"""Passo 0 do ticket 04 — verificar o CSV principal de viagens (2016_Viagem.csv).

Lê o ZIP local baixado (``data/portal_dumps/viagens_2016.zip``), extrai só o
membro ``*_Viagem.csv`` (o dump tem 4 CSVs heterogêneos — Pagamento/Passagem/
Trecho/Viagem) e imprime: colunas reais, encoding, nº de linhas, unicidade do
"Identificador do processo de viagem" (para a UK Silver), amostra com sentinels
(sigilo) e os valores monetários.
Uso: python .scratch/portal-transparencia/tools/_verify_viagens_csv.py
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import polars as pl

from ipolitico.core.config import DATA_DIR

ZIP_PATH = Path(DATA_DIR) / "portal_dumps" / "viagens_2016.zip"


def main() -> None:
    """
    Verifica o CSV principal do dump de viagens baixado.

    Extrai só o ``*_Viagem.csv`` do ZIP local e imprime colunas, encoding,
    nº de linhas, unicidade do ``Identificador do processo de viagem`` (para a
    UK Silver), amostra e valores monetários — com ``quote_char='"'``, o MESMO
    parse quote-aware do ``PortalViagensBulkExtractor`` (o campo Motivo tem
    ``;`` dentro de aspas; sem o parse, os valores monetários desalinham).

    Raises:
        RuntimeError: Se o dump não está baixado ou o membro não existe.
    """
    if not ZIP_PATH.exists():
        raise RuntimeError(f"Dump não baixado: {ZIP_PATH}")

    with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
        members = [m for m in zip_ref.namelist() if not m.endswith("/")]
        viagem = [m for m in members if m.endswith("_Viagem.csv")]
        print(f"membros={members}")
        print(f"viagem_member={viagem}")
        if not viagem:
            raise RuntimeError("Membro *_Viagem.csv não encontrado")
        zip_ref.extract(viagem[0], "/tmp/viagens_verify")

    csv_path = os.path.join("/tmp/viagens_verify", viagem[0])
    df = pl.read_csv(
        csv_path,
        separator=";",
        ignore_errors=True,
        infer_schema_length=0,
        encoding="latin-1",
        truncate_ragged_lines=True,
        quote_char='"',
    )
    df = df.rename({c: c.replace('"', "").strip() for c in df.columns})
    df = df.with_columns(pl.col(pl.String).str.replace_all('"', "").str.strip_chars())
    print(f"n_linhas={df.height}")
    print(f"n_cols={df.width}")
    print(f"colunas={df.columns}")

    id_col = "Identificador do processo de viagem"
    print(f"distinct_{id_col}={df[id_col].n_unique()}")

    print("amostra de 3 linhas:")
    sample = df.head(3).with_columns(pl.all().str.slice(0, 60))
    print(sample)

    money_cols = [c for c in df.columns if c.lower().startswith("valor")]
    print(f"colunas_monetarias={money_cols}")
    for c in money_cols:
        print(f"  {c}: amostra={df[c].to_list()[:5]}")


if __name__ == "__main__":
    main()
