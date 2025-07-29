import requests
import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.contrib import messages
from scholarly import scholarly
import hashlib
import urllib.parse
import logging

logger = logging.getLogger(__name__)

# Create your views here.
def index(request):
    return HttpResponse('Hello folks!')

def paper_search_page(request):
    """
    Render the paper search from page
    """
    context = {
        'sources': [
            ('arxiv', 'Arxiv'),
            ('pubmed', 'Pubmed'),
            ('semantic_scholar', 'Semantic Scholar'),
            ('google_scholar', 'Google Scholar')
        ]
    }
    return render(request, 'papers/search.html', context)

def paper_search_results(request):
    """
    Handle search form submission and display results
    """
    query = request.GET.get('query', '')
    source = request.GET.get('source', 'arxiv')
    author = request.GET.get('author', '')
    year = request.GET.get('year', '')
    limit = int(request.GET.get('limit', 10))
    page = request.GET.get('page', 1)

    if not query:
        messages.error(request, 'Please enter a search query')
        return render(request, 'papers/search.html')

    try:
        if source == 'arxiv':
            results = search_arxiv(query, limit, author, year)
        elif source == 'pubmed':
            results = search_pubmed(query, limit, author, year)
        elif source == 'semantic_scholar':
            results = search_semantic_scholar(query, limit, author, year)
        elif source == 'google_scholar':
            results = search_google_scholar(query, limit, author, year)
        else:
            messages.error(request, f'Unsupported source: {source}')
            return render(request, 'papers/search.html')

        paginator = Paginator(results, 18)
        papers_page = paginator.get_page(page)

        context = {
            'papers': papers_page,
            'query': query,
            'source': source,
            'author': author,
            'year': year,
            'total_results': len(results),
            'sources': [
                ('arxiv', 'ArXiv'),
                ('pubmed', 'PubMed'),
                ('semantic_scholar', 'Semantic Scholar'),
                ('google_scholar', 'Google Scholar'),
            ]
        }

        return render(request, 'papers/results.html', context)

    except Exception as e:
        logger.error(f"Error searching papers: {str(e)}")
        messages.error(request, f'Search failed: {str(e)}')
        return render(request, 'papers/search.html')

def search_arxiv(query, limit=10, author='', year=''):
    """ Search Arxiv Papers"""
    try:
        base_url = "https://export.arxiv.org/api/query"
        # https://export.arxiv.org/api/query?search_query=all:electron&start=0&max_results=10
        # Build a search query
        search_query = f"all:{query}"
        if author:
            search_query += f" AND au:{author}"
        if year:
            search_query += f" AND submittedDate:[{year}0101 TO {year}1231]"

        params = {
            'search_query': search_query,
            'start': 0,
            'max_results': limit,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        response = requests.get(base_url, params=params, timeout=38)
        response.raise_for_status()

        # Parse XML response
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        papers = []

        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            paper = parse_arxiv_entry(entry)
            papers.append(paper)

        return papers

    except Exception as e:
        logger.error(f"Arxiv search error: {str(e)}")
        return []

def parse_arxiv_entry(entry, include_full_text=False):
    """Parse ArXiv XML entry into structured data"""
    ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'https://arxiv.org/schemas/atom'}

    paper_id = entry.find('atom:id', ns).text.split('/')[-1]

    paper = {
        'id': f"arxiv:{paper_id}",
        'title': entry.find('atom:title', ns).text.strip(),
        'abstract': entry.find('atom:summary', ns).text.strip(),
        'authors': [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)],
        'published': entry.find('atom:published', ns).text,
        'updated': entry.find('atom:updated', ns).text,
        'categories': [cat.get('term') for cat in entry.findall('atom:category', ns)],
        'pdf_url': None,
        'source': 'arxiv'
    }

    # Get PDF URL
    for link in entry.findall('atom:link', ns):
        if link.get('type') == 'application/pdf':
            paper['pdf_url'] = link.get('href')
            break

    return paper

