import os
import sys

from locust import HttpUser, between, task

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("MOCK_AI", "1")
os.environ.setdefault("MOCK_AI_DELAY", "0.5")


class PolishUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        username = f"perfuser_{self.environment.runner.user_count}"
        self.client.post(
            "/api/register",
            json={"username": username, "password": "perfpass"},
        )
        self.client.post(
            "/api/login",
            json={"username": username, "password": "perfpass"},
        )

    @task(3)
    def view_history(self):
        self.client.get("/api/history?page=1&per_page=10")

    @task(1)
    def polish_text(self):
        self.client.post(
            "/api/polish",
            json={"text": "写一篇关于 AI 的博客文章"},
        )
