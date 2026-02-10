"""
SEC EDGAR Document Proxy.

Proxies requests to SEC EDGAR to bypass CORS restrictions for iframe embedding.
SEC filings are immutable once published, so aggressive caching is safe.
"""

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sec-proxy", tags=["SEC Proxy"])

# Allowed SEC domains for security
ALLOWED_HOSTS = {"www.sec.gov", "sec.gov", "efts.sec.gov"}

# SEC requires a User-Agent with contact info
SEC_USER_AGENT = "PTC-Agent contact@example.com"


@router.get("/document")
async def proxy_sec_document(
    url: str = Query(..., description="SEC EDGAR document URL"),
):
    """Proxy SEC EDGAR documents to bypass CORS for iframe embedding."""
    # Validate URL domain
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Only SEC EDGAR URLs (sec.gov) are allowed",
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": SEC_USER_AGENT},
                follow_redirects=True,
            )
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="SEC EDGAR request timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"SEC EDGAR returned {e.response.status_code}",
        )
    except httpx.HTTPError as e:
        logger.warning(f"SEC proxy fetch failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch from SEC EDGAR")

    content_type = resp.headers.get("content-type", "text/html")

    return Response(
        content=resp.content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )
