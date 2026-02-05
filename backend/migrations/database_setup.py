#!/usr/bin/env python3
"""
KAI-Flow Database Setup Script - Enhanced Column Synchronization
=================================================================

Bu script, KAI-Flow platformu için veritabanını oluşturur ve günceller.
Mevcut tabloları kontrol eder, eksik olanları oluşturur ve sütun farklılıklarını
yönetir (eksik sütun ekleme/fazla sütun silme).

Desteklenen Tablolar:
- Temel kullanıcı ve organizasyon tabloları
- Workflow ve template tabloları  
- Node ve konfigürasyon tabloları
- Document ve chunk tabloları
- Webhook ve event tabloları
- Vector storage tabloları (vector_collections, vector_documents)

Yeni Özellikler:
- Otomatik sütun senkronizasyonu
- Model-Database sütun karşılaştırması
- Eksik sütun ekleme
- Fazla sütun silme (isteğe bağlı)
- Tür uyumsuzluğu tespiti

Kullanım:
    python database_setup.py [OPTIONS]

Temel Parametreler:
    --force                 : Mevcut tabloları silip yeniden oluşturur
    --check-only           : Sadece mevcut tabloları ve sütunları kontrol eder
    --drop-all             : Tüm tabloları siler ve yeniden oluşturur

Sütun Yönetimi Parametreleri:
    --no-sync-columns      : Sütun senkronizasyonunu devre dışı bırakır
    --no-add-columns       : Eksik sütun eklemeyi devre dışı bırakır  
    --remove-extra-columns : Fazla sütunları siler (DIKKAT: Veri kaybı!)

Örnekler:
    # Sadece kontrol et
    python database_setup.py --check-only

    # Eksik sütunları ekle (varsayılan)
    python database_setup.py

    # Fazla sütunları da sil
    python database_setup.py --remove-extra-columns

    # Sütun işlemlerini atla
    python database_setup.py --no-sync-columns
"""

import asyncio
import sys
import os
import argparse
import logging
from typing import List, Dict, Any, Set
from sqlalchemy import text, inspect, MetaData, Table, Column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.sqltypes import TypeEngine
from dotenv import load_dotenv

load_dotenv()
# Backend dizinini Python path'ine ekle
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)


# Logging konfigürasyonu (emoji kaldırıldı, seviye dinamik)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('database_setup.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
CREATE_DATABASE = os.getenv("CREATE_DATABASE", "true").lower() in ("true", "1", "t")


