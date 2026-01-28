from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Conversation, Message, Document

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    We use write_only for password so it's never returned in API responses.
    """
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        # Use create_user to properly hash passwords
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for individual messages.
    Simple pass-through of model fields.
    """
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for conversations.
    Includes nested messages and message count.
    """
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages', 'message_count']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_message_count(self, obj):
        return obj.messages.count()


class ConversationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing conversations in sidebar.
    We don't include full messages here for performance.
    """
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'updated_at', 'message_count', 'last_message']

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'role': last_msg.role,
                'content': last_msg.content[:50] + '...' if len(last_msg.content) > 50 else last_msg.content
            }
        return None



class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for uploaded PDF documents.
    """
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'filename', 'status', 'num_pages', 'num_chunks',
            'error_message', 'created_at', 'processed_at', 'file_url'
        ]
        read_only_fields = [
            'id', 'status', 'num_pages', 'num_chunks', 
            'error_message', 'created_at', 'processed_at'
        ]
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None