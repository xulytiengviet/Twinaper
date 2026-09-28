#!/usr/bin/env python3
"""Twinaper: real OpenAlex evidence -> optional 4-agent manuscript draft.

No autonomous original discoveries are claimed. Experimental results are
included only if an explicitly supplied dataset was processed successfully.
Uses Python standard library unless --experiment-csv is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DOMAINS = {
    "gis": "geographic information systems spatial analysis",
    "geography": "environmental geography Earth sciences",
    "webgis": "web geographic information systems OGC",
    "geoai": "geospatial artificial intelligence deep learning",
    "remote-sensing": "satellite remote sensing UAV",
    "spatial-ml": "spatial machine learning geostatistics",
    "hydroclimate": "hydrology flood forecasting climate",
    "urban": "urban planning spatial accessibility transport",
}
OPENALEX_URL = "https://api.openalex.org/works"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_json(url: str, *, timeout: int = 40) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Twinaper/0.1 (https://github.com/xulytiengviet/Twinaper)", "Accept": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 502, 503} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("OpenAlex HTTP " + str(exc.code)) from exc
        except urllib.error.URLError as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("OpenAlex unavailable: " + str(exc.reason)) from exc
    raise RuntimeError("OpenAlex request failed")


def abstract_text(inverted: dict | None) -> str:
    if not isinstance(inverted, dict):
        return ""
    positions = {}
    for word, indices in inverted.items():
        if not isinstance(indices, list):
            continue
        for index in indices:
            if isinstance(index, int) and 0 <= index < 6500:
                positions[index] = word
    return " ".join(positions[k] for k in sorted(positions))


def clean_https(value: str | None, host: str) -> str:
    if not isinstance(value, str):
        return ""
    parsed = urllib.parse.urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname == host else ""


def normalize(work: dict) -> dict:
    return {
        "id": clean_https(work.get("id"), "openalex.org"),
        "title": str(work.get("title") or "Untitled"),
        "year": work.get("publication_year") or "n.d.",
        "authors": [
            a.get("author", {}).get("display_name")
            for a in work.get("authorships", [])
            if isinstance(a, dict) and a.get("author", {}).get("display_name")
        ][:8],
        "doi": clean_https(work.get("doi"), "doi.org"),
        "abstract": abstract_text(work.get("abstract_inverted_index"))[:1700],
        "cited_by_count": int(work.get("cited_by_count") or 0),
    }


def find_literature(topic: str, domain: str, limit: int) -> tuple[list[dict], bool]:
    fallback_used = False
    for query in [topic[:115], DOMAINS[domain]]:
        params = {
            "search": query, "per-page": str(limit),
            "filter": "has_abstract:true,from_publication_date:2018-01-01",
            "select": "id,doi,title,publication_year,authorships,abstract_inverted_index,cited_by_count",
        }
        payload = get_json(OPENALEX_URL + "?" + urllib.parse.urlencode(params))
        papers = [normalize(w) for w in payload.get("results", [])]
        papers = list({p["id"]: p for p in papers if p["id"] and p["title"]}.values())
        if papers:
            return papers, fallback_used
        fallback_used = True
    raise RuntimeError("No matching OpenAlex works. Try an English-language or narrower topic.")


def bibliography(papers: list[dict]) -> str:
    return "\n\n".join(
        "[" + str(i) + "] " + (", ".join(p["authors"]) or "See OpenAlex")
        + " (" + str(p["year"]) + "). " + p["title"] + ". " + (p["doi"] or p["id"])
        for i, p in enumerate(papers, 1)
    )


def base_draft(topic: str, domain: str, papers: list[dict], experiment: dict | None = None) -> str:
    results = (
        "A user-supplied dataset was processed by Twinaper's baseline script. "
        "These are preliminary computational measurements, not independently reproduced:\n\n"
        + json.dumps(experiment.get("summary", {}), ensure_ascii=False, indent=2)
        if experiment else "**Chưa thực hiện thí nghiệm; chưa có kết quả khoa học để báo cáo.**"
    )
    return (
        "# " + topic + "\n\n"
        "> **BẢN NHÁP / NOT PEER REVIEWED / AI-ASSISTED**\n\n"
        "**Lĩnh vực:** " + domain + "  \n**Ngày:** " + utc_now()[:10] + "\n\n"
        "## Câu hỏi nghiên cứu\n\n" + topic + "\n\n"
        "## Tài liệu và khoảng trống\n\n"
        "Đã tìm thấy " + str(len(papers)) + " nguồn trên OpenAlex. Cần đọc toàn văn và "
        "đánh giá mức độ liên quan trước khi khẳng định tính mới.\n\n"
        "## Giả thuyết và thiết kế nghiên cứu\n\n"
        "- [ ] Xác định giả thuyết có thể bác bỏ.\n"
        "- [ ] Đánh giá spatial/temporal leakage.\n"
        "- [ ] Chọn dữ liệu có giấy phép rõ ràng và các baseline phù hợp.\n"
        "- [ ] Thực hiện ablation, kiểm định nhiều vùng, đo độ bất định.\n\n"
        "## Kết quả\n\n" + results + "\n\n"
        "## Tài liệu tham khảo ứng viên\n\n" + bibliography(papers) + "\n\n"
        "## Công bố sử dụng AI\n\n"
        "Twinaper hỗ trợ truy xuất metadata và lập bản nháp. Tác giả con người "
        "phải xác minh toàn văn, mã nguồn, kết quả và chịu trách nhiệm công bố.\n"
    )


def call_model(key: str, model: str, role: str, prompt: str, max_tokens: int) -> tuple[str, dict]:
    data = json.dumps({
        "model": model, "temperature": 0.3, "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": (
                "Bạn là " + role + " thuộc Twinaper. Chỉ dùng tài liệu được cung cấp. "
                "Không bịa DOI, tài liệu, kết quả, dữ liệu thực nghiệm, benchmark, xác nhận "
                "tính mới, hay tuyên bố được chấp nhận xuất bản. Dẫn nguồn bằng [R1], [R2]... "
                "Không được coi phản biện AI là peer review độc lập. "
                "Viết tiếng Việt học thuật; nếu không đủ bằng chứng hãy nêu rõ."
            )},
            {"role": "user", "content": prompt},
        ]
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_URL, data=data, method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "X-Title": "Twinaper GeoAI Research",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        message = exc.read(900).decode("utf-8", "replace")
        raise RuntimeError("OpenRouter HTTP " + str(exc.code) + ": " + message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("OpenRouter unavailable: " + str(exc.reason)) from exc
    content = (result.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Model returned no usable text.")
    return content.strip(), result.get("usage") or {}


def check_ai_citations(text: str, papers: list[dict]) -> list[str]:
    """Flag unsupported reference tags and DOI patterns; no false verified claim."""
    allowed = {"R" + str(i) for i in range(1, len(papers) + 1)}
    unknown = sorted(set(re.findall(r"\[(R\d+)\]", text)) - allowed)
    doi_allowlist = {
        urllib.parse.unquote(p["doi"]).removeprefix("https://doi.org/").lower().rstrip(".,;")
        for p in papers if p["doi"]
    }
    candidates = {
        match.lower().rstrip(".,;")
        for match in re.findall(r"10\.\d{4,9}/[^\s)\]<>\"']+", text)
    }
    return ["Unsupported citation tag: " + item for item in unknown] + [
        "Unsupported DOI: " + item for item in sorted(candidates - doi_allowlist)
    ]


def ai_workflow(topic: str, domain: str, papers: list[dict], key: str, model: str,
                experiment: dict | None) -> tuple[str, list[dict]]:
    refs = [
        {"ref": "R" + str(i), "title": p["title"], "year": p["year"],
         "authors": p["authors"], "doi": p["doi"], "openalex": p["id"],
         "abstract": p["abstract"][:750]}
        for i, p in enumerate(papers, 1)
    ]
    evidence = json.dumps(refs, ensure_ascii=False)
    log = []

    def run(role: str, prompt: str, tokens: int) -> str:
        print("AI agent:", role, file=sys.stderr)
        content, usage = call_model(key, model, role, prompt, tokens)
        issues = check_ai_citations(content, papers)
        log.append({"role": role, "usage": usage, "citation_warnings": issues})
        if issues:
            raise RuntimeError(role + " produced unlisted citations/DOIs: " + "; ".join(issues))
        return content

    h = run("Hypothesis Agent", "Đề tài: " + topic + "\nLĩnh vực: " + domain
            + "\nNguồn metadata/abstract:\n" + evidence
            + "\nĐề xuất khoảng trống, giả thuyết có thể bác bỏ, hạn chế và trích dẫn [R#].", 1400)
    m = run("Methods Designer", "Đề tài: " + topic + "\nGiả thuyết:\n" + h
            + "\nNguồn:\n" + evidence
            + "\nThiết kế bộ dữ liệu, baseline, spatial CV, ablation và cách kiểm chứng. "
            "Không giả vờ đã thực hiện thí nghiệm.", 1700)
    r = run("Skeptical Review Agent", "Đề tài: " + topic + "\nGiả thuyết:\n" + h
            + "\nPhương pháp:\n" + m
            + "\nĐóng vai phản biện mô phỏng, chỉ ra hạn chế và yêu cầu kiểm chứng. "
            "Phản biện này không có giá trị chấp nhận hội nghị.", 1000)
    verified_results = json.dumps(experiment, ensure_ascii=False) if experiment else "CHƯA CHẠY THÍ NGHIỆM"
    draft = run("Scientific Writer", "Tạo bản thảo bài báo khoa học bằng Markdown về: " + topic
                + "\nGiả thuyết:\n" + h + "\nPhương pháp:\n" + m
                + "\nPhản biện mô phỏng:\n" + r
                + "\nKết quả thực thi (nếu có, không được tạo thêm số liệu):\n" + verified_results
                + "\nNguồn tham khảo DUY NHẤT:\n" + evidence
                + "\nBao gồm tóm tắt, tổng quan, phương pháp, kết quả thật nếu có, giới hạn, "
                "AI disclosure; nếu chưa chạy hãy ghi Results: CHƯA CÓ THỰC NGHIỆM. "
                "Không tự thêm reference.", 2800)
    paper = ("# " + topic + "\n\n> BẢN THẢO AI HỖ TRỢ · CHƯA PHẢN BIỆN\n\n"
             + draft + "\n\n## Danh mục tài liệu từ OpenAlex\n\n" + bibliography(papers)
             + "\n\n## Trách nhiệm tác giả\n\nCần xác nhận toàn văn, "
             "chạy lại tất cả thí nghiệm, kiểm định kết quả và công bố sử dụng AI.\n")
    return paper, log


def optional_experiment(args: argparse.Namespace, output: Path) -> dict | None:
    if not args.experiment_csv:
        return None
    if not args.features or not args.target:
        raise ValueError("--experiment-csv requires --target and --features")
    cmd = [
        sys.executable, str(Path(__file__).parent / "experiments" / "spatial_benchmark.py"),
        "--csv", args.experiment_csv, "--target", args.target,
        "--features", args.features, "--lat", args.lat, "--lon", args.lon,
        "--block-size", str(args.block_size), "--folds", str(args.folds),
        "--seed", str(args.seed), "--output", str(output / "experiment.json"),
    ]
    print("Running measured spatial benchmark on user-provided data...", file=sys.stderr)
    subprocess.run(cmd, check=True)
    return json.loads((output / "experiment.json").read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--topic", required=True, help="Research question, preferably in English for OpenAlex.")
    p.add_argument("--domain", choices=DOMAINS, default="geoai")
    p.add_argument("--max-papers", type=int, default=10)
    p.add_argument("--model", default="openai/gpt-4.1-mini", help="OpenRouter model ID")
    p.add_argument("--output", default="outputs/latest")
    p.add_argument("--no-ai", action="store_true", help="Create evidence and outline without a model call.")
    p.add_argument("--experiment-csv", help="Optional numeric regression CSV supplied by researcher.")
    p.add_argument("--target", help="CSV numeric target field.")
    p.add_argument("--features", help="Comma-separated numeric predictor fields.")
    p.add_argument("--lat", default="lat")
    p.add_argument("--lon", default="lon")
    p.add_argument("--block-size", type=float, default=0.25)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if len(args.topic.strip()) < 12 or not 3 <= args.max_papers <= 20:
        p.error("Topic needs 12+ characters, and --max-papers must be between 3 and 20.")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    papers, fallback_used = find_literature(args.topic.strip(), args.domain, args.max_papers)
    evidence = {
        "topic": args.topic.strip(), "domain": args.domain, "retrieved_at": utc_now(),
        "provider": "OpenAlex", "fallback_to_domain_search": fallback_used,
        "papers": papers,
    }
    source_bytes = json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode("utf-8")
    (output / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    experiment = optional_experiment(args, output)
    manuscript = base_draft(args.topic, args.domain, papers, experiment)
    agent_log = []
    warnings = []
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key and not args.no_ai:
        try:
            manuscript, agent_log = ai_workflow(args.topic, args.domain, papers, key, args.model, experiment)
        except Exception as exc:
            warnings.append("AI stage failed; only the evidence-backed outline was kept: " + str(exc))
            print(warnings[-1], file=sys.stderr)
    audit = {
        "status": "draft-not-peer-reviewed", "generated_at": utc_now(),
        "evidence_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "openalex_source_count": len(papers),
        "doi_metadata_present": sum(bool(p["doi"]) for p in papers),
        "independent_doi_resolution_checked": False,
        "full_text_checked": False,
        "topic_fallback_to_domain": fallback_used,
        "ai_used": bool(agent_log) and len(agent_log) == 4 and not warnings,
        "ai_peer_review_is_external_peer_review": False,
        "experiments_executed": bool(experiment),
        "experiment_is_independently_reproduced": False,
        "human_review_required": True,
        "warnings": warnings,
    }
    (output / "paper.md").write_text(manuscript, encoding="utf-8")
    (output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "agent_log.json").write_text(json.dumps(agent_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Created:", output, "sources:", len(papers), "AI completed:", audit["ai_used"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
