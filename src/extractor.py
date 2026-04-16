from pathlib import Path
from typing import Tuple, Dict, List, Any
import json
import yaml
import re

from pypdf import PdfReader
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_NAME = "google/gemma-3-1b-it"
PROMPT_TYPES = ["zero-shot", "few-shot", "chain-of-thought"]


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages: List[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text)

    return "\n".join(pages).strip()


def load_and_validate_pdfs(pdf_path_1: str, pdf_path_2: str) -> Tuple[str, str]:
    path1 = Path(pdf_path_1)
    path2 = Path(pdf_path_2)

    if not path1.exists():
        raise FileNotFoundError(f"File not found: {pdf_path_1}")
    if not path2.exists():
        raise FileNotFoundError(f"File not found: {pdf_path_2}")

    if path1.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path_1}")
    if path2.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path_2}")

    text1 = extract_text_from_pdf(path1)
    text2 = extract_text_from_pdf(path2)

    if not text1:
        raise ValueError(f"No readable text found in: {pdf_path_1}")
    if not text2:
        raise ValueError(f"No readable text found in: {pdf_path_2}")

    return text1, text2


def filter_document_text(text: str) -> str:
    """
    Remove obvious table-of-contents and formatting junk before prompt creation.
    """
    lines = text.splitlines()
    filtered: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        low = line.lower()

        if "table of contents" in low:
            continue
        if "terms of use" in low:
            continue
        if low.startswith("page "):
            continue

        if re.search(r"\.{5,}", line):
            continue

        if re.fullmatch(r"\d+", line):
            continue

        if re.fullmatch(r"[\d\.\-\s]+", line):
            continue

        filtered.append(line)

    return "\n".join(filtered)


def build_requirement_focused_text(document_text: str) -> str:
    """
    Pull out lines that look like real controls / requirements / section headings.
    """
    lines = [line.strip() for line in document_text.splitlines() if line.strip()]
    useful: List[str] = []

    keywords = [
        "audit", "log", "logging", "alert", "alerting", "policy", "policies",
        "configuration", "security", "encrypt", "secret", "access", "iam",
        "retention", "monitor", "monitoring", "vulnerability", "scan",
        "control plane", "registry", "permissions", "kubelet", "kubectl",
        "anonymous auth", "profiling", "read-only-port", "authorization"
    ]

    for line in lines:
        low = line.lower()

        if re.match(r"^\d+(\.\d+)+\s+", line):
            useful.append(line)
            continue

        if "(manual)" in low or "(automated)" in low:
            useful.append(line)
            continue

        if any(word in low for word in keywords):
            useful.append(line)
            continue

    return "\n".join(useful[:160])


def build_zero_shot_prompt(document_text: str) -> str:
    return f"""
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
{{
  "element1": {{
    "name": "real key data element",
    "requirements": [
      "exact requirement text from the document"
    ]
  }},
  "element2": {{
    "name": "another real key data element",
    "requirements": [
      "exact requirement text from the document"
    ]
  }}
}}

Document:
{document_text}
""".strip()


def build_few_shot_prompt(document_text: str) -> str:
    return f"""
You are an information extraction system.

Here is a REAL example of the kind of output required.

Example input:
2.1.1 Enable audit logs (Manual)
2.2.1 Configure alerting (Automated)
2.3.1 Define security policies (Manual)

Example output:
{{
  "element1": {{
    "name": "Audit Logs",
    "requirements": [
      "2.1.1 Enable audit logs (Manual)"
    ]
  }},
  "element2": {{
    "name": "Alerting",
    "requirements": [
      "2.2.1 Configure alerting (Automated)"
    ]
  }},
  "element3": {{
    "name": "Security Policies",
    "requirements": [
      "2.3.1 Define security policies (Manual)"
    ]
  }}
}}

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
{document_text}
""".strip()


def build_chain_of_thought_prompt(document_text: str) -> str:
    return f"""
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
{{
  "element1": {{
    "name": "real key data element",
    "requirements": [
      "exact requirement text from the document"
    ]
  }}
}}

Document:
{document_text}
""".strip()


def load_gemma():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
    return tokenizer, model


def _looks_like_placeholder(obj: Any) -> bool:
    text = json.dumps(obj).lower()
    bad_phrases = [
        '"..."',
        "element name",
        "requirement 1",
        "requirement 2",
        "another real key data element",
        "exact requirement text from the document",
        "example output",
        "placeholder"
    ]
    return any(bad in text for bad in bad_phrases)


