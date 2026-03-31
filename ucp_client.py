"""
UCP API Client — thin httpx wrapper for calling the UCP merchant API.
No Firebase dependencies. Just HTTP.
"""
import os
import httpx

UCP_BASE_URL = os.getenv("UCP_BASE_URL", "https://ucp.c0a1.in")
TIMEOUT = 30


def _get(path: str, token: str = None) -> dict | list:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(f"{UCP_BASE_URL}{path}", headers=headers)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, data: dict = None, token: str = None, form: bool = False) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=TIMEOUT) as client:
        if form:
            resp = client.post(f"{UCP_BASE_URL}{path}", data=data, headers=headers)
        else:
            resp = client.post(f"{UCP_BASE_URL}{path}", json=data, headers=headers)
        resp.raise_for_status()
        return resp.json()


# --- Discovery ---

def discover() -> dict:
    """Fetch the UCP discovery profile."""
    return _get("/.well-known/ucp")


def get_oauth_config() -> dict:
    """Fetch the OAuth authorization server config."""
    return _get("/.well-known/oauth-authorization-server")


# --- Agent Auth Session ---

def get_agent_session(session_id: str) -> dict:
    """Check if the user has completed OAuth sign-in for this agent session."""
    return _get(f"/agent/session/{session_id}")


# --- Products (no auth) ---

def list_products(category: str = None) -> list:
    """List all products, optionally filtered by category."""
    path = "/products"
    if category:
        path += f"?category={category}"
    return _get(path)


def get_product(product_id: str) -> dict:
    """Get a single product by ID."""
    return _get(f"/products/{product_id}")


# --- Checkout (auth required) ---

def create_checkout(line_items: list[dict], token: str) -> dict:
    """Create a new checkout session."""
    return _post("/checkout/sessions", data={"line_items": line_items}, token=token)


def update_checkout(session_id: str, buyer: dict, token: str) -> dict:
    """Update a checkout session with buyer info."""
    return _post(f"/checkout/sessions/{session_id}/update", data={"buyer": buyer}, token=token)


def complete_checkout(session_id: str, token: str) -> dict:
    """Complete a checkout session — places the order."""
    return _post(f"/checkout/sessions/{session_id}/complete", token=token)


# --- Orders (auth required) ---

def get_order(order_id: str, token: str) -> dict:
    """Get order details by ID."""
    return _get(f"/orders/{order_id}", token=token)


def list_orders(token: str) -> list:
    """List all orders for the authenticated user."""
    return _get("/orders", token=token)
