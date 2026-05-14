"""Domain-agnostic LLM prompt templates for blog generation.

These prompts adapt to any industry by injecting context from:
- Organization.industry (e.g., "EOR", "Financial Services", "Healthcare")
- Project.master_prompt (e.g., "Monitor employment regulations")
- Jurisdiction.prompt (e.g., "Focus on minimum wage laws")

The same prompts generate:
- Employment law guides for HR professionals and compliance teams
- Banking regulation summaries for compliance officers
- Healthcare compliance briefs for administrators
- Environmental regulation guides for sustainability teams

No hardcoded domain assumptions. Context is resolved at runtime
by traversing: Jurisdiction → Project → Organization.

IMPORTANT: Generated content is industry-generic and should NOT reference
any specific organization, company, or client. Content is suitable for
public-facing SEO pages targeting professionals in the {industry} industry."""

BLOG_SYSTEM_PROMPT = """You are an expert content writer specializing in \
regulatory compliance, policy analysis, and industry-specific guidance \
for the {industry} industry.

DOMAIN CONTEXT (tailor your content to this):
- Industry: {industry}
- Project Focus: {project_prompt}
- Jurisdiction Monitoring Scope: {jurisdiction_prompt}

CRITICAL RULES:
1. You must ONLY use the facts provided in the Context section below.
2. Do NOT invent, assume, or infer any data not explicitly present \
in the Context.
3. Tailor the writing style, terminology, and section structure to \
match the Industry and Project Focus above. For example:
   - EOR industry → employment law guide for HR professionals
   - Financial Services → banking regulation summary for compliance officers
   - Healthcare → healthcare regulation brief for administrators
   - Sustainability → environmental compliance guide for ESG teams
4. If a data point that would typically be expected for this industry \
is missing from the Context, include a section stating: \
"Information currently unavailable — pending regulatory data collection."
5. Do NOT reference the source of the data or mention "the context" \
in your output.
6. Write in a professional, informative tone appropriate for the \
target industry audience.
7. Structure content with clear Markdown headings (##), bullet points, \
and tables where appropriate.
8. Include a brief executive summary at the top.

OUTPUT FORMAT:
Return a JSON object with these exact keys:
- title: A clear, SEO-friendly title relevant to the industry and \
jurisdiction (10-200 characters)
- meta_description: A 120-160 character SEO meta description
- keywords: An array of 3-8 relevant SEO keywords for the specific domain
- content: The full blog post body in Markdown format (minimum 100 characters)

All content must be grounded exclusively in the Context provided. \
No hallucinations, no assumptions, no external knowledge."""


BLOG_CONTENT_PROMPT = """Generate a comprehensive regulatory compliance guide \
for {jurisdiction_name}.

Industry: {industry}
Project Focus: {project_prompt}

Context (ONLY use these confirmed facts — the current Golden Record):
---
{formatted_state}
---

Regulatory Change History (chronological log of accepted changes to this jurisdiction):
---
{history_context}
---

The guide should:
1. Cover all regulatory areas present in the Context.
2. Organize sections based on the actual data fields available — do NOT \
assume a predefined section structure.
3. For any topic commonly expected in the "{industry}" industry that is \
NOT covered in the Context, include a placeholder section noting the \
information is pending.
4. Use tables for comparison data where appropriate.
5. Adapt terminology and depth to the target industry audience.
6. Provide actionable insights for professionals working in {jurisdiction_name}.
7. ALWAYS include a final section titled exactly "## Regulatory Change History" \
containing a Markdown table with columns: \
| Field | Previous Value | New Value | Date Changed | Change Reason |. \
Populate rows only from the Regulatory Change History block above. \
If the history block contains "No changes recorded", write one table row \
with all cells set to "—" and add a note: \
"No regulatory changes have been recorded yet for this jurisdiction."

Remember: Only use information from the Context and Regulatory Change History \
above. If something is not mentioned, either omit it or explicitly mark it as \
"pending data collection"."""


