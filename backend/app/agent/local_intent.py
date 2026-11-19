"""Leitura da pergunta para o agente local: camada semântica, entidade citada e sinais de intenção.

Nada aqui consulta métrica. `parse()` devolve o que a pergunta pede (métricas, dimensões, janelas,
entidade, se é "por que mudou", se está fora do escopo) e o roteador de `local.py` decide quem
responde. Nomes de hub, loja e cidade saem de `repo.meta()`, nunca do código.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app import semantic
from app.repository import Repository

# --------------------------------------------------------------------------- texto


def norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").lower().strip())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", norm(text))


def _part(token: str, part: str) -> bool:
    return token.startswith(part[:-1]) if part.endswith("*") else token == part


def _has(tokens: list[str], phrase: str) -> bool:
    """Palavra inteira, prefixo (`cancel*`, também no fim de frase) ou frase contígua."""
    parts = phrase.split()
    span = len(parts)
    return any(
        all(_part(tokens[i + j], parts[j]) for j in range(span)) for i in range(len(tokens) - span + 1)
    )


def has_any(tokens: list[str], phrases: tuple[str, ...]) -> bool:
    return any(_has(tokens, p) for p in phrases)


# --------------------------------------------------------------------- vocabulário

# Verbos e flexões que o glossário não carrega (ele guarda substantivos): prefixo -> métrica.
_METRIC_STEMS: tuple[tuple[str, str], ...] = (
    ("prepar", "production_p50"),
    ("atras", "sla_rate"),
    ("cancel", "cancel_rate"),
    ("subsidi", "subsidy"),
    ("despach", "expedition_p50"),
    ("colet", "collected_p50"),
    ("demor", "cycle_p50"),
    ("fatur", "gmv"),
    ("estorn", "chargeback_rate"),
    ("rapid", "cycle_p50"),
)
# Métrica vaga: só vale quando a pergunta não cita outra. "pedido" aparece em quase toda pergunta.
_VAGUE_METRICS = ("orders", "cycle_p50", "measured", "delivered")

CHANGE_CUES = (
    "queda", "cair", "caindo", "subir", "subindo", "piorar", "piorando", "melhorar", "melhorando",
    "mudou", "mudanca", "aumento", "reducao", "diminuir", "comparado com o periodo",
    "periodo anterior", "mes anterior", "semana anterior", "vs o periodo", "versus o periodo",
)
PREVIOUS_CUES = ("periodo anterior", "mes passado", "mes anterior", "periodo passado", "vs o periodo", "versus o periodo")
WEEK_CUES = ("ultima semana", "ultimos 7 dias", "nesta semana", "esta semana", "essa semana", "semana passada",
             "na semana", "semana anterior")
COMPARE_CUES = ("vs", "versus", "contra", "compar*", "que o resto", "do que", "mais que", "menos que",
                "pior que", "melhor que", "resto do dia", "resto da semana", "ou")
WORST_CUES = ("pior", "piores", "mais lento", "mais lenta", "atrasa mais", "cancela mais", "cancelam mais")
BEST_CUES = ("melhor", "melhores", "mais rapido", "mais rapida")
LOW_CUES = ("menos", "menor", "menores")

_HOUR_RANGE = re.compile(r"(?<!\d)(\d{1,2})\s*h?\s*(?:-|–|a|ate|às|as)\s*(\d{1,2})\s*h(?![a-z])")

# Fora do escopo: o dataset não registra isso. (tema, frases que disparam, condição extra opcional)
OUT_OF_SCOPE: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("motivo", ("motivo*", "razao", "razoes", "causa do cancelamento", "causas do cancelamento"), ("cancel*", "desist*", "recus*")),
    ("cardapio", ("item", "itens", "produto*", "prato*", "sku", "mais vendido*", "categoria de produto"), ()),
    ("cardapio", ("cardapio", "menu"), ("item", "itens", "vend*", "prato*", "produto*", "mais pedido*")),
    ("avaliacao", ("nps", "estrela*", "satisfacao", "nota media", "nota do cliente", "nota dos clientes"), ()),
    ("avaliacao", ("avaliac*", "nota", "notas"), ("cliente*", "consumidor*", "usuario*")),
    ("clima", ("chuva*", "chov*", "clima", "temperatura", "garoa", "tempestade", "enchente", "frio", "calor"), ()),
    ("entregador", ("qual entregador", "quais entregadores", "quem entrega", "entregador mais", "entregadores mais",
                    "melhor entregador", "pior entregador", "por entregador", "cada entregador", "nome do entregador",
                    "id do entregador", "qual motoboy", "quais motoboys", "motoboy mais", "qual motorista",
                    "ranking de entregadores", "entregador individual"), ()),
    ("reclamacao", ("reclama*", "sac", "atendimento ao cliente", "ouvidoria"), ()),
)

# Palavras comuns da pergunta que nunca identificam hub, loja ou cidade sozinhas.
_STOP = frozenset("""
a o as os de da do das dos e em no na nos nas um uma uns umas que qual quais como esta estao estamos ta tao
hoje hj pra para por pelo pela com sem mais menos muito muita pouco bem mal pior piores melhor melhores loja lojas
hub hubs cidade cidades shopping pedido pedidos tempo semana dia dias mes periodo anterior ultima ultimo ultimos
indo tem temos tivemos foi ser vs sobre isso aqui agora onde quando quanto quantos quantas porque pq explica
fazer comanda critica critico alerta alertas geral resumo operacao entrega entregas sao ao aos ou se ja eu voce
nao sim entao tudo todo toda todos todas me mim nosso nossa deles dela dele ela ele isto esse essa este
quem qual cade oi ola bom boa dia tarde noite favor obrigado rede recorte painel numero numeros
""".split())  # noqa: SIM905

_DIMENSION_WORD = {"hub": ("hub*", "shopping*"), "store": ("loja*", "restaurante*", "parceiro*"),
                   "city": ("cidade*", "praca*")}


@dataclass(frozen=True)
class Entity:
    dimension: str  # hub, store ou city
    ids: tuple  # hub/store: inteiros; city: o nome
    label: str
    term: str  # trecho da pergunta que casou


@dataclass(frozen=True)
class Window:
    label: str
    hours: tuple[int, ...] = ()
    weekdays: tuple[int, ...] = ()


@dataclass
class Intent:
    tokens: list[str]
    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    windows: list[Window] = field(default_factory=list)
    entity: Entity | None = None
    out_of_scope: str | None = None
    change: bool = False
    previous: bool = False
    week: bool = False
    compare: bool = False
    worst: bool = False
    best: bool = False
    low: bool = False

    @property
    def metric(self) -> str | None:
        """Métrica principal: a primeira específica; a vaga só se não houver outra."""
        specific = [m for m in self.metrics if m not in _VAGUE_METRICS]
        if specific:
            return specific[0]
        return self.metrics[0] if self.metrics else None

    @property
    def dimension(self) -> str | None:
        return self.dimensions[0] if self.dimensions else None


# ----------------------------------------------------------------- índice de entidades


@dataclass(frozen=True)
class _EntityIndex:
    phrases: dict[tuple[str, ...], list[tuple[str, str, tuple]]]  # frase -> (dim, rótulo, ids)
    tokens: dict[str, set[tuple[str, str]]]  # token distintivo -> {(dim, rótulo)}
    ids: dict[tuple[str, str], tuple]  # (dim, rótulo) -> ids
    vocab: frozenset[str]
    longest: int


def _vocabulary() -> tuple[frozenset[str], frozenset[tuple[str, ...]]]:
    """Tokens e frases da camada semântica: um nome de dado feito só disso não identifica entidade."""
    layer = semantic.load()
    terms: list[str] = []
    for m in layer.metrics.values():
        terms += [*m.synonyms, m.label, m.key.replace("_", " ")]
    for d in layer.dimensions.values():
        terms += [*d.synonyms, d.label, *d.values.values(), *d.values.keys()]
    for c in layer.concepts.values():
        terms += [*c.synonyms, c.label]
    tokens = frozenset(t for term in terms for t in words(term) if not t.isdigit())
    phrases = frozenset(tuple(words(term)) for term in terms if len(words(term)) > 1)
    return tokens, phrases


# Loja tem centenas de nomes curtos: palavra solta só com 4+ letras. Hub e cidade são poucos.
_MIN_TOKEN = {"store": 4, "hub": 3, "city": 3}


def _build_index(repo: Repository) -> _EntityIndex:
    meta = repo.meta()
    vocab, vocab_phrases = _vocabulary()
    groups: dict[tuple[str, str], list] = {}
    for dim, key in (("hub", "hubs"), ("store", "stores"), ("city", "cities")):
        for option in meta[key]:
            label = str(option["label"] or "").strip()
            if not label:
                continue
            value = int(option["value"]) if dim in ("hub", "store") else str(option["value"])
            bucket = groups.setdefault((dim, label), [])
            if value not in bucket:
                bucket.append(value)

    # Token presente em vários rótulos da mesma dimensão ("shopping") não distingue ninguém.
    seen: dict[tuple[str, str], int] = {}
    for dim, label in groups:
        for t in set(words(label)):
            seen[(dim, t)] = seen.get((dim, t), 0) + 1
    generic = {(dim, t) for (dim, t), n in seen.items() if n >= 3}

    def weak(token: str) -> bool:
        return token in _STOP or token in vocab or token.isdigit()

    phrases: dict[tuple[str, ...], list[tuple[str, str, tuple]]] = {}
    distinct: dict[str, set[tuple[str, str]]] = {}
    ids: dict[tuple[str, str], tuple] = {}
    for (dim, label), values in groups.items():
        ids[(dim, label)] = tuple(values)
        toks = tuple(words(label))
        if not toks:
            continue
        core = tuple(t for t in toks if (dim, t) not in generic) or toks
        candidates = []
        # Nome inteiro: palavra única precisa ser distintiva; frase vale, salvo termo do glossário
        # (nome igual a um conceito do glossário não é entidade; "hub" + adjetivo do glossário é).
        single_ok = len(toks) == 1 and len(toks[0]) >= 3 and not weak(toks[0])
        if (len(toks) > 1 and toks not in vocab_phrases) or single_ok:
            candidates.append(toks)
        # Nome sem a palavra comum ("Golden" de "Golden Shopping"): mesma régua, com o mínimo da dimensão.
        core_ok = (len(core) > 1 and not all(weak(t) for t in core)) or (
            len(core) == 1 and len(core[0]) >= _MIN_TOKEN[dim] and not weak(core[0])
        )
        if core != toks and core_ok:
            candidates.append(core)
        for phrase in candidates:
            phrases.setdefault(phrase, []).append((dim, label, tuple(values)))
        for t in core:
            if len(t) >= _MIN_TOKEN[dim] and not weak(t) and (dim, t) not in generic:
                distinct.setdefault(t, set()).add((dim, label))
    return _EntityIndex(phrases, distinct, ids, vocab, max((len(p) for p in phrases), default=0))


def _index(repo: Repository) -> _EntityIndex:
    return repo.cached("local:entity-index", lambda: _build_index(repo))


def _prefer(cands: list[tuple[str, str, tuple]], tokens: list[str]) -> tuple[str, str, tuple] | None:
    """Mais de um candidato: vale o da dimensão citada ("loja X"). Sem pista e ambíguo, nenhum."""
    named = [c for c in cands if has_any(tokens, _DIMENSION_WORD[c[0]])]
    pool = named or cands
    if len({(c[0], c[1]) for c in pool}) == 1:
        return pool[0]
    return None


def find_entity(question: str, repo: Repository) -> Entity | None:
    """Hub, loja ou cidade citado na pergunta (sem acento nem caixa).

    1. Nome inteiro (ou o nome sem a palavra comum a vários, como "Shopping"); a frase mais longa vence.
    2. Senão, uma palavra distintiva de um nome só ("golden"), ou o começo dela com 5+ letras.
    Ambíguo (duas lojas com a mesma palavra) não vira entidade: melhor responder o recorte.
    """
    tokens = words(question)
    if not tokens:
        return None
    index = _index(repo)
    hits: list[tuple[tuple[int, int], tuple[str, str, tuple], str]] = []
    for i in range(len(tokens)):
        for span in range(min(index.longest, len(tokens) - i), 0, -1):
            phrase = tuple(tokens[i:i + span])
            if phrase in index.phrases:
                text = " ".join(phrase)
                hits += [((span, len(text)), hit, text) for hit in index.phrases[phrase]]
                break
    if hits:
        top = max(h[0] for h in hits)
        chosen = _prefer([h[1] for h in hits if h[0] == top], tokens)
        if chosen:
            term = next(h[2] for h in hits if h[1] == chosen)
            return Entity(chosen[0], chosen[2], chosen[1], term)

    found: dict[tuple[str, str], str] = {}
    for t in tokens:
        if len(t) < 3 or t in _STOP or t in index.vocab:
            continue
        exact = index.tokens.get(t)
        if exact:
            for key in exact:
                found.setdefault(key, t)
            continue
        if len(t) >= 5:
            for label_token, keys in index.tokens.items():
                if label_token.startswith(t):
                    for key in keys:
                        found.setdefault(key, t)
    if not found:
        return None
    chosen = _prefer([(dim, label, index.ids[(dim, label)]) for dim, label in found], tokens)
    if chosen is None:
        return None
    return Entity(chosen[0], chosen[2], chosen[1], found[(chosen[0], chosen[1])])


# ------------------------------------------------------------------------- parse


def _hour_window(text: str) -> Window | None:
    match = _HOUR_RANGE.search(norm(text))
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    if not (0 <= start <= 23 and 0 < end <= 24) or end <= start:
        return None
    # "19h-21h" é a faixa que começa às 19h e termina às 21h (mesma leitura do rótulo dos alertas).
    return Window(f"{start:02d}h–{end:02d}h", hours=tuple(range(start, end)))


def out_of_scope(tokens: list[str]) -> str | None:
    for topic, triggers, needs in OUT_OF_SCOPE:
        if has_any(tokens, triggers) and (not needs or has_any(tokens, needs)):
            return topic
    return None


def parse(question: str, repo: Repository | None = None) -> Intent:
    tokens = words(question)
    layer = semantic.load()
    intent = Intent(tokens=tokens)
    for match in layer.resolve(question):
        if match.kind == "metric":
            intent.metrics.append(match.key)
        elif match.kind == "dimension":
            dim = layer.dimensions[match.key]
            code = layer.value_code(match.key, match.term)
            if match.key == "weekday" and code is not None:
                intent.windows.append(Window(dim.values[code], weekdays=(int(code),)))
            elif match.key not in intent.dimensions:
                intent.dimensions.append(match.key)
        else:
            intent.concepts.append(match.key)
            concept = layer.concepts[match.key]
            if concept.hours or concept.weekdays:
                intent.windows.append(Window(concept.label, tuple(concept.hours), tuple(concept.weekdays)))
    for stem, metric in _METRIC_STEMS:
        if metric not in intent.metrics and any(t.startswith(stem) for t in tokens):
            intent.metrics.append(metric)
    explicit = _hour_window(question)
    if explicit:
        # Faixa escrita ("19h-21h") manda sobre a janela do glossário (jantar = 18h–22h).
        intent.windows = [w for w in intent.windows if not w.hours] + [explicit]

    intent.out_of_scope = out_of_scope(tokens)
    intent.change = "variacao" in intent.concepts or has_any(tokens, CHANGE_CUES)
    intent.previous = has_any(tokens, PREVIOUS_CUES)
    intent.week = has_any(tokens, WEEK_CUES)
    intent.compare = has_any(tokens, COMPARE_CUES)
    intent.worst = has_any(tokens, WORST_CUES)
    intent.best = has_any(tokens, BEST_CUES) and not intent.worst
    intent.low = has_any(tokens, LOW_CUES)
    if repo is not None:
        intent.entity = find_entity(question, repo)
        if intent.entity and intent.entity.dimension in intent.dimensions:
            # "o hub Golden" fala do hub, não pede quebra por hub.
            intent.dimensions.remove(intent.entity.dimension)
    return intent
