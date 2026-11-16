#!/usr/bin/env python3
"""Offline template renderer for fetcher-template.

Renders copier template files using jinja2 directly, without needing external network
or the copier CLI binary. O arquivo de respostas (``.copier-answers.yml``) sai do
próprio template (``{{ _copier_conf.answers_file }}.jinja``), exatamente como o
``copier copy`` o grava; este script só fornece o contexto que o copier fornece
(``_copier_conf``, ``_copier_answers``, ``now()`` e o filtro ``to_nice_yaml``).
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import os
import shutil
import subprocess
from pathlib import Path

import jinja2
import yaml

TEMPLATE_DIR = Path(__file__).resolve().parent
ANSWERS_FILE = ".copier-answers.yml"

# Diretórios ocultos que fazem parte do pacote gerado.
HIDDEN_DIRS = {".github", ".githooks"}
# Arquivos e diretórios do próprio template que não vão para o pacote (espelha _exclude).
EXCLUDED_TOP = {"tests_template"}
EXCLUDED_FILES = {"render.py", "copier.yaml", "copier.yml"}
EXCLUDED_NAMES = {".git", ".DS_Store"}
EXCLUDED_GLOBS = ("~*", "*.py[co]")


def _template_commit() -> str:
    """Referência do template para o ``_commit`` (tag, ou hash curto sem tag)."""
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=TEMPLATE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def _to_nice_yaml(data: object) -> str:
    return yaml.safe_dump(
        data, default_flow_style=False, allow_unicode=True, sort_keys=True
    )


def render_template(
    target_dir: Path,
    *,
    source_id: str,
    source_name: str,
    package_name: str | None = None,
    package_slug: str | None = None,
    description: str | None = None,
    domain: str | None = None,
    author_name: str = "Komesu, D.K.",
    author_email: str = "daniel@dkko.me",
    has_lake: bool = True,
    protocol: str = "http",
    orgao: str = "Órgão responsável pelos dados",
    licenca: str = (
        "Sem licença declarada; dados públicos pela Lei 12.527/2011 (LAI) "
        "e Decreto 8.777/2016"
    ),
    homepage: str = "https://www.gov.br/",
    cadencia: str = "monthly",
    dominio: str = "",
) -> None:
    package_name = package_name or f"{source_id}-fetcher"
    package_slug = package_slug or f"{source_id.replace('-', '_')}_fetcher"
    description = (
        description
        or f"Coletor e conversor Lake Hive de dados abertos de {source_name}"
    )
    domain = domain or source_id

    answers = {
        "source_id": source_id,
        "source_name": source_name,
        "package_name": package_name,
        "package_slug": package_slug,
        "description": description,
        "domain": domain,
        "author_name": author_name,
        "author_email": author_email,
        "has_lake": has_lake,
        "protocol": protocol,
        "orgao": orgao,
        "licenca": licenca,
        "homepage": homepage,
        "cadencia": cadencia,
        "dominio": dominio,
    }
    context = {
        **answers,
        "_copier_conf": {"answers_file": ANSWERS_FILE},
        "_copier_answers": {
            "_commit": _template_commit(),
            "_src_path": str(TEMPLATE_DIR),
            **answers,
        },
        "_copier_operation": "copy",
        "now": lambda: dt.datetime.now(dt.UTC),
    }

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    env.filters["to_nice_yaml"] = _to_nice_yaml

    for root, dirs, files in os.walk(TEMPLATE_DIR):
        rel_root = Path(root).relative_to(TEMPLATE_DIR)
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        if rel_root == Path("."):
            dirs[:] = [
                d
                for d in dirs
                if d not in EXCLUDED_TOP
                and (not d.startswith(".") or d in HIDDEN_DIRS)
            ]

        for fname in files:
            if rel_root == Path(".") and fname in EXCLUDED_FILES:
                continue
            if fname in EXCLUDED_NAMES or any(
                fnmatch.fnmatch(fname, g) for g in EXCLUDED_GLOBS
            ):
                continue

            rel_path_str = str(rel_root / fname)
            # Os nomes de arquivo também são templates ({{ package_slug }},
            # {{ _copier_conf.answers_file }}).
            rendered_rel = env.from_string(rel_path_str).render(**context)
            if rendered_rel.endswith(".jinja"):
                dest_file = target_dir / rendered_rel[: -len(".jinja")]
                content = env.get_template(rel_path_str.replace("\\", "/")).render(
                    **context
                )
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(content, encoding="utf-8")
            else:
                dest_file = target_dir / rendered_rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(root) / fname, dest_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render fetcher-template")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--description")
    parser.add_argument("--domain")
    parser.add_argument("--protocol", default="http")
    parser.add_argument("--orgao", default="Órgão responsável pelos dados")
    parser.add_argument("--homepage", default="https://www.gov.br/")
    parser.add_argument("--cadencia", default="monthly")
    parser.add_argument("--dominio", default="")
    args = parser.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    render_template(
        dest,
        source_id=args.source_id,
        source_name=args.source_name,
        description=args.description,
        domain=args.domain,
        protocol=args.protocol,
        orgao=args.orgao,
        homepage=args.homepage,
        cadencia=args.cadencia,
        dominio=args.dominio,
    )
    print(f"Rendered template for {args.source_id} to {dest}")


if __name__ == "__main__":
    main()
