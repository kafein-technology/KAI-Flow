#!/usr/bin/env python3
"""
Dynamic Node Analyzer Test Script
=================================

Bu script, dynamic node analyzer'ın tüm mevcut node'ları doğru şekilde
analiz edip edemediğini test eder ve docker export functionality'sini
validate eder.
"""

import os
import sys
import json
import traceback
from pathlib import Path

# Add the backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from app.core.dynamic_node_analyzer import DynamicNodeAnalyzer
    from app.core.node_registry import node_registry
    from app.routes.export import analyze_workflow_dependencies, filter_requirements_for_nodes
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

def test_node_discovery():
    """Test node registry discovery functionality."""
    print("🔍 Testing Node Discovery...")
    
    try:
        # Discover all nodes
        node_registry.discover_nodes()
        all_nodes = node_registry.get_all_nodes()
        
        print(f"Discovered {len(all_nodes)} nodes")
        
        # Group by category
        categories = {}
        for node in all_nodes:
            category = node.category
            if category not in categories:
                categories[category] = []
            categories[category].append(node.name)
        
        print("Node Categories:")
        for category, nodes in categories.items():
            print(f"   {category}: {len(nodes)} nodes")
            for node_name in nodes[:3]:  # Show first 3
                print(f"      • {node_name}")
            if len(nodes) > 3:
                print(f"      ... and {len(nodes) - 3} more")
        
        return True, len(all_nodes)
    except Exception as e:
        print(f"Node discovery failed: {e}")
        traceback.print_exc()
        return False, 0

def test_dynamic_analyzer():
    """Test dynamic analyzer with sample workflow."""
    print("\n🤖 Testing Dynamic Node Analyzer...")
    
    try:
        analyzer = DynamicNodeAnalyzer(node_registry)
        
        # Test workflow with different node types
        test_workflow = {
            "nodes": [
                {
                    "id": "openai_1",
                    "type": "OpenAIChat",
                    "data": {
                        "model_name": "gpt-4o",
                        "temperature": 0.7,
                        "api_key": "sk-test123...",
                        "max_tokens": 2000
                    }
                },
                {
                    "id": "tavily_1", 
                    "type": "TavilySearch",
                    "data": {
                        "tavily_api_key": "tvly-test123...",
                        "max_results": 5,
                        "search_depth": "advanced"
                    }
                },
                {
                    "id": "memory_1",
                    "type": "BufferMemory",
                    "data": {
                        "memory_key": "chat_history",
                        "return_messages": True
                    }
                },
                {
                    "id": "cohere_1",
                    "type": "CohereRerankerProvider",
                    "data": {
                        "cohere_api_key": "cohere-test123...",
                        "model": "rerank-english-v3.0",
                        "top_n": 5
                    }
                },
                {
                    "id": "vector_1",
                    "type": "VectorStoreOrchestrator",
                    "data": {
                        "connection_string": "postgresql://user:pass@localhost:5432/db",
                        "collection_name": "test_collection",
                        "embedding_dimension": 1536
                    }
                }
            ],
            "edges": []
        }
        
        # Analyze workflow
        result = analyzer.analyze_workflow(test_workflow)
        
        print(f"Analysis completed!")
        print(f"Node types: {result.node_types}")
        print(f"Required env vars: {len(result.required_env_vars)}")
        print(f"Optional env vars: {len(result.optional_env_vars)}")
        print(f"Package dependencies: {len(result.package_dependencies)}")
        
        # Show detected credentials
        print("\nDetected Credentials:")
        for env_var in result.required_env_vars:
            security_level = getattr(env_var, 'security_level', 'unknown')
            print(f"   • {env_var.name} ({security_level}) - {env_var.description[:50]}...")
        
        # Show package dependencies
        print(f"\nPackage Dependencies ({len(result.package_dependencies)}):")
        for pkg in result.package_dependencies[:10]:  # Show first 10
            print(f"   • {pkg}")
        if len(result.package_dependencies) > 10:
            print(f"   ... and {len(result.package_dependencies) - 10} more")
        
        return True, result
    except Exception as e:
        print(f"Dynamic analyzer failed: {e}")
        traceback.print_exc()
        return False, None

def test_export_integration():
    """Test export system integration."""
    print("\n Testing Export System Integration...")
    
    try:
        # Test workflow for export
        test_workflow = {
            "nodes": [
                {
                    "id": "openai_1",
                    "type": "OpenAIChat", 
                    "data": {
                        "model_name": "gpt-4o-mini",
                        "temperature": 0.1,
                        "api_key": "sk-test123...",
                        "max_tokens": 1000
                    }
                },
                {
                    "id": "tavily_1",
                    "type": "TavilySearch",
                    "data": {
                        "tavily_api_key": "tvly-test123...",
                        "max_results": 3
                    }
                }
            ],
            "edges": []
        }
        
        # Test analyze_workflow_dependencies (now uses dynamic analyzer)
        dependencies = analyze_workflow_dependencies(test_workflow)
        
        print("Export dependency analysis completed!")
        print(f"Nodes: {dependencies.nodes}")
        print(f"Required vars: {len(dependencies.required_env_vars)}")
        print(f"Packages: {len(dependencies.python_packages)}")
        
        # Test filter_requirements_for_nodes (now uses dynamic analyzer)
        requirements = filter_requirements_for_nodes(dependencies.nodes)
        
        print("Requirements filtering completed!")
        req_lines = requirements.split('\n')
        print(f"Generated {len(req_lines)} package entries")
        print("Key packages:")
        for line in req_lines[:5]:
            if line.strip():
                print(f"      • {line}")
        
        return True, dependencies
    except Exception as e:
        print(f"Export integration failed: {e}")
        traceback.print_exc()
        return False, None