def _score_candidate(obj: Any) -> int:
    if not isinstance(obj, dict):
        return -1

    text = json.dumps(obj)
    score = 0

    score += min(len(text), 2000) // 50
    score += len(obj) * 10

    for key, value in obj.items():
        if isinstance(key, str) and key.startswith("element"):
            score += 8
        if isinstance(value, dict):
            if isinstance(value.get("name"), str) and value["name"].strip():
                score += 10
            if isinstance(value.get("requirements"), list):
                score += len(value["requirements"]) * 5

    return score


def _extract_json_candidates(response: str) -> List[Dict]:
    response = response.replace("```json", "").replace("```", "")
    decoder = json.JSONDecoder()
    candidates: List[Dict] = []

    for i, ch in enumerate(response):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(response[i:])
                if isinstance(obj, dict):
                    candidates.append(obj)
            except json.JSONDecodeError:
                pass

    return candidates


def clean_text(text: str) -> str:
    text = str(text)

    text = text.split("\n")[0]
    text = re.sub(r"\.{3,}", " ", text)
    text = re.split(r"Profile Applicability:", text)[0]
    text = re.split(r"Description:", text)[0]
    text = re.sub(r"\s+\d+\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_garbage_text(text: str) -> bool:
    low = text.lower().strip()

    if not low:
        return True
    if low in {".", "..."}:
        return True
    if "table of contents" in low:
        return True
    if "terms of use" in low:
        return True
    if re.fullmatch(r"[\d\.\-\s]+", low):
        return True
    if len(low) < 3:
        return True

    return False


def normalize_kde_output(raw_obj: dict) -> dict:
    normalized = {}
    idx = 1

    if "name" in raw_obj and "requirements" in raw_obj:
        name = clean_text(raw_obj.get("name", ""))
        reqs = raw_obj.get("requirements", [])
        if isinstance(reqs, str):
            reqs = [reqs]

        cleaned_reqs = []
        for r in reqs:
            r_clean = clean_text(r)
            if re.match(r"^\d+\.\d+(\.\d+)*\s+(Ensure|Enable|Configure|Minimize)", r_clean):
                cleaned_reqs.append(r_clean)

        if not is_garbage_text(name) and cleaned_reqs:
            return {
                "element1": {
                    "name": name,
                    "requirements": cleaned_reqs
                }
            }

    for _, value in raw_obj.items():
        if not isinstance(value, dict):
            continue

        name = clean_text(value.get("name", ""))

        if len(name.split()) > 8:
            name = " ".join(name.split()[:8])

        if len(name) > 60:
            name = " ".join(name.split()[:6])

        reqs = []
        for r in value.get("requirements", []):
            r_clean = clean_text(r)
            if re.match(r"^\d+\.\d+(\.\d+)*\s+(Ensure|Enable|Configure|Minimize)", r_clean):
                reqs.append(r_clean)

        if is_garbage_text(name):
            continue
        if not reqs:
            continue

        normalized[f"element{idx}"] = {
            "name": name,
            "requirements": reqs
        }
        idx += 1

    return normalized


def fallback_extract_kdes(document_text: str) -> Dict:
    """
    Fallback extractor based on real control lines only.
    """
    lines = [line.strip() for line in document_text.splitlines() if line.strip()]
    requirement_lines: List[str] = []

    for line in lines:
        if re.match(r"^\d+\.\d+(\.\d+)*\s+(Ensure|Enable|Configure|Minimize)", line):
            requirement_lines.append(line)

    requirement_lines = requirement_lines[:12]

    elements: Dict[str, Dict[str, Any]] = {}
    idx = 1

    for line in requirement_lines:
        cleaned = re.sub(r"^\d+(\.\d+)+\s+", "", line).strip()
        cleaned = re.sub(r"\((manual|automated)\)", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = clean_text(cleaned)

        if is_garbage_text(cleaned):
            continue

        name = cleaned
        if len(name) > 60:
            name = " ".join(name.split()[:6]).strip()

        elements[f"element{idx}"] = {
            "name": name,
            "requirements": [clean_text(line)]
        }
        idx += 1

        if idx > 8:
            break

    if not elements:
        elements["element1"] = {
            "name": "Document Security Requirements",
            "requirements": [clean_text(document_text[:200])]
        }

    return elements


def run_gemma_extraction(prompt: str, tokenizer, model, focused_text: str, max_new_tokens: int = 700) -> Dict:
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False
    )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    candidates = _extract_json_candidates(response)
    if candidates:
        non_placeholder = [c for c in candidates if not _looks_like_placeholder(c)]
        if non_placeholder:
            candidates = non_placeholder

        best = max(candidates, key=_score_candidate)
        normalized = normalize_kde_output(best)

        if normalized and not _looks_like_placeholder(normalized):
            return normalized

    return fallback_extract_kdes(focused_text)


def save_yaml_output(kde_dict: Dict, input_pdf_path: str, output_dir: str = "output_yaml", prompt_type: str | None = None) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_name = Path(input_pdf_path).stem
    if prompt_type:
        yaml_file = output_path / f"{pdf_name}-{prompt_type}-kdes.yaml"
    else:
        yaml_file = output_path / f"{pdf_name}-kdes.yaml"

    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(kde_dict, f, sort_keys=False, allow_unicode=True)

    return str(yaml_file)


def save_llm_output_text(
    llm_name: str,
    prompt_used: str,
    prompt_type: str,
    llm_output: Dict,
    input_pdf_path: str,
    output_dir: str = "output_text",
) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_name = Path(input_pdf_path).stem
    txt_file = output_path / f"{pdf_name}-{prompt_type}-llm-output.txt"

    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("*LLM Name*\n")
        f.write(f"{llm_name}\n\n")
        f.write("*Prompt Used*\n")
        f.write(f"{prompt_used}\n\n")
        f.write("*Prompt Type*\n")
        f.write(f"{prompt_type}\n\n")
        f.write("*LLM Output*\n")
        f.write(json.dumps(llm_output, indent=2))

    return str(txt_file)


def process_single_document(
    pdf_path: str,
    prompt_type: str,
    tokenizer,
    model
) -> None:
    text = extract_text_from_pdf(Path(pdf_path))
    filtered_text = filter_document_text(text)
    focused_text = build_requirement_focused_text(filtered_text)

    if prompt_type == "zero-shot":
        prompt = build_zero_shot_prompt(focused_text)
    elif prompt_type == "few-shot":
        prompt = build_few_shot_prompt(focused_text)
    elif prompt_type == "chain-of-thought":
        prompt = build_chain_of_thought_prompt(focused_text)
    else:
        raise ValueError(f"Unsupported prompt type: {prompt_type}")

    kde_output = run_gemma_extraction(prompt, tokenizer, model, focused_text)

    yaml_path = save_yaml_output(kde_output, pdf_path, prompt_type=prompt_type)
    txt_path = save_llm_output_text(MODEL_NAME, prompt, prompt_type, kde_output, pdf_path)

    print(f"\nProcessed: {pdf_path} [{prompt_type}]")
    print("KDE output:")
    print(json.dumps(kde_output, indent=2))
    print(f"YAML saved to: {yaml_path}")
    print(f"LLM output text saved to: {txt_path}")


def get_required_input_pairs() -> List[Tuple[str, str]]:
    return [
        ("input_pdfs/cis-r1.pdf", "input_pdfs/cis-r1.pdf"),
        ("input_pdfs/cis-r1.pdf", "input_pdfs/cis-r2.pdf"),
        ("input_pdfs/cis-r1.pdf", "input_pdfs/cis-r3.pdf"),
        ("input_pdfs/cis-r1.pdf", "input_pdfs/cis-r4.pdf"),
        ("input_pdfs/cis-r2.pdf", "input_pdfs/cis-r2.pdf"),
        ("input_pdfs/cis-r2.pdf", "input_pdfs/cis-r3.pdf"),
        ("input_pdfs/cis-r2.pdf", "input_pdfs/cis-r4.pdf"),
        ("input_pdfs/cis-r3.pdf", "input_pdfs/cis-r3.pdf"),
        ("input_pdfs/cis-r3.pdf", "input_pdfs/cis-r4.pdf"),
    ]


def main():
    tokenizer, model = load_gemma()
    print("Gemma loaded successfully!")

    pdfs = [
        "input_pdfs/cis-r1.pdf",
        "input_pdfs/cis-r2.pdf"
    ]

    for pdf in pdfs:
        for prompt_type in ["zero-shot", "few-shot", "chain-of-thought"]:
            process_single_document(pdf, prompt_type, tokenizer, model)


if __name__ == "__main__":
    main()