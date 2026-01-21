"""
Chatbot helper module with improved error handling and fallback mechanisms.
Uses Pinecone for vector storage and OpenAI for embeddings and chat.
"""
import logging
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache
from .models import Book, Course, Webinar

logger = logging.getLogger(__name__)

# Optional imports - handle gracefully if not installed
try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    logger.warning("Pinecone package not installed - vector search features will be disabled")
    Pinecone = None
    ServerlessSpec = None
    PINECONE_AVAILABLE = False

try:
    from openai import OpenAI, OpenAIError
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("OpenAI package not installed - AI chat features will be disabled")
    OpenAI = None
    OpenAIError = Exception
    OPENAI_AVAILABLE = False

# Initialize clients with error handling
openai_client = None
pc = None
INDEX_NAME = None

if OPENAI_AVAILABLE and PINECONE_AVAILABLE:
    try:
        openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        INDEX_NAME = settings.PINECONE_INDEX_NAME
        logger.info("AI clients initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AI clients: {e}")
        openai_client = None
        pc = None
        INDEX_NAME = None
else:
    logger.warning("AI services unavailable - missing required packages (pinecone or openai)")


def is_ai_available() -> bool:
    """Check if AI services are available"""
    return openai_client is not None and pc is not None


def get_or_create_index():
    """
    Get existing Pinecone index or create a new one.

    Returns:
        Pinecone Index object or None if unavailable

    Raises:
        Exception: If index creation/retrieval fails
    """
    if not pc:
        logger.error("Pinecone client not initialized")
        return None

    try:
        # Check if index exists
        existing_indexes = pc.list_indexes()
        index_names = [idx.name if hasattr(idx, 'name') else idx['name'] for idx in existing_indexes]

        if INDEX_NAME not in index_names:
            # Create new index
            logger.info(f"Creating new Pinecone index: {INDEX_NAME}")
            pc.create_index(
                name=INDEX_NAME,
                dimension=1536,  # OpenAI text-embedding-3-small dimension
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region='us-east-1'
                )
            )
            logger.info(f"Created new Pinecone index: {INDEX_NAME}")

        return pc.Index(INDEX_NAME)
    except Exception as e:
        logger.error(f"Error creating/getting Pinecone index: {e}")
        return None


def generate_embedding(text: str, use_cache: bool = True) -> Optional[List[float]]:
    """
    Generate OpenAI embedding for given text with caching.

    Args:
        text: Text to generate embedding for
        use_cache: Whether to use cached embeddings

    Returns:
        List of embedding values or None if failed
    """
    if not openai_client:
        logger.error("OpenAI client not initialized")
        return None

    # Check cache first
    if use_cache:
        cache_key = f'embedding_{hash(text)}'
        cached = cache.get(cache_key)
        if cached:
            return cached

    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]  # Limit text length
        )
        embedding = response.data[0].embedding

        # Cache the embedding for 1 hour
        if use_cache:
            cache_key = f'embedding_{hash(text)}'
            cache.set(cache_key, embedding, 3600)

        return embedding
    except OpenAIError as e:
        logger.error(f"OpenAI API error generating embedding: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating embedding: {e}")
        return None


def index_single_product(product, product_type: str) -> bool:
    """
    Index a single product into Pinecone.

    Args:
        product: Product instance (Book, Course, or Webinar)
        product_type: String ('book', 'course', or 'webinar')

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_ai_available():
        logger.warning("AI services unavailable, skipping product indexing")
        return False

    try:
        index = get_or_create_index()
        if not index:
            return False

        # Create document text
        doc_text = (
            f"{product_type.title()}: {product.title}. "
            f"Description: {product.description}. "
            f"Category: {product.category.name if product.category else 'Uncategorized'}. "
            f"Price: ${product.price}. "
            f"Seller: {product.seller.full_name}"
        )

        # Generate embedding
        embedding = generate_embedding(doc_text)
        if not embedding:
            return False

        # Create unique ID
        vector_id = f"{product_type}_{product.id}"

        # Prepare metadata
        metadata = {
            'type': product_type,
            'id': str(product.id),
            'title': product.title[:500],
            'description': product.description[:500],
            'price': str(product.price),
            'category': product.category.name if product.category else 'Uncategorized',
            'seller': product.seller.full_name,
            'seller_id': str(product.seller.id)
        }

        # Upsert to Pinecone
        index.upsert(vectors=[(vector_id, embedding, metadata)])
        logger.info(f"Indexed {product_type}: {product.title}")
        return True
    except Exception as e:
        logger.error(f"Error indexing product {product_type} {product.id}: {e}")
        return False


def delete_product_from_index(product_id: int, product_type: str) -> bool:
    """
    Delete a product from Pinecone index.

    Args:
        product_id: The product ID
        product_type: String ('book', 'course', or 'webinar')

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_ai_available():
        return False

    try:
        index = get_or_create_index()
        if not index:
            return False

        vector_id = f"{product_type}_{product_id}"
        index.delete(ids=[vector_id])
        logger.info(f"Deleted {product_type} {product_id} from index")
        return True
    except Exception as e:
        logger.error(f"Error deleting product from index: {e}")
        return False


