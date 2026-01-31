from django.core.management.base import BaseCommand
from chat.rag_service import SevaBot_RAG_Service
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load PDF documents into the Permanent Knowledge Base'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', 
            type=str, 
            default='permanent_knowledge',
            help='Directory containing PDF files (default: permanent_knowledge/)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reload all documents (clears existing index)'
        )

    def handle(self, *args, **options):
        kb_path = Path(options['path'])
        force_reload = options['force']
        
        if not kb_path.exists():
            self.stdout.write(self.style.ERROR(f"Directory not found: {kb_path}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Initializing RAG Service..."))
        rag_service = SevaBot_RAG_Service()
        
        self.stdout.write(f"Loading documents from {kb_path}...")
        if force_reload:
            self.stdout.write(self.style.WARNING("Force reload enabled: Rebuilding index..."))

        try:
            rag_service.load_permanent_knowledge(
                knowledge_dir=kb_path,
                force_reload=force_reload
            )
            self.stdout.write(self.style.SUCCESS("Successfully loaded Permanent Knowledge Base"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to load KB: {str(e)}"))
