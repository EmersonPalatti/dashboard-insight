"""Testes do agente local: ações operacionais, sem nomes fixos e tratamento de amostra pequena."""

from __future__ import annotations

import ast
import re
from datetime import date
from pathlib import Path

import duckdb
import pytest

from app import fmt
from app.agent import local, local_answers, local_intent
from app.agent.reading import labels_for
from app.alerts import BROKEN_CANCEL, CANCEL_WARN, HUB_MIN, SLA_WARN, STORE_MIN, STUCK_HUB_MAX, detect_alerts
from app.analytics import explain_change
from app.filters import Filters

# Nomes que jamais podem estar hardcoded no código do agente
DISALLOWED_STATIC_NAMES = [
    "Hub Centro",
    "Hub Lento",
    "Hub Preso",
    "Hub Goods",
    "Loja Quebrada",
    "São Paulo",
    "Curitiba",
    "Rio de Janeiro",
    "Porto Alegre",
]

# Cada frase abaixo só aparece na resposta daquele handler.
QUESTIONS_AND_MARKERS = [
    ("quais os alertas e problemas no recorte?", "alertas no recorte ("),
    ("onde esta o gargalo das etapas de entrega?", "Mediana por etapa"),
    ("quais lojas cancelam mais pedidos?", "Cancelamento no recorte"),
    ("quanto estamos gastando de frete e subsidio?", "Frete médio cobrado"),
    ("como esta o pico do jantar?", "Horários de maior volume"),
    ("como esta o sla de entrega no prazo?", "SLA do recorte"),
    ("qual o volume por canal marketplace ou proprio?", "Canais por volume"),
    ("qual o tempo de transito por modal moto e bike?", "Entregas por modal"),
    ("quais as lojas do recorte?", "Lojas com maior GMV"),
    ("quais os hubs com maior volume na praca?", "Hubs por volume"),
    ("qual o gmv e faturamento da operacao?", "entregas · ticket"),
    ("me de um briefing com a visao geral", "**Briefing do recorte**"),
]

# Substring antigo mandava estas frases para o handler errado.
FALSE_POSITIVES = [
    ("qual a situação da operação?", "**Briefing do recorte**", "alertas no recorte ("),
    ("como está a operação hoje?", "**Briefing do recorte**", "alertas no recorte ("),
    ("qual a duração média?", "**Briefing do recorte**", "alertas no recorte ("),
    ("preciso de mais informação", "**Briefing do recorte**", "alertas no recorte ("),
    ("quero uma avaliação do recorte", "**Briefing do recorte**", "alertas no recorte ("),
    ("como melhorar o resultado?", "**Briefing do recorte**", "Horários de maior volume"),
    ("cadê o motorista?", "**Briefing do recorte**", "Entregas por modal"),
    ("tempo de trânsito por modal", "Entregas por modal", "Mediana por etapa"),
]

MISSED_QUESTIONS = [
    ("entrega atrasada", "SLA do recorte"),
    ("lentidão na entrega", "SLA do recorte"),
    ("quais os dias da semana mais fortes?", "Horários de maior volume"),
]

THIN_INTENTS = [
    ("resumo", "**Briefing do recorte**"),
    ("quais os hubs", "Hubs por volume"),
    ("pico do jantar", "Horários de maior volume"),
    ("subsídio de frete", "Frete médio cobrado"),
    ("volume por canal", "Canais por volume"),
    ("qual o modal", "Entregas por modal"),
    ("gmv e receita", "entregas · ticket"),
]


APP_DIR = Path(__file__).resolve().parent.parent / "app"
REAL_PARQUET = Path(__file__).resolve().parent.parent / "data" / "orders.parquet"


