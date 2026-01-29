import logging
from typing import Dict, Any, Optional, Set, List
from datetime import datetime, timedelta
import threading
import uuid
from app.core.encryption import decrypt_data
from app.services.credential_service import CredentialService
from app.services.dependencies import get_credential_service_dep
from app.core.database import get_db_session_context, SessionLocal
from app.models.user_credential import UserCredential
import base64
# ------------------------------------------------------------------
# Legacy Supabase dependency – replaced by SQLAlchemy layer.
# ------------------------------------------------------------------
logger = logging.getLogger(__name__)


class CredentialProvider:
    """
    Singleton credential provider for secure access to encrypted credentials
    Implements caching and lazy loading for performance
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized') or not self._initialized:
            self.cache: Dict[str, Dict[str, Any]] = {}
            self.cache_timestamps: Dict[str, datetime] = {}
            self.cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes
            self.user_contexts: Dict[str, str] = {}  # Maps context_id to user_id
            self._initialized = True
    
    def set_user_context(self, context_id: str, user_id: str):
        """
        Set user context for credential access
        This is called when starting a workflow execution
        """
        self.user_contexts[context_id] = user_id
    
    def clear_user_context(self, context_id: str):
        """Clear user context when workflow execution ends"""
        if context_id in self.user_contexts:
            del self.user_contexts[context_id]
            
        # Also clear related cache entries
        to_remove = [key for key in self.cache.keys() if key.startswith(f"{context_id}:")]
        for key in to_remove:
            del self.cache[key]
            del self.cache_timestamps[key]
    
    async def get_credential(
        self, 
        credential_id: uuid.UUID, 
        user_id: uuid.UUID,
        service_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get credential data by name or ID
        
        Args:
            credential_name_or_id: Name or UUID of the credential
            context_id: Context ID to identify the user
            service_type: Optional service type filter
            
        Returns:
            Decrypted credential data or None if not found
        """
        # Fetch from database
        try:
            async with get_db_session_context() as db:
                cred = await get_credential_service_dep().get_decrypted_credential(db=db, user_id=user_id, credential_id=credential_id)
            return cred
            
        except Exception as e:
            logger.error(f"Error fetching credential {credential_id}: {e}")
            return None
    
    def _process_credential_data(self, credential: UserCredential) -> Dict[str, Any]:
        """Helper to process credential data consistently"""
        try:
            # Convert base64 string back to bytes for decryption
            encrypted_bytes = base64.b64decode(credential.encrypted_secret.encode('utf-8'))
            decrypted_secret = decrypt_data(encrypted_bytes)
            return {
                "id": credential.id,
                "name": credential.name,
                "service_type": credential.service_type,
                "secret": decrypted_secret if decrypted_secret is not None else {},
                "created_at": credential.created_at,
                "updated_at": credential.updated_at
            }
        except Exception as e:
            logger.error(f"{e}")
            # Return credential with empty secret if decryption fails
            return {
                "id": credential.id,
                "name": credential.name,
                "service_type": credential.service_type,
                "secret": {},
                "created_at": credential.created_at,
                "updated_at": credential.updated_at
            }

    def get_credential_sync(
        self, 
        credential_id: uuid.UUID, 
        user_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous version of get_credential for use in non-async contexts (e.g. Nodes)
        """
        if not SessionLocal:
            logger.error("Database not initialized for sync access")
            return None

        session = SessionLocal()
        try:
            credential = session.query(UserCredential).filter_by(user_id=user_id, id=credential_id).first()
            
            if not credential:
                return None
                
            return self._process_credential_data(credential)
        except Exception as e:
            print(f"Error fetching credential sync {credential_id}: {e}")
            return None
        finally:
            session.close()

    def get_credentials_sync(
        self, 
        user_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get all credentials for a user
        """
        if not SessionLocal:
            logger.error("Database not initialized for sync access")
            return []

        session = SessionLocal()
        try:
            credentials = session.query(UserCredential).filter_by(user_id=user_id).all()
            return [self._process_credential_data(credential) for credential in credentials]
        except Exception as e:
            logger.error(f"Error fetching credentials for user {user_id}: {e}")
            return []
        finally:
            session.close()

    async def get_credential_by_service(
        self, 
        service_type: str, 
        context_id: str,
        credential_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the first active credential for a service type
        
        Args:
            service_type: Type of service (openai, anthropic, etc.)
            context_id: Context ID to identify the user
            credential_name: Optional specific credential name
            
        Returns:
            Decrypted credential data or None if not found
        """
        user_id = self.user_contexts.get(context_id)
        if not user_id:
            raise ValueError(f"No user context found for context_id: {context_id}")
        
        try:
            async with get_db_session_context() as db:
                credentials = await get_credential_service_dep().get_by_user_id(db=db, user_id=user_id)
            
            # Filter by service type
            credentials = [c for c in credentials if c.service_type == service_type]
            
            if not credentials:
                return None
            
            # If specific name provided, find it
            if credential_name:
                credential = next(
                    (c for c in credentials if c.name == credential_name),
                    None
                )
            else:
                # Get the first credential
                credential = credentials[0] if credentials else None
            
            if credential:
                return await self.get_credential(credential.id, context_id=context_id, user_id=user_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching credential for service {service_type}: {e}")
            return None

    async def _fetch_credential(
        self, 
        credential_id: uuid.UUID, 
        user_id: str,
        service_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch credential from database by name or ID"""
        
        # Try by ID first
        async with get_db_session_context() as db:
            credential = await get_credential_service_dep().get_by_user_and_id(db=db, user_id=user_id, credential_id=credential_id)
        
        if credential:
            if not service_type or credential.service_type == service_type:
                return credential
        return None
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid"""
        if cache_key not in self.cache_timestamps:
            return False
        
        return datetime.now() - self.cache_timestamps[cache_key] < self.cache_ttl
    
    def clear_cache(self):
        """Clear all cached credentials"""
        self.cache.clear()
        self.cache_timestamps.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        total_entries = len(self.cache)
        valid_entries = sum(1 for key in self.cache.keys() if self._is_cache_valid(key))
        
        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": total_entries - valid_entries,
            "cache_ttl_minutes": self.cache_ttl.total_seconds() / 60
        }


# Global singleton instance
credential_provider = CredentialProvider()

# Convenience functions for easy access
async def get_credential(
    credential_id: uuid.UUID, 
    user_id: uuid.UUID,
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get credential
    """
    return await credential_provider.get_credential(
        credential_id=credential_id,
        user_id=user_id
    )

async def get_openai_credential(context_id: str, name: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key"""
    cred = await credential_provider.get_credential_by_service("openai", context_id, name)
    return cred.get("api_key") if cred else None

async def get_anthropic_credential(context_id: str, name: Optional[str] = None) -> Optional[str]:
    """Get Anthropic API key"""
    cred = await credential_provider.get_credential_by_service("anthropic", context_id, name)
    return cred.get("api_key") if cred else None

async def get_google_credential(context_id: str, name: Optional[str] = None) -> Optional[str]:
    """Get Google API key"""
    cred = await credential_provider.get_credential_by_service("google", context_id, name)
    return cred.get("api_key") if cred else None

def set_workflow_context(context_id: str, user_id: str):
    """Set user context for workflow execution"""
    credential_provider.set_user_context(context_id, user_id)

def clear_workflow_context(context_id: str):
    """Clear workflow context"""
    credential_provider.clear_user_context(context_id) 