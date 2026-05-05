from __future__ import annotations

case_search_prompt = """
You are doing deep editorial research to build a high-quality CSV of AI incident records for import into a PostgreSQL-backed incident log.

Your job is to research real-world AI-related incidents from the calendar year 2023 only and output a single raw CSV file only.

Scope rules:
- Include only incidents whose incident date falls in 2023
- Do not include 2022 incidents
- Do not include 2024 or later incidents
- If a story was reported in 2024 but the incident itself happened in 2023, it may be included if the 2023 incident date is defensible
- If the exact day is uncertain but the incident clearly happened in 2023, choose the most defensible date and explain the uncertainty in notes

Output requirements:
- Return only one fenced ```csv block
- Do not include explanations before or after the CSV
- Do not include markdown tables
- Do not include JSON
- Do not include commentary outside the CSV
- The CSV must be valid and importable
- Produce between 120 and 150 rows
- Every row must represent one distinct real-world AI incident from 2023
- Prefer strong evidence and useful editorial breadth over trying to hit the maximum row count at the expense of quality

Use this exact CSV header:

ref_number,incident_id,company,incident_date,incident_topic,incident_description,mapped_claim,source_links,legitimacy_flag,confidence_level,notes

Field definitions:
- ref_number:
  - Integer sequence starting at 1
  - Must be unique within the file

- incident_id:
  - Stable unique string identifier for the incident
  - Use slug-like IDs such as:
    - inc-legal-001
    - inc-av-002
    - inc-health-003
  - Must be unique within the file
  - Keep IDs short, stable, lowercase, hyphenated
  - IDs should be specific enough to avoid collisions across many 2023 incidents

- company:
  - Main company, institution, or actor involved
  - Examples:
    - OpenAI
    - Cruise
    - UnitedHealthcare
    - Detroit Police
    - Workday
  - Use the most recognizable public-facing name
  - If the incident centers on a government body, police department, school district, military actor, court matter, or platform ecosystem, use the clearest primary actor name

- incident_date:
  - Must use YYYY-MM-DD
  - Must refer to the incident date, not just an article publication date
  - Use the best-supported date from available sources
  - If only month/year are clearly supported, choose a defensible date within that month and explain the limitation in notes

- incident_topic:
  - Short normalized category label
  - Prefer labels like:
    - legal hallucination
    - safety failure
    - operational failure
    - privacy
    - automated adjudication
    - algorithmic bias
    - facial recognition
    - synthetic media
    - misinformation
    - data leakage
    - surveillance
    - copyright
    - defamation
    - infrastructure
    - education failure
    - content moderation
    - public sector
  - Keep labels consistent across rows
  - Reuse the same label for similar incidents instead of inventing near-duplicates

- incident_description:
  - One concise factual sentence
  - No hype
  - No speculation
  - No opinionated language
  - Should summarize:
    - what happened
    - who/what was affected
    - why it matters
  - Keep it specific enough for a public incident feed
  - Do not overload with too many clauses

- mapped_claim:
  - Leave blank unless there is a very clear matching claim ID already known
  - Do not invent claim IDs
  - Blank is acceptable and preferred if uncertain

- source_links:
  - CRITICAL: Every URL in source_links MUST be a first-hand / primary source
  - Primary sources:
    - official government or regulator pages
    - court filings, sanction orders, dockets, complaints, judgments, tribunal decisions
    - company disclosures, incident reports, outage notices, official blog posts, press releases
    - agency actions, settlements, consent orders, enforcement notices
    - official university, school, hospital, police, or public-body statements
    - direct academic papers or official research publications when the incident is research-driven
    - NHTSA records, recall notices, DMV collision reports, EEOC filings
    - original investigative journalism that broke the story with primary evidence
  - Second-hand sources:
    - rewrites, opinion pieces, blog commentary, and analysis articles that only summarize a primary source
  - All rows require at least 3 distinct URLs total
  - All rows require at least 1 primary source whenever a defensible primary source should exist
  - If a likely incident has weaker source coverage, it must be marked REVIEW, and the notes field explicitly says the stronger primary source was not found
  - Separate URLs with: " | "
  - Every URL must begin with http:// or https://
  - Use only direct article/document URLs, never homepages
  - BANNED sources (never include these as source_links):
    - https://incidentdatabase.ai/ or any URL under incidentdatabase.ai
    - Any incident aggregator database, tracker, or index site that merely catalogues incidents reported elsewhere
    - Second-hand rewrites, opinion pieces, blog commentary, or analysis articles that only summarize a primary source
    - Generic homepages, search result pages, or broad topic index pages
  - Second-hand reporting, news rewrites, or commentary articles do NOT count as primary sources and must NOT be included
  - If you cannot find at least 3 distinct source URLs for an incident, do NOT include that incident — omit the row entirely
  - Avoid duplicated URLs
  - Avoid broken links
  - Replace generic homepages with direct document links whenever possible

- legitimacy_flag:
  - Must be one of:
    - ACCEPT
    - REVIEW
    - REJECT
  - Meanings:
    - ACCEPT = strong evidence with at least 2 verifiable primary sources confirming this is a legitimate AI incident
    - REVIEW = likely relevant but has date uncertainty, framing concerns, or primary sources are borderline (e.g. official blog post vs formal report)
    - REJECT = probably not suitable, not actually an AI incident, cannot find 2 primary sources, duplicate, or misleading

- confidence_level:
  - Must be one of:
    - low
    - medium
    - high
  - This is confidence in the editorial judgment and source support, not general model confidence

- notes:
  - Short editorial note
  - Mention uncertainty, duplicate risk, date ambiguity, or why the row is especially strong
  - Note the type of primary sources used (e.g. "court filing + NHTSA record", "company disclosure + regulator notice")
  - Can be blank, but prefer helpful notes when there is any ambiguity

Research quality rules:
- Only include incidents with meaningful evidence that AI was materially involved
- Do not include vague "AI might have contributed" stories unless sources clearly support it
- Do not include generic layoffs, product launches, opinion essays, or broad industry trend pieces unless there is a concrete incident
- Do not include duplicate incidents framed from multiple outlets as separate rows
- If multiple articles cover the same underlying event, combine them into one incident row
- Favor canonical incidents that are useful in a public incident database
- Prefer breadth across 2023 sectors:
  - generative AI
  - legal
  - autonomous vehicles
  - healthcare
  - hiring
  - policing/facial recognition
  - media/deepfakes
  - finance/insurance
  - education
  - public sector
  - infrastructure
  - social platforms
  - copyright and publishing
- Include both high-profile incidents and well-documented less-famous incidents
- Do not fabricate facts
- If evidence is weak, mark REVIEW or REJECT instead of overstating
- Be conservative
- Avoid stuffing the file with borderline rows just to reach 150

2023-specific guidance:
- The row is eligible only if the incident itself belongs in 2023
- A lawsuit filed in 2023 about conduct that clearly occurred earlier may still qualify if the incident record is reasonably anchored to a 2023 development, filing, enforcement action, disclosure, or event
- If there are multiple key dates, choose the one that best represents when the incident entered the real world in a meaningful, documentable way, and explain in notes if needed
- Be consistent in how dates are chosen

Validation rules:
- No duplicate incident_id values
- No duplicate rows describing the same event
- All required columns must be present
- incident_date must be valid YYYY-MM-DD
- source_links must contain at least 3 distinct valid URLs total (no aggregators, no second-hand rewrites)
- source_links must NOT contain any URL from incidentdatabase.ai
- legitimacy_flag must be exactly ACCEPT, REVIEW, or REJECT
- confidence_level must be exactly low, medium, or high
- Escape CSV correctly:
  - quote fields when needed
  - preserve commas inside quoted text
  - preserve quotes correctly

Editorial guidance for scoring:
- Use ACCEPT/high for incidents backed by 3+ strong sources with primary-source support (court filings, regulator records, official disclosures)
- Use ACCEPT/medium for likely real incidents with 3 sources but some date or framing ambiguity
- Use REVIEW/high or REVIEW/medium for incidents that seem relevant but primary sources are borderline
- Use REJECT when the event is too weak, too speculative, duplicate, misleading, cannot meet the 2-primary-source minimum, or not actually an AI incident

Primary source requirements by category:
- Legal hallucination: direct court filings, dockets, judicial opinions, bar association records
- Healthcare denial / hiring bias / government: complaints, settlements, agency actions, EEOC filings, enforcement notices, institutional statements
- Autonomous vehicles: NHTSA records, recall notices, DMV collision reports, regulator enforcement actions
- Deepfakes / synthetic media: law enforcement reports, platform takedown records, official institutional statements
- Privacy / data leakage: regulator enforcement actions, company breach disclosures, data protection authority decisions
- Education / public sector: official university or school district statements, government audit reports, inspector general reports
- Copyright / publishing: court filings, Copyright Office records, licensing disputes with direct documentation
- NEVER use incidentdatabase.ai, AI Incident Database, or any third-party incident aggregator as a source
- NEVER use homepages, generic search results, or broad topic indexes as sources

Target quality:
- Best outcome is a clean, serious 120-150 row 2023 incident corpus
- It is better to include 122 strong rows than 150 padded rows
- Aim for a file that an editor could realistically review and import with limited cleanup

Before final output, silently self-check:
- Is each row a distinct 2023 incident?
- Does each row have at least 3 distinct source URLs?
- Are ALL URLs genuine first-hand primary sources (not rewrites, not aggregators, not commentary)?
- Have I accidentally included any incidentdatabase.ai URL?
- Are any homepage links still present where a direct document link should be used?
- Are any dates too uncertain without a note?
- Are any incident descriptions too vague?
- Are legitimacy_flag and confidence_level too generous?
- Is the file genuinely 2023-only?
- Would every source URL survive editorial fact-checking as a verifiable primary record?
- Are you highly confident that every source URL is currently live and would return an HTTP 200 OK status?

Final instruction:
Return exactly one fenced csv block and nothing else.
""".strip()

__all__ = ["case_search_prompt"]
