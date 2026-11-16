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


# --- Contrato do `copier update` (infraestrutura do template) ---

SKIP_ESPERADO = [
    "src/**",
    "tests/**",
    "docs/**",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    ".python-version",
    "pyproject.toml",
]


def _copier_doc() -> dict:
    return yaml.safe_load((TEMPLATE / "copier.yaml").read_text(encoding="utf-8"))


def test_skip_if_exists_cobre_o_que_e_do_fetcher():
    assert _copier_doc()["_skip_if_exists"] == SKIP_ESPERADO


def test_exclude_do_update_espelha_o_skip_if_exists():
    """No update, os mesmos caminhos do skip não são nem recriados (_exclude)."""
    doc = _copier_doc()
    condicional = [e for e in doc["_exclude"] if "_copier_operation" in e]
    assert len(condicional) == 1
    linhas = [
        linha.strip()
        for linha in condicional[0].splitlines()
        if linha.strip() and not linha.strip().startswith("{%")
    ]
    assert linhas == doc["_skip_if_exists"]


def test_arquivo_de_respostas_sai_do_template(pacote: Path):
    modelo = TEMPLATE / "{{ _copier_conf.answers_file }}.jinja"
    assert modelo.read_text(encoding="utf-8").strip() == (
        "{{ _copier_answers|to_nice_yaml -}}"
    )
    respostas = yaml.safe_load((pacote / ".copier-answers.yml").read_text("utf-8"))
    assert respostas["_src_path"] == str(TEMPLATE)
    assert respostas["_commit"]
    assert respostas["source_id"] == "zeta-norte"
    assert respostas["orgao"] == 'Órgão Zeta "ZN" \\ (ZETA)'
    assert respostas["has_lake"] is True


def test_hooks_do_repo_vao_executaveis(pacote: Path):
    for nome in ("pre-commit", "pre-push"):
        hook = pacote / ".githooks" / nome
        assert hook.is_file()
        assert os.access(hook, os.X_OK)


def test_licenca_com_titular_quantilica(pacote: Path):
    assert "Copyright (c) 2026 Quantilica\n" in (pacote / "LICENSE").read_text("utf-8")


def test_changelog_gerado_tem_data(pacote: Path):
    linha = next(
        ln
        for ln in (pacote / "CHANGELOG.md").read_text("utf-8").splitlines()
        if ln.startswith("## [0.1.0]")
    )
    assert linha.removeprefix("## [0.1.0] - ").count("-") == 2


def test_pyproject_gerado_no_formato_dos_repos(pacote: Path):
    import tomllib

    doc = tomllib.loads((pacote / "pyproject.toml").read_text(encoding="utf-8"))
    assert doc["tool"]["uv"]["required-version"] == ">=0.9"
    assert [i["name"] for i in doc["tool"]["uv"]["index"]] == ["pypi", "quantilica"]
    assert "sources" not in doc["tool"]["uv"]
    assert not any("3.14" in c for c in doc["project"]["classifiers"])


def test_test_yml_gerado_no_formato_dos_repos(pacote: Path):
    texto = (pacote / ".github/workflows/test.yml").read_text(encoding="utf-8")
    wf = yaml.safe_load(texto)
    assert wf["jobs"]["test"]["strategy"]["matrix"]["python-version"] == [
        "3.12",
        "3.13",
    ]
    comandos = "\n".join(
        passo["run"]
        for job in wf["jobs"].values()
        for passo in job["steps"]
        if "run" in passo
    )
    assert "--index" not in comandos
    assert "uv run " not in comandos.replace("uv run --no-sync", "")
    passos = {p.get("name"): p for p in wf["jobs"]["test"]["steps"]}
    assert passos["Type check with pyright"]["continue-on-error"] is True
    assert "pyright" not in wf["jobs"]  # não é mais um job separado
    assert "zizmor" in wf["jobs"]
    # Toda `uses:` fixada por SHA de 40 caracteres.
    import re

    for uses in re.findall(r"uses:\s*(\S+)", texto):
        assert re.fullmatch(r".+@[0-9a-f]{40}", uses), uses
