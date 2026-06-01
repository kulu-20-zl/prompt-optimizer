import os
import sys
import threading
import time

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["MOCK_AI"] = "1"
os.environ["MOCK_AI_DELAY"] = "0"


@pytest.fixture(scope="module")
def live_server():
    from backend.app import create_app

    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "selenium-test",
        }
    )

    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server_thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1", port=port, threaded=True, use_reloader=False
        ),
        daemon=True,
    )
    server_thread.start()
    time.sleep(1)

    class Server:
        url = f"http://127.0.0.1:{port}"

    yield Server()


@pytest.fixture
def driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    service = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=service, options=options)
    drv.implicitly_wait(5)
    yield drv
    drv.quit()


def test_full_flow(driver, live_server):
    username = f"seluser_{int(time.time())}"
    password = "testpass123"
    wait = WebDriverWait(driver, 15)

    driver.get(f"{live_server.url}/")

    driver.find_element(By.CSS_SELECTOR, '[data-switch="register"]').click()
    driver.find_element(By.ID, "register-username").send_keys(username)
    driver.find_element(By.ID, "register-email").send_keys(f"{username}@test.com")
    driver.find_element(By.ID, "register-password").send_keys(password)
    driver.find_element(By.ID, "register-confirm").send_keys(password)
    driver.find_element(By.ID, "register-form").submit()
    time.sleep(0.8)

    driver.find_element(By.ID, "login-username").send_keys(username)
    driver.find_element(By.ID, "login-password").send_keys(password)
    driver.find_element(By.ID, "login-form").submit()

    wait.until(EC.element_to_be_clickable((By.ID, "polish-btn")))

    input_box = driver.find_element(By.ID, "original-text")
    input_box.clear()
    input_box.send_keys("给我一些健康饮食的建议")
    driver.find_element(By.ID, "polish-btn").click()

    polished = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-row.ai .bubble-text"))
    )
    assert "健康" in polished.text or len(polished.text) > 0

    star5 = driver.find_element(
        By.CSS_SELECTOR, ".bubble-rating .rating-star[data-value='5']"
    )
    star5.click()

    rating_msg = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".rate-hint"))
    )
    assert "平均分" in rating_msg.text or "已评分" in rating_msg.text

    driver.find_element(By.CSS_SELECTOR, '.nav-btn[data-view="history"]').click()
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "history-item")))

    history_items = driver.find_elements(By.CLASS_NAME, "history-item")
    assert len(history_items) >= 1
    assert "5星" in history_items[0].text or "★" in history_items[0].text

    delete_btn = history_items[0].find_element(By.CLASS_NAME, "delete-btn")
    driver.execute_script("window.confirm = function(){ return true; }")
    delete_btn.click()
    time.sleep(1)

    driver.refresh()
    driver.find_element(By.CSS_SELECTOR, '.nav-btn[data-view="history"]').click()
    time.sleep(1)
    remaining = driver.find_elements(By.CLASS_NAME, "history-item")
    assert len(remaining) == 0 or "暂无" in driver.find_element(By.ID, "history-list").text
