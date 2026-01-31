"""
Test Script for Nepali RAG Service
Run this to verify everything is working correctly
"""

import sys
import os
from pathlib import Path

# Add your project to path
# sys.path.insert(0, '/path/to/your/project')
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

# import django
# django.setup()

from chat.rag_service import NepaliRAGService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_initialization():
    """Test 1: RAG service initializes correctly"""
    print("\n" + "="*60)
    print("TEST 1: Initialization")
    print("="*60)
    
    try:
        rag = NepaliRAGService()
        print("✅ RAG service initialized successfully")
        
        kb_count = rag.permanent_kb.count()
        print(f"✅ Permanent KB contains {kb_count} articles")
        
        if kb_count == 0:
            print("⚠️  Warning: Permanent KB is empty. Run loadpermanentknowledge command.")
        
        return rag
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return None


def test_parsing(rag, test_pdf_path=None):
    """Test 2: PDF parsing works"""
    print("\n" + "="*60)
    print("TEST 2: PDF Parsing")
    print("="*60)
    
    if not test_pdf_path:
        print("⚠️  No test PDF provided, skipping parsing test")
        print("   To test: test_parsing(rag, 'path/to/test.pdf')")
        return
    
    try:
        text, metadata = rag.parse_pdf_hybrid(test_pdf_path)
        
        print(f"✅ PDF parsed successfully")
        print(f"   Method: {metadata['parsing_method']}")
        print(f"   Pages: {metadata['num_pages']}")
        print(f"   Characters: {metadata['total_chars']}")
        
        # Check quality
        is_good = rag._is_text_quality_good(text)
        print(f"   Quality check: {'✅ PASSED' if is_good else '❌ FAILED'}")
        
        # Show preview
        print(f"\n   Text preview:")
        print(f"   {text[:300]}...")
        
        return text
        
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        return None


def test_chunking(rag, text=None):
    """Test 3: Article-based chunking"""
    print("\n" + "="*60)
    print("TEST 3: Chunking")
    print("="*60)
    
    if not text:
        print("⚠️  No text provided, skipping chunking test")
        return
    
    try:
        chunks = rag.chunk_by_articles(text)
        
        print(f"✅ Chunking completed")
        print(f"   Total chunks: {len(chunks)}")
        
        if not chunks:
            print("❌ No chunks created!")
            return
        
        # Statistics
        token_counts = [c['token_count'] for c in chunks]
        print(f"   Token stats:")
        print(f"      Min: {min(token_counts)}")
        print(f"      Max: {max(token_counts)}")
        print(f"      Avg: {sum(token_counts)/len(token_counts):.0f}")
        
        # Show first 3 chunks
        print(f"\n   First 3 articles:")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n   Chunk {i+1}:")
            print(f"      Article: {chunk['metadata']['article_title']}")
            print(f"      Type: {chunk['metadata']['chunk_type']}")
            print(f"      Tokens: {chunk['token_count']}")
            print(f"      Preview: {chunk['text'][:150]}...")
        
        return chunks
        
    except Exception as e:
        print(f"❌ Chunking failed: {e}")
        return None


def test_embeddings(rag, chunks=None):
    """Test 4: Embedding generation"""
    print("\n" + "="*60)
    print("TEST 4: Embeddings")
    print("="*60)
    
    if not chunks:
        print("⚠️  No chunks provided, skipping embedding test")
        return
    
    try:
        # Test with first 3 chunks
        test_chunks = chunks[:3]
        embeddings = rag.generate_embeddings(test_chunks)
        
        print(f"✅ Embeddings generated")
        print(f"   Chunks: {len(test_chunks)}")
        print(f"   Embedding dimension: {len(embeddings[0])}")
        print(f"   Expected dimension: 1024 (multilingual-e5-large)")
        
        if len(embeddings[0]) == 1024:
            print("   ✅ Correct embedding dimension")
        else:
            print("   ⚠️  Unexpected embedding dimension")
        
        return embeddings
        
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        return None


