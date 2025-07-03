import logging
from typing import Dict, Any
from app.services.RAG_service import query_context_from_memory
from app.db.RAG_db import log_session_interaction, get_recent_memory

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RAGDiagnostic:
    """
    Diagnostic tool to debug RAG service issues
    """
    
    @staticmethod
    def test_rag_service(session_id: str = "test_session") -> Dict[str, Any]:
        """
        Comprehensive test of RAG service functionality
        """
        results = {
            "tests": [],
            "overall_status": "unknown",
            "recommendations": []
        }
        
        # Test 1: Import Test
        try:
            from app.db.RAG_db import log_session_interaction, get_recent_memory
            results["tests"].append({
                "name": "Import Test",
                "status": "PASS",
                "message": "Successfully imported RAG database functions"
            })
        except Exception as e:
            results["tests"].append({
                "name": "Import Test",
                "status": "FAIL",
                "error": str(e),
                "message": "Failed to import RAG database functions"
            })
            results["recommendations"].append("Check if RAG_db module exists and is properly configured")
        
        # Test 2: Database Connection Test
        try:
            # Try to log a test interaction
            test_query = "test query for diagnostics"
            test_response = "test response for diagnostics"
            
            log_session_interaction(test_query, test_response, session_id)
            
            results["tests"].append({
                "name": "Database Connection Test",
                "status": "PASS",
                "message": "Successfully logged test interaction to database"
            })
        except Exception as e:
            results["tests"].append({
                "name": "Database Connection Test",
                "status": "FAIL",
                "error": str(e),
                "message": "Failed to log interaction to database"
            })
            results["recommendations"].append("Check ChromaDB connection and database initialization")
        
        # Test 3: Memory Retrieval Test
        try:
            # Try to retrieve memory
            memory_docs = get_recent_memory(session_id, 5)
            
            if memory_docs:
                results["tests"].append({
                    "name": "Memory Retrieval Test",
                    "status": "PASS",
                    "message": f"Successfully retrieved {len(memory_docs)} memory documents",
                    "data": str(memory_docs)[:200] + "..." if len(str(memory_docs)) > 200 else str(memory_docs)
                })
            else:
                results["tests"].append({
                    "name": "Memory Retrieval Test",
                    "status": "WARN",
                    "message": "Memory retrieval successful but no documents found (this is normal for new sessions)"
                })
        except Exception as e:
            results["tests"].append({
                "name": "Memory Retrieval Test",
                "status": "FAIL",
                "error": str(e),
                "message": "Failed to retrieve memory from database"
            })
            results["recommendations"].append("Check get_recent_memory function implementation")
        
        # Test 4: RAG Service Function Test
        try:
            context = query_context_from_memory("I want to buy a laptop", session_id)

            docs = get_recent_memory(session_id)
            print("Retrieved docs for context:", docs)


            
            if context and context.strip():
                results["tests"].append({
                    "name": "RAG Service Function Test",
                    "status": "PASS",
                    "message": f"RAG service returned context: {len(context)} characters",
                    "data": context[:200] + "..." if len(context) > 200 else context
                })
            else:
                results["tests"].append({
                    "name": "RAG Service Function Test",
                    "status": "WARN",
                    "message": "RAG service function works but returned empty context",
                    "note": "This is normal if no previous conversations exist for this session"
                })
        except Exception as e:
            results["tests"].append({
                "name": "RAG Service Function Test",
                "status": "FAIL",
                "error": str(e),
                "message": "RAG service function failed"
            })
            results["recommendations"].append("Check query_context_from_memory function implementation")
        
        # Test 5: Full Workflow Test
        try:
            # Log a conversation
            test_user_query = "I want to buy a laptop"
            test_assistant_response = "I can help you find laptops on Amazon and Walmart"
            
            log_session_interaction(test_user_query, test_assistant_response, session_id)
            
            # Try to retrieve it
            context = query_context_from_memory("laptop", session_id)
            
            if context and "laptop" in context.lower():
                results["tests"].append({
                    "name": "Full Workflow Test",
                    "status": "PASS",
                    "message": "Successfully logged and retrieved conversation context",
                    "data": context[:200] + "..." if len(context) > 200 else context
                })
            else:
                results["tests"].append({
                    "name": "Full Workflow Test",
                    "status": "PARTIAL",
                    "message": "Logged conversation but context retrieval may not be working properly",
                    "context_returned": str(context)
                })
        except Exception as e:
            results["tests"].append({
                "name": "Full Workflow Test",
                "status": "FAIL",
                "error": str(e),
                "message": "Full workflow test failed"
            })
        
        # Determine overall status
        failed_tests = [t for t in results["tests"] if t["status"] == "FAIL"]
        warn_tests = [t for t in results["tests"] if t["status"] == "WARN"]
        
        if failed_tests:
            results["overall_status"] = "CRITICAL"
            results["recommendations"].append("Critical issues found - RAG service not functioning properly")
        elif warn_tests:
            results["overall_status"] = "WARNING"
            results["recommendations"].append("RAG service working but may have configuration issues")
        else:
            results["overall_status"] = "HEALTHY"
            results["recommendations"].append("RAG service appears to be functioning correctly")
        
        return results
    
    @staticmethod
    def print_diagnostic_report(results: Dict[str, Any]):
        """
        Print a formatted diagnostic report
        """
        print("\n" + "="*60)
        print("RAG SERVICE DIAGNOSTIC REPORT")
        print("="*60)
        
        print(f"\nOVERALL STATUS: {results['overall_status']}")
        
        print("\nTEST RESULTS:")
        print("-" * 40)
        
        for test in results["tests"]:
            status_symbol = {
                "PASS": "✅",
                "FAIL": "❌", 
                "WARN": "⚠️",
                "PARTIAL": "🔶"
            }.get(test["status"], "❓")
            
            print(f"{status_symbol} {test['name']}: {test['status']}")
            print(f"   {test['message']}")
            
            if "error" in test:
                print(f"   Error: {test['error']}")
            
            if "data" in test:
                print(f"   Data: {test['data']}")
            
            print()
        
        if results["recommendations"]:
            print("\nRECOMMENDations:")
            print("-" * 40)
            for i, rec in enumerate(results["recommendations"], 1):
                print(f"{i}. {rec}")
        
        print("\n" + "="*60)

# Usage example:
def run_rag_diagnostic(session_id: str = "diagnostic_test"):
    """
    Run the diagnostic and print results
    """
    diagnostic = RAGDiagnostic()
    results = diagnostic.test_rag_service(session_id)
    diagnostic.print_diagnostic_report(results)
    return results

if __name__ == "__main__":
    # Run diagnostic
    run_rag_diagnostic()
