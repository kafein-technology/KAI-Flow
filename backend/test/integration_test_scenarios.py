#!/usr/bin/env python3
"""
Integration Test Scenarios for Docker Export System

Bu script gerçek API endpoint'leri test eder ve export sisteminin 
end-to-end functionality'sini doğrular.
"""

import os
import sys
import json
import requests
import time
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

# Projedeki backend'e import path ekle
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

class IntegrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token"
        })
        self.test_results = []
        self.temp_dirs = []
    
    def log_result(self, test_name: str, status: str, message: str = ""):
        """Test sonucu logla"""
        print(f"{'' if status == 'PASS' else '' if status == 'FAIL' else ''} {test_name}: {status}")
        if message:
            print(f"   → {message}")
        
        self.test_results.append({
            "test": test_name,
            "status": status,
            "message": message
        })
    
    def test_dynamic_analyzer_direct(self):
        """Direct dynamic analyzer test"""
        self.log_result("Dynamic Analyzer Direct Test", "INFO", "Testing analyzer directly...")
        
        try:
            from app.core.dynamic_node_analyzer import DynamicNodeAnalyzer
            from app.core.node_registry import NodeRegistry
            
            # Initialize components
            registry = NodeRegistry()
            analyzer = DynamicNodeAnalyzer(registry)
            
            # Test workflow
            test_nodes = [
                {
                    "id": "openai_1",
                    "type": "OpenAIChat",
                    "data": {
                        "model_name": "gpt-4o-mini",
                        "api_key": "sk-test123"
                    }
                }
            ]
            
            # Analyze workflow
            result = analyzer.analyze_workflow(test_nodes)
            
            # Validate result
            if not result:
                self.log_result("Dynamic Analyzer Direct", "FAIL", "Analyzer returned None")
                return False
            
            if not result.required_env_vars:
                self.log_result("Dynamic Analyzer Direct", "FAIL", "No environment variables detected")
                return False
            
            # Check for expected OpenAI API key
            openai_key_found = any(
                "OPENAI" in var.name and "API_KEY" in var.name 
                for var in result.required_env_vars
            )
            
            if not openai_key_found:
                self.log_result("Dynamic Analyzer Direct", "FAIL", "OpenAI API key not detected")
                return False
            
            self.log_result("Dynamic Analyzer Direct", "PASS", 
                          f"Detected {len(result.required_env_vars)} env vars, {len(result.python_packages)} packages")
            return True
            
        except Exception as e:
            self.log_result("Dynamic Analyzer Direct", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_export_routes_integration(self):
        """Test export routes functionality"""
        self.log_result("Export Routes Integration", "INFO", "Testing export routes...")
        
        try:
            from app.routes.export import analyze_workflow_dependencies
            
            # Test workflow data
            test_nodes = [
                {
                    "id": "openai_1",
                    "type": "OpenAIChat",
                    "data": {
                        "model_name": "gpt-4o-mini",
                        "api_key": "sk-test123"
                    }
                },
                {
                    "id": "memory_1",
                    "type": "BufferMemory",
                    "data": {
                        "memory_key": "chat_history"
                    }
                }
            ]
            
            # Call the function directly
            dependencies = analyze_workflow_dependencies(test_nodes)
            
            # Validate response
            if not dependencies:
                self.log_result("Export Routes Integration", "FAIL", "No dependencies returned")
                return False
            
            # Check required fields
            required_fields = ["nodes", "required_env_vars", "python_packages"]
            for field in required_fields:
                if not hasattr(dependencies, field):
                    self.log_result("Export Routes Integration", "FAIL", f"Missing field: {field}")
                    return False
            
            # Validate nodes
            if "OpenAIChat" not in dependencies.nodes:
                self.log_result("Export Routes Integration", "FAIL", "OpenAIChat node not detected")
                return False
            
            # Validate environment variables
            env_var_names = [var.name for var in dependencies.required_env_vars]
            if not any("OPENAI" in name and "API_KEY" in name for name in env_var_names):
                self.log_result("Export Routes Integration", "FAIL", "OpenAI API key not in env vars")
                return False
            
            # Validate packages
            if not any("openai" in pkg.lower() for pkg in dependencies.python_packages):
                self.log_result("Export Routes Integration", "FAIL", "OpenAI package not in dependencies")
                return False
            
            self.log_result("Export Routes Integration", "PASS", 
                          f"Successfully analyzed {len(dependencies.nodes)} nodes")
            return True
            
        except Exception as e:
            self.log_result("Export Routes Integration", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_node_registry_discovery(self):
        """Test node registry node discovery"""
        self.log_result("Node Registry Discovery", "INFO", "Testing node discovery...")
        
        try:
            from app.core.node_registry import NodeRegistry
            
            registry = NodeRegistry()
            registry.discover_nodes()
            
            # Check if some expected nodes are discovered
            expected_nodes = ["OpenAIChat", "BufferMemory", "TavilySearch"]
            available_nodes = list(registry.nodes.keys())
            
            found_nodes = [node for node in expected_nodes if node in available_nodes]
            
            if len(found_nodes) < 2:  # En az 2 node bulunmalı
                self.log_result("Node Registry Discovery", "FAIL", 
                              f"Only found {len(found_nodes)} expected nodes: {found_nodes}")
                return False
            
            self.log_result("Node Registry Discovery", "PASS", 
                          f"Discovered {len(available_nodes)} total nodes, {len(found_nodes)} expected nodes")
            return True
            
        except Exception as e:
            self.log_result("Node Registry Discovery", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_package_generation_logic(self):
        """Test package dependency generation logic"""
        self.log_result("Package Generation Logic", "INFO", "Testing package generation...")
        
        try:
            from app.core.dynamic_node_analyzer import PackageAnalyzer
            
            analyzer = PackageAnalyzer()
            
            # Test different node types
            test_cases = [
                ("OpenAIChat", ["openai", "langchain-openai"]),
                ("TavilySearch", ["langchain-tavily"]),
                ("BufferMemory", ["langchain-core"])
            ]
            
            for node_type, expected_packages in test_cases:
                packages = analyzer.get_node_packages(node_type)
                
                # Check if at least one expected package is present
                found_expected = any(
                    any(expected in pkg for pkg in packages)
                    for expected in expected_packages
                )
                
                if not found_expected:
                    self.log_result("Package Generation Logic", "FAIL", 
                                  f"No expected packages found for {node_type}")
                    return False
            
            self.log_result("Package Generation Logic", "PASS", 
                          "All node types generated appropriate packages")
            return True
            
        except Exception as e:
            self.log_result("Package Generation Logic", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_credential_detection_logic(self):
        """Test credential detection logic"""
        self.log_result("Credential Detection", "INFO", "Testing credential detection...")
        
        try:
            from app.core.dynamic_node_analyzer import CredentialDetector
            
            detector = CredentialDetector()
            
            # Test credential detection
            test_data = {
                "api_key": "sk-test123",
                "model_name": "gpt-4o-mini",
                "temperature": 0.7,
                "database_url": "postgresql://user:pass@host/db"
            }
            
            credentials = detector.detect_credentials(test_data, "TestNode")
            
            # Should detect api_key and database_url as credentials
            cred_names = [cred.name for cred in credentials]
            
            expected_credentials = ["TESTNODE_API_KEY", "TESTNODE_DATABASE_URL"]
            found_credentials = [name for name in expected_credentials if name in cred_names]
            
            if len(found_credentials) < 2:
                self.log_result("Credential Detection", "FAIL", 
                              f"Only detected {len(found_credentials)} credentials: {found_credentials}")
                return False
            
            self.log_result("Credential Detection", "PASS", 
                          f"Detected {len(credentials)} credentials correctly")
            return True
            
        except Exception as e:
            self.log_result("Credential Detection", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_fallback_system_behavior(self):
        """Test fallback system"""
        self.log_result("Fallback System", "INFO", "Testing fallback behavior...")
        
        try:
            from app.routes.export import _fallback_static_analysis
            
            # Test fallback with minimal node data
            test_nodes = [
                {
                    "id": "unknown_1", 
                    "type": "UnknownNodeType",
                    "data": {}
                }
            ]
            
            # This should trigger fallback
            dependencies = _fallback_static_analysis(test_nodes)
            
            # Validate fallback response
            if not dependencies:
                self.log_result("Fallback System", "FAIL", "Fallback returned None")
                return False
            
            # Should have basic system dependencies
            if not dependencies.python_packages:
                self.log_result("Fallback System", "FAIL", "No packages in fallback")
                return False
            
            # Should have basic environment variables
            if not dependencies.required_env_vars:
                self.log_result("Fallback System", "FAIL", "No env vars in fallback")
                return False
            
            self.log_result("Fallback System", "PASS", 
                          "Fallback system working correctly")
            return True
            
        except Exception as e:
            self.log_result("Fallback System", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_end_to_end_workflow(self):
        """End-to-end workflow test"""
        self.log_result("End-to-End Workflow", "INFO", "Testing complete workflow...")
        
        try:
            # Import required modules
            from app.core.node_registry import NodeRegistry
            from app.core.dynamic_node_analyzer import DynamicNodeAnalyzer
            from app.routes.export import analyze_workflow_dependencies
            
            # Full workflow test
            test_workflow = [
                {
                    "id": "openai_1",
                    "type": "OpenAIChat", 
                    "data": {
                        "model_name": "gpt-4o-mini",
                        "api_key": "sk-test123",
                        "temperature": 0.7
                    }
                },
                {
                    "id": "memory_1",
                    "type": "BufferMemory",
                    "data": {
                        "memory_key": "chat_history"
                    }
                }
            ]
            
            # Step 1: Node registry
            registry = NodeRegistry()
            registry.discover_nodes()
            
            # Step 2: Dynamic analysis
            analyzer = DynamicNodeAnalyzer(registry)
            analysis_result = analyzer.analyze_workflow(test_workflow)
            
            # Step 3: Export route processing
            dependencies = analyze_workflow_dependencies(test_workflow)
            
            # Validate complete flow
            if not analysis_result or not dependencies:
                self.log_result("End-to-End Workflow", "FAIL", "One component failed")
                return False
            
            # Check consistency between analysis and dependencies
            analyzer_nodes = len(analysis_result.node_types)
            dependencies_nodes = len(dependencies.nodes)
            
            if analyzer_nodes != dependencies_nodes:
                self.log_result("End-to-End Workflow", "FAIL", 
                              f"Node count mismatch: {analyzer_nodes} vs {dependencies_nodes}")
                return False
            
            self.log_result("End-to-End Workflow", "PASS", 
                          "Complete workflow executed successfully")
            return True
            
        except Exception as e:
            self.log_result("End-to-End Workflow", "FAIL", f"Exception: {str(e)}")
            return False
    
    def cleanup(self):
        """Cleanup temporary directories"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def run_all_tests(self):
        """Run all integration tests"""
        print(" DOCKER EXPORT INTEGRATION TESTS")
        print("=" * 40)
        
        tests = [
            self.test_node_registry_discovery,
            self.test_dynamic_analyzer_direct,
            self.test_credential_detection_logic,
            self.test_package_generation_logic,
            self.test_export_routes_integration,
            self.test_fallback_system_behavior,
            self.test_end_to_end_workflow
        ]
        
        for test in tests:
            try:
                test()
                time.sleep(0.2)  # Brief pause
            except Exception as e:
                self.log_result(test.__name__, "FAIL", f"Unexpected error: {str(e)}")
        
        # Summary
        total = len(self.test_results)
        passed = len([r for r in self.test_results if r["status"] == "PASS"])
        failed = len([r for r in self.test_results if r["status"] == "FAIL"])
        
        print(f"\n TEST SUMMARY")
        print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print(f"\n FAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"   • {result['test']}: {result['message']}")
        
        return passed, failed, total

def main():
    """Main test runner"""
    tester = IntegrationTester()
    
    try:
        passed, failed, total = tester.run_all_tests()
        
        if failed == 0:
            print(f"\n ALL TESTS PASSED! System ready for deployment.")
            return 0
        else:
            print(f"\n {failed} test(s) failed. Review issues before deployment.")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test suite crashed: {str(e)}")
        return 2
    finally:
        tester.cleanup()

if __name__ == "__main__":
    exit(main())