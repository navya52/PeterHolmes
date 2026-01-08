"""Extract structured content from website pages."""

from bs4 import BeautifulSoup
from typing import Dict, Optional
from urllib.parse import urljoin
from .basic_scraper import fetch_url


def extract_content_from_html(html: str, base_url: str) -> Dict[str, str]:
    """
    Extract key content sections from HTML.
    
    Args:
        html: HTML content to parse
        base_url: Base URL for resolving relative links
        
    Returns:
        Dictionary with extracted content
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()
    
    homepage_text = soup.get_text(separator=' ', strip=True)
    
    # Try to find and extract other pages (limit to avoid hanging)
    about_content = ""
    contact_content = ""
    products_content = ""
    
    links = soup.find_all('a', href=True)[:20]
    
    # About page
    try:
        for link in links:
            href = link.get('href', '').lower()
            link_text = link.get_text().lower()
            if 'about' in href or 'about' in link_text:
                about_url = urljoin(base_url, link.get('href'))
                about_content = _fetch_page_content(about_url)
                if about_content:
                    break
    except Exception:
        pass
    
    # Contact page
    try:
        for link in links:
            href = link.get('href', '').lower()
            link_text = link.get_text().lower()
            if 'contact' in href or 'contact' in link_text:
                contact_url = urljoin(base_url, link.get('href'))
                contact_content = _fetch_page_content(contact_url)
                if contact_content:
                    break
    except Exception:
        pass
    
    # Products/Services page
    try:
        for link in links:
            href = link.get('href', '').lower()
            link_text = link.get_text().lower()
            if any(keyword in href or keyword in link_text for keyword in ['product', 'service', 'offer']):
                products_url = urljoin(base_url, link.get('href'))
                products_content = _fetch_page_content(products_url)
                if products_content:
                    break
    except Exception:
        pass
    
    return {
        'homepage': homepage_text[:50000],
        'about': about_content[:50000] if about_content else "",
        'contact': contact_content[:50000] if contact_content else "",
        'products': products_content[:50000] if products_content else ""
    }


def _fetch_page_content(url: str) -> Optional[str]:
    """Helper to fetch content from a linked page."""
    try:
        from .basic_scraper import fetch_url
        html = fetch_url(url)
        soup = BeautifulSoup(html, 'lxml')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        return soup.get_text(separator=' ', strip=True)
    except Exception:
        return None


def extract_all_content(url: str, use_playwright: bool = False, job_id: str = None) -> Dict[str, str]:
    """
    Extract all content from a website.
    
    Args:
        url: URL to extract content from
        use_playwright: Whether to use Playwright (for JS sites) or requests. Defaults to False.
        job_id: Optional job ID for logging
            
    Returns:
        Dictionary with all extracted content
    """
    from .basic_scraper import fetch_url
    from ..api.jobs import job_manager
    
    if job_id:
        job_manager.add_log(job_id, f"Fetching website content from {url}")
    
    # Use Playwright if requested, with fallback to basic scraper
    if use_playwright:
        try:
            from .playwright_scraper import scrape_with_playwright
            result = scrape_with_playwright(url)
            html = result['html']
            if job_id:
                job_manager.add_log(job_id, f"Used Playwright scraper, got {len(html)} characters")
        except ImportError:
            if job_id:
                job_manager.add_log(job_id, "Playwright not available, falling back to basic scraper")
            html = fetch_url(url, job_id=job_id)
        except Exception as e:
            if job_id:
                job_manager.add_log(job_id, f"Playwright scraping failed: {e}, falling back to basic scraper")
            html = fetch_url(url, job_id=job_id)
    else:
        html = fetch_url(url, job_id=job_id)
    
    if job_id:
        job_manager.add_log(job_id, f"Extracted {len(html)} characters of HTML")
    
    result = extract_content_from_html(html, url)
    
    if job_id:
        job_manager.add_log(job_id, f"Content extraction complete: homepage={len(result['homepage'])} chars")
    
    return result
