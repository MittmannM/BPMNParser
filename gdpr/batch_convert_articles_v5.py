from __future__ import annotations

import json
from pathlib import Path

from bpmn_quality import validate_bpmn_file
from generator_v5_pools_impl import generate_bpmn_master
from parser_v5_impl import extract_gdpr_structural


MANUAL_OVERRIDES = {
    "art_33": "GDPR_art_33_reviewed.bpmn",
}


def _article_token(article_path: Path) -> str:
    return article_path.stem.lower()


def _output_name(article_token: str) -> str:
    match = article_token.replace("art_", "")
    return f"GDPR_art_{match}.bpmn"


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    article_dir = repo_root / "artikel"
    output_dir = repo_root / "bpmn"
    output_dir.mkdir(parents=True, exist_ok=True)

    article_files = sorted(article_dir.glob("art_*.xml"))
    report: dict[str, object] = {
        "source_dir": str(article_dir),
        "output_dir": str(output_dir),
        "total_articles": len(article_files),
        "generated": [],
        "manual_overrides": [],
        "skipped": [],
    }

    source_xml = str(repo_root / "rioKB_GDPR.xml")

    for article_file in article_files:
        article = _article_token(article_file)
        output_file = output_dir / _output_name(article)

        if article in MANUAL_OVERRIDES:
            manual_file = output_dir / MANUAL_OVERRIDES[article]
            if manual_file.exists():
                quality = validate_bpmn_file(manual_file).to_dict()
                report["manual_overrides"].append(
                    {
                        "article": article,
                        "path": str(manual_file),
                        "quality": quality,
                    }
                )
                continue

        tasks = extract_gdpr_structural(source_xml, target_article=article)
        if not tasks:
            report["skipped"].append(
                {
                    "article": article,
                    "reason": "no_tasks_extracted",
                }
            )
            continue

        generate_bpmn_master(tasks, str(output_file))
        quality = validate_bpmn_file(output_file).to_dict()
        report["generated"].append(
            {
                "article": article,
                "task_count": len(tasks),
                "path": str(output_file),
                "quality": quality,
            }
        )

    report_path = output_dir / "conversion_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Konvertierung abgeschlossen. Report: {report_path}")
    print(
        f"Generiert: {len(report['generated'])}, "
        f"manuelle Overrides: {len(report['manual_overrides'])}, "
        f"übersprungen: {len(report['skipped'])}"
    )


if __name__ == "__main__":
    main()
