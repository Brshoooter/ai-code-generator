"""
Wrapper peste boto3 pentru S3, cu fallback la "stub local" pe disk.

Logica: daca settings.s3_bucket e gol (ex. nu am cont AWS inca), folosim
un director local ca sa simulam S3. API-ul wrapper-ului ramane acelasi —
codul de business (rag_service, routes) nu stie diferenta. Cand utilizatorul
isi face cont AWS si seteaza FILES_S3_BUCKET in .env, comutam automat la
boto3 real fara sa modificam alte fisiere.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class S3Client:

    def __init__(self, settings):
        self.use_stub = not settings.s3_bucket

        if self.use_stub:
            self.stub_dir = Path(settings.s3_local_stub_dir)
            self.stub_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"S3Client in mod STUB local: {self.stub_dir}")
        else:
            # importul boto3 e local (lazy) ca sa nu-l incarcam la pornire
            # daca oricum suntem in mod stub
            import boto3
            self.bucket = settings.s3_bucket
            self.client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            logger.info(f"S3Client in mod AWS real: bucket={self.bucket} region={settings.aws_region}")

    # ─── Operatii uzuale ────────────────────────────────────────────

    def put_object(self, key: str, body: bytes, content_type: str) -> None:
        """Salveaza un obiect (fisier) sub key-ul dat."""
        if self.use_stub:
            target = self.stub_dir / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            return
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def get_object(self, key: str) -> bytes:
        """Citeste un obiect. Util daca vrem ulterior re-procesare."""
        if self.use_stub:
            return (self.stub_dir / key).read_bytes()
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def delete_object(self, key: str) -> None:
        """Sterge un singur obiect. Idempotent: nu da eroare daca lipseste."""
        if self.use_stub:
            target = self.stub_dir / key
            if target.exists():
                target.unlink()
            return
        # boto3 nu da eroare nici el daca obiectul nu exista
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefix(self, prefix: str) -> int:
        """
        Sterge toate obiectele care incep cu prefix. Folosit la cleanup
        cascade din History (DELETE conversation → toate fisierele aferente).
        Returneaza cate obiecte au fost sterse.
        """
        if self.use_stub:
            target_dir = self.stub_dir / prefix
            if not target_dir.exists():
                return 0
            count = sum(1 for _ in target_dir.rglob("*") if _.is_file())
            shutil.rmtree(target_dir, ignore_errors=True)
            return count

        # AWS: list_objects_v2 e paginat — la peste 1000 obiecte trebuie continuation token.
        # Pentru proiectul nostru cu max 5 fisiere/conversatie, o singura pagina e suficienta.
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        contents = resp.get("Contents", [])
        if not contents:
            return 0
        self.client.delete_objects(
            Bucket=self.bucket,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
        )
        return len(contents)
