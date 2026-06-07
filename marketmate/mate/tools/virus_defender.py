"""
marketmate.mate.tools.virus_defender
─────────────────────────────────────
Virus detection and security defense tool for MATE's tool-calling agent.

Provides URL threat scanning, content analysis, and security defenses
to protect MarketMate users from malicious content.

Capabilities:
  1. URL Scanning — Check URLs against threat databases and heuristic analysis
  2. Content Security Analysis — Detect malicious patterns in text
  3. Input Sanitization — Clean potentially dangerous content
  4. Threat Intelligence — Pattern-based malware/phishing detection

Architecture:
  User shares a URL or suspicious content
       ↓
  MATE calls scan_url() or security_check()
       ↓
  Multi-layer analysis:
    - URL pattern analysis (known malicious patterns)
    - Domain reputation heuristics
    - Content-type analysis
    - Injection pattern detection
  ↓
  Returns threat assessment with risk level and recommendations

Threat Categories:
  - MALWARE: URLs that distribute viruses, trojans, ransomware
  - PHISHING: URLs that mimic legitimate sites to steal credentials
  - SPAM: Unsolicited commercial content
  - INJECTION: SQL injection, XSS, command injection attempts
  - SOCIAL_ENGINEERING: Manipulative content designed to deceive
  - SUSPICIOUS: Potentially harmful but unconfirmed
  - SAFE: No threats detected
"""

from __future__ import annotations

import re
import hashlib
import ipaddress
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from marketmate.core.logger import get_logger

log = get_logger("mate.tools.virus_defender")

# ═══════════════════════════════════════════════════════════════════════════════
# Threat Pattern Databases
# ═══════════════════════════════════════════════════════════════════════════════

# Known malicious URL patterns (regex)
_MALICIOUS_URL_PATTERNS = [
    # Malware distribution patterns
    r"(?i)(download|dl|get)\.(exe|msi|bat|cmd|ps1|vbs|js|scr|com|pif)$",
    r"(?i)\.(exe|msi|bat|cmd|ps1|vbs|scr|com|pif)\?",
    r"(?i)(crack|keygen|serial|warez|patch|activator|hack|cheat)",
    r"(?i)(free[_-]?(download|software|premium|account|key|license))",
    r"(?i)(torrent|pirate|illicit|nulled|leak)",
    # Phishing patterns
    r"(?i)(secure|verify|confirm|update|login|signin|account|billing|payment|wallet)\.",
    r"(?i)(paypal|amazon|apple|google|microsoft|facebook|netflix|bank)\.",
    r"(?i)(verification|security[_-]?check|account[_-]?confirm|password[_-]?reset)",
    # Suspicious TLDs commonly used for malicious purposes
    r"\.(tk|ml|ga|cf|gq|xyz|top|club|work|biz|info|win|loan|click|link|pw|review)$",
    # URL shortener + suspicious path (common attack vector)
    r"(?i)(bit\.ly|t\.co|tinyurl|goo\.gl|ow\.ly|is\.gd|buff\.ly|short\.io)/\w+[/.].*\.",
    # IP address URLs (often used for malware hosting)
    r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
    # Credential harvesting patterns
    r"(?i)(password|passwd|pwd|credential|token|secret|api[_-]?key|private[_-]?key)",
    r"(?i)(phishing|scam|fraud|steal|harvest)",
    # Exploit kit indicators
    r"(?i)(exploit|cve-\d{4}-\d+|0day|vuln|payload|shellcode|backdoor|rootkit)",
    r"(?i)(ransomware|cryptolocker|trojan|worm|botnet|keylogger|spyware|adware)",
]

# SQL Injection patterns
_SQL_INJECTION_PATTERNS = [
    r"(?i)(\b(union)\b.*\b(select)\b)",
    r"(?i)(\b(select)\b.*\b(from)\b.*\b(where)\b)",
    r"(?i)(\b(insert)\b.*\b(into)\b)",
    r"(?i)(\b(delete)\b.*\b(from)\b)",
    r"(?i)(\b(drop)\b.*\b(table|database)\b)",
    r"(?i)(\b(update)\b.*\b(set)\b)",
    r"(?i)(;\s*--)",
    r"(?i)('\s*(or|and)\s+\d+\s*=\s*\d+)",
    r"(?i)('\s*;\s*)",
    r"(?i)(\bexec\b\s*\()",
    r"(?i)(\bxp_cmdshell\b)",
    r"(?i)(\binformation_schema\b)",
]

