"""
UCP Agent Tools — 10 functions the agent can call.
3 for identity linking + 7 for commerce.
"""
import json
import uuid
import os
from google.adk.tools import ToolContext
from . import ucp_client


UCP_BASE_URL = os.getenv("UCP_BASE_URL", "https://ucp.c0a1.in")


# ============================================================
# Identity Linking Tools (3)
# ============================================================

def link_account(tool_context: ToolContext) -> dict:
    """Generate a sign-in link for the user to link their account.
    The user must open this link in their browser and sign in with Google.
    After sign-in, the agent will automatically detect the linked account.

    Returns:
        A dict with the sign-in URL for the user.
    """
    session_id = str(uuid.uuid4())
    tool_context.state["agent_session_id"] = session_id

    callback_url = f"{UCP_BASE_URL}/agent/callback?session_id={session_id}"
    oauth_url = (
        f"{UCP_BASE_URL}/oauth/authorize"
        f"?client_id=adk_agent"
        f"&redirect_uri={callback_url}"
        f"&response_type=code"
        f"&state={session_id}"
    )

    return {
        "status": "sign_in_required",
        "sign_in_url": oauth_url,
        "message": "Please ask the user to open this URL and sign in with Google.",
    }


def check_auth(tool_context: ToolContext) -> dict:
    """Check if the user has completed sign-in after clicking the link.
    Call this after asking the user to sign in. If they haven't signed in yet,
    wait a moment and try again.

    Returns:
        A dict with status 'linked' (with email) or 'pending'.
    """
    session_id = tool_context.state.get("agent_session_id")
    if not session_id:
        return {"status": "error", "message": "No sign-in was initiated. Call link_account first."}

    try:
        result = ucp_client.get_agent_session(session_id)
    except Exception as e:
        return {"status": "error", "message": f"Failed to check auth: {e}"}

    if result.get("status") == "linked":
        tool_context.state["auth_token"] = result["token"]
        return {
            "status": "linked",
            "email": result.get("email", ""),
            "message": "Account linked successfully!",
        }

    return {
        "status": "pending",
        "message": "User hasn't signed in yet. Wait a moment and try again.",
    }


def get_auth_status(tool_context: ToolContext) -> dict:
    """Quick check if the user is already authenticated.

    Returns:
        A dict with authenticated (true/false).
    """
    token = tool_context.state.get("auth_token")
    return {"authenticated": token is not None}


# ============================================================
# Commerce Tools (7)
# ============================================================

def browse_products(category: str = "") -> dict:
    """Browse the store's product catalog. Shows all available products with names, prices in INR, and IDs.

    Args:
        category: Optional category filter (e.g. 'electronics', 'fashion', 'home'). Leave empty for all products.

    Returns:
        A dict with a list of products.
    """
    try:
        products = ucp_client.list_products(category=category if category else None)
        # Format for readability
        formatted = []
        for p in products:
            formatted.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "price": p.get("price"),
                "category": p.get("category"),
                "description": p.get("description", ""),
                "inventory": p.get("inventory", 0),
            })
        return {"products": formatted, "count": len(formatted)}
    except Exception as e:
        return {"error": f"Failed to fetch products: {e}"}


def get_product_details(product_id: str) -> dict:
    """Get detailed information about a specific product.

    Args:
        product_id: The unique ID of the product (from browse_products results).

    Returns:
        Full product details including name, price, description, inventory.
    """
    try:
        return ucp_client.get_product(product_id)
    except Exception as e:
        return {"error": f"Product not found: {e}"}


def start_checkout(items: str, tool_context: ToolContext) -> dict:
    """Create a new checkout session with the specified items.
    The user must be authenticated (linked) before calling this.

    Args:
        items: A JSON string containing a list of items. Each item must have:
               id (product ID), name, quantity (int), price (number in INR).
               Example: '[{"id":"abc123","name":"Headphones","quantity":2,"price":4999}]'
        tool_context: Provided automatically.

    Returns:
        Checkout session details with session ID and status.
    """
    token = tool_context.state.get("auth_token")
    if not token:
        return {"error": "User not authenticated. Call link_account first."}

    try:
        line_items = json.loads(items)
    except json.JSONDecodeError:
        return {"error": "Invalid items JSON. Must be a list of {id, name, quantity, price}."}

    try:
        result = ucp_client.create_checkout(line_items, token)
        session_id = result.get("id")
        tool_context.state["checkout_session_id"] = session_id
        return {
            "session_id": session_id,
            "status": result.get("status"),
            "items": result.get("line_items") or result.get("lineItems", []),
            "message": "Checkout session created. Now collect buyer info.",
        }
    except Exception as e:
        return {"error": f"Failed to create checkout: {e}"}


