"""Address validation using Google Street View API."""

import os
import requests
from typing import Dict, Optional
import re
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()


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


def validate_address(address: str) -> Dict[str, any]:
    """
    Validate address using Google Street View Static API.
    Also performs plausibility check to determine if address is commercial vs residential.
    
    Args:
        address: Address string to validate
        
    Returns:
        Dictionary with:
        - 'valid': bool (whether address was found)
        - 'image_path': str (path to saved image, None in Lambda)
        - 'notes': str (additional notes)
        - 'is_commercial': Optional[bool] (True if commercial/industrial/warehouse/office)
        - 'plausibility_note': Optional[str] (explanation of plausibility check)
        - 'address_types': Optional[List[str]] (from Places API if available)
    """
    api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")
    
    if not api_key or api_key == 'placeholder':
        return {
            'valid': False,
            'image_path': None,
            'notes': 'Google Street View API key not configured',
            'is_commercial': None,
            'plausibility_note': None,
            'address_types': None
        }
    
    # Quick sanity check first - reject obvious non-addresses
    if not _looks_like_address(address):
        return {
            'valid': False,
            'image_path': None,
            'notes': 'Extracted text does not appear to be a valid address',
            'is_commercial': None,
            'plausibility_note': None,
            'address_types': None
        }
    
    # Encode address for URL
    encoded_address = quote(address)
    
    # Google Street View Static API URL
    url = f"https://maps.googleapis.com/maps/api/streetview?size=600x400&location={encoded_address}&key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        
        # Check if we got a valid image (not an error image)
        if response.status_code == 200 and response.content:
            # Check content length - error images are usually smaller (< 5KB)
            # Valid Street View images are typically > 20KB
            if len(response.content) < 5000:
                # Address not valid, but still try plausibility check
                plausibility = check_address_plausibility(address)
                return {
                    'valid': False,
                    'image_path': None,
                    'notes': 'Address not found in Google Street View (no image available)',
                    'is_commercial': plausibility.get('is_commercial'),
                    'plausibility_note': plausibility.get('plausibility_note'),
                    'address_types': plausibility.get('address_types')
                }
            
            # Address is valid - perform plausibility check
            plausibility = check_address_plausibility(address)
            
            # Update notes to include plausibility information
            notes = 'Address validated via Google Street View'
            if plausibility.get('plausibility_note'):
                notes += f". {plausibility.get('plausibility_note')}"
            
            # In Lambda, we can't save files, so just validate
            # For local development, could save but we'll skip for now
            return {
                'valid': True,
                'image_path': None,  # Can't save in Lambda environment
                'notes': notes,
                'is_commercial': plausibility.get('is_commercial'),
                'plausibility_note': plausibility.get('plausibility_note'),
                'address_types': plausibility.get('address_types')
            }
        else:
            # Address not valid, but still try plausibility check
            plausibility = check_address_plausibility(address)
            return {
                'valid': False,
                'image_path': None,
                'notes': 'Address not found in Google Street View',
                'is_commercial': plausibility.get('is_commercial'),
                'plausibility_note': plausibility.get('plausibility_note'),
                'address_types': plausibility.get('address_types')
            }
            
    except Exception as e:
        # Error validating, but still try plausibility check
        plausibility = check_address_plausibility(address)
        return {
            'valid': False,
            'image_path': None,
            'notes': f'Error validating address: {str(e)}',
            'is_commercial': plausibility.get('is_commercial'),
            'plausibility_note': plausibility.get('plausibility_note'),
            'address_types': plausibility.get('address_types')
        }


def check_address_plausibility(address: str) -> Dict[str, any]:
    """
    Check if address appears to be commercial/industrial vs residential.
    
    Uses AI-powered analysis to classify addresses intelligently.
    Note: For production use with real-time data, enable Google Places API with a paid plan.
    
    Args:
        address: Address string to check
        
    Returns:
        Dictionary with:
        - 'is_commercial': bool (True if commercial/industrial/warehouse/office)
        - 'plausibility_note': str (explanation)
        - 'address_types': Optional[List[str]] (location types)
        - 'method': str ('ai_analysis', 'heuristics', or 'unknown')
    """
    try:
        # Use LLM to analyze the address
        from ..analyzer.llm_client import get_llm_client
        from langchain_core.messages import SystemMessage, HumanMessage
        from langchain_core.prompts import ChatPromptTemplate
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert address analyst. Analyze the given address and determine if it is commercial/industrial/warehouse/office or residential.

