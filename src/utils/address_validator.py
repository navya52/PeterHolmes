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
    
    Uses Google Places API when available, falls back to text heuristics.
    
    Args:
        address: Address string to check
        
    Returns:
        Dictionary with:
        - 'is_commercial': bool (True if commercial/industrial/warehouse/office)
        - 'plausibility_note': str (explanation)
        - 'address_types': Optional[List[str]] (from Places API if available)
        - 'method': str ('places_api', 'heuristics', or 'unknown')
    """
    # Try Google Places API first
    places_result = _check_with_places_api(address)
    if places_result:
        return places_result
    
    # Fallback to text heuristics
    return _check_with_heuristics(address)


def _check_with_places_api(address: str) -> Optional[Dict[str, any]]:
    """
    Check address plausibility using Google Places API.
    
    Args:
        address: Address string to check
        
    Returns:
        Dictionary with plausibility results if successful, None otherwise
    """
    api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")
    
    if not api_key or api_key == 'placeholder':
        return None
    
    # Try Places API Text Search first
    try:
        encoded_address = quote(address)
        # Use Places API Text Search
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={encoded_address}&key={api_key}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('results'):
                # Get the first result
                result = data['results'][0]
                types = result.get('types', [])
                
                # Check for commercial indicators in types
                commercial_types = [
                    'establishment', 'point_of_interest', 'premise', 'subpremise',
                    'store', 'restaurant', 'cafe', 'shopping_mall', 'supermarket',
                    'bank', 'hospital', 'school', 'university', 'church', 'mosque',
                    'synagogue', 'hindu_temple', 'airport', 'train_station',
                    'bus_station', 'gas_station', 'parking', 'lodging', 'real_estate_agency'
                ]
                
                # Also check for industrial/commercial keywords in address components
                address_components = result.get('formatted_address', '').lower()
                commercial_keywords = [
                    'industrial', 'estate', 'business park', 'trading estate',
                    'warehouse', 'unit', 'suite', 'building', 'park'
                ]
                
                is_commercial = (
                    any(place_type in types for place_type in commercial_types) or
                    any(keyword in address_components for keyword in commercial_keywords)
                )
                
                note = "Address found – appears commercial based on Places API types" if is_commercial else "Address found – appears residential based on Places API types"
                
                return {
                    'is_commercial': is_commercial,
                    'plausibility_note': note,
                    'address_types': types,
                    'method': 'places_api'
                }
        
        # If Text Search doesn't work, try Geocoding API
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 'OK' and data.get('results'):
                result = data['results'][0]
                types = result.get('types', [])
                
                # Check address components for commercial indicators
                address_components = result.get('formatted_address', '').lower()
                commercial_keywords = [
                    'industrial', 'estate', 'business park', 'trading estate',
                    'warehouse', 'unit', 'suite', 'building', 'park'
                ]
                
                # Geocoding API types that suggest commercial
                commercial_types = [
                    'establishment', 'point_of_interest', 'premise', 'subpremise'
                ]
                
                is_commercial = (
                    any(place_type in types for place_type in commercial_types) or
                    any(keyword in address_components for keyword in commercial_keywords)
                )
                
                note = "Address found – appears commercial based on Places API types" if is_commercial else "Address found – appears residential based on Places API types"
                
                return {
                    'is_commercial': is_commercial,
                    'plausibility_note': note,
                    'address_types': types,
                    'method': 'places_api'
                }
    
    except Exception as e:
        # API call failed, return None to fall back to heuristics
        return None
    
    return None


def _check_with_heuristics(address: str) -> Dict[str, any]:
    """
    Check address plausibility using text heuristics.
    
    Args:
        address: Address string to check
        
    Returns:
        Dictionary with plausibility results
    """
    address_lower = address.lower()
    
    # Commercial/industrial keywords
    commercial_keywords = [
        'industrial estate', 'business park', 'trading estate', 'industrial area',
        'warehouse', 'unit', 'suite', 'building', 'park', 'estate',
        'industrial park', 'commercial', 'office', 'offices', 'premises'
    ]
    
    # Check for keywords
    has_commercial_keyword = any(keyword in address_lower for keyword in commercial_keywords)
    
    # Check UK postcode patterns (industrial areas often have specific patterns)
    # UK postcodes: AB1 2CD, AB12 3CD, etc.
    # Some industrial areas have specific postcode patterns, but this is less reliable
    # We'll focus on keywords for now
    
    # Check for unit/suite numbers which suggest commercial
    has_unit_pattern = bool(re.search(r'\b(unit|suite|building|block)\s+\d+', address_lower))
    
    is_commercial = has_commercial_keyword or has_unit_pattern
    
    if is_commercial:
        note = "Address found – appears commercial based on postcode/industrial area"
    else:
        note = "Address found – plausibility check inconclusive (using heuristics)"
    
    return {
        'is_commercial': is_commercial if is_commercial else None,
        'plausibility_note': note,
        'address_types': None,
        'method': 'heuristics'
    }


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