def test_permanent_kb_retrieval(rag):
    """Test 5: Retrieval from permanent KB"""
    print("\n" + "="*60)
    print("TEST 5: Permanent KB Retrieval")
    print("="*60)
    
    if rag.permanent_kb.count() == 0:
        print("❌ Permanent KB is empty. Run loadpermanentknowledge first.")
        return
    
    try:
        # Test queries
        test_queries = [
            "नागरिकताको लागि के चाहिन्छ?",
            "सम्पत्ति कसरी बाँडफाँड गर्ने?",
            "अदालतमा मुद्दा कसरी हाल्ने?"
        ]
        
        for query in test_queries:
            print(f"\n   Query: {query}")
            
            chunks = rag.retrieve_context(
                query=query,
                collection_name=None,  # No user collection
                top_k=3,
                use_permanent_kb=True
            )
            
            print(f"   Retrieved {len(chunks)} chunks:")
            
            for i, chunk in enumerate(chunks):
                print(f"\n   Result {i+1}:")
                print(f"      Article: {chunk['metadata'].get('article_title', 'Unknown')}")
                print(f"      Source: {chunk['source']}")
                print(f"      Relevance: {chunk['relevance_score']:.2%}")
                print(f"      Preview: {chunk['text'][:100]}...")
        
        print("\n✅ Permanent KB retrieval working!")
        
    except Exception as e:
        print(f"❌ Retrieval failed: {e}")


def test_rag_prompt(rag):
    """Test 6: RAG prompt formatting"""
    print("\n" + "="*60)
    print("TEST 6: RAG Prompt Formatting")
    print("="*60)
    
    if rag.permanent_kb.count() == 0:
        print("⚠️  Permanent KB is empty, skipping")
        return
    
    try:
        query = "नागरिकताको लागि के चाहिन्छ?"
        
        chunks = rag.retrieve_context(
            query=query,
            collection_name=None,
            top_k=3,
            use_permanent_kb=True
        )
        
        if not chunks:
            print("❌ No chunks retrieved")
            return
        
        prompt = rag.format_rag_prompt(query, chunks)
        
        print("✅ Prompt formatted successfully")
        print(f"\n   Prompt preview:")
        print(f"   {prompt[:500]}...")
        print(f"\n   Prompt length: {len(prompt)} characters")
        
    except Exception as e:
        print(f"❌ Prompt formatting failed: {e}")


def run_all_tests(test_pdf_path=None):
    """Run all tests"""
    print("\n" + "🧪"*30)
    print("NEPALI RAG SERVICE - COMPREHENSIVE TEST SUITE")
    print("🧪"*30)
    
    # Test 1: Initialize
    rag = test_initialization()
    if not rag:
        print("\n❌ Cannot continue - initialization failed")
        return
    
    # Test 2: Parsing (if PDF provided)
    text = None
    if test_pdf_path:
        text = test_parsing(rag, test_pdf_path)
    
    # Test 3: Chunking (if text available)
    chunks = None
    if text:
        chunks = test_chunking(rag, text)
    
    # Test 4: Embeddings (if chunks available)
    if chunks:
        test_embeddings(rag, chunks)
    
    # Test 5: Permanent KB
    test_permanent_kb_retrieval(rag)
    
    # Test 6: Prompt formatting
    test_rag_prompt(rag)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print("✅ All core tests completed!")
    print("\nNext steps:")
    print("1. If Permanent KB is empty, run: python manage.py loadpermanentknowledge")
    print("2. Test with actual PDF: run_all_tests('path/to/test.pdf')")
    print("3. Test in Django app by uploading a document")
    print("4. Test user chat without documents (should use permanent KB)")


if __name__ == "__main__":
    # Run tests
    # Option 1: Without PDF (tests KB only)
    # run_all_tests()
    
    # Option 2: With test PDF
    # run_all_tests(test_pdf_path="path/to/your/test.pdf")