from fastapi import APIRouter, HTTPException

from api.v1.schemas import JobStatusResponse
from api.v1.routes.analyze import get_jobs_store

router = APIRouter()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
    """
    GET /api/v1/jobs/{job_id}

    Retorna o status de um job assíncrono de análise.
    Jobs ficam em memória 30 min após conclusão (TTL gerenciado pelo lifespan).

    Response:
        status: "processing" | "done" | "error"
        result: AnalyzeResponse | null
        error:  string | null
    """
    jobs = get_jobs_store()

    if job_id not in jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' não encontrado ou já expirou.",
        )

    job = jobs[job_id]

    return JobStatusResponse(
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
    )