def search_pubmed(query, limit=10, author='', year=''):
    """Search PubMed papers"""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

        search_terms = [query]
        if author:
            search_terms.append(f"{author}[Author]")
        if year:
            search_terms.append(f"{year}[Publication Date]")

        params = {
            'db': 'pubmed',
            'term': ' AND '.join(search_terms),
            'retmax': limit,
            'retmode': 'json'
        }
        print(f"PubMed search params: {params}")  # Debug
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        print(f"PubMed search response: {data}")  # Debug
        # Fetch paper details
        if 'esearchresult' in data and 'idlist' in data['esearchresult']:
            paper_ids = data['esearchresult']['idlist']
            return fetch_pubmed_details(paper_ids)

        return []

    except Exception as e:
        logger.error(f"PubMed search error: {str(e)}")
        return []

def fetch_pubmed_details(paper_ids):
    """Fetch detailed PubMed paper information"""
    try:
        if not paper_ids:
            return []

        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': ','.join(paper_ids),
            'retmode': 'xml'
        }

        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        # Parse PubMed XML (simplified parsing)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)

        papers = []
        for article in root.findall('.//PubmedArticle'):
            paper = parse_pubmed_article(article)
            papers.append(paper)

        return papers

    except Exception as e:
        logger.error(f"Error fetching PubMed details: {str(e)}")
        return []


def parse_pubmed_article(article):
    """Parse PubMed XML article into structured data"""
    # Simplified PubMed parsing - you might want to expand this

    try:
        pmid = article.find('.//PMID').text
        title_elem = article.find('.//ArticleTitle')
        abstract_elem = article.find('.//Abstract/AbstractText')

        authors = []
        for author in article.findall('.//Author'):
            lastname = author.find('LastName')
            forename = author.find('ForeName')
            if lastname is not None and forename is not None:
                authors.append(f"{forename.text} {lastname.text}")

        paper = {
            'id': f"pubmed:{pmid}",
            'title': title_elem.text if title_elem is not None else '',
            'abstract': abstract_elem.text if abstract_elem is not None else '',
            'authors': authors,
            'pmid': pmid,
            'source': 'pubmed'
        }

        return paper

    except Exception as e:
        logger.error(f"Error parsing PubMed article: {str(e)}")
        return None

def search_semantic_scholar(query, limit, author, year):
    """Search Semantic Scholar papers"""
    try:
        base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

        params = {
            'query': query,
            'limit': limit,
            'fields': 'paperId,title,abstract,authors,year,citationCount,url,venue'
        }

        if author:
            params['query'] += f" author:{author}"
        if year:
            params['year'] = year

        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        papers = []
        for paper in data.get('data', []):
            formatted_paper = {
                'id': f"semantic_scholar:{paper['paperId']}",
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'authors': [author.get('name', '') for author in paper.get('authors', [])],
                'year': paper.get('year'),
                'citation_count': paper.get('citationCount', 0),
                'venue': paper.get('venue', ''),
                'url': paper.get('url', ''),
                'source': 'semantic_scholar'
            }

            papers.append(formatted_paper)

        return papers

    except Exception as e:
        logger.error(f"Semantic Scholar search error: {str(e)}")
        return []

def paper_detail_page(request, paper_id):
    """
    Display detailed information about a specific paper
    """
    try:
        source, pid = paper_id.split(':', 1) if ':' in paper_id else ('arxiv', paper_id)
        if source == 'arxiv':
            paper_data = fetch_arxiv_paper(pid)
        elif source == 'google_scholar':
            paper_data = fetch_google_scholar_paper(pid)
        elif source == 'pubmed':
            paper_data = fetch_pubmed_paper(pid)
        else:
            messages.error(request, f"Unsupported source: {source}")
            return render(request, 'papers/search.html')

        if not paper_data:
            messages.error(request, 'Paper not found')
            return render(request, 'papers/search.html')

        context = {
            'paper': paper_data,
            'source': source
        }

        return render(request, 'papers/detail.html', context)

    except Exception as e:
        logger.error(f"Error fetching paper {paper_id}: {str(e)}")
        messages.error(request, f'Failed to fetch paper: {str(e)}')
        return render(request, 'papers/search.html')

def fetch_arxiv_paper(paper_id, include_full_text=True):
    """Fetch detailed ArXiv paper information"""
    try:
        base_url = "https://export.arxiv.org/api/query"
        params = {
            'id_list': paper_id,
            'max_results': 1
        }

        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)

        entry = root.find('{http://www.w3.org/2005/Atom}entry')
        if entry is not None:
            return parse_arxiv_entry(entry, include_full_text)

        return None

    except Exception as e:
        logger.error(f"Error fetching ArXiv paper {paper_id}: {str(e)}")
        return None