def add_buyer_info(
    email: str,
    city: str,
    state: str,
    street: str = "",
    zip_code: str = "",
    payment_method: str = "razorpay",
    tool_context: ToolContext = None,
) -> dict:
    """Provide buyer shipping and payment details for the current checkout.

    Args:
        email: Buyer's email address.
        city: Shipping city (e.g. 'Bangalore').
        state: Shipping state (e.g. 'Karnataka' or 'KA').
        street: Street address (optional).
        zip_code: Postal/ZIP code (optional).
        payment_method: Payment method, defaults to 'razorpay'.
        tool_context: Provided automatically.

    Returns:
        Updated checkout session with status (should become 'ready_for_complete').
    """
    token = tool_context.state.get("auth_token")
    if not token:
        return {"error": "User not authenticated. Call link_account first."}

    session_id = tool_context.state.get("checkout_session_id")
    if not session_id:
        return {"error": "No active checkout. Call start_checkout first."}

    buyer = {
        "email": email,
        "shipping_address": {
            "street": street,
            "city": city,
            "state": state,
            "zip": zip_code,
        },
        "payment_method": payment_method,
    }

    try:
        result = ucp_client.update_checkout(session_id, buyer, token)
        return {
            "session_id": session_id,
            "status": result.get("status"),
            "buyer": buyer,
            "message": "Buyer info added. Session is ready for completion." if result.get("status") == "ready_for_complete" else "Buyer info updated.",
        }
    except Exception as e:
        return {"error": f"Failed to update checkout: {e}"}


def complete_purchase(tool_context: ToolContext) -> dict:
    """Finalize and complete the current checkout. This places the order.
    Only call this after the user has confirmed the order summary.

    Args:
        tool_context: Provided automatically.

    Returns:
        Order confirmation with order ID.
    """
    token = tool_context.state.get("auth_token")
    if not token:
        return {"error": "User not authenticated. Call link_account first."}

    session_id = tool_context.state.get("checkout_session_id")
    if not session_id:
        return {"error": "No active checkout. Call start_checkout first."}

    try:
        result = ucp_client.complete_checkout(session_id, token)
        order_id = result.get("orderId") or result.get("order_id", "")
        tool_context.state["last_order_id"] = order_id
        tool_context.state["checkout_session_id"] = ""
        return {
            "status": "complete",
            "order_id": order_id,
            "message": f"Order placed successfully! Order ID: {order_id}",
        }
    except Exception as e:
        return {"error": f"Failed to complete purchase: {e}"}


def check_order_status(order_id: str, tool_context: ToolContext) -> dict:
    """Check the status of an order.

    Args:
        order_id: The order ID (e.g. 'ORD-A1B2C3D4').
        tool_context: Provided automatically.

    Returns:
        Order details including status, items, and tracking info.
    """
    token = tool_context.state.get("auth_token")
    if not token:
        return {"error": "User not authenticated. Call link_account first."}

    try:
        order = ucp_client.get_order(order_id, token)
        return {
            "order_id": order.get("id"),
            "status": order.get("status"),
            "total": order.get("total"),
            "items": order.get("line_items") or order.get("lineItems", []),
            "tracking_url": order.get("tracking_url") or order.get("trackingUrl"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch order: {e}"}


def list_my_orders(tool_context: ToolContext) -> dict:
    """List all orders for the authenticated user.

    Args:
        tool_context: Provided automatically.

    Returns:
        A list of orders with IDs, statuses, and totals.
    """
    token = tool_context.state.get("auth_token")
    if not token:
        return {"error": "User not authenticated. Call link_account first."}

    try:
        orders = ucp_client.list_orders(token)
        formatted = []
        for o in orders:
            formatted.append({
                "order_id": o.get("id"),
                "status": o.get("status"),
                "total": o.get("total"),
                "items_count": len(o.get("line_items") or o.get("lineItems") or []),
            })
        return {"orders": formatted, "count": len(formatted)}
    except Exception as e:
        return {"error": f"Failed to fetch orders: {e}"}