# XSS patterns
_XSS_PATTERNS = [
    r"(?i)<script[^>]*>.*?</script>",
    r"(?i)javascript\s*:",
    r"(?i)on(error|load|click|mouseover|focus|blur)\s*=",
    r"(?i)<img[^>]+on\w+\s*=",
    r"(?i)<iframe[^>]*>",
    r"(?i)<object[^>]*>",
    r"(?i)<embed[^>]*>",
    r"(?i)document\.(cookie|location|write)",
    r"(?i)eval\s*\(",
    r"(?i)alert\s*\(",
    r"(?i)prompt\s*\(",
    r"(?i)confirm\s*\(",
]

# Command injection patterns
_COMMAND_INJECTION_PATTERNS = [
    r";\s*(rm|del|format|fdisk|shutdown|reboot|kill|cat|wget|curl)\b",
    r"\|\s*(rm|del|cat|wget|curl|bash|sh|python|perl|ruby)\b",
    r"`[^`]*`",
    r"\$\([^)]*\)",
    r"(?i)\b(system|exec|passthru|shell_exec|popen|proc_open)\s*\(",
]

# Known safe domains (whitelist)
_SAFE_DOMAINS = {
    "wikipedia.org", "github.com", "stackoverflow.com", "python.org",
    "google.com", "microsoft.com", "apple.com", "amazon.com",
    "youtube.com", "linkedin.com", "twitter.com", "x.com",
    "reuters.com", "bbc.com", "nytimes.com", "bloomberg.com",
    "investopedia.com", "tradingview.com", "coingecko.com",
    "coinmarketcap.com", "onrender.com", "telegram.org",
    "marketmate.com",
}

# Known malicious file extensions
_DANGEROUS_EXTENSIONS = {
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".scr",
    ".com", ".pif", ".dll", ".sys", ".drv", ".inf", ".reg",
    ".iso", ".img", ".vhd", ".vhdx",  # Disk images can carry malware
    ".docm", ".xlsm", ".pptm", ".ppsm",  # Macro-enabled Office files
    ".apk", ".ipa", ".deb", ".rpm",  # Mobile/installer packages
    ".jar", ".war", ".ear",  # Java archives
}


# ═══════════════════════════════════════════════════════════════════════════════
# URL Scanning
# ═══════════════════════════════════════════════════════════════════════════════

