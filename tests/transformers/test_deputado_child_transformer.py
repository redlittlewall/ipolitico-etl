import polars as pl
from ipolitico.transformers.camara.deputado_child_transformer import CamaraDeputadoChildTransformer


def test_profissoes_contract():
    tr = CamaraDeputadoChildTransformer()
    raw = pl.DataFrame(
        {
            "id_deputado": [1],
            "titulo": ["Engenheiro"],
            "entidade": ["CREA"],
            "anoInicio": [2010],
            "anoFim": [2020],
        }
    )
    out = tr.transform(raw, sub_domain="profissoes")
    assert out.height == 1
    assert out["titulo"][0] == "Engenheiro"
