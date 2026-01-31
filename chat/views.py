from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Conversation, Message, Document
from .serializers import (
    UserSerializer, 
    ConversationSerializer, 
    ConversationListSerializer,
    MessageSerializer,
    DocumentSerializer
)
from .rag_service import NepaliRAGService
import logging
import threading

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    User registration endpoint.
    Returns user data and authentication token.
    """
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # Create authentication token
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login endpoint.
    Validates credentials and returns token.
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    # Authenticate user
    user = authenticate(username=username, password=password)
    
    if user is not None:
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })
    
    return Response(
        {'error': 'Invalid credentials'}, 
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout endpoint.
    Deletes the user's authentication token.
    """
    request.user.auth_token.delete()
    return Response({'message': 'Successfully logged out'})







# ... existing auth views ...

class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing document uploads and processing.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """
        Handle PDF upload and trigger background processing.
        """
        file = request.FILES.get('file')
        conversation_id = request.data.get('conversation_id')
        
        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file type
        if not file.name.endswith('.pdf'):
            return Response(
                {'error': 'Only PDF files are supported'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create document record
        document = Document.objects.create(
            user=request.user,
            conversation_id=conversation_id if conversation_id else None,
            file=file,
            filename=file.name,
            status='pending'
        )
        
        # Process document in background
        thread = threading.Thread(
            target=self._process_document_async,
            args=(document.id,)
        )
        thread.start()
        
        serializer = self.get_serializer(document)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def _process_document_async(self, document_id):
        """
        Background task to process document.
        
        CHANGES:
        - Uses new chunking method (one article per chunk)
        - Better error handling
        """
        try:
            document = Document.objects.get(id=document_id)
            document.status = 'processing'
            document.save()
            
            # Initialize RAG service (new version)
            rag_service = NepaliRAGService()
            
            # Process document
            # Note: add_to_permanent_kb=False by default
            # Only admin-uploaded docs should set this to True
            result = rag_service.process_document(
                pdf_path=document.file.path,
                document_id=document.id,
                user_id=document.user.id,
                add_to_permanent_kb=False  # Don't add user docs to permanent KB
            )
            
            if result['success']:
                document.status = 'completed'
                document.collection_id = result['collection_id']
                document.num_pages = result['num_pages']
                document.num_chunks = result['num_chunks']
                document.processed_at = timezone.now()
                
                logger.info(f"Document {document_id} processed: {result['num_chunks']} articles, method: {result['parsing_method']}")
            else:
                document.status = 'failed'
                document.error_message = result['error']
            
            document.save()
            
        except Exception as e:
            logger.error(f"Document processing error: {str(e)}")
            try:
                document = Document.objects.get(id=document_id)
                document.status = 'failed'
                document.error_message = str(e)
                document.save()
            except:
                pass

class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing conversations with RAG support.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a conversation and all its messages.
        """
        conversation = self.get_object()
        logger.info(f"Deleting conversation {conversation.id} for user {request.user.username}")
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """
        Enhanced endpoint with RAG support.
        """
        logger.info(f"add_message called for conversation {pk}")
        
        conversation = self.get_object()
        content = request.data.get('content', '')
        use_rag = request.data.get('use_rag', True)  # Enable RAG by default
        
        # Auto-detect search source based on user documents
        if 'search_source' in request.data:
            # User explicitly specified source
            search_source = request.data.get('search_source')
        else:
            # Auto-detect: if conversation has completed documents, use 'user', else 'permanent'
            documents = conversation.documents.filter(status='completed')
            if documents.exists():
                search_source = 'user'  # Prioritize user's uploaded documents
                logger.info(f"Auto-detected {documents.count()} user documents, setting search_source='user'")
            else:
                search_source = 'permanent'  # Fall back to permanent KB
                logger.info("No user documents found, setting search_source='permanent'")
        
        logger.info(f"Using RAG: {use_rag}, Source: {search_source}")
        
        if not content.strip():
            return Response(
                {'error': 'Content cannot be empty'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add user message
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content
        )
        
        # Generate AI response
        try:
            if use_rag:
                response_data = self.generate_rag_response(
                    conversation, 
                    content,
                    search_source
                )
                assistant_response = response_data['response']
                sources = response_data.get('sources', [])
            else:
                assistant_response = self.generate_simple_response(content)
                sources = []
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            assistant_response = "माफ गर्नुहोस्, मलाई अहिले उत्तर दिन समस्या भइरहेको छ। कृपया फेरि प्रयास गर्नुहोस्।"
            sources = []
        
        # Add assistant message
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=assistant_response
        )
        
        # Update conversation timestamp
        conversation.save()
        
        return Response({
            'user_message': MessageSerializer(user_message).data,
            'assistant_message': MessageSerializer(assistant_message).data,
            'sources': sources  # Include source metadata
        })
    


    def generate_rag_response(self, conversation, user_input, search_source='permanent'):
        """
        Generate response using RAG with selectable source.
        
        Args:
            conversation: Conversation object
            user_input: User question
            search_source: 'permanent', 'user', or 'all'
        """
        from groq import Groq
        from django.conf import settings
        
        # Initialize RAG service
        rag_service = NepaliRAGService()
        
        # Get user's documents
        documents = Document.objects.filter(
            user=self.request.user,
            status='completed'
        )
        
        # Check if conversation has specific documents
        if conversation.documents.filter(status='completed').exists():
            documents = conversation.documents.filter(status='completed')
        
        # Decide retrieval strategy
        all_context_chunks = []
        
        # 1. Retrieve from User Documents if requested
        if search_source in ['user', 'all']:
             documents = conversation.documents.filter(status='completed')
             if not documents.exists():
                 # Fallback to general user documents if not specific to conversation
                 documents = Document.objects.filter(
                    user=self.request.user,
                    status='completed'
                )
             
             if documents.exists():
                logger.info(f"Retrieving from {documents.count()} user documents")
                for doc in documents:
                    if doc.collection_id:
                        chunks = rag_service.retrieve_context(
                            query=user_input,
                            collection_name=doc.collection_id,
                            top_k=3,
                            use_permanent_kb=False
                        )
                        all_context_chunks.extend(chunks)
             else:
                 logger.warning("User search requested but no documents found")
        
        # 2. Retrieve from Permanent KB if requested
        if search_source in ['permanent', 'all']:
            logger.info("Retrieving from Permanent KB")
            kb_chunks = rag_service.retrieve_context(
                query=user_input,
                collection_name=None,
                top_k=5,
                use_permanent_kb=True
            )
            all_context_chunks.extend(kb_chunks)
            
        # Sort by relevance and take top 5
        all_context_chunks.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_chunks = all_context_chunks[:5]
            
        if not top_chunks:
            return """मलाई तपाईंको प्रश्नको उत्तर दिन पर्याप्त जानकारी छैन। 

    कृपया कानुनी दस्तावेज अपलोड गर्नुहोस् वा अधिक विशिष्ट प्रश्न सोध्नुहोस्।

    (I don't have enough information to answer your question. Please upload a legal document or ask a more specific question.)"""
        
        # Log sources for debugging
        sources = {}
        for i, chunk in enumerate(top_chunks):
            source = chunk.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
            # Log detailed context (requested by user)
            print(f"=== Chunk {i+1} [{source}] ===")
            print(f"{chunk.get('text', '')[:300]}...")
            print("================================\n")
            
        print(f"Context sources: {sources}")
        
        # Format RAG prompt
        prompt = rag_service.format_rag_prompt(user_input, top_chunks)
        
        # Generate response using LLM
        try:
            client = Groq(api_key=settings.GROQ_API_KEY)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "तपाईं एक नेपाली कानुनी सहायक हुनुहुन्छ। दिइएको सन्दर्भको आधारमा मात्र नेपालीमा उत्तर दिनुहोस्।"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=800,
            )
            
            # Store response to return with sources
            return {
                'response': response.choices[0].message.content,
                'sources': sources
            }
            
        except Exception as e:
            logger.error(f"LLM API error: {str(e)}")
            raise
        



class MessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual messages.
    Supports delete and edit operations.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        # Only allow access to messages from user's own conversations
        return Message.objects.filter(conversation__user=self.request.user)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a message.
        """
        message = self.get_object()
        logger.info(f"Deleting message {message.id} from conversation {message.conversation.id}")
        return super().destroy(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Edit a user message and regenerate assistant response.
        Only user messages can be edited.
        """
        message = self.get_object()
        
        if message.role != 'user':
            return Response(
                {'error': 'Only user messages can be edited'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_content = request.data.get('content', '').strip()
        if not new_content:
            return Response(
                {'error': 'Content cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Editing message {message.id}: '{message.content}' -> '{new_content}'")
        
        # Update the user message
        message.content = new_content
        message.save()
        
        # Find and delete the subsequent assistant response if it exists
        try:
            next_message = Message.objects.filter(
                conversation=message.conversation,
                created_at__gt=message.created_at,
                role='assistant'
            ).order_by('created_at').first()
            
            if next_message:
                logger.info(f"Deleting old assistant response {next_message.id}")
                next_message.delete()
        except Exception as e:
            logger.warning(f"Could not delete old assistant response: {e}")
        
        # Generate new assistant response using the conversation's RAG logic
        try:
            conversation_viewset = ConversationViewSet()
            conversation_viewset.request = request
            
            # Auto-detect search source
            documents = message.conversation.documents.filter(status='completed')
            search_source = 'user' if documents.exists() else 'permanent'
            
            response_data = conversation_viewset.generate_rag_response(
                message.conversation,
                new_content,
                search_source
            )
            assistant_content = response_data['response']
            
            # Create new assistant message
            assistant_message = Message.objects.create(
                conversation=message.conversation,
                role='assistant',
                content=assistant_content
            )
            
            return Response({
                'user_message': MessageSerializer(message).data,
                'assistant_message': MessageSerializer(assistant_message).data
            })
            
        except Exception as e:
            logger.error(f"Failed to generate new response: {str(e)}")
            return Response(
                {'error': f'Failed to generate response: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
