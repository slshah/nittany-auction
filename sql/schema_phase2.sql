PRAGMA foreign_keys = ON;

-- Core users table from the relational schema.
-- Passwords are stored hashed by loader scripts for security.
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Compatibility table for the current login implementation.
CREATE TABLE IF NOT EXISTS auth_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        LOWER(role) IN ('seller', 'bidder', 'helpdesk', 'unsupported')
    ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS helpdesk (
    email TEXT PRIMARY KEY,
    position TEXT NOT NULL,
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS zipcode_info (
    zipcode TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS address (
    address_id TEXT PRIMARY KEY,
    zipcode TEXT NOT NULL,
    street_num TEXT NOT NULL,
    street_name TEXT NOT NULL,
    FOREIGN KEY (zipcode) REFERENCES zipcode_info(zipcode)
);

CREATE TABLE IF NOT EXISTS bidders (
    email TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER CHECK (age IS NULL OR age >= 0),
    home_address_id TEXT,
    major TEXT,
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE,
    FOREIGN KEY (home_address_id) REFERENCES address(address_id)
);

CREATE TABLE IF NOT EXISTS credit_cards (
    credit_card_num TEXT PRIMARY KEY,
    card_type TEXT NOT NULL,
    expire_month INTEGER NOT NULL CHECK (expire_month BETWEEN 1 AND 12),
    expire_year INTEGER NOT NULL CHECK (expire_year >= 2000),
    security_code TEXT NOT NULL,
    owner_email TEXT NOT NULL,
    FOREIGN KEY (owner_email) REFERENCES bidders(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sellers (
    email TEXT PRIMARY KEY,
    bank_routing_number TEXT NOT NULL,
    bank_account_number TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0 CHECK (balance >= 0),
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS local_vendors (
    email TEXT PRIMARY KEY,
    business_name TEXT NOT NULL,
    business_address_id TEXT,
    customer_service_phone_number TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    FOREIGN KEY (email) REFERENCES sellers(email) ON DELETE CASCADE,
    FOREIGN KEY (business_address_id) REFERENCES address(address_id)
);

CREATE TABLE IF NOT EXISTS categories (
    category_name TEXT PRIMARY KEY,
    parent_category TEXT,
    FOREIGN KEY (parent_category) REFERENCES categories(category_name) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS auction_listings (
    seller_email TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    auction_title TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_description TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    reserve_price REAL NOT NULL CHECK (reserve_price >= 0),
    max_bids INTEGER NOT NULL CHECK (max_bids > 0),
    status INTEGER NOT NULL DEFAULT 1 CHECK (status IN (0, 1, 2)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_reason TEXT,
    remaining_bids_at_removal INTEGER CHECK (
        remaining_bids_at_removal IS NULL OR remaining_bids_at_removal >= 0
    ),
    removed_at TEXT,
    removed_by_email TEXT,
    PRIMARY KEY (seller_email, listing_id),
    FOREIGN KEY (seller_email) REFERENCES sellers(email) ON DELETE CASCADE,
    FOREIGN KEY (category) REFERENCES categories(category_name),
    FOREIGN KEY (removed_by_email) REFERENCES users(email)
);

CREATE TABLE IF NOT EXISTS bids (
    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_email TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    bidder_email TEXT NOT NULL,
    bid_price REAL NOT NULL CHECK (bid_price >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_email, listing_id)
        REFERENCES auction_listings(seller_email, listing_id) ON DELETE CASCADE,
    FOREIGN KEY (bidder_email) REFERENCES bidders(email)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_email TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    bidder_email TEXT NOT NULL,
    transaction_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payment REAL NOT NULL CHECK (payment >= 0),
    UNIQUE (seller_email, listing_id),
    FOREIGN KEY (seller_email, listing_id)
        REFERENCES auction_listings(seller_email, listing_id) ON DELETE CASCADE,
    FOREIGN KEY (bidder_email) REFERENCES bidders(email)
);

CREATE TABLE IF NOT EXISTS ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bidder_email TEXT NOT NULL,
    seller_email TEXT NOT NULL,
    rating_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rating_value INTEGER NOT NULL CHECK (rating_value BETWEEN 1 AND 5),
    rating_desc TEXT,
    transaction_id INTEGER,
    UNIQUE (bidder_email, seller_email, rating_date),
    UNIQUE (transaction_id, bidder_email),
    FOREIGN KEY (bidder_email) REFERENCES bidders(email),
    FOREIGN KEY (seller_email) REFERENCES sellers(email),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS requests (
    request_id INTEGER PRIMARY KEY,
    sender_email TEXT NOT NULL,
    helpdesk_staff_email TEXT NOT NULL,
    request_type TEXT NOT NULL,
    request_desc TEXT NOT NULL,
    request_status INTEGER NOT NULL DEFAULT 0 CHECK (request_status IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (sender_email) REFERENCES users(email),
    FOREIGN KEY (helpdesk_staff_email) REFERENCES helpdesk(email)
);

CREATE INDEX IF NOT EXISTS idx_categories_parent
ON categories(parent_category);

CREATE INDEX IF NOT EXISTS idx_auction_listings_status_category
ON auction_listings(status, category);

CREATE INDEX IF NOT EXISTS idx_auction_listings_seller_status
ON auction_listings(seller_email, status);

CREATE INDEX IF NOT EXISTS idx_auction_listings_search_columns
ON auction_listings(product_name, auction_title, category);

CREATE INDEX IF NOT EXISTS idx_bids_listing_created_at
ON bids(seller_email, listing_id, created_at);

CREATE INDEX IF NOT EXISTS idx_bids_bidder
ON bids(bidder_email);

CREATE INDEX IF NOT EXISTS idx_requests_staff_status
ON requests(helpdesk_staff_email, request_status);

CREATE INDEX IF NOT EXISTS idx_ratings_seller
ON ratings(seller_email);
