import time, logging
from fastapi import Request


class LoggingMiddleware():

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)  


    async def logging_request(self, request: Request, call_next):
        call_up_time = time.time()
        response = await call_next(request)

        duration = (time.time() - call_up_time) * 1000

        self.logger.info(f" {request.method} | {request.url.path} | {request.client.host} | {response.status_code} | {duration:.0f}ms")

        return response