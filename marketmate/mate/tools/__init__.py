"""
marketmate.mate.tools
─────────────────────
External tool integrations for MATE's tool-calling agent.

These tools extend MATE beyond the 7 internal brains,
enabling web search, page reading, security
scanning, and other external capabilities.

MATE never touches the internet directly — it calls tools.
Tools are the ONLY way MATE accesses external information.
This is controlled agency: approved tools, approved access.

Tools:
  - web_search:     Multi-source web search with fallback
  - news_search:    News search with fallback
  - read_url:       Web page content extraction
  - scan_url:       URL threat scanning (malware, phishing, viruses)
  - security_check: Text content security analysis
"""
