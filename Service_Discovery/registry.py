from models import RegisterRequest, ServiceInformation
from datetime import datetime
import threading
import logging
from config import settings
from pydantic import AnyHttpUrl

class ServiceRegistry():

    def __init__(self):
        self.microservices: dict[str, list[ServiceInformation]] = {}
        self.lock = threading.Lock()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    

    def register(self, request: RegisterRequest) -> ServiceInformation:
        with self.lock:
            if request.name not in self.microservices:
                self.microservices[request.name] = []

            for instance in self.microservices[request.name]:
                if request.url == instance.url:
                    instance.service_health = True
                    instance.failed_attempts = 0
                    instance.last_health_verification = datetime.now()
                    self.logger.info(f"Update la instanta de tipul {instance.name} cu url-ul {instance.url}")
                    return instance
                
            serviceInf = ServiceInformation(name = request.name, url = request.url, last_health_verification = datetime.now())
            self.microservices[request.name].append(serviceInf)
            self.logger.info(f"S-a inregistrat o noua instanta de tipul {request.name} cu url-ul {request.url}")
            return serviceInf

            
                    
    def deregister(self, name: str, url: AnyHttpUrl) -> bool:
        with self.lock:
            if name in self.microservices:
                for instance in self.microservices[name]:
                    if instance.url == url:
                        self.microservices[name].remove(instance)
                        if not self.microservices[name]:
                            self.microservices.pop(name)
                            self.logger.info(f"Nu mai exista instante de tipul {name}")
                        else:
                            self.logger.info(f"Instanta {name}: {url} a fost stearsa cu succes")
                        return True
            self.logger.warning(f"Nu s-a depistat nici o instanta de tipul {name} cu url: {url}")
            return False
        
    def get_service(self, name: str) -> list[ServiceInformation] | None:
        with self.lock:
            if name not in self.microservices:
                return None
            services_list = [ x for x in self.microservices[name] if x.service_health == True]
            return services_list
        
    def get_all_services(self) -> dict:
        with self.lock:
            return {name: list(instances) for name, instances in self.microservices.items()}
        
    def update_health(self, name: str, url: AnyHttpUrl, is_healthy: bool) -> None:
        with self.lock:
            if name not in self.microservices:
                self.logger.warning("Acest microserviciu nu exista")
                return
            for instance in self.microservices[name]:
                if instance.url == url:
                    if is_healthy:
                        instance.failed_attempts = 0
                        instance.service_health = True
                        instance.last_health_verification = datetime.now()
                        self.logger.info(f"Instanta {name}: {url} este activa")
                    else:
                        instance.failed_attempts += 1
                        if instance.failed_attempts < settings.fail_attempts:
                            self.logger.info(f"Instanta {name}: {url} a esuat. Nr. esuari: {instance.failed_attempts}")
                        else:
                            self.logger.info(f"Instanta {name}: {url} este cazuta")
                            instance.service_health = False