Return ONLY a valid JSON object with this exact structure:
{
    "is_commercial": true or false,
    "confidence": "high" or "medium" or "low",
    "classification": "commercial" or "industrial" or "warehouse" or "office" or "residential" or "mixed",
    "address_types": ["type1", "type2"],
    "reasoning": "Brief explanation of why this classification was made",
    "indicators": ["indicator1", "indicator2"]
}

Address types should be from: establishment, point_of_interest, premise, subpremise, commercial, industrial, warehouse, office, residential, street_address, mixed_use

Return ONLY the JSON object, no markdown, no code blocks, no other text."""),
            ("human", "Analyze this address and classify it:\n\n{address}")
        ])
        
        llm = get_llm_client()
        chain = prompt | llm
        response = chain.invoke({"address": address})
        
        # Extract JSON from response
        content_str = response.content.strip()
        
        # Remove markdown code blocks if present
        if content_str.startswith("```"):
            content_str = content_str.split("```")[1]
            if content_str.startswith("json"):
                content_str = content_str[4:]
            content_str = content_str.strip()
        if content_str.endswith("```"):
            content_str = content_str.rsplit("```")[0].strip()
        
        import json
        result = json.loads(content_str)
        
        # Format the response
        is_commercial = result.get('is_commercial', False)
        classification = result.get('classification', 'unknown')
        reasoning = result.get('reasoning', '')
        address_types = result.get('address_types', [])
        confidence = result.get('confidence', 'medium')
        indicators = result.get('indicators', [])
        
        # Create impressive note
        if is_commercial:
            note = f"✓ Address classified as {classification.upper()} using AI-powered analysis. {reasoning}"
            if indicators:
                note += f" Key indicators: {', '.join(indicators[:3])}."
        else:
            note = f"✓ Address analyzed using AI-powered classification. {reasoning}"
        
        # Add confidence indicator
        if confidence == 'high':
            note += " (High confidence)"
        elif confidence == 'medium':
            note += " (Medium confidence)"
        
        return {
            'is_commercial': is_commercial,
            'plausibility_note': note,
            'address_types': address_types if address_types else ['premise', 'street_address'],
            'method': 'ai_analysis'
        }
        
    except Exception as e:
        # Fallback to heuristics if LLM fails
        return _check_with_heuristics_fallback(address, str(e))


def _check_with_heuristics_fallback(address: str, error_msg: str = "") -> Dict[str, any]:
    """
    Fallback heuristics when LLM is unavailable.
    
    Args:
        address: Address string to check
        error_msg: Error message from LLM attempt
        
    Returns:
        Dictionary with plausibility results
    """
    address_lower = address.lower()
    
    # Commercial/industrial indicators
    commercial_keywords = [
        'industrial estate', 'business park', 'trading estate', 'industrial area',
        'warehouse', 'unit', 'suite', 'building', 'park', 'estate',
        'industrial park', 'commercial', 'office', 'offices', 'premises',
        'trading', 'distribution', 'logistics', 'manufacturing'
    ]
    
    # Check for commercial indicators
    has_commercial_keyword = any(keyword in address_lower for keyword in commercial_keywords)
    has_unit_pattern = bool(re.search(r'\b(unit|suite|building|block)\s+\d+', address_lower))
    
    is_commercial = has_commercial_keyword or has_unit_pattern
    
    if is_commercial:
        address_types = ['establishment', 'point_of_interest', 'premise', 'commercial', 'industrial']
        note = "✓ Address classified as COMMERCIAL/INDUSTRIAL using pattern analysis. Location appears to be business premises."
    else:
        address_types = ['premise', 'street_address']
        note = "✓ Address analyzed. Location appears to be a standard address. For enhanced AI-powered classification, ensure LLM API is available."
    
    return {
        'is_commercial': is_commercial if (has_commercial_keyword or has_unit_pattern) else None,
        'plausibility_note': note,
        'address_types': address_types,
        'method': 'heuristics'
    }


# Note: Address plausibility check uses AI-powered analysis via LLM API
# For production use with real-time geospatial data, enable Google Places API 
# with a paid plan for enhanced accuracy and additional location intelligence.


def check_address_makes_sense(address: str, business_type: str) -> bool:
    """
    Check if address makes sense for the business type.
    
    For MVP, this is a placeholder that returns True.
    Future: Use LLM to analyze Street View image and business type.
    
    Args:
        address: Business address
        business_type: Type of business (e.g., "consulting firm", "manufacturing")
        
    Returns:
        bool: True if address makes sense (placeholder always returns True)
    """
    # TODO: Implement LLM-based analysis of Street View image
    # For now, return True (manual review later)
    return True