class DatabaseSetup:
    """Veritabanı kurulum ve yönetim sınıfı."""

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
        """Veritabanı bağlantısını başlatır."""
        if not CREATE_DATABASE:
            logger.error("CREATE_DATABASE environment variable is not set to 'true'")
            return False

        if not DATABASE_URL:
            logger.error("DATABASE_URL environment variable is not set")
            return False

        try:
            # Async engine oluştur
            async_url = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://') if DATABASE_URL.startswith(
                'postgresql://') else DATABASE_URL
            self.engine = create_async_engine(
                async_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "server_settings": {"application_name": "kai-flow-setup"},
                    "statement_cache_size": 1000,
                    "prepared_statement_cache_size": 100,
                    "command_timeout": 60,
                }
            )

            # Session factory oluştur
            self.session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            logger.info("Veritabanı bağlantısı başarıyla kuruldu")
            return True

        except Exception as e:
            logger.error(f"Veritabanı bağlantısı kurulamadı: {e}")
            return False

    async def check_connection(self) -> bool:
        """Veritabanı bağlantısını test eder."""
        if not self.engine:
            logger.error("Engine henüz başlatılmamış")
            return False

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                row = result.fetchone()
                if row and row[0] == 1:
                    logger.info("Veritabanı bağlantısı başarılı")
                    return True
                else:
                    logger.error("Veritabanı bağlantı testi başarısız")
                    return False
        except Exception as e:
            logger.error(f"Veritabanı bağlantı testi hatası: {e}")
            return False

    async def get_existing_tables(self) -> List[str]:
        """Mevcut tabloları listeler."""
        if not self.engine:
            return []

        try:
            async with self.engine.begin() as conn:
                # PostgreSQL için tablo listesi sorgusu - DISTINCT ile tekrarları önle
                result = await conn.execute(text("""
                                                 SELECT DISTINCT tablename
                                                 FROM pg_tables
                                                 WHERE schemaname = 'public'
                                                 ORDER BY tablename
                                                 """))
                tables = [row[0] for row in result.fetchall()]

                # Tekrarlanan tabloları kontrol et
                if len(tables) != len(set(tables)):
                    logger.warning("Tekrarlanan tablo isimleri tespit edildi!")
                    logger.warning(f"Ham liste: {tables}")
                    # Tekrarları kaldır
                    tables = list(dict.fromkeys(tables))  # Sırayı koruyarak tekrarları kaldır
                    logger.info(f"Tekrarlar kaldırıldı: {tables}")

                logger.info(f"Mevcut tablolar: {', '.join(tables) if tables else 'Hiç tablo yok'}")
                return tables
        except Exception as e:
            logger.error(f"Tablo listesi alınamadı: {e}")
            return []

    async def check_table_structure(self, table_name: str) -> Dict[str, Any]:
        """Belirli bir tablonun yapısını kontrol eder."""
        if not self.engine:
            return {"exists": False, "columns": []}

        try:
            async with self.engine.begin() as conn:
                # Tablo var mı kontrol et
                result = await conn.execute(text("""
                                                 SELECT EXISTS (SELECT
                                                                FROM information_schema.tables
                                                                WHERE table_schema = 'public'
                                                                  AND table_name = :table_name)
                                                 """), {"table_name": table_name})

                exists = result.fetchone()[0]

                if not exists:
                    return {"exists": False, "columns": []}

                # Tablo sütunlarını al
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
            logger.error(f"{table_name} tablosu yapısı kontrol edilemedi: {e}")
            return {"exists": False, "columns": []}

    def get_model_columns(self, table_name: str) -> Dict[str, Any]:
        """Model'den beklenen sütunları alır."""
        try:
            # Model importları
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

            # API Key modelini kontrol et
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

            # API Key'i de ekle eğer varsa
            try:
                from app.models.api_key import APIKey
                model_mapping['api_keys'] = APIKey
            except ImportError:
                pass

            if table_name not in model_mapping:
                logger.warning(f"{table_name} için model bulunamadı")
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
            logger.error(f"{table_name} model sütunları alınamadı: {e}")
            return {"exists": False, "columns": []}

    def _sqlalchemy_type_to_postgres(self, sqlalchemy_type: TypeEngine) -> str:
        """SQLAlchemy türünü PostgreSQL türüne çevirir."""
        type_name = str(sqlalchemy_type)

        # Temel tür eşlemeleri
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

        # Türü normalize et
        for sql_type, pg_type in type_mapping.items():
            if sql_type in type_name.upper():
                return pg_type

        # VARCHAR(255) gibi durumlarda
        if 'VARCHAR' in type_name.upper():
            return 'character varying'

        # Varsayılan olarak type_name'i döndür
        return type_name.lower()

    async def compare_table_columns(self, table_name: str) -> Dict[str, Any]:
        """Tablo sütunlarını model ile karşılaştırır."""
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

        # Eksik sütunlar (model'de var, DB'de yok)
        missing_columns = []
        for col_name, col_info in model_columns.items():
            if col_name not in db_columns:
                missing_columns.append(col_info)

        # Fazla sütunlar (DB'de var, model'de yok)
        extra_columns = []
        for col_name, col_info in db_columns.items():
            if col_name not in model_columns:
                extra_columns.append(col_info)

        # Tür uyumsuzlukları
        type_mismatches = []
        for col_name in set(db_columns.keys()) & set(model_columns.keys()):
            db_col = db_columns[col_name]
            model_col = model_columns[col_name]

            # Tür karşılaştırması (basit)
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
        """Eksik sütunları ekler."""
        if not missing_columns:
            return True

        try:
            async with self.engine.begin() as conn:
                for column in missing_columns:
                    col_name = column["name"]
                    col_type = column["type"]
                    nullable = "NULL" if column["nullable"] else "NOT NULL"

                    # Primary key sütunları için özel işlem
                    if column.get("primary_key"):
                        logger.info(f"Primary key sütunu {col_name} atlanıyor (manuel müdahale gerekli)")
                        continue

                    # Default değer varsa ekle
                    default_clause = ""
                    if column["default"] and column["default"] != "None":
                        default_clause = f" DEFAULT {column['default']}"

                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable}{default_clause}"

                    logger.info(f"Sütun ekleniyor: {table_name}.{col_name}")
                    await conn.execute(text(alter_sql))

            logger.info(f"{table_name} tablosuna {len(missing_columns)} sütun eklendi")
            return True

        except Exception as e:
            logger.error(f"{table_name} tablosuna sütun ekleme hatası: {e}")
            return False

    async def remove_extra_columns(self, table_name: str, extra_columns: List[Dict[str, Any]]) -> bool:
        """Fazla sütunları siler."""
        if not extra_columns:
            return True

        try:
            async with self.engine.begin() as conn:
                for column in extra_columns:
                    col_name = column["name"]

                    # Kritik sütunları koruma
                    if col_name in ['id', 'created_at', 'updated_at']:
                        logger.info(f"Kritik sütun {col_name} korunuyor")
                        continue

                    alter_sql = f"ALTER TABLE {table_name} DROP COLUMN {col_name}"

                    logger.info(f"Sütun siliniyor: {table_name}.{col_name}")
                    await conn.execute(text(alter_sql))

            logger.info(f"{table_name} tablosundan {len(extra_columns)} sütun silindi")
            return True

        except Exception as e:
            logger.error(f"{table_name} tablosundan sütun silme hatası: {e}")
            return False

    async def sync_table_columns(self, table_name: str, add_missing: bool = True, remove_extra: bool = True) -> bool:
        """Tablo sütunlarını model ile senkronize eder."""
        logger.info(f"{table_name} sütun senkronizasyonu başlatılıyor...")

        comparison = await self.compare_table_columns(table_name)

        if not comparison["table_exists"] or not comparison["model_exists"]:
            logger.error(f"{table_name} senkronizasyonu için tablo veya model mevcut değil")
            return False

        success = True

        # Eksik sütunları ekle
        if add_missing and comparison["missing_columns"]:
            logger.info(f"{len(comparison['missing_columns'])} eksik sütun ekleniyor...")
            if not await self.add_missing_columns(table_name, comparison["missing_columns"]):
                success = False

        # Fazla sütunları sil
        if remove_extra and comparison["extra_columns"]:
            logger.info(f"{len(comparison['extra_columns'])} fazla sütun siliniyor...")
            if not await self.remove_extra_columns(table_name, comparison["extra_columns"]):
                success = False

        # Tür uyumsuzlukları hakkında uyar
        if comparison["type_mismatches"]:
            logger.warning(f"{table_name} tablosunda {len(comparison['type_mismatches'])} tür uyumsuzluğu var:")
            for mismatch in comparison["type_mismatches"]:
                logger.warning(
                    f"   - {mismatch['column_name']}: DB={mismatch['db_type']} ≠ Model={mismatch['model_type']}")

        if success:
            logger.info(f"{table_name} sütun senkronizasyonu tamamlandı")
        else:
            logger.error(f"{table_name} sütun senkronizasyonu başarısız")

        return success

    async def create_tables(self, force: bool = False):
        """Tüm tabloları oluşturur."""
        if not self.engine:
            logger.error("Engine henüz başlatılmamış")
            return False

        try:
            # Model importları
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

            # API Key modelini kontrol et
            try:
                from app.models.api_key import APIKey
                logger.info("API Key modeli bulundu")
            except ImportError:
                logger.warning("API Key modeli bulunamadı, atlanıyor")

            if force:
                logger.warning("FORCE modu: Tüm tablolar silinecek ve yeniden oluşturulacak")
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                logger.info("Tüm tablolar silindi")

            # Tabloları oluştur
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Tüm tablolar başarıyla oluşturuldu")
            return True

        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {e}")
            return False

    async def drop_all_tables(self):
        """Tüm tabloları siler."""
        if not self.engine:
            logger.error("Engine henüz başlatılmamış")
            return False

        try:
            from app.models.base import Base

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

            logger.info("Tüm tablolar silindi")
            return True

        except Exception as e:
            logger.error(f"Tablo silme hatası: {e}")
            return False

    async def validate_tables(self, check_columns: bool = True) -> Dict[str, Any]:
        """Tüm tabloları doğrular ve isteğe bağlı olarak sütunları kontrol eder."""
        existing_tables = await self.get_existing_tables()

        validation_result = {
            "total_expected": len(self.expected_tables),
            "total_existing": len(existing_tables),
            "missing_tables": [],
            "existing_tables": existing_tables,
            "table_details": {},
            "column_issues": {} if check_columns else None
        }

        # Eksik tabloları bul
        for table in self.expected_tables:
            if table not in existing_tables:
                validation_result["missing_tables"].append(table)
            else:
                # Tablo yapısını kontrol et
                structure = await self.check_table_structure(table)
                validation_result["table_details"][table] = structure

                # Sütun kontrolü
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
        """Ana veritabanı kurulum fonksiyonu."""
        logger.info("KAI-Flow Veritabanı Kurulum Scripti Başlatılıyor...")

        # Başlatma
        if not await self.initialize():
            return False

        # Bağlantı testi
        if not await self.check_connection():
            return False

        # Sadece kontrol modu
        if check_only:
            logger.info("Sadece kontrol modu - tablolar oluşturulmayacak")
            validation = await self.validate_tables(check_columns=sync_columns)
            self._print_validation_results(validation)
            return True

        # Tüm tabloları sil
        if drop_all:
            logger.warning("DROP_ALL modu: Tüm tablolar silinecek!")
            if not await self.drop_all_tables():
                return False

        # Mevcut durumu kontrol et
        validation = await self.validate_tables(check_columns=sync_columns)
        self._print_validation_results(validation)

        # Eksik tablolar varsa oluştur
        if validation["missing_tables"] or force:
            if validation["missing_tables"]:
                logger.info(f"Eksik tablolar oluşturuluyor: {', '.join(validation['missing_tables'])}")

            if not await self.create_tables(force=force):
                return False

            # Oluşturma sonrası kontrol
            logger.info("Tablo oluşturma sonrası kontrol...")
            post_validation = await self.validate_tables(check_columns=sync_columns)
            self._print_validation_results(post_validation)

            if post_validation["missing_tables"]:
                logger.error(f"Hala eksik tablolar var: {', '.join(post_validation['missing_tables'])}")
                return False
            else:
                logger.info("Tüm tablolar başarıyla oluşturuldu ve doğrulandı")
        else:
            logger.info("Tüm tablolar zaten mevcut")

        # Sütun senkronizasyonu
        if sync_columns and validation["column_issues"]:
            logger.info("Sütun senkronizasyonu başlatılıyor...")

            for table_name, issues in validation["column_issues"].items():
                await self.sync_table_columns(
                    table_name,
                    add_missing=add_missing_columns,
                    remove_extra=remove_extra_columns
                )

            # Senkronizasyon sonrası son kontrol
            logger.info("Sütun senkronizasyonu sonrası kontrol...")
            final_validation = await self.validate_tables(check_columns=True)
            self._print_validation_results(final_validation)

            if final_validation["column_issues"]:
                remaining_issues = len(final_validation["column_issues"])
                logger.warning(f"{remaining_issues} tabloda hala sütun sorunları var")
            else:
                logger.info("Tüm sütunlar başarıyla senkronize edildi")

        return True

    def _print_validation_results(self, validation: Dict[str, Any]):
        """Doğrulama sonuçlarını yazdırır."""
        logger.info("=" * 60)
        logger.info("VERİTABANI DURUM RAPORU")
        logger.info("=" * 60)
        logger.info(f"Beklenen tablo sayısı: {validation['total_expected']}")
        logger.info(f"Mevcut tablo sayısı: {validation['total_existing']}")

        if validation["missing_tables"]:
            logger.warning(f"Eksik tablolar ({len(validation['missing_tables'])}):")
            for table in validation["missing_tables"]:
                logger.warning(f"   - {table}")
        else:
            logger.info("Tüm beklenen tablolar mevcut")

        # Mevcut tabloları düzenli şekilde göster
        if validation['existing_tables']:
            logger.info("Mevcut tablolar:")
            # Tabloları alfabetik sıraya göre grupla
            sorted_tables = sorted(validation['existing_tables'])
            for i, table in enumerate(sorted_tables, 1):
                logger.info(f"   {i:2d}. {table}")
        else:
            logger.info("Mevcut tablo yok")

        # Sütun sorunlarını göster
        if validation.get("column_issues"):
            logger.warning(f"Sütun sorunları olan tablolar ({len(validation['column_issues'])}):")
            for table_name, issues in validation["column_issues"].items():
                logger.warning(f"   {table_name}:")

                if issues["missing_columns"]:
                    logger.warning(f"      Eksik sütunlar ({len(issues['missing_columns'])}):")
                    for col in issues["missing_columns"]:
                        logger.warning(f"         - {col['name']} ({col['type']})")

                if issues["extra_columns"]:
                    logger.warning(f"      Fazla sütunlar ({len(issues['extra_columns'])}):")
                    for col in issues["extra_columns"]:
                        logger.warning(f"         - {col['name']} ({col['type']})")

                if issues["type_mismatches"]:
                    logger.warning(f"      Tür uyumsuzlukları ({len(issues['type_mismatches'])}):")
                    for mismatch in issues["type_mismatches"]:
                        logger.warning(
                            f"         - {mismatch['column_name']}: DB={mismatch['db_type']} ≠ Model={mismatch['model_type']}")
        elif validation.get("column_issues") is not None:
            logger.info("Tüm sütunlar modellerle uyumlu")

        logger.info("=" * 60)


