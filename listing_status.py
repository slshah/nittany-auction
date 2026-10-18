LISTING_STATUS_INACTIVE = 0
LISTING_STATUS_ACTIVE = 1
LISTING_STATUS_SOLD = 2

SELLER_LISTING_STATUS_GROUPS = [
    {"slug": "active", "code": LISTING_STATUS_ACTIVE, "label": "Active"},
    {"slug": "inactive", "code": LISTING_STATUS_INACTIVE, "label": "Inactive"},
    {"slug": "sold", "code": LISTING_STATUS_SOLD, "label": "Sold"},
]

LISTING_STATUS_TO_SLUG = {
    LISTING_STATUS_ACTIVE: "active",
    LISTING_STATUS_INACTIVE: "inactive",
    LISTING_STATUS_SOLD: "sold",
}

LISTING_STATUS_TO_LABEL = {
    LISTING_STATUS_ACTIVE: "Active",
    LISTING_STATUS_INACTIVE: "Inactive",
    LISTING_STATUS_SOLD: "Sold",
}

UNSUCCESSFUL_AUCTION_REMOVAL_REASON = "Auction ended without meeting reserve price."
