from django.core.management.base import BaseCommand
from pathlib import Path
from chat.rag_service import SevaBot_RAG_Service
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Load permanent legal knowledge into ChromaDB (supports both Preeti and modern PDFs)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--knowledge-dir',
            type=str,
            default='permanent_knowledge',
            help='Directory containing permanent legal PDFs (Preeti or modern)'
        )
        parser.add_argument(
            '--force-reload',
            action='store_true',
            help='Force reload even if collection exists'
        )
    
    def handle(self, *args, **options):
        knowledge_dir = Path(options['knowledge_dir'])
        force_reload = options['force_reload']
        
        if not knowledge_dir.exists():
            self.stdout.write(self.style.ERROR(f'Directory not found: {knowledge_dir}'))
            self.stdout.write('Creating directory...')
            knowledge_dir.mkdir(parents=True)
            self.stdout.write(self.style.WARNING('Please add PDF files to this directory and run again'))
            self.stdout.write('\nNote: Both Preeti/legacy fonts and modern Unicode PDFs are supported!')
            return
        
        self.stdout.write(self.style.SUCCESS('Loading permanent knowledge base...'))
        self.stdout.write('Auto-detecting PDF types (Preeti vs Modern)...')
        
        try:
            rag_service = SevaBot_RAG_Service()
            rag_service.load_permanent_knowledge(
                knowledge_dir=knowledge_dir,
                force_reload=force_reload
            )
            
            self.stdout.write(self.style.SUCCESS('✓ Permanent knowledge loaded successfully!'))
            self.stdout.write(f'Total chunks in database: {rag_service.permanent_collection.count()}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to load knowledge: {str(e)}'))
            import traceback
            traceback.print_exc()