async def main():
    """Ana fonksiyon."""
    parser = argparse.ArgumentParser(description="KAI-Flow Veritabanı Kurulum Scripti")
    parser.add_argument("--force", action="store_true", help="Mevcut tabloları silip yeniden oluşturur")
    parser.add_argument("--check-only", action="store_true", help="Sadece mevcut tabloları kontrol eder")
    parser.add_argument("--drop-all", action="store_true", help="Tüm tabloları siler ve yeniden oluşturur")
    parser.add_argument("--no-sync-columns", action="store_true", help="Sütun senkronizasyonunu devre dışı bırakır")
    parser.add_argument("--no-add-columns", action="store_true", help="Eksik sütun eklemeyi devre dışı bırakır")
    parser.add_argument("--remove-extra-columns", action="store_true",
                        help="Fazla sütunları siler (dikkatli kullanın!)")

    args = parser.parse_args()

    # Environment kontrolü
    if not CREATE_DATABASE:
        logger.error("CREATE_DATABASE environment variable 'true' olarak ayarlanmamış")
        logger.info("Çözüm: export CREATE_DATABASE=true")
        sys.exit(1)

    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable ayarlanmamış")
        logger.info("Çözüm: export DATABASE_URL='your_database_url'")
        sys.exit(1)

    # Sütun silme uyarısı
    if args.remove_extra_columns:
        logger.warning("DIKKAT: --remove-extra-columns parametresi fazla sütunları siler!")
        logger.warning("Bu işlem geri alınamaz ve veri kaybına sebep olabilir!")

    # Database setup başlat
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
            logger.info("Veritabanı kurulumu başarıyla tamamlandı!")
            sys.exit(0)
        else:
            logger.error("Veritabanı kurulumu başarısız!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 