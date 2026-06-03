

from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.core.constants import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    KEYCLOAK_ENABLED, KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_VERIFY_SSL
)
from passlib.context import CryptContext
import requests
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Cache for Keycloak JWKS
_jwks_cache: Dict[str, Any] = {}
_jwks_last_update: Optional[datetime] = None

def get_keycloak_jwks() -> Dict[str, Any]:
    """Fetch and cache Keycloak JWKS."""
    global _jwks_cache, _jwks_last_update
    
    # Refresh cache every hour
    if _jwks_cache and _jwks_last_update and datetime.utcnow() - _jwks_last_update < timedelta(hours=1):
        return _jwks_cache
        
    try:
        jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        response = requests.get(jwks_url, timeout=10, verify=KEYCLOAK_VERIFY_SSL)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_last_update = datetime.utcnow()
        return _jwks_cache
    except Exception as e:
        logger.error(f"Failed to fetch Keycloak JWKS: {e}")
        # Return stale cache if available
        if _jwks_cache:
            return _jwks_cache
        raise

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify token signature and return payload.
    Supports both local HS256 tokens and Keycloak RS256 tokens.
    """
    try:
        # First decode header to check algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
        
        if alg == "HS256":
            # Verify local token
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            
        elif (alg == "RS256" or alg is None) and KEYCLOAK_ENABLED: # RS256 or maybe defaults to RS256 if Keycloak
             # Verify Keycloak token
            try:
                jwks = get_keycloak_jwks()
                return jwt.decode(
                    token,
                    jwks,
                    algorithms=["RS256"],
                    audience="account", # Default client scope often has 'account' audience
                    options={"verify_aud": False} # Relaxing audience check for now as it depends on client config
                )
            except Exception as e:
                 logger.warning(f"Keycloak verification failed: {e}")
                 # If RS256 failed, it might be that it's not a Keycloak token or keys are old.
                 raise
        else:
             # If algo is not HS256 and Keycloak is disabled, or algo is unknown
            raise JWTError("Unsupported algorithm or Keycloak disabled")
            
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
         logger.error(f"Unexpected error in token verification: {e}")
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = verify_token(token)
        # Keycloak often uses 'preferred_username' or 'email' or 'sub'
        username: str = payload.get("preferred_username") or payload.get("sub") or payload.get("email")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain text password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt