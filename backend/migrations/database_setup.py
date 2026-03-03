#!/usr/bin/env python3
"""
KAI-Flow Database Setup Script - Enhanced Column Synchronization
=================================================================

This script creates and updates the database for the KAI-Flow platform.
It checks existing tables, creates missing ones, and manages column
differences (adding missing columns / removing extra columns).

Supported Tables:
- Core user and organization tables
- Workflow and template tables
- Node and configuration tables
- Document and chunk tables
- Webhook and event tables
- Vector storage tables (vector_collections, vector_documents)

Features:
- Automatic column synchronization
- Model-Database column comparison
- Missing column addition
- Extra column removal (optional)
- Type mismatch detection

Usage:
    python database_setup.py [OPTIONS]

Basic Parameters:
    --force                 : Drops and recreates existing tables
    --check-only           : Only checks existing tables and columns
    --drop-all             : Drops all tables and recreates them

Column Management Parameters:
    --no-sync-columns      : Disables column synchronization
    --no-add-columns       : Disables adding missing columns
    --remove-extra-columns : Removes extra columns (WARNING: Data loss!)

Examples:
    # Check only
    python database_setup.py --check-only

    # Add missing columns (default)
    python database_setup.py

    # Also remove extra columns
    python database_setup.py --remove-extra-columns

    # Skip column operations
    python database_setup.py --no-sync-columns
"""

import asyncio
import sys
import os
import argparse
import logging
from typing import List, Dict, Any, Set
from urllib.parse import urlparse, urlunparse, quote
from sqlalchemy import text, inspect, MetaData, Table, Column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.sqltypes import TypeEngine

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)


# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('database_setup.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
CREATE_DATABASE = os.getenv("CREATE_DATABASE", "true").lower() in ("true", "1", "t")


