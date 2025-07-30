from django.db import models

from django.contrib.postgres.fields import ArrayField
import uuid

# Create your models here.

class Paper(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    title = models.TextField()
    abstract = models.TextField(blank=True)
    authors = ArrayField(models.CharField(max_length=200), default=list)
    pmid = models.CharField(max_length=20, null=True, blank=True)
    source = models.CharField(max_length=20)

    pdf_file = models.FileField(upload_to='papers/pdfs', null=True, blank=True)
    pdf_url = models.URLField(null=True, blank=True)
    pdf_downloaded = models.BooleanField(default=False)

    # Processing states
    processed = models.BooleanField(default=False)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('downloading', 'Downloading PDF'),
            ('processing', 'Processing Text'),
            ('embedding', 'Generating Embeddings'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )

    processing_error = models.TextField(null=True, blank=True)

    # Metadata
    publication_year = models.IntegerField(null=True, blank=True)
    journal = models.CharField(max_length=200, null=True, blank=True)
    doi = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PaperChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='chunks')

    # chunks content
    content = models.TextField()
    chunk_index = models.IntegerField()
    page_number = models.IntegerField(null=True, blank=True)

    # chunks metadata
    section_type = models.CharField(
        max_length=50,
        choices=[
            ('abstract', 'Abstract'),
            ('introduction', 'Introduction'),
            ('methods', 'Methods'),
            ('results', 'Results'),
            ('discussion', 'Discussion'),
            ('conclusion', 'Conclusion'),
            ('references', 'References'),
            ('other', 'Other')
        ],
        default='other'
    )

    word_count = models.IntegerField()
    char_count = models.IntegerField()

    # Embedding
    embedding = ArrayField(models.FloatField(), size=384, null=True, blank=True)
    embedding_model = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['paper', 'chunk_index']),
            models.Index(fields=['section_type']),
        ]

