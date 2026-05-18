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

    def to_dict(self) -> dict[str, object]:
        return {
            "institution": self.institution,
            "country": self.country,
            "country_code": self.country_code,
            "confidence": self.confidence,
            "method": self.method,
            "evidence": self.evidence,
            "needs_review": self.needs_review,
        }


class CountryResolverProtocol(Protocol):
    """Define the protocol expected by report generation services."""
    def resolve(self, institution: str) -> CountryResolution:
        ...


class LLMCountryResolutionModel(BaseModel):
    """Validate the structured country inference returned by the LLM."""
    country: str = Field(description="Country or region name in English, or Unknown if not enough evidence.")
    country_code: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2 code when known, otherwise null.")
    confidence: str = Field(description="high, medium, or low")
    evidence: str = Field(description="用中文简明说明依据；如果证据不足，说明为什么不足。")
    needs_review: bool = Field(description="Whether this inference should be manually reviewed.")


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


class LLMCountryResolver:
    """Use the configured LLM for institution locations not covered by rules."""
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


def unknown_country_resolution(
    institution: str,
    *,
    method: str,
    evidence: str,
    needs_review: bool = True,
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
    )


def normalize_confidence(value: str) -> str:
    """Constrain country-resolution confidence values to the supported levels."""
    normalized = value.strip().casefold()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "low"


def trace_to_json(trace: list[CountryResolution]) -> str:
    """Serialize country-resolution evidence for inclusion in report provenance."""
    return json.dumps([item.to_dict() for item in trace], ensure_ascii=False, indent=2)