def test_credential_detection():
    """Test credential detection capabilities."""
    print("\n Testing Credential Detection...")
    
    try:
        analyzer = DynamicNodeAnalyzer(node_registry)
        
        # Test workflow with various credentials
        test_workflow = {
            "nodes": [
                {
                    "id": "node1",
                    "type": "OpenAIChat",
                    "data": {
                        "api_key": "sk-actual-key-here",
                        "model": "gpt-4o"
                    }
                },
                {
                    "id": "node2", 
                    "type": "TavilySearch",
                    "data": {
                        "tavily_api_key": "tvly-actual-key-here",
                        "max_results": 5
                    }
                },
                {
                    "id": "node3",
                    "type": "VectorStoreOrchestrator",
                    "data": {
                        "connection_string": "postgresql://user:password@localhost/db",
                        "collection_name": "test"
                    }
                }
            ]
        }
        
        result = analyzer.analyze_workflow(test_workflow)
        
        # Check credential detection
        credential_vars = [var for var in result.required_env_vars 
                         if var.security_level in ['critical', 'high']]
        
        print(f"Detected {len(credential_vars)} credentials")
        for var in credential_vars:
            print(f"   🔑 {var.name} ({var.security_level}) from {var.source_node}")
        
        return True, len(credential_vars)
    except Exception as e:
        print(f"Credential detection failed: {e}")
        traceback.print_exc()
        return False, 0

def test_package_analysis():
    """Test package dependency analysis."""
    print("\nTesting Package Analysis...")
    
    try:
        analyzer = DynamicNodeAnalyzer(node_registry)
        
        # Test with diverse node types
        test_workflow = {
            "nodes": [
                {"id": "openai", "type": "OpenAIChat", "data": {}},
                {"id": "tavily", "type": "TavilySearch", "data": {}},
                {"id": "cohere", "type": "CohereRerankerProvider", "data": {}},
                {"id": "vector", "type": "VectorStoreOrchestrator", "data": {}},
                {"id": "memory", "type": "BufferMemory", "data": {}}
            ]
        }
        
        result = analyzer.analyze_workflow(test_workflow)
        packages = result.package_dependencies
        
        print(f"Analyzed {len(packages)} packages")
        
        # Check for expected packages
        expected_packages = [
            ("langchain", "Core LangChain"),
            ("openai", "OpenAI integration"), 
            ("langchain-openai", "LangChain OpenAI"),
            ("langchain-tavily", "Tavily search"),
            ("langchain-cohere", "Cohere reranker"),
            ("langchain-postgres", "PostgreSQL vector store"),
            ("fastapi", "API framework")
        ]
        
        found_packages = 0
        for pkg_pattern, description in expected_packages:
            if any(pkg_pattern in pkg for pkg in packages):
                print(f"{description}: Found")
                found_packages += 1
            else:
                print(f"{description}: Missing")
        
        coverage = (found_packages / len(expected_packages)) * 100
        print(f"Package coverage: {coverage:.1f}%")
        
        return True, coverage
    except Exception as e:
        print(f"Package analysis failed: {e}")
        traceback.print_exc()
        return False, 0

def main():
    """Run all tests."""
    print("KAI-Fusion Dynamic Node Analyzer Test Suite")
    print("=" * 50)
    
    results = {}
    
    # Test 1: Node Discovery
    success, node_count = test_node_discovery()
    results['node_discovery'] = (success, node_count)
    
    # Test 2: Dynamic Analyzer
    success, analysis_result = test_dynamic_analyzer()
    results['dynamic_analyzer'] = (success, analysis_result)
    
    # Test 3: Export Integration
    success, dependencies = test_export_integration()
    results['export_integration'] = (success, dependencies)
    
    # Test 4: Credential Detection
    success, credential_count = test_credential_detection()
    results['credential_detection'] = (success, credential_count)
    
    # Test 5: Package Analysis
    success, coverage = test_package_analysis()
    results['package_analysis'] = (success, coverage)
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    total_tests = len(results)
    passed_tests = sum(1 for success, _ in results.values() if success)
    
    for test_name, (success, metric) in results.items():
        status = "PASS" if success else " FAIL"
        print(f"{status} {test_name.replace('_', ' ').title()}")
        
        if success and metric is not None:
            if test_name == 'node_discovery':
                print(f"Discovered {metric} nodes")
            elif test_name == 'credential_detection':
                print(f"Detected {metric} credentials")
            elif test_name == 'package_analysis':
                print(f"Package coverage: {metric:.1f}%")
    
    print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("All tests passed! Dynamic analyzer is working correctly.")
        return True
    else:
        print("Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)