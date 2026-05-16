from ipolitico.core.constants import DomainType
from ipolitico.pipeline.domain_order import expand_camara_domains_with_dependencies


def test_expand_inserts_deputados_before_despesas():
    out = expand_camara_domains_with_dependencies([DomainType.DESPESAS])
    assert out[0] == DomainType.DEPUTADOS
    assert DomainType.DESPESAS in out


def test_expand_inserts_votacoes_before_votos():
    out = expand_camara_domains_with_dependencies([DomainType.VOTOS])
    assert DomainType.VOTACOES in out
    assert out.index(DomainType.VOTACOES) < out.index(DomainType.VOTOS)