def _code_strings(path: Path) -> list[str]:
    """Literais de texto do código, sem docstrings (exemplo em docstring não é nome fixo) e sem comentários."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


def _data_names(repo) -> set[str]:
    """Nomes de hub, loja e cidade do fixture e, quando existe, do parquet real."""
    meta = repo.meta()
    names = {str(o["label"]) for key in ("hubs", "stores", "cities") for o in meta[key] if o["label"]}
    names |= set(DISALLOWED_STATIC_NAMES)
    if REAL_PARQUET.exists():
        con = duckdb.connect()
        try:
            for column in ("hub_name", "store_name", "city"):
                rows = con.execute(f"select distinct {column} from read_parquet(?) where {column} is not null",
                                   [str(REAL_PARQUET)]).fetchall()
                names |= {str(r[0]) for r in rows}
        finally:
            con.close()
    # Nome de 3 letras ou menos casaria com pedaço de palavra comum; o índice de entidades já ignora esses.
    return {n.strip() for n in names if len(n.strip()) >= 4}


def test_no_hardcoded_names_in_source(repo):
    """Regra 4: nenhum nome de hub, loja ou cidade dos dados fixado em literal do código de `app/`."""
    names = _data_names(repo)
    # Sensível a maiúsculas: "loja quebrada" (termo do glossário) e "sigo" (verbo) não são os nomes próprios.
    patterns = [(name, re.compile(rf"(?<!\w){re.escape(name)}(?!\w)")) for name in names]
    found = []
    for path in sorted(APP_DIR.rglob("*.py")):
        for text in _code_strings(path):
            found += [(path.relative_to(APP_DIR).as_posix(), name) for name, rx in patterns if rx.search(text)]
    assert not found, f"Nomes fixos no código: {found[:10]}"


def test_hardcoded_name_guard_sees_code_but_not_docstrings(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text('"""Exemplo: hub Hub Lento."""\n\ndef f():\n    """Hub Lento."""\n    return "líder do Hub Lento"\n',
                      encoding="utf-8")
    assert _code_strings(sample) == ["líder do Hub Lento"]


@pytest.mark.parametrize("question,marker", QUESTIONS_AND_MARKERS)
def test_every_handler_returns_its_own_phrase(repo, question, marker):
    """Cada intenção devolve a frase daquele handler e fecha com ação."""
    res = local.answer(question, repo, Filters())
    assert marker in res, f"Pergunta '{question}' não produziu '{marker}'."
    assert "**Ação:**" in res
    assert len(res.strip().splitlines()) >= 2


@pytest.mark.parametrize("question,expected,forbidden", FALSE_POSITIVES)
def test_ambiguous_words_do_not_steal_the_route(repo, question, expected, forbidden):
    res = local.answer(question, repo, Filters())
    assert expected in res
    assert forbidden not in res


@pytest.mark.parametrize("question,marker", MISSED_QUESTIONS)
def test_previously_missed_questions_hit_the_right_handler(repo, question, marker):
    assert marker in local.answer(question, repo, Filters())


def test_stages_single_hub(repo):
    """Testa _stages com apenas 1 hub no recorte."""
    f = Filters(hub=[2])
    res = local.answer("onde esta o gargalo do preparo e transito?", repo, f)
    assert "**Ação:**" in res
    assert "Hub Lento" in res  # veio dos dados do repo, não fixo no código


def test_low_sample_recorte(repo):
    """Recorte com amostra pequena (low_sample) deve orientar ampliação do período."""
    # Recorte estreito com pedidos medidos < 100
    f = Filters(start=date(2021, 1, 1), end=date(2021, 1, 1), hub=[1], store=[10])
    m = repo.metrics(f)
    assert m["orders"] > 0
    assert m["low_sample"] is True

    # Teste no SLA
    res_sla = local.answer("como esta o sla?", repo, f)
    assert "**Ação:**" in res_sla
    assert "amostra reduzida" in res_sla.lower()
    assert "ampliar o período" in res_sla[res_sla.rfind("**Ação:**"):]

    # Teste no Cancelamento
    res_cancel = local.answer("quais lojas cancelam mais?", repo, f)
    assert "**Ação:**" in res_cancel
    assert "amostra reduzida" in res_cancel.lower()
    assert "ampliar o período" in res_cancel[res_cancel.rfind("**Ação:**"):]


def test_unmatched_question_fallback_to_briefing(repo):
    """Pergunta não reconhecida cai no briefing, sugere perguntas e termina na ação."""
    res = local.answer("algo completamente aleatorio sem sentido", repo, Filters())  # "rota" agora é trânsito no glossário
    assert "**Briefing do recorte**" in res
    action_at = res.rfind("**Ação:**")
    assert action_at != -1
    assert "Tente perguntar:" in res[:action_at]
    assert "Tente perguntar:" not in res[action_at:]
    assert "\n" not in res[action_at:].rstrip()


def test_empty_recorte_ends_on_action(repo):
    res = local.answer("resumo", repo, Filters(city=["Nenhuma"]))
    assert "Nenhum pedido" in res
    assert res.rstrip().endswith("carregar dados da operação.")
    assert res.rfind("**Ação:**") > res.find("Nenhum pedido")


def test_briefing_without_alerts_names_the_busiest_hub(repo, monkeypatch):
    monkeypatch.setattr(local, "detect_alerts", lambda *_args, **_kwargs: [])
    top = repo.breakdown(Filters(), "hub", sort="orders", limit=1)[0]
    res = local.briefing(repo, Filters())
    action = res[res.rfind("**Ação:**"):]
    assert top["label"] in action
    assert "hub de maior volume" not in res


def test_channel_and_revenue_actions_use_real_metrics(repo):
    channels = local.answer("qual o volume por canal?", repo, Filters())
    assert "conversão" not in channels.lower() and "conversao" not in channels.lower()
    revenue = local.answer("qual o gmv?", repo, Filters())
    assert "campanhas de incentivo" not in revenue.lower()
    action = revenue[revenue.rfind("**Ação:**"):].lower()
    # No fixture o food cancela acima do teto: o ramo é o de perda de receita por cancelamento.
    assert "segmento food" in action and "conter perdas de receita por cancelamento" in action


@pytest.mark.parametrize("question,marker", THIN_INTENTS)
def test_thin_sample_widens_period_for_every_intent(repo, question, marker):
    f = Filters(start=date(2021, 1, 1), end=date(2021, 1, 1), hub=[1], store=[10])
    metrics = repo.metrics(f)
    assert metrics["orders"] > 0 and metrics["low_sample"] is True
    res = local.answer(question, repo, f)
    assert res.startswith("Atenção: amostra reduzida")
    assert marker in res
    action = res[res.rfind("**Ação:**"):]
    assert "ampliar o período" in action
    assert "acionar alguém hoje" in action
    assert "Loja 10" in action  # a entidade filtrada entra na ação (Regra 3: onde)
    assert "\n" not in action.rstrip()


def test_followup_reuses_the_previous_user_intent(repo):
    history = [
        {"role": "user", "content": "quais lojas cancelam mais?"},
        {"role": "assistant", "content": "já te respondi"},
    ]
    res = local.answer("e agora?", repo, Filters(), history=history)
    assert "Cancelamento no recorte" in res
    alone = local.answer("e agora?", repo, Filters())
    assert "**Briefing do recorte**" in alone
    assert "Cancelamento no recorte" not in alone


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("como estao as formas de pagamento?", "_payments"),
        ("quantos pedidos presos no fluxo existem?", "_stuck"),
        ("houve queda de volume na semana?", "_volume"),
        ("No ranking por forma de pagamento, quem está pior e o que fazer?", "_payments"),
        ('Sobre a comanda "Pedidos presos no fluxo": o que explica isso neste recorte e o que fazer hoje?', "_stuck"),
        ('Sobre a comanda "Queda de volume na última semana": o que explica isso neste recorte e o que fazer hoje?', "_volume"),
        ('Sobre a comanda "Loja crítica: Loja 25": o que explica isso neste recorte e o que fazer hoje?', "_stores"),
    ],
)
def test_new_handlers_and_comanda_prompts_route_correctly(repo, question, expected):
    handler = local.resolve_handler(question)
    assert handler is not None and handler.__name__ == expected
    res = local.answer(question, repo, Filters())
    assert "**Ação:**" in res


def test_status_filter_honest_responses(repo):
    f_canc = Filters(status=["canceled"])
    for q in ("onde esta o gargalo?", "como esta o sla?", "quanto custa o frete?", "como estao os modais?"):
        res = local.answer(q, repo, f_canc)
        assert "status cancelado" in res.lower()
        assert "ampliar o período" not in res.lower()
        assert "**Ação:**" in res

    res_canc = local.answer("quais lojas cancelam mais?", repo, f_canc)
    assert "100,0%" not in res_canc
    assert "**Ação:**" in res_canc

    res_deliv = local.answer("quais lojas cancelam mais?", repo, Filters(status=["delivered"]))
    assert "0,0%" in res_deliv
    assert "remover o filtro" in res_deliv.lower()
    assert "**Ação:**" in res_deliv


# ----------------------------------------------------------------- entidade citada na pergunta
class _MetaRepo:
    """Só o que o índice de entidades lê: `meta()` e `cached()`. Nomes de teste, não do código."""

    def __init__(self, hubs, stores, cities):
        self._meta = {"hubs": hubs, "stores": stores, "cities": cities}

    def meta(self):
        return self._meta

    def cached(self, key, compute):
        return compute()


def _opt(value, label, parent=None):
    return {"value": value, "label": label, "parent": parent, "orders": 1}


@pytest.fixture
def names_repo():
    return _MetaRepo(
        hubs=[_opt(8, "Golden Shopping", "Rio de Janeiro"), _opt(3, "Green Shopping", "Porto Alegre"),
              _opt(13, "Hip Hop Shopping", "Rio de Janeiro"), _opt(86, "R Shopping", "São Paulo")],
        stores=[_opt(53, "Papa Sucis", 8), _opt(294, "Papa Sucis", 13), _opt(60, "Papa Zum", 3),
                _opt(70, "Iumpica", 8), _opt(30, "Loja Quebrada", 3)],
        cities=[_opt("São Paulo", "São Paulo", "SP"), _opt("Rio de Janeiro", "Rio de Janeiro", "RJ")],
    )


@pytest.mark.parametrize(
    ("question", "dimension", "label", "ids"),
    [
        ("e a loja Papa Sucis, ta indo bem?", "store", "Papa Sucis", (53, 294)),  # homônimas: as duas unidades
        ("como está o hub golden shopping?", "hub", "Golden Shopping", (8,)),
        ("e o golden?", "hub", "Golden Shopping", (8,)),  # palavra distintiva de um nome só
        ("qual o sla do hip hop?", "hub", "Hip Hop Shopping", (13,)),  # nome sem a palavra comum
        ("como anda a iumpi?", "store", "Iumpica", (70,)),  # começo único com 5+ letras
        ("cancelamento em sao paulo", "city", "São Paulo", ("São Paulo",)),  # sem acento
    ],
)
def test_entity_comes_from_data_labels(names_repo, question, dimension, label, ids):
    entity = local_intent.find_entity(question, names_repo)
    assert entity is not None
    assert (entity.dimension, entity.label, entity.ids) == (dimension, label, ids)


@pytest.mark.parametrize(
    "question",
    [
        "as entregas são lentas?",  # "são" não é São Paulo
        "qual shopping cancela mais?",  # palavra comum a vários hubs
        "e a papa?",  # ambígua entre duas lojas
        "tem alguma loja quebrada?",  # nome que é termo do glossário
        "como está o r?",  # nome curto demais
    ],
)
def test_common_words_do_not_become_entities(names_repo, question):
    assert local_intent.find_entity(question, names_repo) is None


def test_named_store_answers_about_that_store(repo):
    reading = local.build_reading("e a loja Loja 25, ta indo bem?", repo, Filters())
    m = repo.metrics(Filters(store=[25]))
    line = next(row for row in reading.answer.splitlines() if row.startswith("- Loja 25:"))
    assert fmt.integer(m["orders"]) in line and fmt.pct(m["cancel_rate"]) in line
    assert "Loja 25" in reading.title and "Loja 25" in reading.action
    assert reading.drilldowns and reading.drilldowns[0].filters == {"store": [25]}


def test_named_broken_store_gets_the_take_down_action(repo):
    reading = local.build_reading("como está a Loja 33?", repo, Filters())
    assert "Tirar Loja 33 do ar" in reading.action
    assert "ampliar o período" not in reading.action  # 100% cancelado: a taxa é o problema, não a amostra


def test_named_hub_answers_with_its_slowest_stage(repo):
    reading = local.build_reading("qual etapa explica o Hub Lento estar lento?", repo, Filters())
    assert "trânsito" in reading.answer
    assert reading.action.startswith("Time de frota") and "Hub Lento" in reading.action


def test_named_entity_never_escapes_the_recorte(repo):
    res = local.answer("como está a Loja 25?", repo, Filters(city=["Curitiba"]))
    assert "não tem pedidos no recorte atual" in res
    assert "**Ação:**" in res


def test_this_hub_means_the_filtered_hub(repo):
    reading = local.build_reading("me da um resumo desse hub", repo, Filters(hub=[2]))
    assert reading.title == "Hub Lento"


# ----------------------------------------------------------------- fora do escopo
@pytest.mark.parametrize(
    ("question", "forbidden"),
    [
        ("quais os motivos dos cancelamentos?", ("principal motivo", "cliente desistiu")),
        ("quais itens do cardápio vendem mais?", ("item mais vendido", "pizza")),
        ("qual a nota media dos clientes nas avaliacoes?", ("estrelas", "nota média de")),
        ("a chuva atrapalhou as entregas?", ("choveu", "dias de chuva")),
        ("qual entregador atrasa mais?", ("o entregador mais",)),
        ("temos muita reclamação de cliente?", ("reclamações registradas",)),
    ],
)
def test_out_of_scope_says_the_data_does_not_exist(repo, question, forbidden):
    reading = local.build_reading(question, repo, Filters())
    assert reading.answer.startswith("O dataset não")
    assert "sem inventar número" in reading.answer
    assert reading.title == "Fora do que o dataset registra"
    assert reading.action.strip()
    for phrase in forbidden:
        assert phrase not in reading.answer.lower()


def test_chargeback_is_measured_with_its_limits(repo):
    res = local.answer("temos muito chargeback?", repo, Filters())
    assert "Chargeback no recorte" in res
    assert "não há valor contestado nem motivo" in res
    assert "**Ação:**" in res


# ----------------------------------------------------------------- por que mudou
def test_why_decomposes_against_the_previous_period(repo):
    f = Filters(start=date(2021, 3, 1), end=date(2021, 3, 31))
    res = local.answer("por que o SLA caiu vs o período anterior?", repo, f)
    change = explain_change(repo, f, metric="sla_rate", by="hub")
    delta = change["total"]["delta"]
    assert f"{fmt.decimal(abs(delta) * 100, 1)} p.p." in res
    assert "no período anterior" in res
    top = max((d for d in change["drivers"] if d["key"] is not None and d["contribution"] * delta > 0),
              key=lambda d: abs(d["contribution"]))
    assert top["label"] in res
    assert "efeito taxa" in res or "efeito mix" in res


def test_why_without_previous_period_compares_the_last_week(repo):
    res = local.answer("o cancelamento subiu vs o período anterior?", repo, Filters())
    assert "não há período anterior" in res
    assert "semana anterior" in res
    assert "**Ação:**" in res


def test_why_at_the_start_of_the_data_says_there_is_nothing_to_compare(repo):
    res = local.answer("o SLA caiu vs o período anterior?", repo, Filters(start=date(2021, 1, 1), end=date(2021, 1, 5)))
    assert "Sem período anterior" in res
    assert "**Ação:**" in res


# ----------------------------------------------------------------- janelas de tempo
def test_weekend_against_weekdays_uses_the_concept_windows(repo):
    res = local.answer("fim de semana é pior que dia útil no SLA?", repo, Filters())
    weekend = repo.subslice_metrics(Filters(), weekdays=[5, 6])
    weekdays = repo.subslice_metrics(Filters(), weekdays=[5, 6], complement=True)
    assert f"SLA {fmt.pct(weekend['sla_rate'])}" in res
    assert f"SLA {fmt.pct(weekdays['sla_rate'])}" in res
    assert "dias úteis" in res.lower()


def test_written_hour_range_beats_the_glossary_window(repo):
    res = local.answer("o jantar (19h-21h) cancela mais que o resto do dia?", repo, Filters())
    inside = repo.subslice_metrics(Filters(), hours=[19, 20])
    outside = repo.subslice_metrics(Filters(), hours=[19, 20], complement=True)
    assert f"cancelamento {fmt.pct(inside['cancel_rate'])}" in res
    assert f"cancelamento {fmt.pct(outside['cancel_rate'])}" in res
    assert "19h–21h" in res


# ----------------------------------------------------------------- ações consistentes
def test_store_that_only_cancels_gets_the_alert_action_family(repo):
    reading = local.build_reading("tem alguma loja que só cancela pedido?", repo, Filters())
    assert reading.action.startswith("Tirar ") and " do ar hoje" in reading.action
    assert "ligar para a loja" not in reading.action.lower()


def test_null_bucket_is_listed_but_never_the_target(repo, monkeypatch):
    real = repo.query_metrics

    def with_null(f, **kwargs):
        out = real(f, **kwargs)
        dims = kwargs.get("group_by") or []
        if dims == ["driver_type"]:
            metric = kwargs["metrics"][0]
            ghost = {"keys": {"driver_type": {"key": None, "label": "Não informado"}}, "orders": 999, "measured": 0,
                     "low_sample": True, metric: 0.99}
            out = {**out, "rows": [ghost, *out["rows"]]}
        return out

    monkeypatch.setattr(repo, "query_metrics", with_null)
    reading = local.build_reading("cancelamento por tipo de entregador", repo, Filters())
    assert "Fora do ranking: Não informado" in reading.answer
    assert "Não informado" not in reading.action


def test_payment_null_bucket_is_not_the_target(repo, monkeypatch):
    real = repo.breakdown

    def with_null(f, by, **kwargs):
        rows = real(f, by, **kwargs)
        if by == "payment_method":
            ghost = {**rows[0], "key": None, "label": "Sem pagamento", "orders": 10**6, "cancel_rate": 0.9,
                     "cancel_above": True}
            rows = [ghost, *rows]
        return rows

    monkeypatch.setattr(repo, "breakdown", with_null)
    reading = local.build_reading("como estão as formas de pagamento?", repo, Filters())
    assert "Sem pagamento" in reading.answer
    assert "Sem pagamento" not in reading.action


# ----------------------------------------------------------------- métrica × dimensão
def test_any_metric_by_any_dimension_routes_to_the_generic_breakdown(repo):
    reading = local.build_reading("cancelamento ta alto em qual cidade", repo, Filters())
    assert reading.title == "Cancelamento por cidade"
    for row in repo.breakdown(Filters(), "city", sort="cancel_rate", min_orders=100):
        assert f"- {row['label']}: {fmt.pct(row['cancel_rate'])}" in reading.answer
    # A ação desce da cidade para a loja que mais cancela nela (aqui, uma loja quebrada: tirar do ar).
    worst_city = repo.breakdown(Filters(), "city", sort="cancel_rate", limit=1, min_orders=100)[0]
    stores = repo.breakdown(Filters(city=[worst_city["key"]]), "store", sort="cancel_rate", limit=1, min_orders=150)
    assert stores[0]["label"] in reading.action


def test_worst_hour_looks_at_every_hour_with_base(repo):
    res = local.answer("em que horario o sla fica pior?", repo, Filters())
    rows = repo.breakdown(Filters(), "hour", sort="sla_rate", desc=False, limit=24, min_measured=100)
    worst = rows[0]
    first = next(line for line in res.splitlines() if line.startswith("- "))
    assert first.startswith(f"- {int(worst['key']):02d}h: {fmt.pct(worst['sla_rate'])}")


def test_prepare_verb_routes_to_preparation_time(repo):
    res = local.answer("as lojas estão demorando pra preparar?", repo, Filters())
    assert f"recorte em {fmt.minutes(repo.metrics(Filters())['production_p50'])}" in res
    assert "Preparo" in res


def test_how_many_orders_answers_the_volume(repo):
    f = Filters(start=date(2021, 3, 1), end=date(2021, 3, 31))
    res = local.answer("quantos pedidos tivemos?", repo, f)
    assert fmt.integer(repo.metrics(f)["orders"]) in res


def test_channel_question_compares_marketplace_and_own(repo):
    reading = local.build_reading("marketplace ou canal próprio, qual cancela mais?", repo, Filters())
    for row in repo.breakdown(Filters(), "channel_type"):
        assert f"cancelamento {fmt.pct(row['cancel_rate'])}" in reading.answer
    assert "marketplace" in reading.action or "canal próprio" in reading.action


def test_unrouted_question_closes_with_the_lead_alert_action(repo):
    reading = local.build_reading("algo completamente aleatorio sem sentido", repo, Filters())
    assert reading.action in {a.action for a in detect_alerts(repo, Filters())}
    assert not reading.action.startswith("Operador deve usar uma das perguntas")


NEW_ROUTES = [
    "e a loja Loja 25, ta indo bem?",
    "qual etapa explica o Hub Lento estar lento?",
    "quais os motivos dos cancelamentos?",
    "temos muito chargeback?",
    "por que o cancelamento subiu vs o período anterior?",
    "o volume caiu na última semana?",
    "fim de semana é pior que dia útil no SLA?",
    "como está o almoço?",
    "cancelamento por cidade",
    "em que horario o sla fica pior?",
    "melhor hub em SLA",
    "qual hub tem menos pedidos?",
]


@pytest.mark.parametrize("question", NEW_ROUTES)
def test_new_routes_keep_the_comanda_contract(repo, question):
    reading = local.build_reading(question, repo, Filters(start=date(2021, 2, 1), end=date(2021, 3, 31)))
    assert reading.title.strip() and reading.diagnosis.strip() and reading.action.strip()
    assert "**Ação:**" not in reading.action and "**Ação:**" in reading.answer
    assert reading.tools
    assert all("get_" not in label and "query_" not in label for label in labels_for(reading.tools))
    hubs = {int(h["key"]) for h in repo.breakdown(Filters(), "hub", limit=100)}
    for drill in reading.drilldowns:
        assert set(drill.filters) <= {"city", "hub", "store", "segment", "channel_type", "modal", "status"}
        assert all(h in hubs for h in drill.filters.get("hub", []))


def test_answer_helpers_format_ptbr():
    assert local_answers.signed("sla_rate", -0.0001) == "0,0 p.p."
    assert local_answers.signed("sla_rate", 0.018) == "+1,8 p.p."
    assert local_answers.in_window("dias úteis") == "nos dias úteis"
    assert local_answers.in_window("Sexta") == "na sexta"
    assert local_answers.in_window("19h–21h") == "na faixa 19h–21h"


# ----------------------------------------------------------------- corpo, ação e atalho na mesma entidade
ENTITY_ROUTES = [
    "qual hub tem o pior SLA?",
    "quantos pedidos presos no fluxo existem?",
    "quais lojas cancelam mais?",
    "quais as lojas do recorte?",
    "onde esta o gargalo?",
    "quanto estamos subsidiando de frete?",
    "quais os hubs com maior volume na praca?",
    "qual o volume do recorte?",
    "resumo",
]


def _entity_labels(repo) -> list[str]:
    meta = repo.meta()
    return [str(o["label"]) for key in ("hubs", "stores") for o in meta[key]]


def _named_in(text: str, labels: list[str]) -> set[str]:
    return {name for name in labels if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text)}


@pytest.mark.parametrize("question", ENTITY_ROUTES)
@pytest.mark.parametrize("f", [Filters(), Filters(segment=["food"]), Filters(city=["São Paulo"])],
                         ids=["tudo", "food", "cidade"])
def test_drilldown_names_the_entity_the_action_targets(repo, question, f):
    """A-04: o atalho aponta o hub/loja que a ação cobra, e esse nome aparece no corpo ou na ação."""
    reading = local.build_reading(question, repo, f)
    labels = _entity_labels(repo)
    in_action = _named_in(reading.action, labels)
    in_answer = _named_in(reading.answer, labels)
    for drill in reading.drilldowns:
        name = drill.label.removeprefix("Ver só ").strip()
        if set(drill.filters) & {"hub", "store"}:
            assert name in in_answer, f"{question}: atalho {name} não aparece na resposta"
    entity_drills = [d for d in reading.drilldowns if set(d.filters) & {"hub", "store"}]
    if in_action and entity_drills:
        first = entity_drills[0].label.removeprefix("Ver só ").strip()
        assert first in in_action, f"{question}: ação cobra {in_action}, atalho aponta {first}"


def test_sla_ranking_separates_the_stuck_hub_with_the_reason(repo):
    reading = local.build_reading("qual hub tem o pior SLA?", repo, Filters())
    ranking = reading.answer.split("Hubs com pior SLA", 1)[1].split("\n\n", 1)[0]
    assert "Hub Preso" not in ranking
    assert "Fora do ranking de SLA por excesso de pedidos presos" in reading.answer
    assert "Hub Preso" in reading.answer.split("Fora do ranking", 1)[1]
    assert "Hub Lento" in reading.action
    assert [d.filters for d in reading.drilldowns] == [{"hub": [2]}]


def test_stages_drill_and_action_name_the_same_hub(repo):
    reading = local.build_reading("onde esta o gargalo?", repo, Filters())
    target = reading.drilldowns[0].label.removeprefix("Ver só ")
    assert target in reading.action and target in reading.diagnosis


# ----------------------------------------------------------------- amostra fina × loja quebrada
@pytest.mark.parametrize("question", ["como está a Loja Quebrada?", "quais os alertas?", "quais lojas cancelam mais?"])
def test_broken_store_keeps_the_take_down_action_on_its_own_slice(repo, question):
    """A-05: 100% cancelado com pedido de sobra não é amostra pequena; o 'tirar do ar' do alerta fica."""
    f = Filters(store=[30])
    assert repo.metrics(f)["low_sample"] is True
    reading = local.build_reading(question, repo, f)
    assert "Tirar Loja Quebrada do ar" in reading.action
    assert "ampliar o período" not in reading.action


def test_thin_sample_without_dates_does_not_ask_to_widen_the_period(repo):
    """A-05: sem filtro de data o recorte já cobre a base inteira; a ação afrouxa os outros filtros."""
    f = Filters(store=[36])
    m = repo.metrics(f)
    assert m["orders"] < 100 and m["delivered"] > 0
    reading = local.build_reading("como esta o sla?", repo, f)
    assert reading.answer.startswith("Atenção: amostra reduzida")
    assert "ampliar o período" not in reading.action
    assert "já cobre todo o período dos dados" in reading.action
    assert "Loja 36" in reading.action and "acionar alguém hoje" in reading.action


# ----------------------------------------------------------------- status = cancelado
@pytest.mark.parametrize(
    "question",
    ["como está a Loja 38?", "cancelamento por cidade", "cancelamento por hub", "fim de semana é pior que dia útil no SLA?",
     "quais os motivos dos cancelamentos?"],
)
def test_canceled_status_never_takes_a_store_offline(repo, question):
    """A-06: com status = cancelado toda loja tem 100% por definição; isso não é loja quebrada."""
    f = Filters(status=["canceled"])
    reading = local.build_reading(question, repo, f)
    text = reading.answer.lower()
    assert "tirar" not in text and "do ar" not in text
    assert "100,0%" not in reading.answer
    assert "status cancelado" in text or "status = cancelado" in text


@pytest.mark.parametrize(
    "question", ["como está a Loja 38?", "cancelamento por cidade", "fim de semana é pior que dia útil no SLA?"]
)
def test_canceled_status_points_to_removing_the_filter(repo, question):
    reading = local.build_reading(question, repo, Filters(status=["canceled"]))
    assert "status cancelado" in reading.answer.lower()
    assert "remover o filtro" in reading.action


def test_canceled_status_entity_reports_the_canceled_count(repo):
    f = Filters(status=["canceled"])
    reading = local.build_reading("como está a Loja 38?", repo, f)
    assert fmt.integer(repo.metrics(Filters(status=["canceled"], store=[38]))["orders"]) in reading.answer
    assert reading.drilldowns and reading.drilldowns[0].filters == {"store": [38]}


# ----------------------------------------------------------------- loja homônima no recorte
def _store_intent(repo, ids, label):
    intent = local_intent.parse(f"como está a {label}?", repo)
    intent.entity = local_intent.Entity("store", tuple(ids), label, label.lower())
    return intent


def test_homonymous_store_counts_only_the_units_in_the_recorte(repo):
    """A-07: unidade homônima fora do recorte não entra na contagem, no hub nem no atalho."""
    f = Filters(hub=[2])
    res = local_answers.entity_answer(repo, f, _store_intent(repo, (25, 10), "Loja 25"))  # 10 é do Hub Centro
    assert "unidades" not in res.text
    assert "2 hubs" not in res.text
    assert "(hub Hub Lento)" in res.text
    assert [d.filters for d in res.drills] == [{"store": [25]}]


def test_homonymous_broken_store_uses_the_unit_in_the_recorte(repo):
    f = Filters(hub=[3])
    res = local_answers.entity_answer(repo, f, _store_intent(repo, (10, 30), "Loja Quebrada"))
    assert "Tirar Loja Quebrada do ar" in res.text
    assert [d.filters for d in res.drills] == [{"store": [30]}]


def test_homonymous_store_lists_units_when_both_are_in_the_recorte(repo):
    res = local_answers.entity_answer(repo, Filters(), _store_intent(repo, (25, 10), "Loja 25"))
    assert "tem 2 unidades com esse nome no recorte" in res.text
    assert [d.filters for d in res.drills] == [{"store": [25, 10]}] or [d.filters for d in res.drills] == [{"store": [10, 25]}]


# ----------------------------------------------------------------- métrica pedida × rota antiga
@pytest.mark.parametrize(
    ("question", "title"),
    [
        ("qual o subsídio por modal?", "Subsídio de frete por modal"),
        ("qual o cancelamento por modal?", "Cancelamento por modal"),
        ("qual o SLA por canal?", "SLA por canal"),
    ],
)
def test_metric_by_dimension_beats_the_generic_route(repo, question, title):
    """A-19: a rota de modal/canal só cobre as métricas que mostra; o resto vai para a quebra genérica."""
    reading = local.build_reading(question, repo, Filters())
    assert reading.title == title
    assert reading.answer.startswith(title)


# ----------------------------------------------------------------- ação com "quando"
_WHEN = re.compile(r"hoje|semana|pico|\d+h|agora|antes de")


def test_fallback_actions_say_when(repo, monkeypatch):
    """A-29 (Regra 3): os ramos de reserva também dizem quando agir."""
    monkeypatch.setattr(repo, "breakdown", lambda *_a, **_k: [])
    f = Filters()
    actions = [
        local_answers._oos_menu(repo, f)[1],
        local_answers._oos_experience(repo, f)[1],
        local_answers._oos_courier(repo, f)[1],
    ]
    texts = [
        local._channels(repo, f)[0],
        local._payments(repo, f),
        local._hubs(repo, f)[0],
        local._stores(repo, f)[0],
        local._stores(repo, Filters(status=["canceled"]))[0],
        local._cancel(repo, Filters(status=["canceled"]))[0],
    ]
    actions += [t[t.rfind("**Ação:**"):] for t in texts]
    for action in actions:
        assert _WHEN.search(action), action


def test_by_dimension_without_named_rows_says_when(repo, monkeypatch):
    real = repo.query_metrics

    def only_nulls(f, **kwargs):
        out = real(f, **kwargs)
        return {**out, "rows": [r for r in out["rows"] if all(k["key"] is None for k in r["keys"].values())]}

    monkeypatch.setattr(repo, "query_metrics", only_nulls)
    res = local_answers.by_dimension(repo, Filters(), "sla_rate", "hub")
    action = res.text[res.text.rfind("**Ação:**"):]
    assert _WHEN.search(action), action


# ----------------------------------------------------------------- limiares e rótulos
def test_local_thresholds_come_from_the_alerts(repo):
    """A-30: local.py não repete os limiares dos alertas como número solto."""
    tree = ast.parse((APP_DIR / "agent" / "local.py").read_text(encoding="utf-8"))
    shared = {SLA_WARN, CANCEL_WARN, STUCK_HUB_MAX, BROKEN_CANCEL, HUB_MIN, STORE_MIN}
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) in (int, float)}
    assert not (literals & shared), literals & shared


def test_segment_action_uses_the_ptbr_label(repo):
    """A-31: 'segmento goods', nunca o código cru 'good'."""
    reading = local.build_reading("qual o faturamento?", repo, Filters(segment=["good"]))
    assert "segmento goods" in reading.action
    assert not re.search(r"segmento good\b", reading.action)
    assert all(d.label != "Ver só good" for d in reading.drilldowns)


def test_payment_action_uses_the_ptbr_name(repo, monkeypatch):
    real = repo.breakdown

    def raw_code(f, by, **kwargs):
        rows = real(f, by, **kwargs)
        if by == "payment_method":
            fake = {**rows[0], "key": "store_direct_payment", "label": "store_direct_payment", "orders": 10**6,
                    "cancel_rate": 0.5, "cancel_above": True}
            rows = [fake, *rows]
        return rows

    monkeypatch.setattr(repo, "breakdown", raw_code)
    reading = local.build_reading("como estão as formas de pagamento?", repo, Filters())
    assert "store_direct_payment" not in reading.action
    assert "pagamento direto na loja" in reading.action


def test_rows_without_parent_never_print_none(repo, monkeypatch):
    real = repo.breakdown
    monkeypatch.setattr(repo, "breakdown", lambda f, by, **kw: [{**r, "parent": None} for r in real(f, by, **kw)])
    for question in ("quais os hubs?", "qual o volume do recorte?", "quais lojas cancelam mais?"):
        assert "(None)" not in local.answer(question, repo, Filters())
        assert "(None)" not in local.answer(question, repo, Filters(status=["canceled"]))
    assert local._with_parent({"label": "Loja 1", "parent": None}) == "Loja 1"
    assert local._with_parent({"label": "Loja 1", "parent": "Hub X"}) == "Loja 1 (Hub X)"


def test_narrow_matches_city_ignoring_case(repo):
    """O filtro de cidade não diferencia maiúsculas; o recorte da entidade também não."""
    city = str(repo.meta()["cities"][0]["value"])
    entity = local_intent.Entity("city", (city,), city, city.lower())
    narrowed = local_answers.narrow(Filters(city=[city.upper()]), entity)
    assert narrowed is not None and narrowed.city == [city]