class DatabaseSetup:
    """Database setup and management class."""

    def __init__(self):
        self.engine = None
        self.session_factory = None
        self.expected_tables = [
            "users",
            "user_credentials",
            "workflows",
            "workflow_templates",
            "workflow_executions",
            "execution_checkpoints",
            "roles",
            "organization",
            "organization_user",
            "login_method",
            "login_activity",
            "chat_message",
            "variable",
            "memories",
            "node_configurations",
            "node_registry",
            "api_keys",
            "scheduled_jobs",
            "job_executions",
            "document_collections",
            "documents",
            "document_chunks",
            "document_access_logs",
            "document_versions",
            "webhook_endpoints",
            "webhook_events",
            "vector_collections",
            "vector_documents",
            "external_workflows"
        ]

    async def initialize(self):
        """Initializes the database connection."""
        if not CREATE_DATABASE:
            logger.error("CREATE_DATABASE environment variable is not set to 'true'")
            return False

        if not DATABASE_URL:
            logger.error("DATABASE_URL environment variable is not set")
            return False

        try:
            # Build database URL with credentials using proper URL parsing
            parsed = urlparse(DATABASE_URL)
            # URL-encode credentials to handle special characters like @
            safe_user = quote(POSTGRES_USERNAME, safe='')
            safe_pass = quote(POSTGRES_PASSWORD, safe='')
            # Replace credentials, keeping the original host, port, path, etc.
            db_url = urlunparse((
                parsed.scheme or 'postgresql',  # scheme
                f"{safe_user}:{safe_pass}@{parsed.hostname}"
                + (f":{parsed.port}" if parsed.port else ""),  # netloc with new creds
                parsed.path,    # database name
                parsed.params,
                parsed.query,
                parsed.fragment,
            ))
            logger.info(f"Database URL built for user: {POSTGRES_USERNAME}")

            # Convert to async URL
            async_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
            self.engine = create_async_engine(
                async_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "server_settings": {"application_name": "kai-fusion-setup"},
                    "statement_cache_size": 1000,
                    "prepared_statement_cache_size": 100,
                    "command_timeout": 60,
                }
            )

            # Create session factory
            self.session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            logger.info("Database connection established successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to establish database connection: {e}")
            return False

    async def check_connection(self) -> bool:
        """Tests the database connection."""
        if not self.engine:
            logger.error("Engine has not been initialized yet")
            return False

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                if row and row[0] == 1:
                    logger.info("Database connection test successful")
                    return True
                else:
                    logger.error("Database connection test failed")
                    return False
        except Exception as e:
            logger.error(f"Database connection test error: {e}")
            return False

    async def get_existing_tables(self) -> List[str]:
        """Lists existing tables."""
        if not self.engine:
            return []

        try:
            async with self.engine.begin() as conn:
                # PostgreSQL table list query - DISTINCT to prevent duplicates
                result = await conn.execute(text("""
                                                 SELECT DISTINCT tablename
                                                 FROM pg_tables
                                                 WHERE schemaname = 'public'
                                                 ORDER BY tablename
                                                 """))
                tables = [row[0] for row in result.fetchall()]

                # Check for duplicate table names
                if len(tables) != len(set(tables)):
                    logger.warning("Duplicate table names detected!")
                    logger.warning(f"Raw list: {tables}")
                    # Remove duplicates while preserving order
                    tables = list(dict.fromkeys(tables))
                    logger.info(f"Duplicates removed: {tables}")

                logger.info(f"Existing tables: {', '.join(tables) if tables else 'No tables found'}")
                return tables
        except Exception as e:
            logger.error(f"Failed to retrieve table list: {e}")
            return []

    async def check_table_structure(self, table_name: str) -> Dict[str, Any]:
        """Checks the structure of a specific table."""
        if not self.engine:
            return {"exists": False, "columns": []}

        try:
            async with self.engine.begin() as conn:
                # Check if table exists
                result = await conn.execute(text("""
                                                 SELECT EXISTS (SELECT
                                                                FROM information_schema.tables
                                                                WHERE table_schema = 'public'
                                                                  AND table_name = :table_name)
                                                 """), {"table_name": table_name})

                exists = result.fetchone()[0]

                if not exists:
                    return {"exists": False, "columns": []}

                # Get table columns
                result = await conn.execute(text("""
                                                 SELECT column_name, data_type, is_nullable, column_default
                                                 FROM information_schema.columns
                                                 WHERE table_schema = 'public'
                                                   AND table_name = :table_name
                                                 ORDER BY ordinal_position
                                                 """), {"table_name": table_name})

                columns = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                        "default": row[3]
                    }
                    for row in result.fetchall()
                ]

                return {"exists": True, "columns": columns}

        except Exception as e:
            logger.error(f"Failed to check structure of table {table_name}: {e}")
            return {"exists": False, "columns": []}

    def get_model_columns(self, table_name: str) -> Dict[str, Any]:
        """Gets expected columns from the model."""
        try:
            # Model imports
            from app.models.base import Base
            from app.models import (
                User, UserCredential, Workflow, WorkflowTemplate,
                WorkflowExecution, ExecutionCheckpoint, Role, Organization,
                OrganizationUser, LoginMethod, LoginActivity, ChatMessage,
                Variable, Memory, NodeConfiguration, NodeRegistry,
                ScheduledJob, JobExecution,
                DocumentCollection, Document, DocumentChunk, DocumentAccessLog, DocumentVersion,
                WebhookEndpoint, WebhookEvent,
                VectorCollection, VectorDocument,
                ExternalWorkflow
            )

            # Check API Key model
            try:
                from app.models.api_key import APIKey
            except ImportError:
                pass

            # Model mapping
            model_mapping = {
                'users': User,
                'user_credentials': UserCredential,
                'workflows': Workflow,
                'workflow_templates': WorkflowTemplate,
                'workflow_executions': WorkflowExecution,
                'execution_checkpoints': ExecutionCheckpoint,
                'roles': Role,
                'organization': Organization,
                'organization_user': OrganizationUser,
                'login_method': LoginMethod,
                'login_activity': LoginActivity,
                'chat_message': ChatMessage,
                'variable': Variable,
                'memories': Memory,
                'node_configurations': NodeConfiguration,
                'node_registry': NodeRegistry,
                'scheduled_jobs': ScheduledJob,
                'job_executions': JobExecution,
                'document_collections': DocumentCollection,
                'documents': Document,
                'document_chunks': DocumentChunk,
                'document_access_logs': DocumentAccessLog,
                'document_versions': DocumentVersion,
                'webhook_endpoints': WebhookEndpoint,
                'webhook_events': WebhookEvent,
                'vector_collections': VectorCollection,
                'vector_documents': VectorDocument,
                'external_workflows': ExternalWorkflow
            }

            # Add API Key if available
            try:
                from app.models.api_key import APIKey
                model_mapping['api_keys'] = APIKey
            except ImportError:
                pass

            if table_name not in model_mapping:
                logger.warning(f"No model found for {table_name}")
                return {"exists": False, "columns": []}

            model_class = model_mapping[table_name]
            table = model_class.__table__

            model_columns = []
            for column in table.columns:
                model_columns.append({
                    "name": column.name,
                    "type": self._sqlalchemy_type_to_postgres(column.type),
                    "nullable": column.nullable,
                    "default": str(column.default) if column.default else None,
                    "primary_key": column.primary_key
                })

            return {"exists": True, "columns": model_columns}

        except Exception as e:
            logger.error(f"Failed to get model columns for {table_name}: {e}")
            return {"exists": False, "columns": []}

    def _sqlalchemy_type_to_postgres(self, sqlalchemy_type: TypeEngine) -> str:
        """Converts SQLAlchemy type to PostgreSQL type."""
        type_name = str(sqlalchemy_type)

        # Basic type mappings
        type_mapping = {
            'UUID': 'uuid',
            'VARCHAR': 'character varying',
            'TEXT': 'text',
            'BOOLEAN': 'boolean',
            'INTEGER': 'integer',
            'TIMESTAMP': 'timestamp with time zone',
            'DATETIME': 'timestamp with time zone',
            'JSONB': 'jsonb',
            'JSON': 'json'
        }

        # Normalize type
        for sql_type, pg_type in type_mapping.items():
            if sql_type in type_name.upper():
                return pg_type

        # For cases like VARCHAR(255)
        if 'VARCHAR' in type_name.upper():
            return 'character varying'

        # Return type_name as default
        return type_name.lower()

    async def compare_table_columns(self, table_name: str) -> Dict[str, Any]:
        """Compares table columns with the model."""
        db_structure = await self.check_table_structure(table_name)
        model_structure = self.get_model_columns(table_name)

        if not db_structure["exists"] or not model_structure["exists"]:
            return {
                "table_exists": db_structure["exists"],
                "model_exists": model_structure["exists"],
                "missing_columns": [],
                "extra_columns": [],
                "type_mismatches": []
            }

        db_columns = {col["name"]: col for col in db_structure["columns"]}
        model_columns = {col["name"]: col for col in model_structure["columns"]}

        # Missing columns (in model, not in DB)
        missing_columns = []
        for col_name, col_info in model_columns.items():
            if col_name not in db_columns:
                missing_columns.append(col_info)

        # Extra columns (in DB, not in model)
        extra_columns = []
        for col_name, col_info in db_columns.items():
            if col_name not in model_columns:
                extra_columns.append(col_info)

        # Type mismatches
        type_mismatches = []
        for col_name in set(db_columns.keys()) & set(model_columns.keys()):
            db_col = db_columns[col_name]
            model_col = model_columns[col_name]

            # Simple type comparison
            if db_col["type"] != model_col["type"]:
                type_mismatches.append({
                    "column_name": col_name,
                    "db_type": db_col["type"],
                    "model_type": model_col["type"]
                })

        return {
            "table_exists": True,
            "model_exists": True,
            "missing_columns": missing_columns,
            "extra_columns": extra_columns,
            "type_mismatches": type_mismatches
        }

    async def add_missing_columns(self, table_name: str, missing_columns: List[Dict[str, Any]]) -> bool:
        """Adds missing columns."""
        if not missing_columns:
            return True

        try:
            async with self.engine.begin() as conn:
                for column in missing_columns:
                    col_name = column["name"]
                    col_type = column["type"]
                    nullable = "NULL" if column["nullable"] else "NOT NULL"

                    # Special handling for primary key columns
                    if column.get("primary_key"):
                        logger.info(f"Skipping primary key column {col_name} (manual intervention required)")
                        continue

                    # Add default value if present
                    default_clause = ""
                    if column["default"] and column["default"] != "None":
                        default_clause = f" DEFAULT {column['default']}"

                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable}{default_clause}"

                    logger.info(f"Adding column: {table_name}.{col_name}")
                    await conn.execute(text(alter_sql))

            logger.info(f"Added {len(missing_columns)} columns to {table_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding columns to {table_name}: {e}")
            return False

    async def remove_extra_columns(self, table_name: str, extra_columns: List[Dict[str, Any]]) -> bool:
        """Removes extra columns."""
        if not extra_columns:
            return True

        try:
            async with self.engine.begin() as conn:
                for column in extra_columns:
                    col_name = column["name"]

                    # Protect critical columns
                    if col_name in ['id', 'created_at', 'updated_at']:
                        logger.info(f"Protecting critical column {col_name}")
                        continue

                    alter_sql = f"ALTER TABLE {table_name} DROP COLUMN {col_name}"

                    logger.info(f"Removing column: {table_name}.{col_name}")
                    await conn.execute(text(alter_sql))

            logger.info(f"Removed {len(extra_columns)} columns from {table_name}")
            return True

        except Exception as e:
            logger.error(f"Error removing columns from {table_name}: {e}")
            return False

    async def sync_table_columns(self, table_name: str, add_missing: bool = True, remove_extra: bool = True) -> bool:
        """Synchronizes table columns with the model."""
        logger.info(f"Starting column synchronization for {table_name}...")

        comparison = await self.compare_table_columns(table_name)

        if not comparison["table_exists"] or not comparison["model_exists"]:
            logger.error(f"Table or model not available for {table_name} synchronization")
            return False

        success = True

        # Add missing columns
        if add_missing and comparison["missing_columns"]:
            logger.info(f"Adding {len(comparison['missing_columns'])} missing columns...")
            if not await self.add_missing_columns(table_name, comparison["missing_columns"]):
                success = False

        # Remove extra columns
        if remove_extra and comparison["extra_columns"]:
            logger.info(f"Removing {len(comparison['extra_columns'])} extra columns...")
            if not await self.remove_extra_columns(table_name, comparison["extra_columns"]):
                success = False

        # Warn about type mismatches
        if comparison["type_mismatches"]:
            logger.warning(f"{table_name} has {len(comparison['type_mismatches'])} type mismatches:")
            for mismatch in comparison["type_mismatches"]:
                logger.warning(
                    f"   - {mismatch['column_name']}: DB={mismatch['db_type']} != Model={mismatch['model_type']}")

        if success:
            logger.info(f"Column synchronization completed for {table_name}")
        else:
            logger.error(f"Column synchronization failed for {table_name}")

        return success

    async def create_tables(self, force: bool = False):
        """Creates all tables."""
        if not self.engine:
            logger.error("Engine has not been initialized yet")
            return False

        try:
            # Model imports
            from app.models.base import Base
            from app.models import (
                User, UserCredential, Workflow, WorkflowTemplate,
                WorkflowExecution, ExecutionCheckpoint, Role, Organization,
                OrganizationUser, LoginMethod, LoginActivity, ChatMessage,
                Variable, Memory, NodeConfiguration, NodeRegistry,
                ScheduledJob, JobExecution,
                DocumentCollection, Document, DocumentChunk, DocumentAccessLog, DocumentVersion,
                WebhookEndpoint, WebhookEvent,
                VectorCollection, VectorDocument,
                ExternalWorkflow
            )

            # Check API Key model
            try:
                from app.models.api_key import APIKey
                logger.info("API Key model found")
            except ImportError:
                logger.warning("API Key model not found, skipping")

            if force:
                logger.warning("FORCE mode: All tables will be dropped and recreated")
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                logger.info("All tables dropped")

            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("All tables created successfully")
            return True

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return False

    async def drop_all_tables(self):
        """Drops all tables."""
        if not self.engine:
            logger.error("Engine has not been initialized yet")
            return False

        try:
            from app.models.base import Base

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

            logger.info("All tables dropped")
            return True

        except Exception as e:
            logger.error(f"Error dropping tables: {e}")
            return False

    async def validate_tables(self, check_columns: bool = True) -> Dict[str, Any]:
        """Validates all tables and optionally checks columns."""
        existing_tables = await self.get_existing_tables()

        validation_result = {
            "total_expected": len(self.expected_tables),
            "total_existing": len(existing_tables),
            "missing_tables": [],
            "existing_tables": existing_tables,
            "table_details": {},
            "column_issues": {} if check_columns else None
        }

        # Find missing tables
        for table in self.expected_tables:
            if table not in existing_tables:
                validation_result["missing_tables"].append(table)
            else:
                # Check table structure
                structure = await self.check_table_structure(table)
                validation_result["table_details"][table] = structure

                # Column check
                if check_columns:
                    column_comparison = await self.compare_table_columns(table)
                    if (column_comparison["missing_columns"] or
                            column_comparison["extra_columns"] or
                            column_comparison["type_mismatches"]):
                        validation_result["column_issues"][table] = column_comparison

        return validation_result

    async def setup_database(self, force: bool = False, check_only: bool = False, drop_all: bool = False,
                             sync_columns: bool = True, add_missing_columns: bool = True,
                             remove_extra_columns: bool = False):
        """Main database setup function."""
        logger.info("KAI-Fusion Database Setup Script Starting...")

        # Initialize
        if not await self.initialize():
            return False

        # Connection test
        if not await self.check_connection():
            return False

        # Check-only mode
        if check_only:
            logger.info("Check-only mode - tables will not be created")
            validation = await self.validate_tables(check_columns=sync_columns)
            self._print_validation_results(validation)
            return True

        # Drop all tables
        if drop_all:
            logger.warning("DROP_ALL mode: All tables will be dropped!")
            if not await self.drop_all_tables():
                return False

        # Check current state
        validation = await self.validate_tables(check_columns=sync_columns)
        self._print_validation_results(validation)

        # Create missing tables if any
        if validation["missing_tables"] or force:
            if validation["missing_tables"]:
                logger.info(f"Creating missing tables: {', '.join(validation['missing_tables'])}")

            if not await self.create_tables(force=force):
                return False

            # Post-creation check
            logger.info("Post-creation validation...")
            post_validation = await self.validate_tables(check_columns=sync_columns)
            self._print_validation_results(post_validation)

            if post_validation["missing_tables"]:
                logger.error(f"Still missing tables: {', '.join(post_validation['missing_tables'])}")
                return False
            else:
                logger.info("All tables created and validated successfully")
        else:
            logger.info("All tables already exist")

        # Column synchronization
        if sync_columns and validation["column_issues"]:
            logger.info("Starting column synchronization...")

            for table_name, issues in validation["column_issues"].items():
                await self.sync_table_columns(
                    table_name,
                    add_missing=add_missing_columns,
                    remove_extra=remove_extra_columns
                )

            # Post-synchronization check
            logger.info("Post-synchronization validation...")
            final_validation = await self.validate_tables(check_columns=True)
            self._print_validation_results(final_validation)

            if final_validation["column_issues"]:
                remaining_issues = len(final_validation["column_issues"])
                logger.warning(f"{remaining_issues} tables still have column issues")
            else:
                logger.info("All columns synchronized successfully")

        return True

    def _print_validation_results(self, validation: Dict[str, Any]):
        """Prints validation results."""
        logger.info("=" * 60)
        logger.info("DATABASE STATUS REPORT")
        logger.info("=" * 60)
        logger.info(f"Expected table count: {validation['total_expected']}")
        logger.info(f"Existing table count: {validation['total_existing']}")

        if validation["missing_tables"]:
            logger.warning(f"Missing tables ({len(validation['missing_tables'])}):")
            for table in validation["missing_tables"]:
                logger.warning(f"   - {table}")
        else:
            logger.info("All expected tables exist")

        # Display existing tables
        if validation['existing_tables']:
            logger.info("Existing tables:")
            sorted_tables = sorted(validation['existing_tables'])
            for i, table in enumerate(sorted_tables, 1):
                logger.info(f"   {i:2d}. {table}")
        else:
            logger.info("No tables found")

        # Display column issues
        if validation.get("column_issues"):
            logger.warning(f"Tables with column issues ({len(validation['column_issues'])}):")
            for table_name, issues in validation["column_issues"].items():
                logger.warning(f"   {table_name}:")

                if issues["missing_columns"]:
                    logger.warning(f"      Missing columns ({len(issues['missing_columns'])}):")
                    for col in issues["missing_columns"]:
                        logger.warning(f"         - {col['name']} ({col['type']})")

                if issues["extra_columns"]:
                    logger.warning(f"      Extra columns ({len(issues['extra_columns'])}):")
                    for col in issues["extra_columns"]:
                        logger.warning(f"         - {col['name']} ({col['type']})")

                if issues["type_mismatches"]:
                    logger.warning(f"      Type mismatches ({len(issues['type_mismatches'])}):")
                    for mismatch in issues["type_mismatches"]:
                        logger.warning(
                            f"         - {mismatch['column_name']}: DB={mismatch['db_type']} != Model={mismatch['model_type']}")
        elif validation.get("column_issues") is not None:
            logger.info("All columns are compatible with models")

        logger.info("=" * 60)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="KAI-Fusion Database Setup Script")
    parser.add_argument("--force", action="store_true", help="Drops and recreates existing tables")
    parser.add_argument("--check-only", action="store_true", help="Only checks existing tables")
    parser.add_argument("--drop-all", action="store_true", help="Drops all tables and recreates them")
    parser.add_argument("--no-sync-columns", action="store_true", help="Disables column synchronization")
    parser.add_argument("--no-add-columns", action="store_true", help="Disables adding missing columns")
    parser.add_argument("--remove-extra-columns", action="store_true",
                        help="Removes extra columns (use with caution!)")

    args = parser.parse_args()

    # Environment check
    if not CREATE_DATABASE:
        logger.error("CREATE_DATABASE environment variable is not set to 'true'")
        logger.info("Solution: Set CREATE_DATABASE=true in backend/.env or export CREATE_DATABASE=true")
        sys.exit(1)

    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable is not set")
        logger.info("Solution: Set DATABASE_URL in backend/.env or export DATABASE_URL='your_database_url'")
        sys.exit(1)

    # Column removal warning
    if args.remove_extra_columns:
        logger.warning("WARNING: --remove-extra-columns will remove extra columns!")
        logger.warning("This operation is irreversible and may cause data loss!")

    # Start database setup
    db_setup = DatabaseSetup()

    try:
        success = await db_setup.setup_database(
            force=args.force,
            check_only=args.check_only,
            drop_all=args.drop_all,
            sync_columns=not args.no_sync_columns,
            add_missing_columns=not args.no_add_columns,
            remove_extra_columns=args.remove_extra_columns
        )

        if success:
            logger.info("Database setup completed successfully!")
            sys.exit(0)
        else:
            logger.error("Database setup failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())