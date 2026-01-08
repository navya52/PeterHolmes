"""Extract business address from website content."""

from typing import Optional, Dict
import re
from langchain_core.messages import HumanMessage, SystemMessage
from ..analyzer.llm_client import get_llm_client


def _looks_like_address(text: str) -> bool:
    """Check if text looks like a valid address."""
    # Must not contain common e-commerce UI terms
    ecommerce_terms = ['add to basket', 'add to cart', 'best sellers', 'add to wishlist', 
                       'buy now', 'checkout', 'shopping cart', 'price', '£', '$', '€',
                       'add to bag', 'shop now', 'view cart']
    text_lower = text.lower()
    if any(term in text_lower for term in ecommerce_terms):
        return False
    
    # Must contain street indicators or postal code patterns
    has_street = bool(re.search(r'\b(Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Way|Boulevard|Blvd|Close|Cl|Crescent|Cres|Place|Pl|Square|Sq)\b', text, re.IGNORECASE))
    has_postal = bool(re.search(r'\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b|\b\d{5}(-\d{4})?\b', text, re.IGNORECASE))
    has_number = bool(re.search(r'\b\d+\b', text))
    
    # Must have at least street indicator OR postal code, AND a number, AND minimum word count
    return (has_street or has_postal) and has_number and len(text.split()) >= 4


def extract_address(content: Dict[str, str], job_id: str = None) -> Optional[str]:
    """Extract business address from website content."""
    from ..api.jobs import job_manager
    
    if job_id:
        job_manager.add_log(job_id, "Extracting address from website content...")
    
    # Combine contact and about pages (prioritize contact page)
    text = f"{content.get('contact', '')} {content.get('about', '')} {content.get('homepage', '')}"
    
    # Try regex patterns for common address formats
    address_patterns = [
        r'\d+[,\s]+[A-Za-z\s]+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Way|Boulevard|Blvd)[,\s]+[A-Za-z\s]+(?:,\s*)?[A-Za-z\s]+(?:,\s*)?[A-Z]{2}\s*\d{5,10}',
        r'\d+[,\s]+[A-Za-z\s]+(?:Street|St|Road|Rd|Avenue|Ave)[,\s]+[A-Za-z\s]+(?:,\s*)?[A-Za-z\s]+(?:,\s*)?[A-Z]{2}',
    ]
    
    for pattern in address_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result = matches[0].strip()
            # Validate it looks like an address
            if _looks_like_address(result):
                if job_id:
                    job_manager.add_log(job_id, f"Address found via regex: {result[:50]}...")
                return result
    
    # Try LLM extraction if regex fails
    try:
        # Build prompt text using f-string - no template variables to avoid parsing issues
        text_to_analyze = text[:5000]
        prompt_text = f"""Extract the business address from this text. Return only the complete address, or 'None' if not found:

{text_to_analyze}"""
        
        # Construct messages directly - bypasses template parsing entirely
        messages = [
            SystemMessage(content="""You are an address extraction assistant. Extract ONLY the complete business address from the text.
            A valid address must include:
            - Street number and name (e.g., "123 Main Street")
            - City name
            - State/Province or postal code
            - Country (optional but preferred)
            
            Do NOT extract:
            - Product names, prices, or e-commerce UI text
            - Phone numbers or email addresses alone
            - Partial addresses or just city names
            - Text like "Add to Basket", "Best Sellers", "Add to wishlist", etc.
            - Shopping cart or checkout related text
            
            Return ONLY the address, or 'None' if no valid address is found."""),
            HumanMessage(content=prompt_text)
        ]
        
        llm = get_llm_client()
        response = llm.invoke(messages)
        
        address = response.content.strip()
        # Remove quotes if present
        address = address.strip('"\'')
        
        # Validate the extracted address
        if address and address.lower() != 'none' and len(address) > 10:
            # Check if it looks like an address
            if _looks_like_address(address):
                if job_id:
                    job_manager.add_log(job_id, f"Address found via LLM: {address[:50]}...")
                return address
            else:
                if job_id:
                    job_manager.add_log(job_id, f"LLM extracted text doesn't look like an address: {address[:50]}...")
    except Exception as e:
        if job_id:
            job_manager.add_log(job_id, f"LLM address extraction failed: {e}")
    
    if job_id:
        job_manager.add_log(job_id, "No address found")
    return None
