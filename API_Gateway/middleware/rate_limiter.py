import logging
import time

from config import settings


class RateLimiter:
    """
    Sliding-window log rate limiter cu doua bucket-uri logice:
      - "anon": pentru cereri neautentificate (login, register). Cheie = IP.
        Limita mai mica, rol anti-brute-force.
      - "user": pentru cereri autentificate. Cheie = user_id din JWT.
        Limita mai mare, useri diferiti pe acelasi IP nu se mai blocheaza reciproc.
    """

    def __init__(self):
        # Dictionar separat pentru fiecare bucket logic.
        self.buckets: dict[str, dict[str, list[float]]] = {
            "anon": {},
            "user": {},
        }

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _is_allowed(self, bucket_name: str, key: str, limit: int, window: int) -> bool:
        current_time = time.time()
        bucket = self.buckets[bucket_name]

        # Curata timestamp-urile expirate doar pentru cheia curenta (O(M), nu O(N*M)).
        timestamps = [t for t in bucket.get(key, []) if current_time - t < window]

        if len(timestamps) >= limit:
            bucket[key] = timestamps
            self.logger.warning(
                f"Rate limit depasit [{bucket_name}] pentru cheia {key} "
                f"({len(timestamps)}/{limit} in {window}s)"
            )
            return False

        timestamps.append(current_time)
        bucket[key] = timestamps
        return True

    def allow_anon(self, ip: str) -> bool:
        return self._is_allowed(
            "anon",
            ip,
            settings.rate_limit_anon_requests,
            settings.rate_limit_time_window,
        )

    def allow_user(self, user_id: str) -> bool:
        return self._is_allowed(
            "user",
            user_id,
            settings.rate_limit_user_requests,
            settings.rate_limit_time_window,
        )
