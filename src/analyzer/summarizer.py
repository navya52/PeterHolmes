"""LLM summarization for website content."""

from typing import Dict
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List
import json
from .llm_client import get_llm_client


class BusinessSummary(BaseModel):
    nature: str = Field(description="The nature of the business")
    products_services: str = Field(description="Products and services offered")
    countries_operating: List[str] = Field(description="Countries where the company operates")
    countries_dealing_with: List[str] = Field(description="Countries the company does business with")


def summarize_website_structured(content: Dict[str, str], job_id: str = None) -> Dict:
    """Generate a structured summary of a business website."""
    from ..api.jobs import job_manager
    
    if job_id:
        job_manager.add_log(job_id, "Generating business summary with LLM...")
    
    # Combine all content
    full_text = f"""
Homepage: {content.get('homepage', '')[:10000]}
About: {content.get('about', '')[:5000]}
Products: {content.get('products', '')[:5000]}
Contact: {content.get('contact', '')[:2000]}
"""
    
    # Build prompt text using f-string - no template variables to avoid parsing issues
    prompt_text = f"""Analyze this business website and extract:
1. Nature of the business
2. Products and services offered
3. Countries where the company operates
4. Countries the company deals with

You must return ONLY a valid JSON object with this exact structure:
{{"nature": "description", "products_services": "description", "countries_operating": ["country1"], "countries_dealing_with": ["country1"]}}

Keep all descriptions concise and focused.

Website content:
{full_text}

Return ONLY the JSON object, no markdown, no code blocks, no other text."""
    
    # Construct messages directly - bypasses template parsing entirely
    messages = [
        SystemMessage(content="You are a business analyst. Analyze the website content and extract structured information. You must respond with ONLY valid JSON, no other text."),
        HumanMessage(content=prompt_text)
    ]
    
    llm = get_llm_client()
    # Don't use with_structured_output - Perplexity doesn't support it. Just call LLM directly.
    response = llm.invoke(messages)
    
    # Extract JSON from response content
    content_str = response.content if hasattr(response, 'content') else str(response)
    
    # Clean up the response to extract JSON
    json_str = content_str.strip()
    
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
        result = BusinessSummary(**data).model_dump()
    except Exception as e:
        if job_id:
            job_manager.add_log(job_id, f"Failed to parse summary response: {e}, content: {content_str[:200]}")
        raise ValueError(f"Failed to parse business summary: {e}. Response: {content_str[:200]}")
    
    if job_id:
        job_manager.add_log(job_id, f"Summary generated: {result.get('nature', '')[:100]}...")
    
    return result
