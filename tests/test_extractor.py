from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from extractor import (
    extract_text_from_pdf,
    load_and_validate_pdfs,
    build_zero_shot_prompt,
    build_few_shot_prompt,
    build_chain_of_thought_prompt,
    fallback_extract_kdes,
)


def test_extract_text_from_pdf_returns_string():
    text = extract_text_from_pdf(Path("input_pdfs/cis-r1.pdf"))
    assert isinstance(text, str)
    assert len(text) > 0


def test_load_and_validate_pdfs_returns_two_strings():
    text1, text2 = load_and_validate_pdfs("input_pdfs/cis-r1.pdf", "input_pdfs/cis-r2.pdf")
    assert isinstance(text1, str)
    assert isinstance(text2, str)
    assert len(text1) > 0
    assert len(text2) > 0


def test_zero_shot_prompt_contains_document_text():
    sample = "2.1.1 Enable audit logs (Manual)"
    prompt = build_zero_shot_prompt(sample)
    assert sample in prompt
    assert "Return ONLY valid JSON." in prompt


def test_few_shot_prompt_contains_example():
    sample = "2.1.1 Enable audit logs (Manual)"
    prompt = build_few_shot_prompt(sample)
    assert sample in prompt
    assert "Example input:" in prompt


def test_chain_of_thought_prompt_contains_task_language():
    sample = "3.1.1 Ensure that the kubeconfig file permissions are set properly"
    prompt = build_chain_of_thought_prompt(sample)
    assert sample in prompt
    assert "Task:" in prompt


def test_fallback_extract_kdes_returns_expected_structure():
    sample = """
    2.1.1 Enable audit logs (Manual)
    2.1.2 Ensure audit logs are collected and managed (Manual)
    """
    result = fallback_extract_kdes(sample)
    assert isinstance(result, dict)
    assert "element1" in result
    assert "name" in result["element1"]
    assert "requirements" in result["element1"]