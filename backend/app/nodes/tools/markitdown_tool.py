import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from ..base import ProviderNode, NodeOutput, NodeType, NodePropertyType, NodeProperty, NodePosition
from app.services.minio_service import minio_service

try:
    from markitdown import MarkItDown
    from langchain_core.tools import Tool
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

logger = logging.getLogger(__name__)


class MarkItDownToolNode(ProviderNode):
    """
    MarkItDown Tool Provider with MinIO Integration.
    
    This node creates a LangChain Tool that enables AI agents to convert documents
    stored in MinIO/S3-compatible storage to Markdown format. The tool supports
    20+ document formats and provides optional OpenAI integration for enhanced
    OCR and audio transcription capabilities.
    
    Node Configuration:
    - MinIO Credential: Required - Stored credential with endpoint and access keys
    - Bucket Name: Required - MinIO bucket containing documents
    - Object Key: Required - Default object path (can be overridden at runtime)
    - LLM Credential: Optional - OpenAI or compatible API for OCR and transcription
    - LLM Base URL: Optional - Custom endpoint for compatible APIs (Azure, local, etc.)
    - LLM Model: Optional - Model to use (default: gpt-4o)
    - Max File Size: Optional - File size limit in MB (default: 100MB)
    
    Tool Behavior:
    - Downloads document from MinIO to temporary file
    - Converts to Markdown using MarkItDown library
    - Returns formatted markdown with source attribution
    - Automatically cleans up temporary files
    - Supports runtime object key override for dynamic document selection
    
    Integration Example:
    ```python
    # In workflow: MarkItDown Tool → ReactAgent
    # Agent can invoke: markitdown_minio_reader('reports/annual-report.pdf')
    # Returns: Markdown content ready for analysis
    ```
    
    Error Handling:
    - Validates credentials before execution
    - Checks file size before download
    - Provides detailed error messages for troubleshooting
    - Gracefully handles missing objects or buckets
    
    Performance Considerations:
    - Downloads in 1MB chunks for memory efficiency
    - Temporary files cleaned up immediately after conversion
    - Credential caching reduces database queries
    - Supports concurrent conversions across workflows
    """

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "MarkItDownTool",
            "display_name": "MarkItDown Tool",
            "description": (
                "Enterprise document conversion tool for AI agents. Converts documents from MinIO storage "
                "to Markdown format. Supports PDF, DOCX, PPTX, XLSX, images (with OCR), audio/video "
                "(with transcription), and 20+ other formats. Optional LLM integration for enhanced OCR "
                "and transcription (supports OpenAI, Azure OpenAI, and compatible APIs)."
            ),
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "markitdown", "path": "icons/markitdown.svg", "alt": "MarkItDown Document Converter"},
            "colors": ["emerald-500", "cyan-500"],
            "inputs": [],
            "outputs": [
                NodeOutput(
                    name="tool",
                    displayName="MarkItDown Tool",
                    type="BaseTool",
                    description="LangChain tool for converting MinIO documents to Markdown. Connect to agents.",
                    direction=NodePosition.TOP,
                    is_connection=True,
                ),
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="MinIO Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    serviceType="minio",
                    required=True,
                    hint="Select MinIO/S3 credential containing endpoint, access_key, and secret_key. "
                         "Create credentials in Settings → Credentials.",
                ),
                NodeProperty(
                    name="bucket_name",
                    displayName="Bucket Name",
                    type=NodePropertyType.TEXT,
                    placeholder="documents",
                    required=True,
                    hint="MinIO bucket containing documents to convert. Bucket must exist and be accessible "
                         "with the provided credentials.",
                ),
                NodeProperty(
                    name="object_key",
                    displayName="Default Object Key",
                    type=NodePropertyType.TEXT,
                    placeholder="reports/annual-report.pdf",
                    required=True,
                    hint="Default document path in bucket. Can be overridden when agent invokes the tool. "
                         "Example: 'documents/report.pdf' or 'data/spreadsheet.xlsx'",
                ),
                NodeProperty(
                    name="llm_credential_id",
                    displayName="LLM Credential (Optional - For OCR/Audio)",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    serviceType="openai_compatible",
                    required=False,
                    hint="Optional: OpenAI-compatible API credential (OpenRouter, Azure OpenAI, etc.) "
                         "for enhanced OCR (images) and audio/video transcription. "
                         "Create an 'OpenAI Compatible' credential with your API key and base URL.",
                ),
                NodeProperty(
                    name="llm_base_url",
                    displayName="LLM Base URL (Optional)",
                    type=NodePropertyType.TEXT,
                    placeholder="https://api.openai.com/v1",
                    required=False,
                    hint="Optional: Custom base URL for OpenAI-compatible APIs. "
                         "Leave empty for standard OpenAI API. "
                         "Examples: Azure OpenAI, local LLM servers, etc.",
                ),
                NodeProperty(
                    name="llm_model",
                    displayName="LLM Model (Optional)",
                    type=NodePropertyType.TEXT,
                    placeholder="openai/gpt-4o",
                    default="openai/gpt-4o",
                    required=False,
                    hint="Model to use for OCR and transcription. "
                         "For OpenRouter use provider/model format (e.g. openai/gpt-4o, anthropic/claude-3.5-sonnet). "
                         "For direct OpenAI use model name only (e.g. gpt-4o).",
                ),
                NodeProperty(
                    name="max_file_size_mb",
                    displayName="Max File Size (MB)",
                    type=NodePropertyType.NUMBER,
                    default=100,
                    required=False,
                    hint="Maximum file size to download and convert. Set to 0 for unlimited (not recommended). "
                         "Default: 100MB",
                ),
            ],
        }
    def _get_minio_client(self):
        """Get MinIO S3 client - required, no fallback."""
        credential_id = self.user_data.get("credential_id")
        if not credential_id:
            raise ValueError(
                "MinIO credential is required. Please select a MinIO credential in the node configuration."
            )

        credential = self.get_credential(credential_id)
        if not credential:
            raise ValueError(
                f"Selected MinIO credential (ID: {credential_id}) could not be found for the current user. "
                "Please ensure the credential is saved and accessible."
            )

        secret = credential.get("secret") or {}
        
        # Support multiple credential field naming conventions
        endpoint = secret.get("endpoint", "").strip()
        access_key = (
            secret.get("access_key") or 
            secret.get("username") or 
            secret.get("id") or 
            ""
        ).strip()
        secret_key = (
            secret.get("secret_key") or 
            secret.get("password") or 
            secret.get("secret") or 
            ""
        ).strip()
        
        # Clean endpoint URL (remove protocol if present)
        if endpoint.startswith("http://"):
            endpoint = endpoint[7:]
        elif endpoint.startswith("https://"):
            endpoint = endpoint[8:]
        
        use_ssl_val = secret.get("use_ssl", False)
        use_ssl = use_ssl_val is True or str(use_ssl_val).lower() in ['true', '1', 'yes']

        if not endpoint or not access_key or not secret_key:
            raise ValueError(
                "MinIO credential is incomplete. Required fields: endpoint, access_key (or username), "
                "and secret_key (or password) must be provided."
            )

        logger.info(
            "Creating MinIO client: endpoint=%s, access_key=%s***, use_ssl=%s",
            endpoint,
            access_key[:4] if len(access_key) > 4 else "***",
            use_ssl,
        )

        try:
            return minio_service.get_client(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                use_ssl=use_ssl,
            )
        except Exception as e:
            logger.error(f"Failed to create MinIO client: {str(e)}")
            raise ValueError(f"Failed to connect to MinIO at {endpoint}: {str(e)}")

    def _get_markitdown_instance(self):
        """Get MarkItDown instance with optional LLM integration for OCR/Audio."""
        llm_credential_id = self.user_data.get("llm_credential_id")
        
        if not llm_credential_id:
            logger.info("No LLM credential provided, using basic MarkItDown (no OCR/Audio support)")
            return MarkItDown()

        credential = self.get_credential(llm_credential_id)
        if not credential:
            logger.warning(
                "Selected LLM credential (ID: %s) not found, falling back to basic MarkItDown",
                llm_credential_id
            )
            return MarkItDown()

        secret = credential.get("secret") or {}
        
        # Support multiple API key field names
        api_key = (
            secret.get("api_key") or 
            secret.get("key") or 
            secret.get("token") or 
            secret.get("password") or
            ""
        ).strip()
        
        if not api_key:
            logger.warning("LLM credential missing api_key field, falling back to basic MarkItDown")
            return MarkItDown()

        # Get base URL: prioritize node property override, fallback to credential secret
        base_url = (self.user_data.get("llm_base_url") or "").strip()
        if not base_url:
            base_url = (secret.get("base_url") or "").strip()
        model = (self.user_data.get("llm_model") or "").strip()
        if not model:
            model = (secret.get("model_name") or "gpt-4o").strip()
        
        try:
            from openai import OpenAI
            
            # Create OpenAI client with optional base URL
            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
                logger.info(
                    "Initializing MarkItDown with custom LLM: model=%s, base_url=%s",
                    model,
                    base_url
                )
            else:
                logger.info(
                    "Initializing MarkItDown with OpenAI: model=%s",
                    model
                )
            
            llm_client = OpenAI(**client_kwargs)
            return MarkItDown(llm_client=llm_client, llm_model=model)
            
        except Exception as e:
            logger.error(
                f"Failed to initialize LLM client: {str(e)}, falling back to basic MarkItDown"
            )
            return MarkItDown()

    def _download_object_to_tempfile(self, client, bucket_name: str, object_key: str, max_file_size_mb: int) -> str:
        """Download MinIO object to temporary file with size validation."""
        max_bytes = max_file_size_mb * 1024 * 1024 if max_file_size_mb > 0 else None

        try:
            # Check object size before downloading
            head_response = client.head_object(Bucket=bucket_name, Key=object_key)
            content_length = head_response.get("ContentLength", 0)
            
            logger.info(
                "Downloading MinIO object: bucket=%s, key=%s, size=%d bytes",
                bucket_name,
                object_key,
                content_length
            )
            
            if max_bytes and content_length and content_length > max_bytes:
                raise ValueError(
                    f"Object '{object_key}' exceeds the maximum file size of {max_file_size_mb} MB "
                    f"(actual size: {content_length / (1024 * 1024):.2f} MB)."
                )

            # Download object
            response = client.get_object(Bucket=bucket_name, Key=object_key)
            body = response["Body"]
            suffix = Path(object_key).suffix or ".bin"

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                with temp_file as handle:
                    bytes_downloaded = 0
                    while True:
                        chunk = body.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        handle.write(chunk)
                        bytes_downloaded += len(chunk)
                
                logger.info(
                    "Successfully downloaded %d bytes to temp file: %s",
                    bytes_downloaded,
                    temp_file.name
                )
                return temp_file.name
            except Exception as e:
                logger.error(f"Error during download: {str(e)}")
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                raise
            finally:
                try:
                    body.close()
                except Exception:
                    pass
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise ValueError(
                    f"Object '{object_key}' not found in bucket '{bucket_name}'. "
                    "Please verify the object key and bucket name."
                )
            elif "NoSuchBucket" in str(e):
                raise ValueError(
                    f"Bucket '{bucket_name}' does not exist. "
                    "Please verify the bucket name or create the bucket first."
                )
            else:
                raise ValueError(f"Failed to download object from MinIO: {str(e)}")

    def _convert_minio_object(self, client, md, bucket_name: str, object_key: str, max_file_size_mb: int) -> str:
        """Convert MinIO object to Markdown using MarkItDown."""
        temp_path = None
        try:
            # Download object to temporary file
            temp_path = self._download_object_to_tempfile(client, bucket_name, object_key, max_file_size_mb)
            
            logger.info(
                "Converting document to Markdown: bucket=%s, key=%s, temp_path=%s",
                bucket_name,
                object_key,
                temp_path,
            )
            
            # Convert to Markdown
            result = md.convert(temp_path)
            text_content = getattr(result, "text_content", None) or str(result)
            
            # Format output with source attribution
            output = f"""# Document: {object_key}
**Source:** s3://{bucket_name}/{object_key}
**Converted by:** MarkItDown

---

{text_content}
"""
            
            logger.info(
                "Successfully converted document: %d characters of markdown generated",
                len(output)
            )
            
            return output
            
        except Exception as e:
            logger.error(
                "Failed to convert MinIO object bucket=%s key=%s: %s",
                bucket_name,
                object_key,
                str(e)
            )
            raise ValueError(f"MarkItDown conversion failed for '{object_key}': {str(e)}")
        finally:
            # Clean up temporary file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug("Cleaned up temporary file: %s", temp_path)
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to remove temporary file %s: %s",
                        temp_path,
                        str(cleanup_error)
                    )

    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute node to create MarkItDown tool with MinIO backend.
        
        This method validates configuration, establishes MinIO connection,
        and creates a LangChain Tool that agents can use to convert documents
        to Markdown format on-demand.
        
        Returns:
            Dict containing 'markitdown_tool' key with configured LangChain Tool
            
        Raises:
            ImportError: If markitdown or langchain_core not installed
            ValueError: If configuration invalid or credentials missing
        """
        if not MARKITDOWN_AVAILABLE:
            raise ImportError(
                "Required packages not installed. Run: pip install 'markitdown[all]>=0.1.5' langchain-core>=0.1.0"
            )

        # Validate and extract configuration
        bucket_name = (self.user_data.get("bucket_name") or "").strip()
        object_key = (self.user_data.get("object_key") or "").strip()
        max_file_size_mb = int(self.user_data.get("max_file_size_mb", 100))

        # Validate required configuration
        if not bucket_name:
            raise ValueError(
                "Bucket name is required. Please specify the MinIO bucket containing your documents."
            )
        if not object_key:
            raise ValueError(
                "Object key is required. Please specify the default document path (e.g., 'reports/document.pdf')."
            )

        logger.info(
            "Initializing MarkItDown Tool: bucket=%s, default_key=%s, max_size=%dMB",
            bucket_name,
            object_key,
            max_file_size_mb
        )

        # Get MinIO client (will raise if credential missing or invalid)
        client = self._get_minio_client()
        
        # Get MarkItDown instance (with optional OpenAI enhancement)
        md = self._get_markitdown_instance()

        def markitdown_minio_reader(object_key_override: str = "") -> str:
            """
            Read and convert a document from MinIO storage to Markdown format.
            
            Args:
                object_key_override: Path to the document in MinIO bucket. 
                                   If empty, uses the default configured document.
                                   Example: 'reports/annual-report.pdf'
                
            Returns:
                The document content converted to Markdown format with source attribution.
            """
            try:
                # Use override if provided, otherwise use configured key
                read_key = object_key_override.strip() if object_key_override else object_key
                if not read_key:
                    return (
                        f"ERROR: No document specified. "
                        f"Please provide a document path (e.g., 'reports/document.pdf') "
                        f"or configure a default document in the node settings."
                    )
                
                logger.info(
                    "MarkItDown tool invoked: bucket=%s, key=%s (override=%s)",
                    bucket_name,
                    read_key,
                    bool(object_key_override)
                )

                return self._convert_minio_object(
                    client=client,
                    md=md,
                    bucket_name=bucket_name,
                    object_key=read_key,
                    max_file_size_mb=max_file_size_mb,
                )
            except ValueError as e:
                # Return user-friendly error message
                return f"ERROR: {str(e)}"
            except Exception as e:
                logger.exception(
                    "Unexpected error during MarkItDown conversion: bucket=%s key=%s",
                    bucket_name,
                    object_key_override or object_key
                )
                return f"ERROR: Unexpected error during document conversion: {str(e)}"

        # Create LangChain Tool with agent-optimized description
        tool_description = (
            f"Read and convert documents from MinIO storage to Markdown text. "
            f"This tool accesses documents stored in MinIO bucket '{bucket_name}'. "
            f"Default document: '{object_key}'. "
            f"\n\nSupported formats: PDF, DOCX, PPTX, XLSX, CSV, images (PNG, JPG), audio, video, HTML, and more."
            f"\n\nUsage:"
            f"\n- To read the default document: Call without parameters"
            f"\n- To read a specific document: Provide the document path as 'object_key_override' parameter"
            f"\n\nExample: To read 'reports/annual-report.pdf', call with object_key_override='reports/annual-report.pdf'"
            f"\n\nThe tool returns the document content converted to Markdown format."
        )

        tool = Tool(
            name="read_document_from_minio",
            func=markitdown_minio_reader,
            description=tool_description,
        )

        logger.info(
            "✓ MarkItDown MinIO tool successfully created: bucket=%s, default_key=%s, max_size=%dMB",
            bucket_name,
            object_key,
            max_file_size_mb
        )

        # Return format: {"output_name": {"tool": tool_object}}
        # This matches Tavily and other tool providers
        return {
            "tool": {"tool": tool}
        }


__all__ = ["MarkItDownToolNode"]
