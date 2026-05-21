"""Resolve institution strings into reportable country or region buckets."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from typing import Protocol

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def Field(default=None, **kwargs):  # type: ignore
        if "default_factory" in kwargs:
            return kwargs["default_factory"]()
        return default


@dataclass(frozen=True)
class CountryResolution:
    """Record one institution-to-country decision with confidence and evidence."""
    institution: str
    country: str
    country_code: str | None
    confidence: str
    method: str
    evidence: str
    needs_review: bool = False
    basis: str = "unknown"
    is_inferred: bool = False
    author_id: str | None = None
    author_name: str | None = None
    country_hints: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "author_id": self.author_id,
            "author_name": self.author_name,
            "institution": self.institution,
            "country": self.country,
            "country_code": self.country_code,
            "confidence": self.confidence,
            "method": self.method,
            "evidence": self.evidence,
            "needs_review": self.needs_review,
            "basis": self.basis,
            "is_inferred": self.is_inferred,
            "country_hints": list(self.country_hints),
        }


@dataclass(frozen=True)
class AuthorCountryInput:
    """Compact author-level country evidence sent to deterministic or LLM resolvers."""
    author_id: str
    author_name: str
    institutions: tuple[str, ...] = ()
    country_hints: tuple[str, ...] = ()


class CountryResolverProtocol(Protocol):
    """Define the protocol expected by report generation services."""
    def resolve(self, institution: str) -> CountryResolution:
        ...

    def resolve_many(self, institutions: list[str]) -> dict[str, CountryResolution]:
        ...

    def resolve_author_many(self, authors: list[AuthorCountryInput]) -> dict[str, CountryResolution]:
        ...


class LLMCountryResolutionModel(BaseModel):
    """Validate the structured country inference returned by the LLM."""
    author_id: Optional[str] = Field(default=None, description="Original OpenAlex author id when provided.")
    institution: Optional[str] = Field(default=None, description="Original input institution name when resolving a batch.")
    country: str = Field(description="Country or region name in English, or Unknown if not enough evidence.")
    country_code: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2 code when known, otherwise null.")
    confidence: str = Field(description="high, medium, or low")
    evidence: str = Field(description="用中文简明说明依据；如果证据不足，说明为什么不足。")
    needs_review: bool = Field(description="Whether this inference should be manually reviewed.")
    basis: str = Field(default="unknown", description="explicit_country_code, explicit_country_name, institution_name, llm_inference, or unknown.")


class LLMCountryResolutionBatchModel(BaseModel):
    """Validate batch country inferences returned by the LLM."""
    resolutions: list[LLMCountryResolutionModel] = Field(
        default_factory=list,
        description="One country inference per input institution, in the same order when possible.",
    )


COUNTRY_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("tsinghua", "peking university", "chinese academy", "harbin institute", "zhejiang university", "shanghai jiao tong", "china"), "China", "CN"),
    (("mit", "massachusetts institute", "stanford", "berkeley", "carnegie mellon", "cmu", "university of washington", "united states", " usa", "u.s."), "United States", "US"),
    (("oxford", "cambridge", "imperial college", "university college london", "ucl", "united kingdom", " uk", "england"), "United Kingdom", "GB"),
    (("eth zurich", "epfl", "switzerland"), "Switzerland", "CH"),
    (("university of toronto", "mcgill", "canada"), "Canada", "CA"),
    (("national university of singapore", "nanyang technological", "singapore"), "Singapore", "SG"),
    (("tokyo", "kyoto university", "japan"), "Japan", "JP"),
    (("seoul national", "kaist", "korea"), "South Korea", "KR"),
    (("australian national", "university of melbourne", "australia"), "Australia", "AU"),
    (("inria", "sorbonne", "france"), "France", "FR"),
    (("tum", "technical university of munich", "max planck", "germany"), "Germany", "DE"),
)

COUNTRY_CODE_NAMES: dict[str, tuple[str, str]] = {
    "AU": ("Australia", "AU"),
    "BD": ("Bangladesh", "BD"),
    "CA": ("Canada", "CA"),
    "CH": ("Switzerland", "CH"),
    "CN": ("China", "CN"),
    "DE": ("Germany", "DE"),
    "ET": ("Ethiopia", "ET"),
    "FI": ("Finland", "FI"),
    "FR": ("France", "FR"),
    "GB": ("United Kingdom", "GB"),
    "GH": ("Ghana", "GH"),
    "GR": ("Greece", "GR"),
    "HK": ("Hong Kong", "HK"),
    "ID": ("Indonesia", "ID"),
    "IN": ("India", "IN"),
    "JP": ("Japan", "JP"),
    "KR": ("South Korea", "KR"),
    "NZ": ("New Zealand", "NZ"),
    "PT": ("Portugal", "PT"),
    "RU": ("Russia", "RU"),
    "SG": ("Singapore", "SG"),
    "SI": ("Slovenia", "SI"),
    "US": ("United States", "US"),
}

COUNTRY_NAME_CODES: dict[str, tuple[str, str]] = {
    country.casefold(): (country, code)
    for code, (country, _same_code) in COUNTRY_CODE_NAMES.items()
}
COUNTRY_NAME_CODES.update(
    {
        "usa": ("United States", "US"),
        "u.s.": ("United States", "US"),
        "u.s.a.": ("United States", "US"),
        "united states of america": ("United States", "US"),
        "uk": ("United Kingdom", "GB"),
        "u.k.": ("United Kingdom", "GB"),
        "england": ("United Kingdom", "GB"),
        "south korea": ("South Korea", "KR"),
        "korea": ("South Korea", "KR"),
    }
)


class RuleBasedCountryResolver:
    """Resolve common institution names with deterministic country keyword rules."""
    def resolve(self, institution: str) -> CountryResolution:
        """Return a high-confidence country when an institution matches known rules."""
        normalized = f" {institution.strip().casefold()} "
        if not normalized.strip():
            return unknown_country_resolution(institution, method="rule", evidence="机构字段为空。")

        for keywords, country, code in COUNTRY_RULES:
            if any(keyword in normalized for keyword in keywords):
                return CountryResolution(
                    institution=institution,
                    country=country,
                    country_code=code,
                    confidence="high",
                    method="rule",
                    evidence=f"规则命中: {country}",
                    needs_review=False,
                )
        return unknown_country_resolution(institution, method="rule", evidence="未命中内置国家/地区规则。", needs_review=True)

    def resolve_many(self, institutions: list[str]) -> dict[str, CountryResolution]:
        """Resolve a batch of institutions using deterministic rules only."""
        return {institution: self.resolve(institution) for institution in institutions}


class LLMCountryResolver:
    """Use the configured LLM for institution locations not covered by rules."""
    batch_size = 40

    def resolve(self, institution: str) -> CountryResolution:
        """Infer an institution country with structured confidence and review flags."""
        from apps.analyzer.config import build_llm, invoke_llm_with_retry

        llm = build_llm()
        structured_llm = llm.with_structured_output(LLMCountryResolutionModel, method="function_calling")
        prompt = (
            "你正在根据学术机构名称推断该机构所在国家或地区。"
            "只根据机构名称本身和通用常识判断；不要编造不存在的信息。"
            "字段名和枚举值不要翻译。confidence 必须是 high、medium 或 low。"
            "如果机构名称不足以可靠判断，country 必须返回 Unknown，country_code 返回 null，needs_review=true。"
            "evidence 必须使用中文，简明说明判断依据或不确定原因。"
        )
        result = invoke_llm_with_retry(
            structured_llm,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Institution:\n{institution}"},
            ],
            "阶段7国家地区解析",
        )
        country = str(result.country or "Unknown").strip() or "Unknown"
        confidence = normalize_confidence(str(result.confidence or "low"))
        needs_review = bool(result.needs_review) or confidence == "low" or country.casefold() == "unknown"
        if needs_review:
            country = "Unknown"
        return CountryResolution(
            institution=institution,
            country=country,
            country_code=result.country_code,
            confidence=confidence,
            method="llm",
            evidence=str(result.evidence or "llm_country_resolution"),
            needs_review=needs_review,
        )

    def resolve_many(self, institutions: list[str]) -> dict[str, CountryResolution]:
        """Infer countries for institutions in chunks to avoid one LLM call per author."""
        from apps.analyzer.config import build_llm, invoke_llm_with_retry
        from packages.shared.runtime_logging import get_runtime_logger

        unique_institutions = [institution for institution in dict.fromkeys(institutions) if institution.strip()]
        if not unique_institutions:
            return {}

        llm = build_llm()
        structured_llm = llm.with_structured_output(LLMCountryResolutionBatchModel, method="function_calling")
        prompt = (
            "你正在批量根据学术机构名称推断该机构所在国家或地区。"
            "只根据机构名称本身和通用常识判断；不要编造不存在的信息。"
            "必须为每个输入机构返回一个 resolutions 条目，且 institution 必须原样复制输入。"
            "字段名和枚举值不要翻译。confidence 必须是 high、medium 或 low。"
            "如果机构名称不足以可靠判断，country 必须返回 Unknown，country_code 返回 null，needs_review=true。"
            "evidence 必须使用中文，简明说明判断依据或不确定原因。"
        )
        resolved: dict[str, CountryResolution] = {}
        logger = get_runtime_logger()
        for chunk_start in range(0, len(unique_institutions), self.batch_size):
            chunk = unique_institutions[chunk_start:chunk_start + self.batch_size]
            logger.detail(
                "report.country_batch",
                "批量解析机构国家/地区",
                batch_start=chunk_start + 1,
                batch_size=len(chunk),
                total=len(unique_institutions),
            )
            numbered = "\n".join(f"{idx + 1}. {institution}" for idx, institution in enumerate(chunk))
            result = invoke_llm_with_retry(
                structured_llm,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Institutions:\n{numbered}"},
                ],
                "阶段7国家地区批量解析",
            )
            chunk_results = list(getattr(result, "resolutions", []) or [])
            for institution, item in zip(chunk, chunk_results):
                resolved[institution] = _coerce_llm_country_resolution(institution, item, method="llm_batch")
            for institution in chunk:
                resolved.setdefault(
                    institution,
                    unknown_country_resolution(
                        institution,
                        method="llm_batch_missing",
                        evidence="批量模型输出缺少该机构结果。",
                        needs_review=True,
                    ),
                )
        return resolved

    def resolve_author_many(self, authors: list[AuthorCountryInput]) -> dict[str, CountryResolution]:
        """Infer countries from compact author evidence in batches."""
        from apps.analyzer.config import build_llm, invoke_llm_with_retry
        from packages.shared.runtime_logging import get_runtime_logger

        unresolved = [
            author for author in authors
            if author.institutions or author.country_hints
        ]
        if not unresolved:
            return {}

        llm = build_llm()
        structured_llm = llm.with_structured_output(LLMCountryResolutionBatchModel, method="function_calling")
        prompt = (
            "你正在根据作者的 OpenAlex 信息判断国家或地区。"
            "每条输入包含 author_id、作者名、institutions 和 country_hints。"
            "优先级必须是：1) 明确国家代码；2) 明确国家名；3) 机构名；4) 弱推断；5) Unknown。"
            "如果 country_hints 中有明确国家代码或国家名，直接输出对应国家，confidence=high，basis=explicit_country_code 或 explicit_country_name。"
            "如果没有明确国家信息但机构名能判断，输出该国家，basis=institution_name。"
            "如果只是推断，basis=llm_inference，confidence=medium 或 low。"
            "如果信息仍不足，country=Unknown，country_code=null，basis=unknown。"
            "不要因为存在一定歧义就强制 Unknown；只要能给出合理国家，就输出国家并降低 confidence。"
            "字段名和枚举值不要翻译。confidence 必须是 high、medium 或 low。"
            "evidence 必须用中文说明：原因：..."
            "必须为每个输入作者返回一个 resolutions 条目，且 author_id 必须原样复制输入。"
        )
        resolved: dict[str, CountryResolution] = {}
        logger = get_runtime_logger()
        for chunk_start in range(0, len(unresolved), self.batch_size):
            chunk = unresolved[chunk_start:chunk_start + self.batch_size]
            logger.detail(
                "report.country_author_batch",
                "批量解析作者国家/地区",
                batch_start=chunk_start + 1,
                batch_size=len(chunk),
                total=len(unresolved),
            )
            payload = [
                {
                    "author_id": author.author_id,
                    "author_name": author.author_name,
                    "institutions": list(author.institutions),
                    "country_hints": list(author.country_hints),
                }
                for author in chunk
            ]
            result = invoke_llm_with_retry(
                structured_llm,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
                ],
                "阶段7作者国家地区批量解析",
            )
            chunk_results = list(getattr(result, "resolutions", []) or [])
            by_author_id = {
                str(getattr(item, "author_id", "") or "").strip(): item
                for item in chunk_results
            }
            for author, item in zip(chunk, chunk_results):
                if not str(getattr(item, "author_id", "") or "").strip():
                    resolved[author.author_id] = _coerce_llm_country_resolution_for_author(author, item, method="llm_author_batch")
            for author in chunk:
                item = by_author_id.get(author.author_id)
                if item is not None:
                    resolved[author.author_id] = _coerce_llm_country_resolution_for_author(author, item, method="llm_author_batch")
                resolved.setdefault(
                    author.author_id,
                    unknown_country_resolution(
                        "; ".join(author.institutions),
                        method="llm_author_batch_missing",
                        evidence=f"{author.author_name}: 批量模型输出缺少该作者结果。",
                        needs_review=True,
                        author=author,
                    ),
                )
        return resolved


class HybridCountryResolver:
    """Prefer deterministic country rules and fall back to LLM inference when needed."""
    def __init__(
        self,
        rule_resolver: CountryResolverProtocol | None = None,
        llm_resolver: CountryResolverProtocol | None = None,
        *,
        use_llm: bool = True,
    ) -> None:
        self._rule_resolver = rule_resolver or RuleBasedCountryResolver()
        self._llm_resolver = llm_resolver
        self._use_llm = use_llm

    def resolve(self, institution: str) -> CountryResolution:
        """Return the strongest available country inference for an institution."""
        rule_result = self._rule_resolver.resolve(institution)
        if rule_result.country != "Unknown" and rule_result.confidence == "high":
            return rule_result
        if not self._use_llm:
            return rule_result
        llm_resolver = self._llm_resolver or LLMCountryResolver()
        try:
            return llm_resolver.resolve(institution)
        except Exception as exc:
            return unknown_country_resolution(
                institution,
                method="llm_failed",
                evidence=f"{exc.__class__.__name__}: {exc}",
                needs_review=True,
            )

    def resolve_many(self, institutions: list[str]) -> dict[str, CountryResolution]:
        """Resolve a batch with rules first and one LLM call per unresolved chunk."""
        unique_institutions = [institution for institution in dict.fromkeys(institutions) if institution.strip()]
        resolved: dict[str, CountryResolution] = {}
        unresolved: list[str] = []
        for institution in unique_institutions:
            rule_result = self._rule_resolver.resolve(institution)
            if rule_result.country != "Unknown" and rule_result.confidence == "high":
                resolved[institution] = rule_result
            else:
                unresolved.append(institution)

        if not unresolved:
            return resolved
        if not self._use_llm:
            for institution in unresolved:
                resolved[institution] = self._rule_resolver.resolve(institution)
            return resolved

        llm_resolver = self._llm_resolver or LLMCountryResolver()
        try:
            if hasattr(llm_resolver, "resolve_many"):
                resolved.update(llm_resolver.resolve_many(unresolved))  # type: ignore[attr-defined]
            else:
                resolved.update({institution: llm_resolver.resolve(institution) for institution in unresolved})
        except Exception as exc:
            for institution in unresolved:
                resolved[institution] = unknown_country_resolution(
                    institution,
                    method="llm_batch_failed",
                    evidence=f"{exc.__class__.__name__}: {exc}",
                    needs_review=True,
                )
        return resolved

    def resolve_author_many(self, authors: list[AuthorCountryInput]) -> dict[str, CountryResolution]:
        """Resolve author-level country evidence with explicit hints before LLM inference."""
        resolved: dict[str, CountryResolution] = {}
        unresolved: list[AuthorCountryInput] = []
        for author in authors:
            explicit = resolve_explicit_country_hint(author)
            if explicit:
                resolved[author.author_id] = explicit
                continue
            if not author.institutions:
                resolved[author.author_id] = unknown_country_resolution(
                    "",
                    method="missing",
                    evidence=f"{author.author_name}: 缺少明确国家代码、国家名和机构字段。",
                    needs_review=True,
                    author=author,
                )
                continue
            unresolved.append(author)

        if unresolved and self._use_llm:
            llm_resolver = self._llm_resolver or LLMCountryResolver()
            try:
                if hasattr(llm_resolver, "resolve_author_many"):
                    resolved.update(llm_resolver.resolve_author_many(unresolved))  # type: ignore[attr-defined]
                else:
                    resolved.update(_resolve_author_inputs_by_institution(unresolved, llm_resolver))
            except Exception as exc:
                for author in unresolved:
                    resolved[author.author_id] = unknown_country_resolution(
                        "; ".join(author.institutions),
                        method="llm_author_batch_failed",
                        evidence=f"{exc.__class__.__name__}: {exc}",
                        needs_review=True,
                        author=author,
                    )
        elif unresolved:
            resolved.update(_resolve_author_inputs_by_institution(unresolved, self._rule_resolver))
        return resolved


def _coerce_llm_country_resolution(
    institution: str,
    result: object,
    *,
    method: str,
) -> CountryResolution:
    """Normalize one structured LLM country result into the internal dataclass."""
    country = str(getattr(result, "country", None) or "Unknown").strip() or "Unknown"
    confidence = normalize_confidence(str(getattr(result, "confidence", None) or "low"))
    needs_review = bool(getattr(result, "needs_review", False)) or confidence == "low" or country.casefold() == "unknown"
    return CountryResolution(
        institution=institution,
        country=country,
        country_code=getattr(result, "country_code", None),
        confidence=confidence,
        method=method,
        evidence=str(getattr(result, "evidence", None) or "llm_country_resolution"),
        needs_review=needs_review,
        basis=normalize_basis(str(getattr(result, "basis", None) or "llm_inference")),
        is_inferred=normalize_basis(str(getattr(result, "basis", None) or "llm_inference")) in {"institution_name", "llm_inference"},
    )


def _coerce_llm_country_resolution_for_author(
    author: AuthorCountryInput,
    result: object,
    *,
    method: str,
) -> CountryResolution:
    """Normalize one structured LLM country result for author-level map inputs."""
    country = str(getattr(result, "country", None) or "Unknown").strip() or "Unknown"
    confidence = normalize_confidence(str(getattr(result, "confidence", None) or "low"))
    basis = normalize_basis(str(getattr(result, "basis", None) or "llm_inference"))
    needs_review = bool(getattr(result, "needs_review", False)) or confidence == "low" or country.casefold() == "unknown"
    evidence = str(getattr(result, "evidence", None) or "llm_country_resolution").strip()
    if evidence and not evidence.startswith("原因："):
        evidence = f"原因：{evidence}"
    return CountryResolution(
        institution="; ".join(author.institutions),
        country=country,
        country_code=getattr(result, "country_code", None),
        confidence=confidence,
        method=method,
        evidence=evidence or "原因：LLM 根据作者国家输入判断。",
        needs_review=needs_review,
        basis=basis,
        is_inferred=basis in {"institution_name", "llm_inference"},
        author_id=author.author_id,
        author_name=author.author_name,
        country_hints=author.country_hints,
    )


def unknown_country_resolution(
    institution: str,
    *,
    method: str,
    evidence: str,
    needs_review: bool = True,
    author: AuthorCountryInput | None = None,
) -> CountryResolution:
    """Create an Unknown country result that preserves why resolution failed."""
    return CountryResolution(
        institution=institution,
        country="Unknown",
        country_code=None,
        confidence="low",
        method=method,
        evidence=evidence,
        needs_review=needs_review,
        basis="unknown",
        is_inferred=False,
        author_id=author.author_id if author else None,
        author_name=author.author_name if author else None,
        country_hints=author.country_hints if author else (),
    )


def normalize_confidence(value: str) -> str:
    """Constrain country-resolution confidence values to the supported levels."""
    normalized = value.strip().casefold()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "low"


def normalize_basis(value: str) -> str:
    """Constrain country-resolution basis values to supported labels."""
    normalized = value.strip().casefold()
    if normalized in {"explicit_country_code", "explicit_country_name", "institution_name", "llm_inference", "unknown"}:
        return normalized
    return "llm_inference"


def resolve_explicit_country_hint(author: AuthorCountryInput) -> CountryResolution | None:
    """Resolve direct country code/name hints before invoking LLM inference."""
    for hint in author.country_hints:
        text = str(hint or "").strip()
        if not text:
            continue
        upper = text.upper()
        if upper in COUNTRY_CODE_NAMES:
            country, code = COUNTRY_CODE_NAMES[upper]
            return CountryResolution(
                institution="; ".join(author.institutions),
                country=country,
                country_code=code,
                confidence="high",
                method="explicit_country_hint",
                evidence=f"原因：输入中已有明确国家代码 {upper}，直接归为 {country}。",
                needs_review=False,
                basis="explicit_country_code",
                is_inferred=False,
                author_id=author.author_id,
                author_name=author.author_name,
                country_hints=author.country_hints,
            )
        normalized = text.casefold()
        if normalized in COUNTRY_NAME_CODES:
            country, code = COUNTRY_NAME_CODES[normalized]
            return CountryResolution(
                institution="; ".join(author.institutions),
                country=country,
                country_code=code,
                confidence="high",
                method="explicit_country_hint",
                evidence=f"原因：输入中已有明确国家名 {text}，直接归为 {country}。",
                needs_review=False,
                basis="explicit_country_name",
                is_inferred=False,
                author_id=author.author_id,
                author_name=author.author_name,
                country_hints=author.country_hints,
            )
    return None


def _resolve_author_inputs_by_institution(
    authors: list[AuthorCountryInput],
    resolver: CountryResolverProtocol,
) -> dict[str, CountryResolution]:
    """Resolve author inputs through the legacy institution-only resolver path."""
    resolved: dict[str, CountryResolution] = {}
    for author in authors:
        institution = author.institutions[0] if author.institutions else ""
        if not institution:
            resolved[author.author_id] = unknown_country_resolution(
                "",
                method="missing",
                evidence=f"{author.author_name}: 缺少明确国家代码、国家名和机构字段。",
                needs_review=True,
                author=author,
            )
            continue
        result = resolver.resolve(institution)
        resolved[author.author_id] = CountryResolution(
            institution=result.institution,
            country=result.country,
            country_code=result.country_code,
            confidence=result.confidence,
            method=result.method,
            evidence=result.evidence,
            needs_review=result.needs_review,
            basis=result.basis,
            is_inferred=result.is_inferred,
            author_id=author.author_id,
            author_name=author.author_name,
            country_hints=author.country_hints,
        )
    return resolved


def trace_to_json(trace: list[CountryResolution]) -> str:
    """Serialize country-resolution evidence for inclusion in report provenance."""
    return json.dumps([item.to_dict() for item in trace], ensure_ascii=False, indent=2)
