#!/usr/bin/env python3
"""Offline template renderer for fetcher-template.

Renders copier template files using jinja2 directly, without needing external network
or the copier CLI binary, and generates .copier-answers.yml.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import jinja2

TEMPLATE_DIR = Path(__file__).resolve().parent


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

    context = {
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
        "now_date": dt.date.today().isoformat(),
        "now": lambda _tz, fmt: dt.date.today().strftime(fmt),
    }

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )

    # 1. Write .copier-answers.yml
    answers = [
        f"_commit: v0.1.0",
        f"_src_path: {TEMPLATE_DIR}",
        f"author_email: {author_email}",
        f"author_name: {author_name}",
        f"cadencia: {cadencia}",
        f"description: {description}",
        f"domain: {domain}",
        f"dominio: '{dominio}'",
        f"has_lake: {str(has_lake).lower()}",
        f"homepage: {homepage}",
        f"licenca: {licenca}",
        f"orgao: {orgao}",
        f"package_name: {package_name}",
        f"package_slug: {package_slug}",
        f"protocol: {protocol}",
        f"source_id: {source_id}",
        f"source_name: {source_name}",
        "",
    ]
    (target_dir / ".copier-answers.yml").write_text("\n".join(answers), encoding="utf-8")

    # 2. Iterate template files
    for root, _dirs, files in os.walk(TEMPLATE_DIR):
        rel_root = Path(root).relative_to(TEMPLATE_DIR)
        if any(part.startswith(".") for part in rel_root.parts if part != ".github"):
            continue
        if rel_root.parts and rel_root.parts[0] in ("tests_template", "__pycache__"):
            continue
        if "render.py" in files and rel_root == Path("."):
            pass

        for fname in files:
            if fname in ("render.py", "copier.yaml", "copier.yml"):
                continue

            src_file = Path(root) / fname
            rel_path_str = str(rel_root / fname)

            # Resolve template in path
            rendered_rel_path_str = rel_path_str.replace("{{ package_slug }}", package_slug)
            if rendered_rel_path_str.endswith(".jinja"):
                dest_rel_path = Path(rendered_rel_path_str[:-6])
                template = env.get_template(rel_path_str)
                content = template.render(**context)
                dest_file = target_dir / dest_rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(content, encoding="utf-8")
            else:
                dest_file = target_dir / Path(rendered_rel_path_str)
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)


import os
import shutil


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
