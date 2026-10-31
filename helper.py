# Add your utilities or helper functions to this file.

import os
from dotenv import load_dotenv, find_dotenv
                     
def load_env():
    _ = load_dotenv(find_dotenv(), override=True)

def get_openai_api_key():
    load_env()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    return openai_api_key


def get_phoenix_endpoint():
    load_env()
    phoenix_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    print(f"Phoenix endpoint: {phoenix_endpoint}")
    return phoenix_endpoint


def get_phoenix_trace_endpoint():
    phoenix_endpoint = get_phoenix_endpoint()
    if not phoenix_endpoint:
        raise RuntimeError("PHOENIX_COLLECTOR_ENDPOINT must be set to export Phoenix traces.")
    return f"{phoenix_endpoint.rstrip('/')}/v1/traces"

