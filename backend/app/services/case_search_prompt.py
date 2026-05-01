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
  - At least 3 distinct valid URLs per row
  - Separate URLs with: " | "
  - Every URL must begin with http:// or https://
  - Prefer direct article/document URLs, not homepages
  - Source types:
    - Primary sources:
      - official government or regulator pages
      - court filings, sanction orders, dockets, complaints, judgments, tribunal decisions
      - company disclosures, incident reports, outage notices, official blog disclosures
      - agency actions, settlements, consent orders, enforcement notices
      - official university, school, hospital, police, or public-body statements
      - direct academic papers or official research publications when the incident is research-driven
    - Second-hand sources:
      - major reporting
      - reputable trade publications
      - law blogs, research blogs, analysis writeups, incident trackers, and commentary
      - any article summarizing or quoting a primary source rather than being the primary record itself
  - require at least 3 distinct URLs total
  - require at least 1 primary source whenever a defensible primary source should exist
  - If no primary source is reasonably available, second-hand-only rows may remain in scope only if they are strongly sourced, marked REVIEW, and the notes field explicitly says the stronger primary source was not found
  - Generic homepages, search pages, or index pages should not count as the required primary source when a direct filing, report, or article URL exists
  - Avoid duplicated URLs
  - Avoid broken links
  - When possible include at least one primary source
  - Replace generic homepages with direct links whenever possible

- legitimacy_flag:
  - Must be one of:
    - ACCEPT
    - REVIEW
    - REJECT
  - Meanings:
    - ACCEPT = strong evidence this is a legitimate AI incident worth tracking
    - REVIEW = likely relevant but has ambiguity, weak sourcing, date uncertainty, framing concerns, or lacks a primary source where one should exist
    - REJECT = probably not suitable, not actually an AI incident, too weakly sourced, duplicate, or misleading

- confidence_level:
  - Must be one of:
    - low
    - medium
    - high
  - This is confidence in the editorial judgment and source support, not general model confidence

- notes:
  - Short editorial note
  - Mention uncertainty, missing stronger primary source, duplicate risk, date ambiguity, or why the row is especially strong
  - If a row relies only on second-hand sourcing, explicitly say that a stronger primary source was not found
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
- source_links must contain at least 3 distinct valid URLs
- legitimacy_flag must be exactly ACCEPT, REVIEW, or REJECT
- confidence_level must be exactly low, medium, or high
- Escape CSV correctly:
  - quote fields when needed
  - preserve commas inside quoted text
  - preserve quotes correctly

Editorial guidance for scoring:
- Use ACCEPT/high for incidents with strong primary evidence or multiple highly reliable sources
- Use ACCEPT/medium for likely real incidents with decent support but some ambiguity
- Use REVIEW/high or REVIEW/medium for incidents that seem relevant but need editor judgment
- Use REVIEW when the source stack is strong overall but only second-hand sources were found and a defensible primary source could not be located
- Use REJECT when the event is too weak, too speculative, duplicate, misleading, or not actually an AI incident

Important sourcing preferences:
- Prefer direct court filings, regulator notices, EEOC actions, NHTSA records, recall notices, company disclosures, academic papers, or official incident records when available
- For legal hallucination incidents, prefer direct court materials first, then legal analysis with primary references
- For healthcare denial, hiring bias, and government incidents, prefer complaints, settlements, agency actions, enforcement notices, or institutional statements first
- For autonomous vehicle incidents, prefer regulator records, collision reports, recall notices, DMV or NHTSA records, and strong reporting
- For deepfake, platform, and education incidents, prefer direct institutional evidence where available, otherwise strong reporting with REVIEW
- Avoid using homepages, generic search results, or broad topic indexes when a direct incident-specific URL exists

Target quality:
- Best outcome is a clean, serious 120-150 row 2023 incident corpus
- It is better to include 122 strong rows than 150 padded rows
- Aim for a file that an editor could realistically review and import with limited cleanup

Before final output, silently self-check:
- Is each row a distinct 2023 incident?
- Does each row have 3 or more real URLs?
- Are any homepage links still present where a direct article link should be used?
- Are any dates too uncertain without a note?
- Are any incident descriptions too vague?
- Are legitimacy_flag and confidence_level too generous?
- Is the file genuinely 2023-only?

Final instruction:
Return exactly one fenced csv block and nothing else.
""".strip()

__all__ = ["case_search_prompt"]
