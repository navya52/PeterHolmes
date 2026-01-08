"""NAICS code classification using LLM."""

from typing import Dict
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List
import json
from .llm_client import get_llm_client


class NAICSClassification(BaseModel):
    codes: List[str] = Field(description="List of NAICS codes (6-digit format)")
    primary_code: str = Field(description="Primary NAICS code")
    explanation: str = Field(description="Brief explanation of classification")


def classify_naics_structured(summary: Dict, job_id: str = None) -> Dict:
    """Classify business using NAICS codes with structured output."""
    from ..api.jobs import job_manager
    
    if job_id:
        job_manager.add_log(job_id, "Classifying NAICS codes with LLM...")
    
    # Build prompt text using f-string - no template variables to avoid parsing issues
    nature = summary.get('nature', '')
    products = summary.get('products_services', '')
    countries = ', '.join(summary.get('countries_operating', []))
    
    prompt_text = f"""Based on the following business information, assign appropriate NAICS codes (6-digit format).

Business Nature: {nature}
Products/Services: {products}
Countries Operating: {countries}

You must return ONLY a valid JSON object with this exact structure:
{{"codes": ["code1", "code2"], "primary_code": "main_code", "explanation": "brief explanation"}}

Keep the explanation concise (2-3 sentences maximum).

Return ONLY the JSON object, no markdown, no code blocks, no other text."""
    
    # Construct messages directly - bypasses template parsing entirely
    messages = [
        SystemMessage(content="You are a business classification expert. Assign NAICS codes based on business descriptions. You must respond with ONLY valid JSON, no other text."),
        HumanMessage(content=prompt_text)
    ]
    
    llm = get_llm_client()
    # Don't use with_structured_output - Perplexity doesn't support it. Just call LLM directly.
    response = llm.invoke(messages)
    
    # Extract JSON from response content
    content = response.content if hasattr(response, 'content') else str(response)
    
    # Clean up the response to extract JSON
    json_str = content.strip()
    
    # Remove markdown code blocks if present
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    elif json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    json_str = json_str.strip()
    
    # Try to find JSON object in the string if there's extra text
    if not json_str.startswith("{"):
        # Find first {
        start_idx = json_str.find("{")
        if start_idx >= 0:
            json_str = json_str[start_idx:]
            # Find matching closing brace
            brace_count = 0
            end_idx = -1
            for i, char in enumerate(json_str):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx > 0:
                json_str = json_str[:end_idx]
    
    # Parse JSON and validate with Pydantic
    try:
        data = json.loads(json_str)
        result = NAICSClassification(**data).model_dump()
    except Exception as e:
        if job_id:
            job_manager.add_log(job_id, f"Failed to parse NAICS response: {e}, content: {content[:200]}")
        raise ValueError(f"Failed to parse NAICS classification: {e}. Response: {content[:200]}")
    
    if job_id:
        job_manager.add_log(job_id, f"NAICS classified: {result.get('primary_code', 'N/A')}")
    
    return result
