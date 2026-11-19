"""Roda o benchmark do agente e escreve o placar.

    cd backend
    python -m evals.run --engine local                      # regras locais, sem rede
    python -m evals.run --engine auto --repeat 3 --sleep 4  # cadeia completa (LLM se houver OPENROUTER_API_KEY)
    python -m evals.run --cases sla,why-* --out placar.md --json placar.json

Chama `app.agent.service.chat` direto, sem HTTP, com um `Repository` montado das settings.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from app.agent.service import chat
from app.config import Settings, get_settings
from app.filters import Filters
from app.repository import Repository
from app.schemas import ChatRequest
from evals.cases import CASES, Case, select
from evals.grader import CaseNotApplicable, Grade, error_grade, grade

DEFAULT_LOCAL_LATENCY_S = 5.0


@dataclass
class RunResult:
    case_id: str
    category: str
    question: str
    filters: dict
    run: int
    mode: str | None
    model: str | None
    latency_s: float | None
    score: float
    passed: bool
    checks: list[dict]
    answer: str = ""
    action: str = ""
    error: str | None = None
    fallback_reason: str | None = None


@dataclass
class SuiteResult:
    engine: str
    data_path: str
    model: str | None
    llm_enabled: bool
    started_at: str
    repeat: int
    results: list[RunResult] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------- agregados
    def summary(self) -> dict:
        rs = self.results
        n = len(rs)
        latencies = sorted(r.latency_s for r in rs if r.latency_s is not None)
        modes = Counter(r.mode or "erro" for r in rs)
        by_cat: dict[str, list[RunResult]] = defaultdict(list)
        for r in rs:
            by_cat[r.category].append(r)
        by_mode: dict[str, list[RunResult]] = defaultdict(list)
        for r in rs:
            by_mode[r.mode or "erro"].append(r)
        fails = Counter(c["name"] for r in rs for c in r.checks if c["score"] < 1 - 1e-9)
        llm_runs = n if self.llm_enabled and self.engine == "auto" else 0
        return {
            "runs": n,
            "cases": len({r.case_id for r in rs}),
            "skipped": len(self.skipped),
            "pass_rate": (sum(r.passed for r in rs) / n) if n else 0.0,
            "mean_score": (statistics.fmean(r.score for r in rs)) if n else 0.0,
            "by_category": {
                cat: {"runs": len(v), "pass_rate": sum(r.passed for r in v) / len(v), "mean_score": statistics.fmean(r.score for r in v)}
                for cat, v in sorted(by_cat.items())
            },
            "by_mode": {
                mode: {"runs": len(v), "pass_rate": sum(r.passed for r in v) / len(v), "mean_score": statistics.fmean(r.score for r in v)}
                for mode, v in sorted(by_mode.items())
            },
            "fallback_local_rate": (modes.get("local", 0) / llm_runs) if llm_runs else None,
            "fallback_context_rate": (modes.get("llm-context", 0) / llm_runs) if llm_runs else None,
            "fallback_reasons": dict(Counter(r.fallback_reason for r in rs if r.fallback_reason)),
            "latency_p50_s": _percentile(latencies, 0.50),
            "latency_p95_s": _percentile(latencies, 0.95),
            "failed_checks": dict(fails.most_common()),
        }


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return values[index]


def _filters_dict(f: Filters) -> dict:
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in f.model_dump().items() if v not in (None, [])}


# ----------------------------------------------------------------- execução
def run_case(
    case: Case,
    repo: Repository,
    settings: Settings,
    engine: str,
    run: int = 1,
    max_latency_s: float | None = None,
) -> RunResult:
    """Uma execução de um caso. CaseNotApplicable sobe para quem chamou (o caso sai do placar)."""
    f, question, exp = case.build(repo)
    use_llm = engine == "auto"
    req = ChatRequest(question=question, filters=f, engine="auto" if use_llm else "local")
    started = time.perf_counter()
    try:
        resp = chat(req, repo, settings, use_llm=use_llm)
    except Exception as exc:  # noqa: BLE001 — exceção do agente vira caso reprovado, não derruba a suíte
        g: Grade = error_grade(f"{type(exc).__name__}: {exc}")
        return RunResult(
            case.id, case.category, question, _filters_dict(f), run, None, None,
            time.perf_counter() - started, g.score, g.passed, [asdict(c) for c in g.checks], error=str(exc),
        )
    latency = time.perf_counter() - started
    g = grade(resp, exp, repo, f, latency_s=latency, default_max_latency_s=max_latency_s)
    return RunResult(
        case_id=case.id,
        category=case.category,
        question=question,
        filters=_filters_dict(f),
        run=run,
        mode=resp.mode,
        model=resp.model,
        latency_s=latency,
        score=g.score,
        passed=g.passed,
        checks=[asdict(c) for c in g.checks],
        answer=resp.answer,
        action=resp.action,
        fallback_reason=resp.fallback_reason,
    )


def run_suite(
    repo: Repository,
    settings: Settings,
    cases: list[Case],
    engine: str = "local",
    repeat: int = 1,
    sleep_s: float = 0.0,
    max_latency_s: float | None = None,
    data_path: str = "",
    progress: bool = False,
) -> SuiteResult:
    suite = SuiteResult(
        engine=engine,
        data_path=data_path,
        model=settings.openrouter_model if (engine == "auto" and settings.llm_enabled) else None,
        llm_enabled=settings.llm_enabled,
        started_at=datetime.now().isoformat(timespec="seconds"),
        repeat=repeat,
    )
    calls_llm = engine == "auto" and settings.llm_enabled
    first = True
    for case in cases:
        for run in range(1, repeat + 1):
            if calls_llm and sleep_s > 0 and not first:
                time.sleep(sleep_s)
            first = False
            try:
                result = run_case(case, repo, settings, engine, run=run, max_latency_s=max_latency_s)
            except CaseNotApplicable as exc:
                suite.skipped.append({"case_id": case.id, "category": case.category, "reason": str(exc)})
                break
            except Exception as exc:  # noqa: BLE001 — erro ao montar a verdade do caso também reprova
                g = error_grade(f"expectativa: {type(exc).__name__}: {exc}")
                result = RunResult(case.id, case.category, "", {}, run, None, None, None, g.score, g.passed,
                                   [asdict(c) for c in g.checks], error=str(exc))
            suite.results.append(result)
            if progress:
                mark = "ok " if result.passed else "FAIL"
                print(f"  {mark} {result.case_id:<18} {result.score:4.2f} {result.mode or '-':<11} "
                      f"{(result.latency_s or 0):5.2f}s", flush=True)
            if not calls_llm:
                # Sem LLM a resposta é determinística: repetir não acrescenta nada.
                break
    return suite


# ----------------------------------------------------------------- relatório
def _p(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%".replace(".", ",")


def _s(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}".replace(".", ",")


def _cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def render_markdown(suite: SuiteResult) -> str:
    s = suite.summary()
    lines = [
        "# Placar do agente de insights",
        "",
        f"- Motor: `{suite.engine}`" + (f" · modelo `{suite.model}`" if suite.model else "")
        + ("" if suite.engine == "local" or suite.llm_enabled else " · **sem OPENROUTER_API_KEY: cadeia caiu nas regras**"),
        f"- Dados: `{suite.data_path}`",
        f"- Início: {suite.started_at} · repetições: {suite.repeat}",
        "",
        "## Resumo",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Casos | {s['cases']} ({s['runs']} execuções, {s['skipped']} fora do placar) |",
        f"| Taxa de aprovação | **{_p(s['pass_rate'])}** |",
        f"| Nota média | {_s(s['mean_score'])} |",
        f"| Latência p50 / p95 | {_s(s['latency_p50_s'])}s / {_s(s['latency_p95_s'])}s |",
    ]
    if s["fallback_local_rate"] is not None:
        lines += [
            f"| Caiu nas regras locais | {_p(s['fallback_local_rate'])} |",
            f"| Caiu no LLM com contexto | {_p(s['fallback_context_rate'])} |",
        ]
        reasons = s.get("fallback_reasons") or {}
        if reasons:
            names = {"quota": "cota", "busy": "provedor congestionado", "timeout": "prazo", "error": "erro"}
            text = " · ".join(f"{names.get(k, k)} {v}" for k, v in sorted(reasons.items()))
            lines.append(f"| Motivo do fallback | {text} |")
        if reasons.get("quota"):
            lines += [
                "",
                (
                    f"> **Atenção:** {reasons['quota']} execuções caíram por cota esgotada do modelo. "
                    "Essas notas medem as regras locais, não o LLM."
                ),
            ]
    lines += ["", "## Por categoria", "", "| Categoria | Execuções | Aprovação | Nota média |", "|---|---|---|---|"]
    for cat, v in s["by_category"].items():
        lines.append(f"| {cat} | {v['runs']} | {_p(v['pass_rate'])} | {_s(v['mean_score'])} |")
    lines += ["", "## Por modo de resposta", "", "| Modo | Execuções | Aprovação | Nota média |", "|---|---|---|---|"]
    for mode, v in s["by_mode"].items():
        lines.append(f"| {mode} | {v['runs']} | {_p(v['pass_rate'])} | {_s(v['mean_score'])} |")
    lines += ["", "## Verificações que mais falham", "", "| Verificação | Falhas |", "|---|---|"]
    for name, n in s["failed_checks"].items():
        lines.append(f"| {name} | {n} |")
    lines += ["", "## Casos", "", "| Caso | Categoria | Modo | Nota | Passou | Latência |", "|---|---|---|---|---|---|"]
    for r in suite.results:
        lines.append(
            f"| {r.case_id}" + (f" #{r.run}" if suite.repeat > 1 else "")
            + f" | {r.category} | {r.mode or 'erro'} | {_s(r.score)} | {'sim' if r.passed else '**não**'} | {_s(r.latency_s)}s |"
        )
    failed = [r for r in suite.results if r.score < 1 - 1e-9]
    if failed:
        lines += ["", "## Falhas e motivos", ""]
        for r in failed:
            lines += [f"### {r.case_id}" + (f" #{r.run}" if suite.repeat > 1 else "") + f" ({r.category})", ""]
            lines.append(f"- Pergunta: “{_cell(r.question)}”" + (f" · recorte `{json.dumps(r.filters, ensure_ascii=False)}`" if r.filters else ""))
            for c in r.checks:
                if c["score"] < 1 - 1e-9:
                    tag = "aviso" if c["level"] == "warn" else "erro"
                    lines.append(f"- **{c['name']}** ({tag}, nota {_s(c['score'])}): {_cell(c['reason'])}")
            if r.action:
                lines.append(f"- Ação devolvida: {_cell(r.action)[:240]}")
            lines.append("")
    if suite.skipped:
        lines += ["", "## Fora do placar (dados não sustentam o caso)", ""]
        lines += [f"- {sk['case_id']} ({sk['category']}): {sk['reason']}" for sk in suite.skipped]
    return "\n".join(lines).rstrip() + "\n"


def print_summary(suite: SuiteResult) -> None:
    s = suite.summary()
    print(f"\nMotor {suite.engine} · {s['cases']} casos · {s['runs']} execuções · {s['skipped']} fora do placar")
    print(f"Aprovação {_p(s['pass_rate'])} · nota média {_s(s['mean_score'])} · "
          f"latência p50 {_s(s['latency_p50_s'])}s p95 {_s(s['latency_p95_s'])}s")
    if s["fallback_local_rate"] is not None:
        print(f"Fallback: regras {_p(s['fallback_local_rate'])} · contexto {_p(s['fallback_context_rate'])}")
    for cat, v in s["by_category"].items():
        print(f"  {cat:<14} {_p(v['pass_rate']):>7}  nota {_s(v['mean_score'])}  ({v['runs']})")
    if s["failed_checks"]:
        print("Falhas por verificação: " + ", ".join(f"{k} {v}" for k, v in s["failed_checks"].items()))


# ----------------------------------------------------------------- CLI
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m evals.run", description="Benchmark do agente de insights.")
    p.add_argument("--engine", choices=("local", "auto"), default="local",
                   help="local = só regras; auto = cadeia completa (LLM se houver OPENROUTER_API_KEY)")
    p.add_argument("--data", type=Path, default=None, help="parquet de pedidos (padrão: settings.data_path)")
    p.add_argument("--cases", default=None, help="ids ou categorias separados por vírgula; 'why-*' casa prefixo")
    p.add_argument("--all-cases", action="store_true", help="ignora a marcação engines e roda todos os casos")
    p.add_argument("--out", type=Path, default=None, help="placar em markdown")
    p.add_argument("--json", type=Path, default=None, help="resultado completo em JSON")
    p.add_argument("--log", type=Path, default=None, help="grava log INFO do agente (tokens, finish_reason, fallbacks)")
    p.add_argument("--repeat", type=int, default=1, help="repetições por caso (só com LLM)")
    p.add_argument("--sleep", type=float, default=0.0, help="segundos entre chamadas ao LLM (cota gratuita)")
    p.add_argument("--max-latency", type=float, default=None,
                   help=f"teto de latência por caso (padrão: {DEFAULT_LOCAL_LATENCY_S:.0f}s local, chat_budget_s + 5 no auto)")
    p.add_argument("--quiet", action="store_true", help="sem uma linha por caso")
    return p


def main(argv: list[str] | None = None) -> SuiteResult:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    settings = get_settings()
    data_path = args.data or settings.data_path
    repo = Repository(Path(data_path), settings.sla_food_min, settings.sla_good_min)

    if args.engine == "auto" and not settings.llm_enabled:
        print("Aviso: OPENROUTER_API_KEY ausente; a cadeia auto vai responder com as regras locais.", file=sys.stderr)
    tag = None if args.all_cases else ("llm" if args.engine == "auto" and settings.llm_enabled else "local")
    cases = select(CASES, args.cases, engine_tag=tag)
    if not cases:
        raise SystemExit(f"Nenhum caso casa com --cases {args.cases!r}")

    max_latency = args.max_latency
    if max_latency is None:
        max_latency = settings.chat_budget_s + 5 if args.engine == "auto" and settings.llm_enabled else DEFAULT_LOCAL_LATENCY_S

    print(f"Rodando {len(cases)} casos · motor {args.engine} · dados {data_path}", flush=True)
    agent_logger = logging.getLogger("app.agent")
    prev_level = agent_logger.level
    log_handler: logging.Handler | None = None
    if args.log is not None:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        log_handler = logging.FileHandler(args.log, mode="w", encoding="utf-8")
        log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        agent_logger.setLevel(logging.INFO)
        agent_logger.addHandler(log_handler)
    try:
        suite = run_suite(
            repo, settings, cases,
            engine=args.engine,
            repeat=max(1, args.repeat),
            sleep_s=max(0.0, args.sleep),
            max_latency_s=max_latency,
            data_path=str(data_path),
            progress=not args.quiet,
        )
    finally:
        if log_handler is not None:
            log_handler.flush()
            agent_logger.removeHandler(log_handler)
            log_handler.close()
            agent_logger.setLevel(prev_level)
    print_summary(suite)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_markdown(suite), encoding="utf-8")
        print(f"Placar: {args.out}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": suite.summary(), **asdict(suite)}
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"JSON: {args.json}")
    return suite


if __name__ == "__main__":
    main()
