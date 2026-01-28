from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import authenticate
from django.utils import timezone
from django.contrib.auth.models import User
from .rag_service import NepaliRAGService
from .models import Conversation, Message, Document
from .serializers import (
    UserSerializer, 
    ConversationSerializer, 
    ConversationListSerializer,
    MessageSerializer,
    DocumentSerializer
)
import requests
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


class ConversationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing conversations.
    Automatically provides list, create, retrieve, update, destroy actions.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """
        Use lightweight serializer for list view,
        full serializer for detail view.
        """
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        """
        Filter conversations to only show the authenticated user's conversations.
        """
        return Conversation.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """
        Automatically set the user when creating a conversation.
        """
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """
        Custom endpoint to add a message to a conversation.
        URL: /api/conversations/{id}/add_message/
        """
        logger.info(f"add_message called for conversation {pk}")
        logger.info(f"Request data: {request.data}")
        
        conversation = self.get_object()
        content = request.data.get('content', '')
        
        if not content.strip():
            logger.warning("Empty content received")
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
        logger.info(f"User message created: {user_message.id}")
        
        # Generate AI response
        try:
            assistant_response = self.generate_ai_response(conversation, content)
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            assistant_response = "I apologize, but I'm having trouble generating a response right now. Please try again."
        
        # Add assistant message
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=assistant_response
        )
        logger.info(f"Assistant message created: {assistant_message.id}")
        
        # Update conversation timestamp
        conversation.save()
        
        response_data = {
            'user_message': MessageSerializer(user_message).data,
            'assistant_message': MessageSerializer(assistant_message).data
        }
        logger.info(f"Sending response: {response_data}")
        
        return Response(response_data)
    


    # def generate_ai_response(self, conversation, user_input):
    #     """
    #     Generate AI response using Groq (FREE & FAST)
    #     """
    #     from groq import Groq
    #     from django.conf import settings
        
    #     client = Groq(api_key=settings.GROQ_API_KEY)
        
    #     # Get conversation history
    #     messages = conversation.messages.order_by('created_at')[:10]
    #     history = [
    #         {"role": msg.role, "content": msg.content}
    #         for msg in messages
    #     ]
        
    #     # Add current user message
    #     history.append({"role": "user", "content": user_input})
        
    #     try:
    #         response = client.chat.completions.create(
    #             model="llama-3.3-70b-versatile",  # Fast and good
    #             messages=history,
    #             temperature=0.7,
    #             max_tokens=500,
    #         )
            
    #         return response.choices[0].message.content
            
    #     except Exception as e:
    #         logger.error(f"Groq API error: {str(e)}")
    #         return "I'm having trouble connecting to my AI brain. Please try again!"






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
        """
        try:
            document = Document.objects.get(id=document_id)
            document.status = 'processing'
            document.save()
            
            # Initialize RAG service
            rag_service = NepaliRAGService()
            
            # Process document
            result = rag_service.process_document(
                pdf_path=document.file.path,
                document_id=document.id,
                user_id=document.user.id
            )
            
            if result['success']:
                document.status = 'completed'
                document.collection_id = result['collection_id']
                document.num_pages = result['num_pages']
                document.num_chunks = result['num_chunks']
                document.processed_at = timezone.now()
            else:
                document.status = 'failed'
                document.error_message = result['error']
            
            document.save()
            logger.info(f"Document {document_id} processing completed: {document.status}")
            
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
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """
        Enhanced endpoint with RAG support.
        """
        logger.info(f"add_message called for conversation {pk}")
        
        conversation = self.get_object()
        content = request.data.get('content', '')
        use_rag = request.data.get('use_rag', True)  # Enable RAG by default
        
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
                assistant_response = self.generate_rag_response(
                    conversation, 
                    content
                )
            else:
                assistant_response = self.generate_simple_response(content)
                
        except Exception as e:
            logger.error(f"AI generation failed: {str(e)}")
            assistant_response = "माफ गर्नुहोस्, मलाई अहिले उत्तर दिन समस्या भइरहेको छ। कृपया फेरि प्रयास गर्नुहोस्।"
        
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
            'assistant_message': MessageSerializer(assistant_message).data
        })
    
    def generate_rag_response(self, conversation, user_input):
        """
        Generate response using RAG (Retrieval-Augmented Generation).
        """
        from groq import Groq
        from django.conf import settings
        
        # Initialize RAG service
        rag_service = NepaliRAGService()
        
        # Get all documents for this conversation or user
        documents = Document.objects.filter(
            user=self.request.user,
            status='completed'
        )
        
        if conversation.documents.filter(status='completed').exists():
            # Use conversation-specific documents
            documents = conversation.documents.filter(status='completed')
        
        if not documents.exists():
            return "कृपया पहिले कानुनी दस्तावेज अपलोड गर्नुहोस्। (Please upload a legal document first.)"
        
        # Retrieve context from all relevant documents
        all_context_chunks = []
        for doc in documents:
            if doc.collection_id:
                chunks = rag_service.retrieve_context(
                    query=user_input,
                    collection_name=doc.collection_id,
                    top_k=3  # Get top 3 from each document
                )
                all_context_chunks.extend(chunks)
        
        if not all_context_chunks:
            return "मलाई तपाईंको प्रश्नसँग सम्बन्धित जानकारी फेला परेन। (I couldn't find relevant information for your question.)"
        
        # Sort by relevance and take top 5
        all_context_chunks.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_chunks = all_context_chunks[:5]
        
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
                temperature=0.3,  # Lower temperature for factual responses
                max_tokens=800,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM API error: {str(e)}")
            raise
    
    def generate_simple_response(self, user_input):
        """
        Fallback: simple response without RAG.
        """
        return f"तपाईंले भन्नुभयो: '{user_input}'. कृपया कानुनी दस्तावेज अपलोड गर्नुहोस् वा RAG सक्षम गर्नुहोस्।"