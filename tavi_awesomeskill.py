"""Read AwesomeSkill metadata as untrusted discovery data; never install or execute."""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ORIGIN = 'https://awesomeskill.ai'
MAX_BYTES = 2_000_000
STOP = set('a an the to of for and or in on with my our this that it is be use please can you i want make help find new online skill skills agent download install integration missing need needed'.split())


def search_url(query):
    query = query.strip()
    if not query or len(query) > 160:
        raise ValueError('Search query must contain 1–160 characters')
    return ORIGIN+'/search?'+urllib.parse.urlencode({'sort': 'stars', 'q': query})


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        if url.scheme != 'https' or url.netloc != 'awesomeskill.ai':
            raise ValueError('AwesomeSkill redirected outside its HTTPS origin')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'awesomeskill.ai' or parsed.path != '/search':
        raise ValueError('Unexpected AwesomeSkill URL')
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Tavi/0.6 (+https://github.com/marceli1404/tavi)', 'Accept': 'text/html'})
    with urllib.request.build_opener(SameOriginRedirect()).open(request, timeout=20) as response:
        data = response.read(MAX_BYTES+1)
    if len(data) > MAX_BYTES:
        raise ValueError('AwesomeSkill response exceeds discovery size limit')
    return data.decode('utf-8')


class FlightParser(HTMLParser):
    """Parse JSON strings only. Do not evaluate scripts or interpret their instructions."""
    def __init__(self):
        super().__init__()
        self.script = False
        self.parts = []
        self.buff = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.script = True
            self.buff = []

    def handle_data(self, data):
        if self.script:
            self.buff.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script:
            self.script = False
            text = ''.join(self.buff).strip()
            prefix = 'self.__next_f.push('
            if text.startswith(prefix) and text.endswith(')'):
                try:
                    value = json.loads(text[len(prefix):-1])
                    if isinstance(value, list) and len(value) == 2 and value[0] == 1 and isinstance(value[1], str):
                        self.parts.append(value[1])
                except ValueError:
                    pass


def parse_listings(html):
    if len(html.encode('utf-8')) > MAX_BYTES:
        raise ValueError('AwesomeSkill response exceeds discovery size limit')
    parser = FlightParser()
    parser.feed(html)
    text = ''.join(parser.parts)
    # The public server page carries the skill metadata array in its Flight JSON.
    # Fail visibly if that format changes, rather than inventing an empty success.
    for match in re.finditer(r'"skills"\s*:\s*(?=\[)', text):
        try:
            value, _ = json.JSONDecoder().raw_decode(text[match.end():])
            if isinstance(value, list) and len(value) <= 100:
                return value
        except ValueError:
            continue
    if re.search(r'"children"\s*:\s*\[0,\s*" skills found"\]', text):
        return []
    raise ValueError('AwesomeSkill listing format changed or metadata is unavailable')


def terms(text):
    words = set(re.findall(r'[a-z][a-z0-9]+', text.lower())) - STOP
    return words | {w[:-1] for w in words if w.endswith('s') and len(w) > 4}


def search(query, limit=5, installed_names=()):
    from tavi_discovery import REPO_PATTERN, validate_path
    url = search_url(query)
    result = dict(query=query.strip(), provider='awesomeskill', source_url=url,
                  sort='stars', status='ok', candidates=[], repositories=[],
                  installation_authorized=False,
                  ranking='Task keyword overlap first, repository stars second; neither proves safety or task success.',
                  next_step='Inspect the pinned upstream skill with review-skill before passive staging or installation.')
    try:
        listings = parse_listings(fetch(url))
        # Phrase searches on the current site are literal. Try one transparent,
        # bounded keyword query after an explicitly empty result, on the same site.
        keywords = [w for w in re.findall(r'[a-z][a-z0-9-]+', query.lower()) if w not in STOP]
        if not listings and len(keywords) > 1:
            keyword = keywords[0]
            url = search_url(keyword)
            result.update(requested_source_url=result['source_url'], source_url=url,
                          fallback_query=keyword)
            listings = parse_listings(fetch(url))
    except (ValueError, OSError, UnicodeError) as error:
        result.update(status='unavailable', error=str(error), incomplete=True)
        return result
    candidates = []
    seen = set()
    installed = {name.casefold() for name in installed_names}
    rejected = 0
    for row in listings:
        try:
            if not isinstance(row, dict):
                raise ValueError('Invalid listing')
            name, slug, repo = (row.get(k) for k in ('name', 'slug', 'github_repo'))
            path, description = row.get('github_path'), row.get('description') or ''
            if not all(isinstance(x, str) for x in (name, slug, repo, path, description)):
                raise ValueError('Missing listing fields')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,200}', slug) or not re.fullmatch(REPO_PATTERN, repo):
                raise ValueError('Invalid source identity')
            if any(part in ('.', '..') for part in repo.split('/')):
                raise ValueError('Invalid repository')
            skill_path = path.rstrip('/')
            if not skill_path.endswith('SKILL.md'):
                skill_path = (skill_path+'/' if skill_path else '')+'SKILL.md'
            validate_path(skill_path)
            identity = (repo.casefold(), skill_path.casefold())
            if identity in seen:
                continue
            seen.add(identity)
            shared = sorted(terms(query) & terms(name+' '+description[:1500]))
            if not shared:
                continue
            stars = row.get('github_stars')
            stars = stars if type(stars) is int and 0 <= stars <= 100_000_000 else 0
            duplicate = name.casefold() in installed
            candidates.append(dict(name=name[:200], description=description[:800], repo=repo,
                skill_path=skill_path, url=ORIGIN+'/skill/'+slug, stars=stars,
                shared_task_terms=shared, duplicate=duplicate,
                recommendation='skip_duplicate' if duplicate else 'review_required',
                review_command=['python', 'tavi.py', 'review-skill', repo, skill_path, '--task', query],
                installation_authorized=False))
        except ValueError:
            rejected += 1
    candidates.sort(key=lambda r: (r['duplicate'], -len(r['shared_task_terms']), -r['stars'], r['name']))
    result['candidates'] = candidates[:min(10, max(1, limit))]
    result['rejected_listings'] = rejected
    result['incomplete'] = True  # One bounded result page; not an exhaustive catalog search.
    result['status'] = 'ok' if result['candidates'] else 'no_relevant_candidates'
    return result
