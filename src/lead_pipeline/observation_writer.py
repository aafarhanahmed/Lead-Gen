"""Cold outreach observation writer for scored leads."""

from __future__ import annotations


def write_observation(raw: dict, scorecard: dict, lead_score_result: dict) -> str:
    """
    Return a short human-readable observation suitable for a cold email opener.
    """
    lead_capture = raw.get("lead_capture") if isinstance(raw.get("lead_capture"), dict) else {}
    trust_signals = raw.get("trust_signals") if isinstance(raw.get("trust_signals"), dict) else {}

    phone_detected = bool(
        raw.get("phone_detected")
        or raw.get("phone_numbers")
        or lead_capture.get("phones")
    )
    tel_link_present = bool(lead_capture.get("tel_link_present"))
    cta_detected = bool(
        raw.get("cta_detected")
        or lead_capture.get("cta_buttons_sample")
        or lead_capture.get("cta_inventory")
    )
    trust_detected = bool(
        raw.get("trust_detected")
        or raw.get("trust_keywords_found")
        or trust_signals.get("trust_keywords_found")
        or trust_signals.get("review_platform_links")
        or trust_signals.get("social_links")
    )

    if phone_detected and not tel_link_present:
        return (
            "I noticed your phone number appears on the site, but I did not detect "
            "a click-to-call link, which can add friction for mobile visitors trying "
            "to call quickly."
        )
    if not cta_detected:
        return (
            "I did not detect clear quote/contact CTA wording like \"Book,\" \"Call,\" "
            "\"Request a Quote,\" or \"Schedule,\" which may make the next step less "
            "obvious for visitors."
        )
    if not raw.get("contact_page_found"):
        return (
            "I could not detect a dedicated contact page in the crawl, which can make "
            "the lead path harder than it needs to be."
        )
    if not trust_detected:
        return (
            "I did not detect many visible trust signals such as reviews, testimonials, "
            "licensing, or credibility wording on the crawled pages."
        )
    if not raw.get("meta_description_exists"):
        return (
            "I noticed the homepage does not appear to have a meta description, which "
            "is a basic search/readiness and first-impression gap."
        )
    return (
        "I found a few public-facing website and lead-path improvements that may be "
        "worth reviewing before spending more on ads, SEO, or a redesign."
    )