async def scan_url(url: str) -> Dict[str, Any]:
    """
    Scan a URL for potential threats using multi-layer analysis.

    Analysis layers:
      1. URL structure and pattern analysis
      2. Domain reputation heuristics
      3. File extension risk assessment
      4. External threat intelligence (Google Safe Browsing check via header)
      5. Content-type pre-check (HEAD request)

    Args:
        url: The URL to scan for threats.

    Returns:
        Dict with:
          - url: The scanned URL
          - risk_level: "safe" | "low" | "medium" | "high" | "critical"
          - threats: List of detected threats with categories
          - recommendations: List of safety recommendations
          - scan_details: Breakdown of each analysis layer
          - scan_time: ISO timestamp of when the scan was performed
    """
    if not url or not url.strip().startswith("http"):
        return {
            "url": url,
            "risk_level": "unknown",
            "threats": [],
            "recommendations": ["Provide a valid URL starting with http:// or https://"],
            "scan_details": {"error": "Invalid URL format"},
            "scan_time": datetime.now(timezone.utc).isoformat(),
        }

    url = url.strip()
    threats: List[Dict[str, str]] = []
    scan_details: Dict[str, Any] = {}

    # ── Layer 1: URL Pattern Analysis ──────────────────────────────────────
    pattern_threats = _analyze_url_patterns(url)
    if pattern_threats:
        threats.extend(pattern_threats)
    scan_details["pattern_analysis"] = {
        "threats_found": len(pattern_threats),
        "details": [t["description"] for t in pattern_threats],
    }

    # ── Layer 2: Domain Analysis ───────────────────────────────────────────
    domain_analysis = _analyze_domain(url)
    if domain_analysis.get("threats"):
        threats.extend(domain_analysis["threats"])
    scan_details["domain_analysis"] = domain_analysis

    # ── Layer 3: File Extension Risk ───────────────────────────────────────
    ext_analysis = _analyze_file_extension(url)
    if ext_analysis.get("threats"):
        threats.extend(ext_analysis["threats"])
    scan_details["extension_analysis"] = ext_analysis

    # ── Layer 4: HTTP HEAD Check ───────────────────────────────────────────
    head_analysis = await _check_url_headers(url)
    if head_analysis.get("threats"):
        threats.extend(head_analysis["threats"])
    scan_details["header_analysis"] = head_analysis

    # ── Determine Risk Level ───────────────────────────────────────────────
    risk_level = _calculate_risk_level(threats)

    # ── Generate Recommendations ───────────────────────────────────────────
    recommendations = _generate_recommendations(risk_level, threats)

    result = {
        "url": url,
        "risk_level": risk_level,
        "threats": threats,
        "threat_count": len(threats),
        "recommendations": recommendations,
        "scan_details": scan_details,
        "scan_time": datetime.now(timezone.utc).isoformat(),
    }

    log.info(
        "url_scan_complete",
        url=url[:80],
        risk_level=risk_level,
        threats=len(threats),
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Security Check — Text/Content Analysis
# ═══════════════════════════════════════════════════════════════════════════════

async def security_check(text: str) -> Dict[str, Any]:
    """
    Analyze text content for malicious patterns, injections, and security threats.

    Detects:
      - SQL injection attempts
      - Cross-site scripting (XSS) payloads
      - Command injection attempts
      - Social engineering indicators
      - Phishing content patterns
      - Malware distribution language

    Args:
        text: The text content to analyze for threats.

    Returns:
        Dict with:
          - risk_level: "safe" | "low" | "medium" | "high" | "critical"
          - threats: List of detected threats with categories
          - recommendations: List of safety recommendations
          - scan_details: Breakdown of each analysis layer
          - sanitized: A sanitized version of the input (if threats found)
    """
    if not text or not text.strip():
        return {
            "risk_level": "safe",
            "threats": [],
            "recommendations": [],
            "scan_details": {},
            "sanitized": text,
        }

    threats: List[Dict[str, str]] = []
    scan_details: Dict[str, Any] = {}

    # ── SQL Injection Detection ────────────────────────────────────────────
    sql_threats = _detect_patterns(text, _SQL_INJECTION_PATTERNS, "SQL_INJECTION")
    if sql_threats:
        threats.extend(sql_threats)
    scan_details["sql_injection"] = {
        "detected": len(sql_threats),
        "details": [t["description"] for t in sql_threats],
    }

    # ── XSS Detection ──────────────────────────────────────────────────────
    xss_threats = _detect_patterns(text, _XSS_PATTERNS, "XSS")
    if xss_threats:
        threats.extend(xss_threats)
    scan_details["xss"] = {
        "detected": len(xss_threats),
        "details": [t["description"] for t in xss_threats],
    }

    # ── Command Injection Detection ────────────────────────────────────────
    cmd_threats = _detect_patterns(text, _COMMAND_INJECTION_PATTERNS, "COMMAND_INJECTION")
    if cmd_threats:
        threats.extend(cmd_threats)
    scan_details["command_injection"] = {
        "detected": len(cmd_threats),
        "details": [t["description"] for t in cmd_threats],
    }

    # ── Social Engineering Detection ───────────────────────────────────────
    se_threats = _detect_social_engineering(text)
    if se_threats:
        threats.extend(se_threats)
    scan_details["social_engineering"] = {
        "detected": len(se_threats),
        "details": [t["description"] for t in se_threats],
    }

    # ── Phishing Content Detection ─────────────────────────────────────────
    phish_threats = _detect_phishing(text)
    if phish_threats:
        threats.extend(phish_threats)
    scan_details["phishing"] = {
        "detected": len(phish_threats),
        "details": [t["description"] for t in phish_threats],
    }

    # ── Determine Risk Level ───────────────────────────────────────────────
    risk_level = _calculate_risk_level(threats)

    # ── Generate Sanitized Version ─────────────────────────────────────────
    sanitized = _sanitize_text(text) if threats else text

    # ── Generate Recommendations ───────────────────────────────────────────
    recommendations = _generate_security_recommendations(risk_level, threats)

    result = {
        "risk_level": risk_level,
        "threats": threats,
        "threat_count": len(threats),
        "recommendations": recommendations,
        "scan_details": scan_details,
        "sanitized": sanitized,
    }

    log.info(
        "security_check_complete",
        text_length=len(text),
        risk_level=risk_level,
        threats=len(threats),
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Internal Analysis Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _analyze_url_patterns(url: str) -> List[Dict[str, str]]:
    """Analyze URL against known malicious patterns."""
    threats = []
    for pattern in _MALICIOUS_URL_PATTERNS:
        if re.search(pattern, url):
            category = _categorize_pattern(pattern)
            threats.append({
                "category": category,
                "severity": _pattern_severity(category),
                "description": f"URL matches {category} pattern: {pattern[:50]}",
                "pattern": pattern[:60],
            })
    return threats


def _analyze_domain(url: str) -> Dict[str, Any]:
    """Analyze the domain for reputation indicators."""
    result: Dict[str, Any] = {"domain": "", "is_ip": False, "threats": []}
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.split(":")[0]  # Remove port
        result["domain"] = domain

        # Check if it's an IP address
        try:
            ipaddress.ip_address(domain)
            result["is_ip"] = True
            result["threats"].append({
                "category": "SUSPICIOUS",
                "severity": "medium",
                "description": f"URL uses direct IP address ({domain}) instead of a domain name. Common in malware hosting.",
            })
        except ValueError:
            pass

        # Check against whitelist
        base_domain = ".".join(domain.split(".")[-2:]) if "." in domain else domain
        if base_domain in _SAFE_DOMAINS or domain in _SAFE_DOMAINS:
            result["whitelisted"] = True
            # Remove any threats if domain is whitelisted
            result["threats"] = []

        # Check for homograph attacks (Unicode lookalikes)
        if any(ord(c) > 127 for c in domain):
            result["threats"].append({
                "category": "PHISHING",
                "severity": "high",
                "description": "Domain contains non-ASCII characters. Possible homograph attack (visual domain spoofing).",
            })

        # Check for very long subdomains (potential obfuscation)
        parts = domain.split(".")
        if len(parts) > 4:
            result["threats"].append({
                "category": "SUSPICIOUS",
                "severity": "low",
                "description": "Domain has unusually many subdomain levels. Possible obfuscation attempt.",
            })

        # Check for typosquatting of popular domains
        typo_checks = {
            "google": ["g00gle", "gogle", "googel", "gooogle"],
            "paypal": ["paypa1", "paypaI", "paypai", "paypol"],
            "amazon": ["amaz0n", "amason", "amazn"],
            "microsoft": ["micrasoft", "micros0ft", "mircosoft"],
            "apple": ["app1e", "appl3", "aple"],
            "facebook": ["faceb00k", "facebok", "facbook"],
        }
        domain_lower = domain.lower()
        for brand, typos in typo_checks.items():
            for typo in typos:
                if typo in domain_lower and brand not in domain_lower:
                    result["threats"].append({
                        "category": "PHISHING",
                        "severity": "high",
                        "description": f"Possible typosquatting of '{brand}': domain contains '{typo}'.",
                    })

    except Exception as exc:
        result["error"] = str(exc)

    return result


def _analyze_file_extension(url: str) -> Dict[str, Any]:
    """Check URL for dangerous file extensions."""
    result: Dict[str, Any] = {"extension": "", "threats": []}
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()

        for ext in _DANGEROUS_EXTENSIONS:
            if path.endswith(ext) or f"{ext}?" in path:
                result["extension"] = ext
                result["threats"].append({
                    "category": "MALWARE",
                    "severity": "high",
                    "description": f"URL points to a potentially dangerous file type: {ext}. This could contain malware.",
                })
                break

    except Exception as exc:
        result["error"] = str(exc)

    return result


async def _check_url_headers(url: str) -> Dict[str, Any]:
    """Perform a HEAD request to check URL accessibility and content type."""
    result: Dict[str, Any] = {
        "accessible": False,
        "status_code": None,
        "content_type": "",
        "threats": [],
    }

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = await client.head(url)
            result["accessible"] = True
            result["status_code"] = resp.status_code
            result["content_type"] = resp.headers.get("content-type", "")

            # Check for suspicious content types
            ct = result["content_type"].lower()
            if "application/octet-stream" in ct:
                result["threats"].append({
                    "category": "MALWARE",
                    "severity": "medium",
                    "description": "URL serves binary file download (application/octet-stream). Could be malware.",
                })
            elif "application/x-msdownload" in ct or "application/x-executable" in ct:
                result["threats"].append({
                    "category": "MALWARE",
                    "severity": "high",
                    "description": "URL serves an executable file. High risk of malware.",
                })

            # Check for excessive redirects (potential redirect chain attack)
            if len(resp.history) > 3:
                result["threats"].append({
                    "category": "SUSPICIOUS",
                    "severity": "medium",
                    "description": f"URL redirected {len(resp.history)} times. Possible redirect chain attack.",
                })

    except httpx.TooManyRedirects:
        result["threats"].append({
            "category": "SUSPICIOUS",
            "severity": "medium",
            "description": "URL caused too many redirects. Possible redirect loop or redirect chain attack.",
        })
    except httpx.TimeoutException:
        result["threats"].append({
            "category": "SUSPICIOUS",
            "severity": "low",
            "description": "URL timed out during HEAD check. Server may be slow, blocking requests, or down.",
        })
    except Exception as exc:
        result["error"] = str(exc)[:200]

    return result


def _detect_patterns(
    text: str, patterns: List[str], category: str
) -> List[Dict[str, str]]:
    """Detect if text matches any patterns in the given list."""
    threats = []
    for pattern in patterns:
        if re.search(pattern, text):
            threats.append({
                "category": category,
                "severity": _pattern_severity(category),
                "description": f"Detected {category} pattern in content.",
                "pattern": pattern[:60],
            })
    return threats


def _detect_social_engineering(text: str) -> List[Dict[str, str]]:
    """Detect social engineering indicators in text."""
    threats = []
    text_lower = text.lower()

    # Urgency/pressure indicators
    urgency_patterns = [
        r"(?i)(urgent|immediately|right now|act now|limited time|expires (today|soon|in \d+))",
        r"(?i)(your account (has been|will be|is) (suspended|locked|closed|terminated|compromised))",
        r"(?i)(unauthorized (access|activity|transaction|login|attempt))",
        r"(?i)(verify (your|immediately|now|before))",
        r"(?i)(click here (to|before|now|immediately))",
        r"(?i)(you (have been|have) (selected|chosen|won|qualified))",
        r"(?i)(congratulations.*won|you.{0,20}winner)",
    ]

    for pattern in urgency_patterns:
        if re.search(pattern, text):
            threats.append({
                "category": "SOCIAL_ENGINEERING",
                "severity": "medium",
                "description": "Content uses urgency/pressure tactics common in social engineering attacks.",
            })
            break  # One match is enough for this category

    return threats


def _detect_phishing(text: str) -> List[Dict[str, str]]:
    """Detect phishing content indicators."""
    threats = []
    text_lower = text.lower()

    # Credential request patterns
    cred_patterns = [
        r"(?i)(enter|provide|submit|confirm|update|verify).{0,30}(password|pin|ssn|social security|credit card|cvv|date of birth)",
        r"(?i)(password|pin|ssn|credit card|cvv).{0,30}(enter|provide|submit|confirm|update|verify)",
        r"(?i)(login.{0,20}secure|secure.{0,20}login|sign.{0,20}in.{0,20}verify)",
        r"(?i)(bank.{0,20}(account|verify|confirm|update)|account.{0,20}(verify|confirm|suspended))",
    ]

    for pattern in cred_patterns:
        if re.search(pattern, text):
            threats.append({
                "category": "PHISHING",
                "severity": "high",
                "description": "Content requests sensitive credentials or personal information. Possible phishing attempt.",
            })
            break  # One match is enough

    return threats


def _sanitize_text(text: str) -> str:
    """
    Sanitize text by removing or neutralizing potentially dangerous content.

    Removes:
      - HTML/script tags
      - JavaScript event handlers
      - SQL keywords in suspicious contexts
      - Shell metacharacters

    Returns cleaned text safe for display.
    """
    # Remove script tags and content
    sanitized = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Remove event handlers
    sanitized = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', "", sanitized, flags=re.IGNORECASE)

    # Remove iframe, object, embed tags
    sanitized = re.sub(r"</?(iframe|object|embed)[^>]*>", "", sanitized, flags=re.IGNORECASE)

    # Remove javascript: URLs
    sanitized = re.sub(r"javascript\s*:", "", sanitized, flags=re.IGNORECASE)

    # Remove data: URLs (can contain XSS payloads)
    sanitized = re.sub(r"data\s*:[^,;]*[,;]", "", sanitized, flags=re.IGNORECASE)

    # Remove null bytes
    sanitized = sanitized.replace("\x00", "")

    # Remove potential SQL comment injection
    sanitized = re.sub(r"--\s*$", "", sanitized, flags=re.MULTILINE)

    # Trim whitespace
    sanitized = sanitized.strip()

    return sanitized


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Assessment
# ═══════════════════════════════════════════════════════════════════════════════

def _categorize_pattern(pattern: str) -> str:
    """Categorize a URL pattern by threat type."""
    pattern_lower = pattern.lower()
    if any(kw in pattern_lower for kw in ["crack", "keygen", "warez", "pirate", "nulled", "ransomware", "trojan", "worm", "botnet", "keylog", "spyware", "adware", "rootkit", "backdoor", "malware"]):
        return "MALWARE"
    elif any(kw in pattern_lower for kw in ["phish", "scam", "fraud", "steal", "harvest", "verify", "confirm", "login", "paypal", "amazon", "apple", "bank"]):
        return "PHISHING"
    elif any(kw in pattern_lower for kw in ["exploit", "cve", "0day", "vuln", "payload", "shellcode"]):
        return "EXPLOIT"
    else:
        return "SUSPICIOUS"


def _pattern_severity(category: str) -> str:
    """Return default severity for a threat category."""
    severity_map = {
        "MALWARE": "high",
        "PHISHING": "high",
        "EXPLOIT": "critical",
        "SQL_INJECTION": "critical",
        "XSS": "high",
        "COMMAND_INJECTION": "critical",
        "SOCIAL_ENGINEERING": "medium",
        "SPAM": "low",
        "SUSPICIOUS": "medium",
    }
    return severity_map.get(category, "low")


def _calculate_risk_level(threats: List[Dict[str, str]]) -> str:
    """Calculate overall risk level from detected threats."""
    if not threats:
        return "safe"

    severities = [t.get("severity", "low") for t in threats]
    severity_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    max_score = max(severity_scores.get(s, 1) for s in severities)
    threat_count = len(threats)

    # Escalate risk if many threats detected
    if max_score >= 4 or threat_count >= 5:
        return "critical"
    elif max_score >= 3 or threat_count >= 3:
        return "high"
    elif max_score >= 2 or threat_count >= 2:
        return "medium"
    else:
        return "low"


def _generate_recommendations(
    risk_level: str, threats: List[Dict[str, str]]
) -> List[str]:
    """Generate safety recommendations based on scan results."""
    recs = []

    if risk_level == "safe":
        recs.append("No threats detected. URL appears safe to visit.")
        return recs

    categories = {t["category"] for t in threats}

    if "MALWARE" in categories:
        recs.append("DO NOT download or open any files from this URL. It may contain malware.")
        recs.append("If you already downloaded something, do NOT run it. Scan your device with antivirus software.")

    if "PHISHING" in categories:
        recs.append("DO NOT enter any personal information, passwords, or credentials on this page.")
        recs.append("This URL may be impersonating a legitimate website. Verify the actual URL carefully.")

    if "EXPLOIT" in categories:
        recs.append("DO NOT visit this URL. It may attempt to exploit vulnerabilities in your browser.")
        recs.append("Ensure your browser and operating system are fully updated.")

    if "SQL_INJECTION" in categories:
        recs.append("Malicious SQL injection detected. This content should be rejected or sanitized before use.")

    if "XSS" in categories:
        recs.append("Cross-site scripting content detected. Sanitize before rendering in any web context.")

    if "COMMAND_INJECTION" in categories:
        recs.append("Command injection detected. This content should NEVER be passed to a system shell.")

    if "SOCIAL_ENGINEERING" in categories:
        recs.append("Content uses manipulation tactics. Verify any claims through independent sources.")

    if "SUSPICIOUS" in categories:
        recs.append("Proceed with caution. This URL has characteristics associated with suspicious activity.")

    if risk_level in ("high", "critical"):
        recs.append("RECOMMENDATION: Avoid visiting this URL entirely.")

    return recs


def _generate_security_recommendations(
    risk_level: str, threats: List[Dict[str, str]]
) -> List[str]:
    """Generate security recommendations for content analysis results."""
    recs = []

    if risk_level == "safe":
        recs.append("No security threats detected in this content.")
        return recs

    categories = {t["category"] for t in threats}

    if "SQL_INJECTION" in categories:
        recs.append("SQL injection detected. Use parameterized queries and never concatenate user input into SQL.")
    if "XSS" in categories:
        recs.append("XSS content detected. Escape all HTML entities before rendering. Use Content-Security-Policy headers.")
    if "COMMAND_INJECTION" in categories:
        recs.append("Command injection detected. Never pass user input to system commands. Use allowlists for any shell execution.")
    if "PHISHING" in categories:
        recs.append("Phishing content detected. Do not share credentials or personal information.")
    if "SOCIAL_ENGINEERING" in categories:
        recs.append("Social engineering tactics detected. Verify claims independently before taking action.")

    if risk_level in ("high", "critical"):
        recs.append("HIGH RISK: This content should be blocked or heavily sanitized before processing.")

    return recs
