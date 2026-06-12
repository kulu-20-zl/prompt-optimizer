import os
import sys
import time

from locust import HttpUser, between, task

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("MOCK_AI", "1")
os.environ.setdefault("MOCK_AI_DELAY", "0.1")


class PolishUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        uid = f"{int(time.time() * 1000)}_{self.environment.runner.user_count}"
        username = f"perfuser_{uid}"
        email = f"{username}@perf.test"
        password = "perfpass123"

        with self.client.post(
            "/api/register",
            json={
                "username": username,
                "email": email,
                "password": password,
                "confirm_password": password,
            },
            catch_response=True,
        ) as resp:
            if resp.status_code not in (201, 409):
                resp.failure(f"register failed: {resp.status_code}")

        with self.client.post(
            "/api/login",
            json={"username": username, "password": password},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"login failed: {resp.status_code}")

    @task(3)
    def view_history(self):
        self.client.get("/api/history?page=1&per_page=10", name="/api/history")

    @task(1)
    def polish_text(self):
        self.client.post(
            "/api/polish",
            json={"text": "写一篇关于 AI 的博客文章", "mode": "writing"},
            name="/api/polish",
        )
