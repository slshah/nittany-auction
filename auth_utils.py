SUPPORTED_ROLES = {"seller", "bidder", "helpdesk"}

ROLE_TO_ENDPOINT = {
    "seller": "seller.seller_welcome",
    "bidder": "bidder.bidder_welcome",
    "helpdesk": "helpdesk.helpdesk_welcome",
}

def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_role_label(value: str):
    if not value:
        return None
    role = value.strip().lower()
    if role == "buyer":
        return "bidder"
    if role in SUPPORTED_ROLES:
        return role
    return None
