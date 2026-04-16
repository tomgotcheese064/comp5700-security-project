# zero-shot

You are an information extraction system.

Extract REAL key data elements (KDEs) from the document below.

IMPORTANT RULES:
- Ignore table of contents text.
- Ignore page numbers.
- Ignore dotted leader lines.
- Use only real security requirement content from the document.
- Do not use placeholders.
- Do not output "...", "element name", "requirement 1", "example", or similar.
- Identify 3 to 8 real key data elements if possible.
- Group exact document text under the correct element.
- Return ONLY valid JSON.
- No markdown fences.
- No explanations.
- The top-level keys must be element1, element2, element3, etc.

Required JSON structure:
{
  "element1": {
    "name": "real key data element",
    "requirements": [
      "exact requirement text from the document"
    ]
  }
}

Document:
<DOCUMENT_TEXT>


# few-shot

You are an information extraction system.

Here is a REAL example of the kind of output required.

Example input:
2.1.1 Enable audit logs (Manual)
2.2.1 Configure alerting (Automated)
2.3.1 Define security policies (Manual)

Example output:
{
  "element1": {
    "name": "Audit Logs",
    "requirements": [
      "2.1.1 Enable audit logs (Manual)"
    ]
  },
  "element2": {
    "name": "Alerting",
    "requirements": [
      "2.2.1 Configure alerting (Automated)"
    ]
  },
  "element3": {
    "name": "Security Policies",
    "requirements": [
      "2.3.1 Define security policies (Manual)"
    ]
  }
}

Now extract REAL KDEs from the following document.

Rules:
- Use only real content from the document.
- Ignore table of contents, page numbers, and dotted leader lines.
- Do not use placeholders.
- Return ONLY valid JSON.
- No markdown fences.
- No explanations.
- Top-level keys must be element1, element2, element3, etc.

Document:
<DOCUMENT_TEXT>


# chain-of-thought

You are an information extraction system.

Task:
1. Read the document.
2. Identify real security-related key data elements.
3. Group exact requirement text under the right element.
4. Output only the final JSON answer.

Rules:
- Use only real content from the document.
- Ignore table of contents, page numbers, and dotted leader lines.
- Do not use placeholders.
- Return ONLY valid JSON.
- No markdown fences.
- No explanations.
- Top-level keys must be element1, element2, element3, etc.

Required JSON structure:
{
  "element1": {
    "name": "real key data element",
    "requirements": [
      "exact requirement text from the document"
    ]
  }
}

Document:
<DOCUMENT_TEXT>