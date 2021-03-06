from pprint import pprint  # noqa
from elasticsearch.helpers import scan

from aleph.core import es, es_index
from aleph.search.result import SearchQueryResult
from aleph.search.parser import SearchQueryParser


class Query(object):
    RESULT_CLASS = SearchQueryResult
    DOC_TYPES = []
    RETURN_FIELDS = True
    TEXT_FIELDS = ['_all']
    MULTI_FIELDS = ['collection_id', 'schema', 'countries']
    SORT = {
        'default': ['_score']
    }

    def __init__(self, parser):
        self.parser = parser

    def get_text_query(self):
        if not self.parser.text:
            return {'match_all': {}}
        return {
            "simple_query_string": {
                "query": self.parser.text,
                "fields": self.TEXT_FIELDS,
                "default_operator": "AND"
            }
        }

    def get_filters(self, exclude=None):
        """Apply query filters from the user interface."""
        filters = []
        for field, values in self.parser.filters.items():
            if field == exclude:
                continue
            if field in ['id', '_id']:
                filters.append({'ids': {'values': list(values)}})
            elif field in self.MULTI_FIELDS:
                filters.append({'terms': {field: list(values)}})
            else:
                for value in values:
                    filters.append({'term': {field: value}})
        return filters

    def get_query(self):
        return {
            'bool': {
                'should': [],
                'must': [self.get_text_query()],
                'must_not': [],
                'filter': self.get_filters()
            }
        }

    def get_aggregations(self):
        """Aggregate the query in order to generate faceted results."""
        aggs = {}
        for name in self.parser.facet_names:
            facet = {
                name: {
                    'terms': {
                        'field': name,
                        'size': self.parser.facet_size
                    }
                }
            }
            # Fields to be excluded from their own aggregation. This is true
            # when a filter on a faceted fied is not supposed to affect the
            # selection of aggregations.
            if name in self.MULTI_FIELDS:
                if 'scoped' not in aggs:
                    aggs['scoped'] = {
                        'global': {},
                        'aggregations': {}
                    }
                aggs['scoped']['aggregations'][name] = {
                    'filter': {
                        'bool': {
                            'filter': self.get_filters(exclude=name)
                        }
                    },
                    'aggregations': facet
                }
            else:
                aggs.update(facet)
        return aggs

    def get_sort(self):
        """Pick one of a set of named result orderings."""
        default = self.SORT.get('default')
        return self.SORT.get(self.parser.sort, default)

    def get_highlight(self):
        return {}

    def get_body(self):
        return {
            'query': self.get_query(),
            'from': self.parser.offset,
            'size': self.parser.limit,
            'aggregations': self.get_aggregations(),
            'sort': self.get_sort(),
            'highlight': self.get_highlight(),
            '_source': self.RETURN_FIELDS
        }

    def search(self):
        """Execute the query as assmbled."""
        # pprint(self.get_body())
        return es.search(index=es_index,
                         doc_type=self.DOC_TYPES,
                         body=self.get_body())

    def scan(self):
        """Return an iterator over the whole result set, unpaginated and
        without aggregations."""
        body = {
            'query': self.get_query(),
            '_source': self.RETURN_FIELDS
        }
        return scan(es,
                    index=es_index,
                    doc_type=self.DOC_TYPES,
                    query=body)

    @classmethod
    def handle_request(cls, request, limit=None, schema=None, **kwargs):
        parser = SearchQueryParser(request.args, request.authz, limit=limit)
        result = cls(parser, **kwargs).search()
        return cls.RESULT_CLASS(request, parser, result, schema=schema)


class AuthzQuery(Query):
    """Apply roles-based filtering to the results.

    This enforces the authorization (access control) rules on a particular
    query by comparing the roles a user is in with the ones on the document.
    """

    def get_filters(self, exclude=None):
        filters = super(AuthzQuery, self).get_filters(exclude=exclude)
        # Hot-wire authorization entirely for admins.
        if not self.parser.authz.is_admin:
            filters.append({
                'terms': {
                    'roles': list(self.parser.authz.roles)
                }
            })
        return filters
