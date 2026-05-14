"""Shared constants for AI-powered change detection.

This module contains reusable prompt fragments and rules for semantic change
detection to ensure consistency across different services.
"""

# Cosmetic change detection rules used by both DiffAIService and DataPageService
COSMETIC_CHANGE_RULES = """
COSMETIC CHANGES TO IGNORE (DO NOT REPORT):
- Date format variations: "31st of December" vs "December 31st" = SAME DATE
- Currency formatting: "$10,500.00" vs "$10500" = SAME AMOUNT
- Code additions/removals: "License (LIC-001)" vs "License" = SAME MEANING
- Punctuation: semicolons vs commas, periods, etc.
- Case changes: "DAILY" vs "daily" = SAME WORD
- Whitespace: extra spaces, line breaks, etc.

ONLY REPORT if the ACTUAL INFORMATION changed (different date, different amount,
different requirement).
"""

# Examples for AI prompts
COSMETIC_CHANGE_EXAMPLES = """
EXAMPLES:
- "31st of December" vs "December 31st" = COSMETIC (same date)
- "$10,500" vs "$15,500" = SIGNIFICANT (different amounts)
- "License (LIC-001)" vs "License" = COSMETIC (code removed, same meaning)
- Semicolons vs commas = COSMETIC (punctuation)
- "DAILY" vs "daily" = COSMETIC (case only)
"""


def build_change_detection_prompt(
    monitoring_instruction: str,
    old_json: str,
    new_json: str,
    field_name_mapping: dict | None = None,
) -> str:
    """Build the change detection prompt for LLM.

    Args:
        monitoring_instruction: User goal for change detection.
        old_json: Serialized old data (JSON string).
        new_json: Serialized new data (JSON string).
        field_name_mapping: Optional mapping of internal to display names.

    Returns:
        Complete prompt string for change detection.
    """
    import json

    mapping_json = json.dumps(field_name_mapping or {}, indent=2)

    return f"""You are a Regulatory Compliance Auditor.
TASK: Compare OLD vs NEW data and determine if meaningful changes occurred.
USER GOAL: "{monitoring_instruction}"

CRITICAL INSTRUCTIONS:
- The data has been NORMALIZED - field names are already aligned for comparison
- Focus ONLY on VALUE changes, NOT field name differences
- Report factual/material changes with EXACT VALUES (e.g., "$500 to $600")
- DO NOT mention structural changes, field renaming, or key reorganization
- MANDATORY: Provide specific details in BOTH change_summary AND field_changes array
- VAGUE SUMMARIES ARE UNACCEPTABLE

OUTPUT RULES (CRITICAL):
1. Return ONLY valid JSON matching this exact schema:
{{
  "has_changed": true|false,
  "change_summary": "Specific summary with EXACT old→new values for key changes",
  "risk_level": "LOW"|"MEDIUM"|"HIGH",
  "field_changes": [
    {{
      "field_name": "canonical_field_name",
      "display_name": "Human Readable Field Name",
      "old_value": "exact previous value",
      "new_value": "exact new value",
      "change_type": "modified"|"added"|"removed",
      "change_description": "Human-readable sentence describing this specific change"
    }}
  ]
}}

2. CONSISTENCY RULE: Use EXACT same field names/structure every time.
   - However, for the SUMMARY text, use human-readable field names if a mapping is provided.

FIELD NAME MAPPING (Use these display names in SUMMARY and FIELD NAME output):
{mapping_json}

⚠️ CHANGE DESCRIPTION RULES (MANDATORY - DO NOT SKIP):
- For EACH field_name, you MUST generate a change_description
- This is a REQUIRED field - responses without it will be REJECTED
- The change_description MUST:
  * Use human-readable field names (convert snake_case to Title Case)
  * Be a complete sentence with exact old and new values
  * Example: "Standard License Fee increased from $32,500.00 to $33,500.00"
  * NOT: "standard_license_fee modified: $32,500 → $33,500"

FORMATTING RULES:
- When writing the `change_summary`, ALWAYS replace the internal key with the MAPPED
  DISPLAY NAME (if available).
- If no mapping exists, humanize the key (e.g., "annual_audit_deadline" ->
  "Annual Audit Deadline").
- Do NOT use underscores in the summary or change_description.

CHANGE DETECTION RULES:
- Ignore formatting, whitespace, or metadata differences
- Only report changes that affect the USER GOAL
- Missing or null fields in both versions are NOT changes
- risk_level: LOW for minor changes, MEDIUM for significant value changes, HIGH for
  critical compliance changes

{COSMETIC_CHANGE_RULES}

EXAMPLES OF GOOD vs BAD SUMMARIES:
❌ BAD (too vague): "Factual changes in the fee schedule and compliance requirements"
✅ GOOD (specific): "Standard License fee increased from $5,500 to $7,500;
  Enterprise Renewal fee decreased from $10,000 to $5,000"

❌ BAD (mentions structure): "Field name changed from visa_price to price_visa"
✅ GOOD (values only): "Visa price increased from $500 to $600"

❌ BAD (no numbers): "The deadline was changed"
✅ GOOD (exact values): "Audit deadline changed from 'December 31st' to 'January 15th'"

EXAMPLES OF GOOD FIELD CHANGES:
✅ GOOD:
{{
  "field_name": "fee_schedule_fee_1",
  "display_name": "Standard License Fee",
  "old_value": "$32,500.00",
  "new_value": "$33,500.00",
  "change_type": "modified",
  "change_description": "Standard License Fee increased from $32,500.00 to $33,500.00"
}}

❌ BAD (uses technical name in description):
{{
  "field_name": "fee_schedule_fee_1",
  "display_name": "Standard License Fee",
  "change_description": "fee_schedule_fee_1 modified: $32,500.00 → $33,500.00"
}}

REQUIRED: change_summary MUST include the actual old and new values for any changed fields.

--- OLD DATA (Normalized) ---
{old_json}

--- NEW DATA (Normalized) ---
{new_json}
"""
