#!/usr/bin/env python3
"""
Create Webhook Tables Migration Script
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.constants import DATABASE_URL, API_START, API_VERSION
from app.models.webhook import WebhookEndpoint, WebhookEvent
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_webhook_tables():
    """Create webhook-related database tables"""

    if not DATABASE_URL:
        logger.error(" DATABASE_URL not found in environment")
        return False

    try:
        # Create async engine
        engine = create_async_engine(
            DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            if DATABASE_URL.startswith("postgresql://")
            else DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            echo=True,  # Show SQL commands
        )

        # Create tables
<<<<<<< HEAD
        logger.info("Creating webhook tables...")
=======
        logger.info(" Creating webhook tables...")
>>>>>>> serialization_fixes
        async with engine.begin() as conn:
            # Create webhook_endpoints table
            await conn.run_sync(Base.metadata.create_all)

<<<<<<< HEAD
        logger.info("Webhook tables created successfully!")
=======
        logger.info(" Webhook tables created successfully!")
>>>>>>> serialization_fixes

        # Verify table creation
        async_session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            # Check if webhook_endpoints table exists and has correct structure
            result = await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'webhook_endpoints' ORDER BY ordinal_position"
                )
            )
            columns = [row[0] for row in result.fetchall()]

<<<<<<< HEAD
            logger.info(f"webhook_endpoints columns: {columns}")

            # Verify webhook_id column exists
            if "webhook_id" in columns:
                logger.info("webhook_id column exists")
            else:
                logger.error("webhook_id column not found!")
=======
            logger.info(f" webhook_endpoints columns: {columns}")

            # Verify webhook_id column exists
            if "webhook_id" in columns:
                logger.info(" webhook_id column exists")
            else:
                logger.error(" webhook_id column not found!")
>>>>>>> serialization_fixes
                return False

            # Check webhook_events table
            result = await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'webhook_events' ORDER BY ordinal_position"
                )
            )
            event_columns = [row[0] for row in result.fetchall()]
<<<<<<< HEAD
            logger.info(f"webhook_events columns: {event_columns}")
=======
            logger.info(f" webhook_events columns: {event_columns}")
>>>>>>> serialization_fixes

        await engine.dispose()
        return True

    except Exception as e:
<<<<<<< HEAD
        logger.error(f"Error creating webhook tables: {e}")
=======
        logger.error(f" Error creating webhook tables: {e}")
>>>>>>> serialization_fixes
        return False


async def insert_test_webhook_endpoints():
    """Insert test webhook endpoints for existing webhook IDs"""

    if not DATABASE_URL:
<<<<<<< HEAD
        logger.error("DATABASE_URL not found")
=======
        logger.error(" DATABASE_URL not found")
>>>>>>> serialization_fixes
        return False

    try:
        async_url = (
            DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            if DATABASE_URL.startswith("postgresql://")
            else DATABASE_URL
        )
        engine = create_async_engine(async_url, echo=False)
        async_session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            # Insert test webhook endpoints
            test_endpoints = [
                WebhookEndpoint(
                    webhook_id="wh_3f3fead612b4",
                    workflow_id=None,  # Will be set when workflow is associated
                    node_id="WebhookTrigger-1",
                    endpoint_path=f"/{API_START}/{API_VERSION}/webhook/wh_3f3fead612b4",
                    secret_token="webhook_token_123",
                    config={
                        "authentication_required": True,
                        "max_payload_size": 1024,
                        "rate_limit_per_minute": 60,
                        "webhook_timeout": 30,
                        "enable_cors": True,
                        "node_behavior": "auto",
                    },
                    is_active=True,
                    node_behavior="auto",
                ),
                WebhookEndpoint(
                    webhook_id="wh_second_workflow_123",
                    workflow_id=None,
                    node_id="WebhookTrigger-2",
                    endpoint_path=f"/{API_START}/{API_VERSION}/webhook/wh_second_workflow_123",
                    secret_token="webhook_token_456",
                    config={
                        "authentication_required": True,
                        "max_payload_size": 1024,
                        "rate_limit_per_minute": 60,
                        "webhook_timeout": 30,
                        "enable_cors": True,
                        "node_behavior": "auto",
                    },
                    is_active=True,
                    node_behavior="auto",
                ),
                WebhookEndpoint(
                    webhook_id="wh_http_scraping_test_456",
                    workflow_id=None,
                    node_id="WebhookTrigger-3",
                    endpoint_path=f"/{API_START}/{API_VERSION}/webhook/wh_http_scraping_test_456",
                    secret_token="http_scraping_token_789",
                    config={
                        "authentication_required": True,
                        "max_payload_size": 1024,
                        "rate_limit_per_minute": 60,
                        "webhook_timeout": 30,
                        "enable_cors": True,
                        "node_behavior": "auto",
                    },
                    is_active=True,
                    node_behavior="auto",
                ),
            ]

            # Check if endpoints already exist
            for endpoint in test_endpoints:
                existing = await session.execute(
                    text(
                        "SELECT id FROM webhook_endpoints WHERE webhook_id = :webhook_id"
                    ),
                    {"webhook_id": endpoint.webhook_id},
                )
                if existing.fetchone():
                    logger.info(
<<<<<<< HEAD
                        f" Webhook {endpoint.webhook_id} already exists, skipping"
=======
                        f"⏭️ Webhook {endpoint.webhook_id} already exists, skipping"
>>>>>>> serialization_fixes
                    )
                    continue

                session.add(endpoint)
<<<<<<< HEAD
                logger.info(f"Added webhook endpoint: {endpoint.webhook_id}")
            
=======
                logger.info(f"➕ Added webhook endpoint: {endpoint.webhook_id}")

>>>>>>> serialization_fixes
            await session.commit()
            logger.info(" Test webhook endpoints created successfully!")

        await engine.dispose()
        return True

    except Exception as e:
        logger.error(f" Error inserting test webhook endpoints: {e}")
        return False


async def main():
    """Main migration function"""
    logger.info(" Starting webhook tables migration...")

    # Step 1: Create tables
    success = await create_webhook_tables()
    if not success:
        logger.error(" Failed to create webhook tables")
        return

    # Step 2: Insert test data
    success = await insert_test_webhook_endpoints()
    if not success:
        logger.error(" Failed to insert test webhook endpoints")
        return

<<<<<<< HEAD
    logger.info(" Webhook tables migration completed successfully!")
=======
    logger.info("🎉 Webhook tables migration completed successfully!")
>>>>>>> serialization_fixes
    logger.info(" You can now use webhook endpoints with the following IDs:")
    logger.info("   • wh_3f3fead612b4 (token: webhook_token_123)")
    logger.info("   • wh_second_workflow_123 (token: webhook_token_456)")
    logger.info("   • wh_http_scraping_test_456 (token: http_scraping_token_789)")


if __name__ == "__main__":
    asyncio.run(main())
