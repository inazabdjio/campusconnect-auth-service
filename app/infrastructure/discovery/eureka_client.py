import socket
import threading
import time
import httpx


class EurekaClient:
    def __init__(
        self,
        enabled: bool,
        eureka_url: str,
        app_name: str,
        port: int,
        host_name: str | None = None,
        heartbeat_interval: int = 30,
    ):
        self.enabled = enabled
        self.eureka_url = eureka_url.rstrip("/")
        self.app_name = app_name.upper()
        self.port = port
        self.host_name = host_name or socket.gethostname()
        self.instance_id = f"{self.host_name}:{self.app_name.lower()}:{self.port}"
        self.heartbeat_interval = heartbeat_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _apps_base_url(self) -> str:
        if self.eureka_url.endswith("/eureka"):
            return f"{self.eureka_url}/apps/{self.app_name}"
        return f"{self.eureka_url}/eureka/apps/{self.app_name}"

    def _instance_payload(self) -> dict:
        ip_addr = socket.gethostbyname(self.host_name)
        return {
            "instance": {
                "instanceId": self.instance_id,
                "hostName": self.host_name,
                "app": self.app_name,
                "vipAddress": self.app_name.lower(),
                "secureVipAddress": self.app_name.lower(),
                "ipAddr": ip_addr,
                "status": "UP",
                "port": {"$": self.port, "@enabled": "true"},
                "healthCheckUrl": f"http://{self.host_name}:{self.port}/health",
                "statusPageUrl": f"http://{self.host_name}:{self.port}/health",
                "homePageUrl": f"http://{self.host_name}:{self.port}/",
                "dataCenterInfo": {
                    "@class": "com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo",
                    "name": "MyOwn",
                },
            }
        }

    def register(self) -> None:
        if not self.enabled:
            return
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(self._apps_base_url(), json=self._instance_payload())
                resp.raise_for_status()
        except Exception:
            pass

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.heartbeat_interval):
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.put(
                        f"{self._apps_base_url()}/{self.instance_id}",
                        params={"status": "UP"},
                    )
                    if resp.status_code == 404:
                        self.register()
            except Exception:
                pass

    def start(self) -> None:
        if not self.enabled:
            return
        self.register()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        try:
            with httpx.Client(timeout=5.0) as client:
                client.delete(f"{self._apps_base_url()}/{self.instance_id}")
        except Exception:
            pass