BLOG_PLACEHOLDER_CONTENT = """# {jurisdiction_name} Compliance Guide — Coming Soon

## Overview

We are actively collecting and verifying regulatory data for {jurisdiction_name}. \
This guide will be available once our systems complete the initial data extraction \
and validation process.

## What to Expect

This guide will provide comprehensive, up-to-date information on:
- Key regulatory requirements for the {industry} industry
- Compliance obligations specific to {jurisdiction_name}
- Actionable insights for {project_prompt}

## Next Steps

Check back soon for the latest regulatory updates. Our team is working to ensure \
all information is accurate and current before publication.

---

*This content is automatically generated from verified regulatory sources and is \
updated whenever new regulations are published or existing rules change.*
"""

BLOG_SYSTEM_PROMPT = """You are an expert content writer specializing in \
regulatory compliance, policy analysis, and industry-specific guidance.

DOMAIN CONTEXT (tailor your content to this):
- Industry: {industry}
- Project Focus: {project_prompt}
- Jurisdiction Monitoring Scope: {jurisdiction_prompt}

CRITICAL RULES:
1. You must ONLY use the facts provided in the Context section below.
2. Do NOT invent, assume, or infer any data not explicitly present \
in the Context.
3. Tailor the writing style, terminology, and section structure to \
match the Industry and Project Focus above. For example:
   - An EOR company → employment law guide for HR professionals
   - A fintech company → banking regulation summary for compliance officers
   - A healthcare org → healthcare regulation brief for administrators
4. If a data point that would typically be expected for this industry/domain \
is missing from the Context, include a section for it stating: \
"Information currently unavailable — pending regulatory data collection."
5. Do NOT reference the source of the data or mention "the context" \
in your output.
6. Write in a professional, informative tone appropriate for the \
target industry audience.
7. Structure the content with clear Markdown headings (##), bullet points, \
and tables where appropriate.
8. Include a brief executive summary at the top.

OUTPUT FORMAT:
Return a JSON object with these exact keys:
- title: A clear, SEO-friendly title relevant to the industry and \
jurisdiction (10-200 characters)
- meta_description: A 120-160 character SEO meta description
- keywords: An array of 3-8 relevant SEO keywords for the specific domain
- content: The full blog post body in Markdown format (minimum 100 characters)

All content must be grounded exclusively in the Context provided. \
No hallucinations, no assumptions, no external knowledge."""


BLOG_CONTENT_PROMPT = """Generate a comprehensive regulatory compliance guide \
for the jurisdiction: {jurisdiction_name}.

Industry: {industry}
Project Focus: {project_prompt}

Context (ONLY use these confirmed facts — the current Golden Record):
---
{formatted_state}
---

Regulatory Change History (chronological log of accepted changes to this jurisdiction):
---
{history_context}
---

The guide should:
1. Cover all regulatory areas present in the Context.
2. Organize sections based on the actual data fields available — do NOT \
assume a predefined section structure.
3. For any topic commonly expected in the "{industry}" industry that is \
NOT covered in the Context, include a placeholder section noting the \
information is pending.
4. Use tables for comparison data where appropriate.
5. Adapt terminology and depth to the target industry audience.
6. Provide actionable insights relevant to {industry} organizations \
operating in {jurisdiction_name}.
7. ALWAYS include a final section titled exactly "## Regulatory Change History" \
containing a Markdown table with columns: \
| Field | Previous Value | New Value | Date Changed | Change Reason |. \
Populate rows only from the Regulatory Change History block above. \
If the history block contains "No changes recorded", write one table row \
with all cells set to "—" and add a note: \
"No regulatory changes have been recorded yet for this jurisdiction."

Remember: Only use information from the Context and Regulatory Change History \
above. If something is not mentioned, either omit it or explicitly mark it as \
"pending data collection"."""


BLOG_PLACEHOLDER_CONTENT = """# {jurisdiction_name} Compliance Guide — Coming Soon

## Overview

We are actively collecting and verifying regulatory data for {jurisdiction_name}. \
This guide will be available once our systems complete the initial data extraction \
and validation process.

## What to Expect

This guide will provide comprehensive, up-to-date information on:
- Key regulatory requirements for {industry} organizations
- Compliance obligations specific to {jurisdiction_name}
- Actionable insights for {industry} operations

## Next Steps

Check back soon or enable notifications to be alerted when this guide is published. \
Our team is working to ensure all information is accurate and current before release.

---

*This content is automatically generated from verified regulatory sources and is \
updated whenever new regulations are published or existing rules change.*
"""
