from locust import HttpUser, task, between
import random
import string

def random_url():
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=5))
    return f"http://example.com/{rand_str}"

class URLShortenerUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def create_link(self):
        original_url = random_url()
        self.client.post("/links/shorten", json={"original_url": original_url})

    @task(2)
    def redirect_link(self):
        original_url = random_url()
        response = self.client.post("/links/shorten", json={"original_url": original_url})
        if response.ok:
            short_code = response.json()["short_code"]
            self.client.get(f"/links/{short_code}", allow_redirects=False)