def index_all_products() -> int:
    """
    Index all active products into Pinecone.

    Returns:
        int: Number of successfully indexed products
    """
    if not is_ai_available():
        logger.warning("AI services unavailable, skipping batch indexing")
        return 0

    try:
        index = get_or_create_index()
        if not index:
            return 0

        # Get all active, non-deleted products
        books = Book.objects.filter(is_active=True, is_deleted=False).select_related('category', 'seller')
        courses = Course.objects.filter(is_active=True, is_deleted=False).select_related('category', 'seller')
        webinars = Webinar.objects.filter(is_active=True, is_deleted=False).select_related('category', 'seller')

        vectors = []
        successful_count = 0

        # Process books
        for book in books:
            try:
                doc_text = f"Book: {book.title}. Description: {book.description}. Category: {book.category.name if book.category else 'Uncategorized'}. Price: ${book.price}"
                embedding = generate_embedding(doc_text)

                if embedding:
                    metadata = {
                        'type': 'book',
                        'id': str(book.id),
                        'title': book.title[:500],
                        'description': book.description[:500],
                        'price': str(book.price),
                        'category': book.category.name if book.category else 'Uncategorized',
                        'seller': book.seller.full_name,
                        'seller_id': str(book.seller.id)
                    }
                    vectors.append((f"book_{book.id}", embedding, metadata))
                    successful_count += 1
            except Exception as e:
                logger.error(f"Error processing book {book.id}: {e}")

        # Process courses
        for course in courses:
            try:
                doc_text = f"Course: {course.title}. Description: {course.description}. Category: {course.category.name if course.category else 'Uncategorized'}. Price: ${course.price}"
                embedding = generate_embedding(doc_text)

                if embedding:
                    metadata = {
                        'type': 'course',
                        'id': str(course.id),
                        'title': course.title[:500],
                        'description': course.description[:500],
                        'price': str(course.price),
                        'category': course.category.name if course.category else 'Uncategorized',
                        'seller': course.seller.full_name,
                        'seller_id': str(course.seller.id)
                    }
                    vectors.append((f"course_{course.id}", embedding, metadata))
                    successful_count += 1
            except Exception as e:
                logger.error(f"Error processing course {course.id}: {e}")

        # Process webinars
        for webinar in webinars:
            try:
                doc_text = f"Webinar: {webinar.title}. Description: {webinar.description}. Category: {webinar.category.name if webinar.category else 'Uncategorized'}. Price: ${webinar.price}"
                embedding = generate_embedding(doc_text)

                if embedding:
                    metadata = {
                        'type': 'webinar',
                        'id': str(webinar.id),
                        'title': webinar.title[:500],
                        'description': webinar.description[:500],
                        'price': str(webinar.price),
                        'category': webinar.category.name if webinar.category else 'Uncategorized',
                        'seller': webinar.seller.full_name,
                        'seller_id': str(webinar.seller.id)
                    }
                    vectors.append((f"webinar_{webinar.id}", embedding, metadata))
                    successful_count += 1
            except Exception as e:
                logger.error(f"Error processing webinar {webinar.id}: {e}")

        # Batch upsert to Pinecone (max 100 at a time)
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                index.upsert(vectors=batch)
            except Exception as e:
                logger.error(f"Error upserting batch {i//batch_size}: {e}")

        logger.info(f"Successfully indexed {successful_count} products to Pinecone")
        return successful_count
    except Exception as e:
        logger.error(f"Error indexing all products: {e}")
        return 0


