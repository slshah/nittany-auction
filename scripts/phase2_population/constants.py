ROLE_FILE_MAP = {
    "seller": "Sellers.csv",
    "bidder": "Bidders.csv",
    "helpdesk": "Helpdesk.csv",
}
ROLE_PRIORITY = ("helpdesk", "seller", "bidder")

HELPDESK_TEAM_EMAIL = "helpdeskteam@lsu.edu"
HELPDESK_TEAM_POSITION = "Queue"
HELPDESK_TEAM_PASSWORD = "helpdeskteam-disabled"

ROOT_CATEGORY_NAME = "All"
ROOT_PARENT_TOKEN = "root"

LISTING_STATUS_MAP = {
    "0": 0,
    "1": 1,
    "2": 2,
    "inactive": 0,
    "active": 1,
    "sold": 2,
}

REQUEST_STATUS_MAP = {
    "0": 0,
    "1": 1,
    "incomplete": 0,
    "completed": 1,
}

TABLE_DELETE_ORDER = [
    "requests",
    "ratings",
    "transactions",
    "bids",
    "auction_listings",
    "local_vendors",
    "credit_cards",
    "helpdesk",
    "sellers",
    "bidders",
    "address",
    "zipcode_info",
    "categories",
    "auth_users",
    "users",
]

SEQUENCE_RESET_TABLES = ("auth_users", "bids", "transactions", "ratings")