def search_google_scholar(query, limit=10, author='', year=''):
    """Search Google Scholar using the scholarly module"""
    try:
        results = []
        search_query = query

        if author:
            search_query += f' author:f"{author}"'

        search_results = scholarly.search_pubs(search_query)
        count = 0

        for pub in search_results:
            if count >= limit:
                break

            if year and 'pub_year' in pub['bib']:
                if str(pub['bib']['pub_year']) != str(year):
                    continue

            paper_id = generate_google_scholar_id(pub)

            paper = {
                'id': paper_id,
                'title': pub['bib'].get('title', 'No title'),
                'authors': pub['bib'].get('author', []),
                'year': pub['bib'].get('pub_year', 'Unknown'),
                'abstract': pub['bib'].get('abstract', 'No abstract available'),
                'url': pub.get('pub_url', ''),
                'venue': pub['bib'].get('venue', 'Unknown venue'),
                'citations': pub.get('num_citations', 0)
            }

            results.append(paper)
            count += 1

        return results

    except Exception as e:
        logger.error(f"Error searching Google Scholar: {str(e)}")
        raise e

def fetch_google_scholar_paper(paper_id, include_full_text=True):
    """Fetch detailed Google Scholar paper information"""
    try:
        # For Google Scholar, paper_id could be a title, DOI, or scholar ID
        # Trying to search by the paper_id first
        search_results = scholarly.search_pubs(paper_id)

        # Get the first result and fill in details
        pub = next(search_results, None)
        if not pub:
            return None

        # Fill the publication with detailed information
        filled_pub = scholarly.fill(pub)

        # Extract paper data in a consistent format
        paper_data = {
            'id': paper_id,
            'title': filled_pub['bib'].get('title', 'No title'),
            'authors': filled_pub['bib'].get('author', []),
            'year': filled_pub['bib'].get('pub_year', 'Unknown'),
            'abstract': filled_pub['bib'].get('abstract', 'No abstract available'),
            'url': filled_pub.get('pub_url', ''),
            'venue': filled_pub['bib'].get('venue', 'Unknown venue'),
            'citations': filled_pub.get('num_citations', 0),
            'doi': filled_pub['bib'].get('doi', ''),
            'source': 'google_scholar'
        }

        # Add citation information if available
        if 'citedby_url' in filled_pub:
            paper_data['citedby_url'] = filled_pub['citedby_url']

        # Add related papers if available
        if 'related_articles' in filled_pub:
            paper_data['related_articles'] = filled_pub['related_articles']

        # For full text, we can only provide the URL if available
        if include_full_text and 'eprint_url' in filled_pub:
            paper_data['full_text_url'] = filled_pub['eprint_url']

        return paper_data

    except Exception as e:
        logger.error(f"Error fetching Google Scholar paper {paper_id}: {str(e)}")
        return None

def generate_google_scholar_id(pub):
    """Generate a unique ID for Google Scholar papers"""
    # Try different approaches to create a unique identifier
    # Option 1: Using scholar_id if available
    if 'scholar_id' in pub:
        return f"google_scholar:{pub['scholar_id']}"

    # Option 2: Using DOI if available
    if 'doi' in pub['bib'] and pub['bib']['doi']:
        doi = pub['bib']['doi'].replace('/', '_').replace(':', '_')
        return f"google_scholar:doi_{doi}"

    # Option 3: Using pub_url if available
    if 'pub_url' in pub and pub['pub_url']:
        url_hash = hashlib.md5(pub['pub_url'].encode()).hexdigest()[:10]
        return f"google_scholar:url_{url_hash}"

    # Option 4: Create hash from title and first author
    title = pub['bib'].get('title', 'untitled')
    authors = pub['bib'].get('author', ['unknown'])
    first_author = authors[0] if authors else 'unknown'

    # Create a hash from title and first author and year
    year = str(pub['bib'].get('pub_year', ''))
    identifier_string = f"{title}_{first_author}_{year}"
    paper_hash = hashlib.md5(identifier_string.encode()).hexdigest()[:12]

    return f"google_scholar:hash_{paper_hash}"

def fetch_pubmed_paper(paper_id, include_full_text=True):
    """Fetch single PubMed paper"""
    return fetch_pubmed_details([paper_id])[0] if fetch_pubmed_details([paper_id]) else None