"""Background worker for processing analysis jobs."""

import time
from datetime import datetime
from .jobs import job_manager, JobStatus
from .models import AnalysisResult, BusinessSummary, NAICSResponse, FlagsResponse, FlagResult, AddressResponse, AddressValidation, CompanyRegistration

from src.scraper.content_extractor import extract_all_content
from src.analyzer.summarizer import summarize_website_structured
from src.analyzer.naics_classifier import classify_naics_structured
from src.flags.flag_runner import run_all_checks
from src.utils.address_extractor import extract_address
from src.utils.company_registration import extract_company_registration


def process_analysis_job(job_id: str, url: str) -> None:
    """Process an analysis job."""
    try:
        # Update status: Processing
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=10,
            message="Scraping website..."
        )
        job_manager.add_log(job_id, f"Starting analysis for {url}")
        
        # Step 1: Scrape website
        content = extract_all_content(url, use_playwright=False, job_id=job_id)
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=20,
            message="Website scraped, analyzing content..."
        )
        
        # Step 2: Generate summary
        summary_dict = summarize_website_structured(content, job_id=job_id)
        summary = BusinessSummary(**summary_dict)
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=40,
            message="Summary generated, checking flags..."
        )
        
        # Step 3: Run flag checks
        flags_dict = run_all_checks(content, job_id=job_id)
        flags = FlagsResponse(
            sanctions=FlagResult(**flags_dict['sanctions']),
            military=FlagResult(**flags_dict['military']),
            dual_use=FlagResult(**flags_dict['dual_use']),
            any_flags=flags_dict['any_flags']
        )
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=60,
            message="Flags checked, classifying NAICS..."
        )
        
        # Step 4: Classify NAICS
        naics_dict = classify_naics_structured(summary_dict, job_id=job_id)
        naics = NAICSResponse(**naics_dict)
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=70,
            message="NAICS classified, extracting details..."
        )
        
        # Step 5: Extract company registration
        company_registration = extract_company_registration(content, job_id=job_id)
        company_reg_obj = CompanyRegistration(**company_registration) if any(company_registration.values()) else None
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=80,
            message="Company registration extracted, extracting address..."
        )
        
        # Step 6: Extract address
        address_text = extract_address(content, job_id=job_id)
        if address_text:
            # Actually validate the address
            from src.utils.address_validator import validate_address, check_address_makes_sense
            address_validation_dict = validate_address(address_text)
            address_sense = check_address_makes_sense(address_text, summary.nature)
            
            address = AddressResponse(
                address=address_text,
                validation=AddressValidation(**address_validation_dict),
                makes_sense=address_sense
            )
        else:
            address = AddressResponse(
                address=None,
                validation=AddressValidation(valid=False, notes="No address found"),
                makes_sense=None
            )
        
        job_manager.update_job_status(
            job_id,
            JobStatus.PROCESSING,
            progress=95,
            message="Finalizing results..."
        )
        
        # Step 7: Create result
        result = AnalysisResult(
            url=url,
            timestamp=datetime.now().isoformat(),
            summary=summary,
            naics_codes=naics,
            flags=flags,
            address=address,
            company_registration=company_reg_obj,
            screenshots={}
        )
        
        # Update status: Completed
        job_manager.update_job_status(
            job_id,
            JobStatus.COMPLETED,
            progress=100,
            message="Analysis completed successfully",
            result=result
        )
        job_manager.add_log(job_id, "Analysis completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        job_manager.add_log(job_id, f"Error: {error_msg}")
        job_manager.update_job_status(
            job_id,
            JobStatus.FAILED,
            progress=0,
            message=f"Analysis failed: {error_msg}",
            error=error_msg
        )
