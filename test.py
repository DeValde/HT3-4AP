import pytest
import time
import random
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
import redis_client

client = TestClient(app)


# Override redis client for tests
class FakeRedis:
    def get(self, key):
        return None

    def set(self, key, value, ex=None):
        pass

    def delete(self, key):
        pass


redis_client.r = FakeRedis()


def register_user(username: str, email: str, password: str):
    response = client.post("/users/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    return response


def login_user(username: str, password: str):
    response = client.post("/token", data={
        "username": username,
        "password": password
    })
    return response.json()


def normalize_url(url: str) -> str:
    return url.rstrip("/")


def test_create_and_redirect_link():
    original_url = "http://example.com"
    response = client.post("/links/shorten", json={"original_url": original_url})
    assert response.status_code == 200, response.text
    data = response.json()
    short_code = data["short_code"]

    redirect_response = client.get(f"/links/{short_code}", follow_redirects=False)
    assert redirect_response.status_code in (302, 307)
    assert normalize_url(redirect_response.headers["location"]) == normalize_url(original_url)


def test_create_link_with_custom_alias():
    custom_alias = f"custom{random.randint(1000, 9999)}"
    original_url = "http://example.org"
    response = client.post("/links/shorten", json={
        "original_url": original_url,
        "custom_alias": custom_alias
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["short_code"] == custom_alias


def test_link_stats():
    original_url = "http://example.net"
    create_response = client.post("/links/shorten", json={"original_url": original_url})
    assert create_response.status_code == 200, create_response.text
    short_code = create_response.json()["short_code"]
    #aimulate redirect
    client.get(f"/links/{short_code}", follow_redirects=False)
    stats_response = client.get(f"/links/{short_code}/stats")
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()
    assert normalize_url(stats["original_url"]) == normalize_url(original_url)
    assert stats["click_count"] >= 1
    assert "created_at" in stats


def test_update_and_delete_link():
    unique_suffix = str(int(time.time() * 1000)) + str(random.randint(100, 999))
    username = f"tester_{unique_suffix}"
    email = f"tester_{unique_suffix}@example.com"
    password = "secretpassword"
    reg_response = register_user(username, email, password)
    if reg_response.status_code not in (200, 400):
        pytest.fail(f"Unexpected registration status: {reg_response.status_code}, {reg_response.text}")

    token_data = login_user(username, password)
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    original_url = "http://update.com"
    create_response = client.post("/links/shorten", json={"original_url": original_url}, headers=headers)
    assert create_response.status_code == 200, create_response.text
    short_code = create_response.json()["short_code"]

    new_url = "http://updated.com"
    update_response = client.put(f"/links/{short_code}", json={"original_url": new_url}, headers=headers)
    assert update_response.status_code == 200, update_response.text
    updated_data = update_response.json()
    assert normalize_url(updated_data["original_url"]) == normalize_url(new_url)

    delete_response = client.delete(f"/links/{short_code}", headers=headers)
    assert delete_response.status_code == 200, delete_response.text

    get_response = client.get(f"/links/{short_code}")
    assert get_response.status_code == 404


def test_search_link():
    original_url = "http://searchtest.com"
    create_response = client.post("/links/shorten", json={"original_url": original_url})
    assert create_response.status_code == 200, create_response.text

    search_response = client.get(f"/links/search?original_url={original_url}")
    assert search_response.status_code == 200, search_response.text
    links = search_response.json()
    assert isinstance(links, list)
    assert any(normalize_url(link["original_url"]) == normalize_url(original_url) for link in links)



def test_expired_link():
    past_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    original_url = "http://expired.com"
    response = client.post("/links/shorten", json={
        "original_url": original_url,
        "expires_at": past_time
    })
    assert response.status_code == 200, response.text
    short_code = response.json()["short_code"]
    redirect_response = client.get(f"/links/{short_code}", follow_redirects=False)
    assert redirect_response.status_code == 410


def test_duplicate_registration():
    username = "duplicateuser"
    email = "duplicate@example.com"
    password = "secret"
    response1 = register_user(username, email, password)
    assert response1.status_code in (200, 400)
    response2 = register_user(username, email, password)
    assert response2.status_code == 400


def test_update_link_unauthorized():
    unique_suffix = str(int(time.time() * 1000)) + str(random.randint(100, 999))
    username1 = f"user1_{unique_suffix}"
    email1 = f"user1_{unique_suffix}@example.com"
    password1 = "secret1"
    register_user(username1, email1, password1)
    token_data1 = login_user(username1, password1)
    token1 = token_data1["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    original_url = "http://updateunauth.com"
    create_response = client.post("/links/shorten", json={"original_url": original_url}, headers=headers1)
    assert create_response.status_code == 200, create_response.text
    short_code = create_response.json()["short_code"]

    username2 = f"user2_{unique_suffix}"
    email2 = f"user2_{unique_suffix}@example.com"
    password2 = "secret2"
    register_user(username2, email2, password2)
    token_data2 = login_user(username2, password2)
    token2 = token_data2["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    new_url = "http://unauthorizedupdate.com"
    update_response = client.put(f"/links/{short_code}", json={"original_url": new_url}, headers=headers2)
    assert update_response.status_code == 404


def test_delete_link_unauthorized():
    unique_suffix = str(int(time.time() * 1000)) + str(random.randint(100, 999))
    username1 = f"deluser1_{unique_suffix}"
    email1 = f"deluser1_{unique_suffix}@example.com"
    password1 = "secret1"
    register_user(username1, email1, password1)
    token_data1 = login_user(username1, password1)
    token1 = token_data1["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    original_url = "http://deleteunauth.com"
    create_response = client.post("/links/shorten", json={"original_url": original_url}, headers=headers1)
    assert create_response.status_code == 200, create_response.text
    short_code = create_response.json()["short_code"]

    username2 = f"deluser2_{unique_suffix}"
    email2 = f"deluser2_{unique_suffix}@example.com"
    password2 = "secret2"
    register_user(username2, email2, password2)
    token_data2 = login_user(username2, password2)
    token2 = token_data2["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    delete_response = client.delete(f"/links/{short_code}", headers=headers2)
    assert delete_response.status_code == 404