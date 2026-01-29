#!/usr/bin/env python3
"""
Docker Export Functionality - Comprehensive Test Suite

Bu test suite, dinamik Docker export sisteminin tüm bileşenlerini 
test eder ve export edilen paketlerin doğru çalışıp çalışmadığını doğrular.
"""

import os
import sys
import json
import asyncio
import aiohttp
import aiofiles
import zipfile
import tempfile
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.core.constants import API_START,API_VERSION

# Test configuration
BASE_URL = "http://localhost:8000"
API_TOKEN = "test-token"
TEST_TIMEOUT = 30

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class DockerExportTester:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_results = []
        self.temp_dirs = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TEST_TIMEOUT),
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        # Cleanup temp directories
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def log_test(self, test_name: str, status: str, message: str = "", details: Dict = None):
        """Test sonuçlarını logla"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if status == "PASS":
            color = Colors.GREEN
        elif status == "FAIL":
            color = Colors.RED
        elif status == "SKIP":
            color = Colors.YELLOW
        else:
            color = Colors.BLUE
        
        print(f"{color} [{timestamp}] {test_name}: {status}{Colors.END}")
        if message:
            print(f"   {message}")
        
        self.test_results.append({
            "test_name": test_name,
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": timestamp
        })
    
    async def test_workflow_dependency_analysis(self) -> bool:
        """Test Scenario 1: Basic OpenAI Workflow Dependency Analysis"""
        self.log_test("Workflow Dependency Analysis", "INFO", "Starting basic OpenAI workflow test...")
        
        # Test data - OpenAI workflow
        test_workflow = {
            "workflow_id": "test-openai-workflow",
            "flow_data": {
                "nodes": [
                    {
                        "id": "openai_1",
                        "type": "OpenAIChat",
                        "data": {
                            "model_name": "gpt-4o-mini",
                            "temperature": 0.7,
                            "max_tokens": 1000,
                            "api_key": "sk-test123..."
                        }
                    },
                    {
                        "id": "memory_1",
                        "type": "BufferMemory",
                        "data": {
                            "memory_key": "chat_history",
                            "return_messages": True
                        }
                    }
                ],
                "edges": []
            }
        }
        
        try:
            # First, create workflow for testing
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/workflows",
                json=test_workflow,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status not in [200, 201]:
                    self.log_test("Workflow Creation", "FAIL", f"Failed to create test workflow: {response.status}")
                    return False
            
            # Test dependency analysis
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/export/workflow/test-openai-workflow",
                json={
                    "include_credentials": True,
                    "export_format": "docker"
                },
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    self.log_test("Dependency Analysis", "FAIL", f"API call failed: {response.status}")
                    return False
                
                data = await response.json()
                
                # Validate response structure
                required_fields = ["workflow_id", "required_env_vars", "dependencies", "export_ready"]
                for field in required_fields:
                    if field not in data:
                        self.log_test("Response Structure", "FAIL", f"Missing field: {field}")
                        return False
                
                # Validate environment variables
                env_vars = data.get("required_env_vars", {}).get("required", [])
                expected_env_vars = ["DATABASE_URL", "OPENAI_API_KEY"]
                
                found_env_vars = [var["name"] for var in env_vars]
                for expected_var in expected_env_vars:
                    if expected_var not in found_env_vars:
                        self.log_test("Environment Variables", "FAIL", f"Missing env var: {expected_var}")
                        return False
                
                # Validate dependencies
                dependencies = data.get("dependencies", {})
                if "nodes" not in dependencies or "python_packages" not in dependencies:
                    self.log_test("Dependencies Structure", "FAIL", "Missing nodes or python_packages")
                    return False
                
                nodes = dependencies["nodes"]
                expected_nodes = ["OpenAIChat", "BufferMemory"]
                for expected_node in expected_nodes:
                    if expected_node not in nodes:
                        self.log_test("Node Detection", "FAIL", f"Missing node: {expected_node}")
                        return False
                
                # Validate python packages
                packages = dependencies["python_packages"]
                expected_packages = ["fastapi", "langchain", "langchain-openai", "openai"]
                for expected_pkg in expected_packages:
                    if not any(expected_pkg in pkg for pkg in packages):
                        self.log_test("Package Dependencies", "FAIL", f"Missing package: {expected_pkg}")
                        return False
                
                self.log_test("Workflow Dependency Analysis", "PASS", 
                             f"Found {len(env_vars)} env vars, {len(nodes)} nodes, {len(packages)} packages")
                return True
                
        except Exception as e:
            self.log_test("Workflow Dependency Analysis", "FAIL", f"Exception: {str(e)}")
            return False
    
    async def test_complex_workflow_analysis(self) -> bool:
        """Test Scenario 2: Complex Multi-Node Workflow Analysis"""
        self.log_test("Complex Workflow Analysis", "INFO", "Starting complex multi-node workflow test...")
        
        # Complex workflow with multiple node types
        complex_workflow = {
            "workflow_id": "test-complex-workflow",
            "flow_data": {
                "nodes": [
                    {
                        "id": "openai_1",
                        "type": "OpenAIChat",
                        "data": {
                            "model_name": "gpt-4o",
                            "api_key": "sk-openai-key..."
                        }
                    },
                    {
                        "id": "tavily_1",
                        "type": "TavilySearch",
                        "data": {
                            "tavily_api_key": "tvly-search-key...",
                            "max_results": 5,
                            "search_depth": "advanced"
                        }
                    },
                    {
                        "id": "cohere_1",
                        "type": "CohereRerankerProvider",
                        "data": {
                            "cohere_api_key": "cohere-key...",
                            "model": "rerank-english-v3.0",
                            "top_n": 3
                        }
                    }
                ]
            }
        }
        
        try:
            # Create complex workflow
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/workflows",
                json=complex_workflow,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status not in [200, 201]:
                    self.log_test("Complex Workflow Creation", "FAIL", f"Failed to create workflow: {response.status}")
                    return False
            
            # Analyze complex workflow
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/export/workflow/test-complex-workflow",
                json={
                    "include_credentials": True,
                    "export_format": "docker"
                },
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    self.log_test("Complex Analysis", "FAIL", f"API call failed: {response.status}")
                    return False
                
                data = await response.json()
                
                # Validate multiple credential detection
                env_vars = data.get("required_env_vars", {}).get("required", [])
                expected_credentials = ["OPENAI_API_KEY", "TAVILY_API_KEY", "COHERE_API_KEY"]
                
                found_credentials = [var["name"] for var in env_vars]
                for cred in expected_credentials:
                    if cred not in found_credentials:
                        self.log_test("Multi-Credential Detection", "FAIL", f"Missing credential: {cred}")
                        return False
                
                # Validate node-specific packages
                packages = data.get("dependencies", {}).get("python_packages", [])
                expected_package_groups = ["langchain-openai", "langchain-tavily", "langchain-cohere"]
                
                for pkg_group in expected_package_groups:
                    if not any(pkg_group in pkg for pkg in packages):
                        self.log_test("Complex Package Dependencies", "FAIL", f"Missing package group: {pkg_group}")
                        return False
                
                self.log_test("Complex Workflow Analysis", "PASS", 
                             f"Successfully analyzed complex workflow with {len(expected_credentials)} credentials")
                return True
                
        except Exception as e:
            self.log_test("Complex Workflow Analysis", "FAIL", f"Exception: {str(e)}")
            return False
    
    async def test_complete_export_generation(self) -> bool:
        """Test Scenario 3: Complete Export Package Generation"""
        self.log_test("Complete Export Generation", "INFO", "Starting complete export test...")
        
        export_config = {
            "env_vars": {
                "DATABASE_URL": "postgresql://user:pass@localhost:5432/test_db",
                "OPENAI_API_KEY": "sk-test-key-12345",
                "SECRET_KEY": "test-secret-key-67890"
            },
            "security": {
                "require_api_key": True,
                "api_keys": "test-key-1,test-key-2",
                "allowed_hosts": "*"
            },
            "monitoring": {
                "enable_langsmith": True,
                "langsmith_api_key": "lsv2_sk_test...",
                "langsmith_project": "test-project"
            },
            "docker": {
                "api_port": 8000,
                "docker_port": 8080
            }
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/export/workflow/test-openai-workflow/complete",
                json=export_config,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    self.log_test("Export Generation", "FAIL", f"API call failed: {response.status}")
                    return False
                
                data = await response.json()
                
                # Validate response
                required_fields = ["download_url", "package_size", "ready_to_run"]
                for field in required_fields:
                    if field not in data:
                        self.log_test("Export Response", "FAIL", f"Missing field: {field}")
                        return False
                
                if not data.get("ready_to_run"):
                    self.log_test("Export Readiness", "FAIL", "Package not marked as ready to run")
                    return False
                
                download_url = data["download_url"]
                package_size = data["package_size"]
                
                self.log_test("Complete Export Generation", "PASS", 
                             f"Generated package: {package_size} bytes, URL: {download_url}")
                return True
                
        except Exception as e:
            self.log_test("Complete Export Generation", "FAIL", f"Exception: {str(e)}")
            return False
    
    async def test_package_download_and_validation(self) -> bool:
        """Test Scenario 4: Package Download and Content Validation"""
        self.log_test("Package Download", "INFO", "Starting package download and validation...")
        
        try:
            # Download the package
            async with self.session.get(
                f"{BASE_URL}/{API_START}/{API_VERSION}/export/download/workflow-export-test-openai-workflow.zip"
            ) as response:
                
                if response.status != 200:
                    self.log_test("Package Download", "FAIL", f"Download failed: {response.status}")
                    return False
                
                # Create temp directory for extraction
                temp_dir = tempfile.mkdtemp(prefix="export_test_")
                self.temp_dirs.append(temp_dir)
                
                # Save downloaded file
                zip_path = os.path.join(temp_dir, "export_package.zip")
                async with aiofiles.open(zip_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                
                # Extract and validate
                extract_dir = os.path.join(temp_dir, "extracted")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Validate directory structure
                expected_files = [
                    ".env",
                    "docker-compose.yml", 
                    "Dockerfile",
                    "requirements.txt",
                    "README.md",
                    "main.py",
                    "workflow-definition.json"
                ]
                
                for expected_file in expected_files:
                    file_path = os.path.join(extract_dir, expected_file)
                    if not os.path.exists(file_path):
                        self.log_test("File Structure", "FAIL", f"Missing file: {expected_file}")
                        return False
                
                # Validate .env file content
                env_path = os.path.join(extract_dir, ".env")
                async with aiofiles.open(env_path, 'r') as f:
                    env_content = await f.read()
                
                expected_env_vars = ["OPENAI_API_KEY", "DATABASE_URL", "SECRET_KEY"]
                for env_var in expected_env_vars:
                    if env_var not in env_content:
                        self.log_test("Env File Content", "FAIL", f"Missing env var in .env: {env_var}")
                        return False
                
                # Validate requirements.txt
                req_path = os.path.join(extract_dir, "requirements.txt")
                async with aiofiles.open(req_path, 'r') as f:
                    req_content = await f.read()
                
                expected_packages = ["fastapi", "langchain", "openai"]
                for package in expected_packages:
                    if package not in req_content:
                        self.log_test("Requirements Content", "FAIL", f"Missing package: {package}")
                        return False
                
                # Validate docker-compose.yml
                compose_path = os.path.join(extract_dir, "docker-compose.yml")
                if not os.path.exists(compose_path):
                    self.log_test("Docker Compose", "FAIL", "Missing docker-compose.yml")
                    return False
                
                self.log_test("Package Download", "PASS", 
                             f"Package downloaded and validated successfully in {extract_dir}")
                return True
                
        except Exception as e:
            self.log_test("Package Download", "FAIL", f"Exception: {str(e)}")
            return False
    
    async def test_fallback_system(self) -> bool:
        """Test Scenario 5: Fallback System Test"""
        self.log_test("Fallback System", "INFO", "Testing fallback behavior...")
        
        # Test with non-existent workflow to trigger fallback
        try:
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/export/workflow/non-existent-workflow",
                json={
                    "include_credentials": True,
                    "export_format": "docker"
                },
                headers={"Content-Type": "application/json"}
            ) as response:
                
                # Should handle gracefully with fallback
                if response.status == 404:
                    self.log_test("Fallback System", "PASS", "Correctly handled non-existent workflow")
                    return True
                elif response.status == 200:
                    data = await response.json()
                    if data.get("fallback_used"):
                        self.log_test("Fallback System", "PASS", "Fallback system activated correctly")
                        return True
                    else:
                        self.log_test("Fallback System", "FAIL", "Expected fallback activation")
                        return False
                else:
                    self.log_test("Fallback System", "FAIL", f"Unexpected response: {response.status}")
                    return False
                    
        except Exception as e:
            self.log_test("Fallback System", "FAIL", f"Exception: {str(e)}")
            return False
    
    async def test_performance_metrics(self) -> bool:
        """Test Scenario 6: Performance Validation"""
        self.log_test("Performance Metrics", "INFO", "Testing performance...")
        
        try:
            start_time = time.time()
            
            # Test analysis performance
            async with self.session.post(
                f"{BASE_URL}/{API_START}/{API_VERSION}/export/workflow/test-openai-workflow",
                json={
                    "include_credentials": True,
                    "export_format": "docker"
                },
                headers={"Content-Type": "application/json"}
            ) as response:
                
                analysis_time = time.time() - start_time
                
                if response.status != 200:
                    self.log_test("Performance Test", "FAIL", f"API call failed: {response.status}")
                    return False
                
                # Performance criteria: Analysis should complete in < 2 seconds
                if analysis_time > 2.0:
                    self.log_test("Analysis Performance", "FAIL", 
                                f"Analysis took {analysis_time:.2f}s (expected < 2s)")
                    return False
                
                self.log_test("Performance Metrics", "PASS", 
                             f"Analysis completed in {analysis_time:.2f}s")
                return True
                
        except Exception as e:
            self.log_test("Performance Metrics", "FAIL", f"Exception: {str(e)}")
            return False
    
    def print_test_summary(self):
        """Test sonuçlarının özetini yazdır"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}  DOCKER EXPORT FUNCTIONALITY TEST SUMMARY{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
        
        total_tests = len(self.test_results)
        passed = len([r for r in self.test_results if r["status"] == "PASS"])
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        skipped = len([r for r in self.test_results if r["status"] == "SKIP"])
        
        print(f"\n{Colors.WHITE}Total Tests: {total_tests}{Colors.END}")
        print(f"{Colors.GREEN} Passed: {passed}{Colors.END}")
        print(f"{Colors.RED} Failed: {failed}{Colors.END}")
        print(f"{Colors.YELLOW} Skipped: {skipped}{Colors.END}")
        
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.END}")
        
        if failed > 0:
            print(f"\n{Colors.RED}{Colors.BOLD}FAILED TESTS:{Colors.END}")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"{Colors.RED} {result['test_name']}: {result['message']}{Colors.END}")
        
        # Overall assessment
        if success_rate >= 95:
            print(f"\n{Colors.GREEN}{Colors.BOLD} EXCELLENT: System ready for production!{Colors.END}")
        elif success_rate >= 80:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}GOOD: Minor issues to address{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD} NEEDS WORK: Major issues detected{Colors.END}")

async def main():
    """Ana test fonksiyonu"""
    print(f"{Colors.BOLD}{Colors.MAGENTA}")
    print("DOCKER EXPORT FUNCTIONALITY TEST SUITE")
    print("=" * 50)
    print(f"{Colors.END}")
    
    async with DockerExportTester() as tester:
        # Test sequence
        test_functions = [
            tester.test_workflow_dependency_analysis,
            tester.test_complex_workflow_analysis,
            tester.test_complete_export_generation,
            tester.test_package_download_and_validation,
            tester.test_fallback_system,
            tester.test_performance_metrics
        ]
        
        print(f"{Colors.BLUE} Starting test sequence...{Colors.END}\n")
        
        for test_func in test_functions:
            try:
                await test_func()
                await asyncio.sleep(0.5)  # Brief pause between tests
            except Exception as e:
                tester.log_test(test_func.__name__, "FAIL", f"Unexpected error: {str(e)}")
        
        # Print summary
        tester.print_test_summary()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.RED}Test suite failed: {str(e)}{Colors.END}")