# test_env.py
import os
import dotenv

# Load .env file
dotenv.load_dotenv()

# Print all environment variables
print("Environment variables:")
for key, value in os.environ.items():
    if "AUTH0" in key:
        print(f"{key}: {value}")

# Specifically check for AUTH0_DOMAIN
auth0_domain = os.environ.get("AUTH0_DOMAIN")
print(f"AUTH0_DOMAIN: {auth0_domain}")