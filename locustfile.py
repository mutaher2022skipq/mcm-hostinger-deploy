from locust import HttpUser, task, between

class MCMUser(HttpUser):
    wait_time = between(1, 5)

    @task(3)
    def load_login(self):
        """Simulate loading the login page (high traffic)"""
        self.client.get("/accounts/login/")

    @task(1)
    def load_register(self):
        """Simulate loading the registration page"""
        self.client.get("/accounts/register/")

    @task(2)
    def load_static_assets(self):
        """Simulate browser fetching static files (Nginx test)"""
        self.client.get("/static/css/style.css")  # Adjust path if needed
        self.client.get("/static/images/logo.png")

    # Note: To test authenticated pages (dashboard), we would need to 
    # simulate login by posting credentials, but for general capacity 
    # testing, hitting public endpoints is a good first step to test 
    # Nginx/Gunicorn throughput.
