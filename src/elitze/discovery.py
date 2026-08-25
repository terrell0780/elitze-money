"""DISCOVER — candidate generation.

Produces lawful, real-execution experiment candidates for each revenue
engine. Candidates are templates that describe a concrete, budgeted,
measurable experiment. An optional LLM pass can refine the thesis.
"""

from __future__ import annotations

from decimal import Decimal

from .domain.enums import EngineType
from .domain.models import ExperimentCandidate

# Lawful, bounded, measurable experiment templates per engine.
_TEMPLATES: dict[EngineType, list[dict]] = {
    EngineType.LEAD_GENERATION: [
        {
            "title": "Local SMB lead-gen landing page",
            "thesis": "A conversion-focused landing page with a paid search budget can acquire qualified leads for local service businesses.",
            "target_market": "local home-services SMBs",
            "estimated_cost": "250",
            "expected_roi_min": "20",
            "complexity": 2,
            "tags": ["leadgen", "local", "search_ads"],
        },
        {
            "title": "Directory + retargeting lead pilot",
            "thesis": "Paid directory placement plus retargeting outperforms directory placement alone.",
            "target_market": "B2B consultants",
            "estimated_cost": "300",
            "expected_roi_min": "15",
            "complexity": 3,
            "tags": ["leadgen", "directory", "retargeting"],
        },
        {
            "title": "Quiz-funnel lead capture",
            "thesis": "An interactive qualification quiz converts cold traffic to leads better than a static form.",
            "target_market": "financial advisory prospects",
            "estimated_cost": "400",
            "expected_roi_min": "25",
            "complexity": 3,
            "tags": ["leadgen", "quiz", "funnel"],
        },
    ],
    EngineType.B2B_SERVICES: [
        {
            "title": "Outbound outreach cadence to verified SMBs",
            "thesis": "A 5-touch personalized cadence to verified business registrations produces qualified discovery calls.",
            "target_market": "SMBs needing bookkeeping automation",
            "estimated_cost": "150",
            "expected_roi_min": "40",
            "complexity": 2,
            "tags": ["b2b", "outreach", "cadence"],
        },
        {
            "title": "Vertical specialization offer",
            "thesis": "A vertical-specific service package converts better than a generalist pitch.",
            "target_market": "dental practices",
            "estimated_cost": "200",
            "expected_roi_min": "35",
            "complexity": 3,
            "tags": ["b2b", "vertical", "offer"],
        },
        {
            "title": "Partnership referral program",
            "thesis": "Referral partnerships with adjacent providers lower acquisition cost.",
            "target_market": "accounting firms",
            "estimated_cost": "100",
            "expected_roi_min": "50",
            "complexity": 2,
            "tags": ["b2b", "partnerships", "referral"],
        },
    ],
    EngineType.DIGITAL_PRODUCTS: [
        {
            "title": "Niche how-to ebook with upsell",
            "thesis": "A narrowly-scoped how-to ebook with a bundled template upsells to a positive return.",
            "target_market": "content creators",
            "estimated_cost": "120",
            "expected_roi_min": "30",
            "complexity": 2,
            "tags": ["digital", "ebook", "upsell"],
        },
        {
            "title": "Template pack storefront",
            "thesis": "A curated template pack solves a specific workflow pain and sells as a one-time purchase.",
            "target_market": "operations managers",
            "estimated_cost": "150",
            "expected_roi_min": "30",
            "complexity": 2,
            "tags": ["digital", "templates", "storefront"],
        },
        {
            "title": "Mini-course + community",
            "thesis": "A short video course with a community tier increases lifetime value over a one-off product.",
            "target_market": "aspiring freelancers",
            "estimated_cost": "350",
            "expected_roi_min": "40",
            "complexity": 4,
            "tags": ["digital", "course", "community"],
        },
    ],
    EngineType.AFFILIATE_MARKETING: [
        {
            "title": "Comparison content with disclosure",
            "thesis": "Honest, disclosed comparison content ranks and converts better than generic listicles.",
            "target_market": "SaaS tool buyers",
            "estimated_cost": "100",
            "expected_roi_min": "25",
            "complexity": 2,
            "tags": ["affiliate", "comparison", "disclosure"],
        },
        {
            "title": "Review-site niche authority",
            "thesis": "Deep single-niche reviews with disclosure build trust and steady affiliate clicks.",
            "target_market": "home-office equipment buyers",
            "estimated_cost": "180",
            "expected_roi_min": "20",
            "complexity": 3,
            "tags": ["affiliate", "reviews", "niche"],
        },
        {
            "title": "Email newsletter affiliate digest",
            "thesis": "A curated newsletter with disclosed affiliate links monetizes attention over time.",
            "target_market": "productivity tool users",
            "estimated_cost": "80",
            "expected_roi_min": "25",
            "complexity": 2,
            "tags": ["affiliate", "newsletter", "disclosure"],
        },
    ],
    EngineType.MARKET_INTELLIGENCE: [
        {
            "title": "Industry trend report subscription",
            "thesis": "A recurring, data-backed trend report commands a subscription in a fast-moving niche.",
            "target_market": "e-commerce operators",
            "estimated_cost": "150",
            "expected_roi_min": "35",
            "complexity": 3,
            "tags": ["intel", "subscription", "trends"],
        },
        {
            "title": "Public-filings insight briefs",
            "thesis": "Insight briefs synthesized from public filings serve investors who lack time to read them.",
            "target_market": "retail investors",
            "estimated_cost": "100",
            "expected_roi_min": "30",
            "complexity": 2,
            "tags": ["intel", "filings", "briefs"],
        },
        {
            "title": "Pricing benchmark dataset",
            "thesis": "A cleaned, normalized pricing benchmark dataset sells to operators making pricing decisions.",
            "target_market": "SaaS operators",
            "estimated_cost": "220",
            "expected_roi_min": "40",
            "complexity": 4,
            "tags": ["intel", "pricing", "dataset"],
        },
    ],
    EngineType.SAAS: [
        {
            "title": "Waitlist-first micro-SaaS",
            "thesis": "A landing page + waitlist validates demand before any meaningful build spend.",
            "target_market": "freelancers tracking invoices",
            "estimated_cost": "200",
            "expected_roi_min": "30",
            "complexity": 3,
            "tags": ["saas", "waitlist", "mvp"],
        },
        {
            "title": "Integratable widget with usage tier",
            "thesis": "A drop-in widget with a free usage tier drives bottom-up adoption into paid tiers.",
            "target_market": "web agencies",
            "estimated_cost": "400",
            "expected_roi_min": "35",
            "complexity": 4,
            "tags": ["saas", "widget", "freemium"],
        },
        {
            "title": "Automation service with per-seat pricing",
            "thesis": "A narrowly-scoped automation service with per-seat pricing converts a pain point into recurring revenue.",
            "target_market": "e-commerce operations teams",
            "estimated_cost": "300",
            "expected_roi_min": "35",
            "complexity": 3,
            "tags": ["saas", "automation", "per-seat"],
        },
    ],
}


class Discover:
    """Candidate generation for the DISCOVER phase."""

    def generate(self, engine: EngineType | None = None) -> list[ExperimentCandidate]:
        engines = [engine] if engine else list(EngineType)
        candidates: list[ExperimentCandidate] = []
        for eng in engines:
            for tpl in _TEMPLATES.get(eng, []):
                candidates.append(
                    ExperimentCandidate(
                        engine=eng,
                        title=tpl["title"],
                        thesis=tpl["thesis"],
                        target_market=tpl["target_market"],
                        estimated_cost=Decimal(tpl["estimated_cost"]),
                        expected_roi_min=Decimal(tpl["expected_roi_min"]),
                        complexity=tpl["complexity"],
                        tags=tpl["tags"],
                    )
                )
        return candidates
