from config import settings
from fastapi import Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx, logging


class ProxyService:

    def __init__(self):
        self.client = httpx.AsyncClient()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)


    async def forward_request(self, request: Request, target_url: str, path: str):
        try:
            url = target_url.rstrip("/") + path
            if request.query_params:
                url += "?" + str(request.query_params)
            body = await request.body()

            headers = dict(request.headers)
            headers.pop("host", None)

            req = self.client.build_request(
                method=request.method,
                url = url,
                content = body,
                headers = headers,
                timeout = settings.request_timeout
            )

            response = await self.client.send(req, stream=True)

            async def _stream_response():
                try:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                finally:
                    await response.aclose()

            return StreamingResponse(
                _stream_response(),
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "text/plain")
            )
        except Exception as e:
            self.logger.error(f"Eroare in proxy la trimiterea requestului catre {target_url}: {e}")
            return JSONResponse(
                status_code=502,
                content={"detail": "Eroare la comunicarea cu microserviciul"}
            )