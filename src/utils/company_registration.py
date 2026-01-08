"""Extract company registration details from website content."""

from typing import Dict, Optional
import re
import json
from langchain_core.messages import HumanMessage, SystemMessage
from ..analyzer.llm_client import get_llm_client


def extract_company_registration(content: Dict[str, str], job_id: str = None) -> Dict[str, Optional[str]]:
    """Extract company registration details from website content."""
    from ..api.jobs import job_manager
    
    if job_id:
        job_manager.add_log(job_id, "Extracting company registration details...")
    
    # Combine all content
    text = f"{content.get('homepage', '')} {content.get('about', '')} {content.get('contact', '')}"
    
    # Try regex patterns
    company_number = _extract_company_number(text)
    vat_number = _extract_vat_number(text)
    eori_number = _extract_eori_number(text)
    established_date = _extract_established_date(text)
    
    # Use LLM for remaining fields
    try:
        llm_result = _extract_with_llm(text)
        company_name = llm_result.get('company_name')
        country_of_registration = llm_result.get('country_of_registration')
        
        # Use LLM results if regex didn't find them
        if not company_number:
            company_number = llm_result.get('company_number')
        if not vat_number:
            vat_number = llm_result.get('vat_number')
        if not eori_number:
            eori_number = llm_result.get('eori_number')
        if not established_date:
            established_date = llm_result.get('established_date')
    except Exception as e:
        if job_id:
            job_manager.add_log(job_id, f"LLM extraction failed: {e}")
        company_name = None
        country_of_registration = None
    
    result = {
        'company_number': str(company_number) if company_number else None,
        'vat_number': str(vat_number) if vat_number else None,
        'eori_number': str(eori_number) if eori_number else None,
        'company_name': str(company_name) if company_name else None,
        'established_date': str(established_date) if established_date else None,
        'country_of_registration': str(country_of_registration) if country_of_registration else None
    }
    
    if job_id:
        found = [k for k, v in result.items() if v]
        job_manager.add_log(job_id, f"Company registration: found {len(found)} field(s)")
    
    return result


def _extract_company_number(text: str) -> Optional[str]:
    """Extract company number using regex."""
    patterns = [
        r'(?:Company\s*No|Company\s*Reg(?:istration)?\s*No|CRN)[:\s]*([A-Z0-9]{2,10}(?:\s*[A-Z0-9]{2,10})?)',
        r'\b(?:Co\.\s*No\.|Company\s*Number)\s*(\d{6,10})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_vat_number(text: str) -> Optional[str]:
    """Extract VAT number using regex."""
    patterns = [
        r'(?:VAT\s*No|VAT\s*Reg(?:istration)?\s*No)[:\s]*([A-Z]{2}\s*\d{9,12})',
        r'\b(\d{9})\s*(?:VAT)\b'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_eori_number(text: str) -> Optional[str]:
    """Extract EORI number using regex."""
    pattern = r'(?:EORI\s*No|EORI)[:\s]*([A-Z]{2}\s*\d{10,15})'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_established_date(text: str) -> Optional[str]:
    """Extract established date using regex."""
    patterns = [
        r'(?:Established|Founded|Incorporated|Since)[:\s]*(?:in)?\s*(\d{4})',
        r'(?:Established|Founded|Incorporated|Since)[:\s]*(?:on)?\s*(\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_with_llm(text: str) -> Dict[str, Optional[str]]:
    """Use LLM to extract company registration details."""
    # Build prompt text using f-string - no template variables to avoid parsing issues
    text_to_analyze = text[:10000]
    prompt_text = f"""Extract company registration details:

{text_to_analyze}

JSON:"""
    
    # Construct messages directly - bypasses template parsing entirely
    messages = [
        SystemMessage(content="""Extract company registration details from the text. Return JSON with keys: 'company_name', 'company_number', 'vat_number', 'eori_number', 'established_date', 'country_of_registration'. Use 'None' for missing values."""),
        HumanMessage(content=prompt_text)
    ]
    
    llm = get_llm_client()
    response = llm.invoke(messages)
    
    try:
        # Try to parse JSON from response
        content = response.content.strip()
        # Remove markdown code blocks if present
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        result = json.loads(content)
        # Ensure all values are strings
        for key, value in result.items():
            if value is not None:
                result[key] = str(value)
        return result
    except json.JSONDecodeError:
        return {
            'company_name': None,
            'company_number': None,
            'vat_number': None,
            'eori_number': None,
            'established_date': None,
            'country_of_registration': None
        }
