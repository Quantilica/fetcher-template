"""Smoke do template: gera um pacote pelo ``render.py`` (sem copier nem rede).

Confere que o ``plugin.py`` declara o ``FetcherInfo`` com escape correto, que o
``tests/test_registry_info.py`` gerado passa e que o ``copier.yaml`` é YAML válido.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")
yaml = pytest.importorskip("yaml")

TEMPLATE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TEMPLATE))

import render  # noqa: E402


@pytest.fixture(scope="module")
def pacote(tmp_path_factory) -> Path:
    dest = tmp_path_factory.mktemp("gen")
    render.render_template(
        dest,
        source_id="zeta-norte",
        source_name="Fonte Zeta Norte",
        orgao='Órgão Zeta "ZN" \\ (ZETA)',
        homepage="https://zeta.example.gov.br/dados",
        cadencia="yearly",
        dominio="fiscal",
    )
    return dest


def test_copier_yaml_valido_com_perguntas_do_info():
    doc = yaml.safe_load((TEMPLATE / "copier.yaml").read_text(encoding="utf-8"))
    for pergunta in ("orgao", "licenca", "homepage", "cadencia", "dominio"):
        assert pergunta in doc
    assert doc["has_lake"]["default"] is True
    assert doc["cadencia"]["choices"] == [
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "yearly",
        "irregular",
    ]


def test_plugin_declara_fetcher_info(pacote: Path):
    src = (pacote / "src/zeta_norte_fetcher/plugin.py").read_text(encoding="utf-8")
    call = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "FetcherInfo"
    )
    kw = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    assert kw["id"] == "zeta-norte"
    assert kw["nome"] == "Fonte Zeta Norte"
    assert kw["orgao"] == 'Órgão Zeta "ZN" \\ (ZETA)'
    assert kw["cadencia"] == "yearly"
    assert kw["dominio"] == "fiscal"
    assert kw["homepage"].startswith("https://")
    assert kw["licenca"]


def test_dominio_vazio_nao_e_declarado(tmp_path: Path):
    render.render_template(tmp_path, source_id="zeta", source_name="Zeta", dominio="")
    src = (tmp_path / "src/zeta_fetcher/plugin.py").read_text(encoding="utf-8")
    assert "dominio=" not in src


def test_teste_de_identidade_gerado_passa(pacote: Path):
    python = os.environ.get("TEMPLATE_TEST_PYTHON", sys.executable)
    res = subprocess.run(
        [
            python,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_registry_info.py",
        ],
        cwd=pacote,
        env={**os.environ, "PYTHONPATH": str(pacote / "src")},
        capture_output=True,
        text=True,
    )
    if "No module named" in res.stdout + res.stderr and "quantilica" in (
        res.stdout + res.stderr
    ):
        pytest.skip("quantilica-cli/core ausentes neste interpretador")
    assert res.returncode == 0, res.stdout + res.stderr
