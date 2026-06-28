from ipolitico.pipeline.job_resume import filter_despesas_api_jobs


def test_filter_despesas_api_jobs_skips_covered_pairs():
    jobs = [
        {"deputado_id": 1, "year": 2023},
        {"deputado_id": 2, "year": 2023},
        {"deputado_id": 1, "year": 2024},
    ]
    covered = {(1, 2023), (2, 2023)}
    out = filter_despesas_api_jobs(jobs, covered)
    assert out == [{"deputado_id": 1, "year": 2024}]


def test_filter_votacao_ids_pending_votos():
    from ipolitico.pipeline.job_resume import filter_votacao_ids_pending_votos

    pending = filter_votacao_ids_pending_votos(["a", "b", "c"], {"a", "b"})
    assert pending == ["c"]
