USE kai_demo;

CREATE TABLE customers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(160) NOT NULL,
    status ENUM('active', 'inactive', 'lead') NOT NULL DEFAULT 'lead',
    country_code CHAR(2) NOT NULL,
    lifetime_value DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_customers_email (email),
    KEY idx_customers_status_country (status, country_code)
) ENGINE=InnoDB;

CREATE TABLE products (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sku VARCHAR(64) NOT NULL,
    name VARCHAR(180) NOT NULL,
    category VARCHAR(80) NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    stock_quantity INT UNSIGNED NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_sku (sku),
    KEY idx_products_category_active (category, active)
) ENGINE=InnoDB;

CREATE TABLE orders (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_number VARCHAR(40) NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    status ENUM('pending', 'paid', 'shipped', 'cancelled') NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(14, 2) NOT NULL,
    ordered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_orders_order_number (order_number),
    KEY idx_orders_customer_status (customer_id, status),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (id)
) ENGINE=InnoDB;

CREATE TABLE order_items (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_order_product (order_id, product_id),
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products (id)
) ENGINE=InnoDB;

CREATE TABLE workflow_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_key VARCHAR(100) NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    payload JSON NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    processed_at TIMESTAMP(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_workflow_events_event_key (event_key),
    KEY idx_workflow_events_pending (processed, created_at)
) ENGINE=InnoDB;

INSERT INTO customers (email, full_name, status, country_code, lifetime_value) VALUES
    ('ada@example.com', 'Ada Lovelace', 'active', 'GB', 1540.50),
    ('grace@example.com', 'Grace Hopper', 'active', 'US', 2325.00),
    ('alan@example.com', 'Alan Turing', 'lead', 'GB', 0.00),
    ('sabiha@example.com', 'Sabiha Rifat Gürayman', 'inactive', 'TR', 875.25);

INSERT INTO products (sku, name, category, price, stock_quantity) VALUES
    ('KAI-KEY-001', 'Mechanical Keyboard', 'hardware', 129.90, 42),
    ('KAI-HUB-002', 'USB-C Workflow Hub', 'hardware', 89.50, 75),
    ('KAI-AUTO-003', 'Automation Starter Pack', 'software', 49.00, 999),
    ('KAI-OBS-004', 'Observability Dashboard', 'software', 79.00, 999);

INSERT INTO orders (order_number, customer_id, status, total_amount, ordered_at) VALUES
    ('ORD-2026-0001', 1, 'paid', 219.40, '2026-07-24 09:30:00'),
    ('ORD-2026-0002', 2, 'shipped', 178.50, '2026-07-25 11:10:00'),
    ('ORD-2026-0003', 1, 'pending', 49.00, '2026-07-28 08:45:00');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 129.90),
    (1, 2, 1, 89.50),
    (2, 3, 2, 49.00),
    (2, 4, 1, 79.00),
    (3, 3, 1, 49.00);

INSERT INTO workflow_events (event_key, event_type, payload, processed) VALUES
    ('evt-demo-001', 'customer.created', JSON_OBJECT('customer_id', 3, 'source', 'demo'), FALSE),
    ('evt-demo-002', 'order.paid', JSON_OBJECT('order_number', 'ORD-2026-0001', 'amount', 219.40), TRUE),
    ('evt-demo-003', 'inventory.low', JSON_OBJECT('sku', 'KAI-KEY-001', 'threshold', 50), FALSE);

CREATE VIEW customer_order_summary AS
SELECT
    c.id AS customer_id,
    c.email,
    c.full_name,
    COUNT(o.id) AS order_count,
    COALESCE(SUM(o.total_amount), 0.00) AS total_order_value,
    MAX(o.ordered_at) AS latest_order_at
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.email, c.full_name;