def search_products(query: str, n_results: int = 5) -> List[Dict]:
    """
    Search for relevant products based on user query.

    Args:
        query: User's search query
        n_results: Number of results to return

    Returns:
        List of product metadata dictionaries, empty list if failed
    """
    if not is_ai_available():
        logger.warning("AI services unavailable, returning empty results")
        return []

    # Check cache first
    cache_key = f'search_{hash(query)}_{n_results}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        index = get_or_create_index()
        if not index:
            return []

        # Generate query embedding
        query_embedding = generate_embedding(query)
        if not query_embedding:
            return []

        # Search in Pinecone
        results = index.query(
            vector=query_embedding,
            top_k=n_results,
            include_metadata=True
        )

        # Extract metadata from results
        products = []
        for match in results.get('matches', []):
            if match.get('metadata'):
                products.append(match['metadata'])

        # Cache results for 5 minutes
        cache.set(cache_key, products, 300)

        return products
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return []


def generate_chat_response(query: str, context_products: List[Dict], conversation_history: Optional[List[Dict]] = None):
    """
    Generate AI response using OpenAI Chat API with streaming and conversation memory.

    Args:
        query: User's current question
        context_products: List of relevant product metadata
        conversation_history: Optional list of previous messages in format:
                            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    Returns:
        Stream object for response or None if failed
    """
    if not openai_client:
        logger.error("OpenAI client not initialized")
        return None

    try:
        from django.urls import reverse

        # Build context from products
        if context_products:
            context = "Here are the relevant products from our catalog:\n\n"
            for i, product in enumerate(context_products[:5], 1):
                try:
                    product_id = int(product.get('id', 0))
                    product_type = product.get('type', 'book')
                    product_url = f"http://127.0.0.1:8000{reverse('product_detail', args=[product_type, product_id])}"
                    product_title = product.get('title', 'Unknown')

                    context += f"{i}. {product.get('type', '').title()}: {product_title}\n"
                    context += f"   Price: ${product.get('price', '0')}\n"
                    context += f"   Category: {product.get('category', 'Uncategorized')}\n"
                    context += f"   Seller: {product.get('seller', 'Unknown')}\n"
                    context += f"   Product Link: [{product_title}]({product_url})\n"
                    context += f"   Description: {product.get('description', '')[:200]}...\n\n"
                except Exception as e:
                    logger.error(f"Error processing product {i}: {e}")
        else:
            context = "No products found matching your query."

        # Create system prompt with conversation memory instructions
        system_prompt = """You are a helpful e-commerce shopping assistant for an online marketplace that sells books, courses, and webinars.

Guidelines:
- You have access to the conversation history - use it to maintain context
- Remember what the user asked previously and reference it naturally
- When user says "the first one" or "that book", refer to items mentioned earlier in the conversation
- Adapt response length based on the question complexity
- For simple questions (price, availability, single product): 1-2 sentences
- For comparison or multiple products: 3-4 sentences
- For recommendations or explanations: 4-5 sentences
- List products with: title, price, and clickable link
- ALWAYS include the product link in format: [Product Title](URL)
- Be natural, friendly, and match the tone of the question
- If user asks for brief info, keep it short
- If user asks for details or comparisons, provide comprehensive answer
- If no products found, suggest browsing categories
- Maintain conversation continuity - if user asks follow-up questions, understand the context"""

        # Create user prompt with current query and context
        user_prompt = f"""Context (Available Products):
{context}

User Question: {query}

Provide a helpful response that matches the question's needs - short for simple queries, detailed for complex ones."""

        # Build messages array with conversation history
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history if available (limited to prevent token overflow)
        if conversation_history:
            # Take only the last 10 message pairs (20 messages) to stay within token limits
            history_limit = 20
            recent_history = conversation_history[-history_limit:] if len(conversation_history) > history_limit else conversation_history
            messages.extend(recent_history)
            logger.info(f"Added {len(recent_history)} messages from conversation history")

        # Add current query with context
        messages.append({"role": "user", "content": user_prompt})

        # Call OpenAI Chat API with streaming
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=300,
            stream=True
        )

        return response
    except OpenAIError as e:
        logger.error(f"OpenAI API error generating chat response: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating chat response: {e}")
        return None


def get_fallback_response(query: str) -> str:
    """
    Generate a fallback response when AI is unavailable.

    Args:
        query: User's query

    Returns:
        Fallback response string
    """
    return (
        "I apologize, but our AI assistant is temporarily unavailable. "
        "Please try browsing our categories or using the search function to find products. "
        "If you need assistance, please contact our support team."
    )
