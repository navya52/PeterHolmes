"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    """Request model for website analysis."""
    url: str = Field(..., description="Website URL to analyze")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.example.com"
            }
        }


class FlagResult(BaseModel):
    """Flag check result."""
    flags_raised: bool
    matches: List[str] = []
    evidence: List[str] = []
    risk_level: str = Field("NONE", description="Risk level: NONE, LOW, MEDIUM, HIGH")
    risk_score: int = Field(0, ge=0, le=100, description="Risk score from 0 to 100")
    risk_explanation: str = Field("", description="Explanation of the risk level")


class FlagsResponse(BaseModel):
    """Flags check response."""
    sanctions: FlagResult
    military: FlagResult
    dual_use: FlagResult
    any_flags: bool


class BusinessSummary(BaseModel):
    """Business summary response."""
    nature: str
    products_services: str
    countries_operating: List[str]
    countries_dealing_with: List[str]


class NAICSResponse(BaseModel):
    """NAICS classification response."""
    codes: List[str]
    primary_code: str
    explanation: str


class AddressValidation(BaseModel):
    """Address validation response."""
    valid: Optional[bool] = None  # True = valid, False = invalid, None = unknown/not checked
    image_path: Optional[str] = None
    notes: str
    is_commercial: Optional[bool] = None
    plausibility_note: Optional[str] = None
    address_types: Optional[List[str]] = None


class AddressResponse(BaseModel):
    """Address extraction and validation response."""
    address: Optional[str]
    validation: AddressValidation
    makes_sense: Optional[bool]


class CompanyRegistration(BaseModel):
    """Company registration details."""
    company_number: Optional[str] = None
    vat_number: Optional[str] = None
    eori_number: Optional[str] = None
    company_name: Optional[str] = None
    established_date: Optional[str] = None
    country_of_registration: Optional[str] = None


class LogEntry(BaseModel):
    """A single log entry."""
    timestamp: datetime
    message: str


class AnalyzeResponse(BaseModel):
    """Response model for analysis job submission."""
    job_id: str
    status: JobStatus
    message: str


class StatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: JobStatus
    progress: int = Field(0, ge=0, le=100)
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    logs: List[LogEntry] = []


class AnalysisResult(BaseModel):
    """Full analysis result."""
    url: str
    timestamp: str
    summary: BusinessSummary
    naics_codes: NAICSResponse
    flags: FlagsResponse
    address: AddressResponse
    company_registration: Optional[CompanyRegistration] = None
    screenshots: Dict[str, str] = {}


class ResultsResponse(BaseModel):
    """Response model for analysis results."""
    job_id: str
    status: JobStatus
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None


class HistoryItem(BaseModel):
    """History item model."""
    job_id: str
    url: str
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime] = None


class HistoryResponse(BaseModel):
    """Response model for analysis history."""
    items: List[HistoryItem]
    total: int

