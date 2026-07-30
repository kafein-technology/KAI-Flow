# Local MySQL demo

Start only the demo database:

```bash
docker compose up -d mysql
docker compose ps mysql
```

The first startup runs `init/001-demo-schema.sql` and creates `customers`,
`products`, `orders`, `order_items`, `workflow_events`, and the
`customer_order_summary` view.

Use these development credentials from a host-run KAI-Flow backend:

```text
Host: localhost
Port: 3306
Database: kai_demo
User: kai
Password: kai
```

When the backend itself runs in the root Compose stack, use `mysql` as the host.
Initialization scripts only run for a new volume. To rebuild the sample data,
remove only the `mysql_demo_data` volume and start the service again.
