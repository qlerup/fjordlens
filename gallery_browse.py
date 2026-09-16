"""Bounded gallery pages, independent of filesystem discovery and folder counts."""


def photo_page(query, visible, matches, *, offset, limit):
    """Fill a page after ACL/search filtering; resume at the first unused match.

    The cursor counts logical query results, including filtered-out results. A
    lookahead distinguishes a full final page from a page that has a successor.
    """
    items = []
    cursor = offset
    batch_size = min(256, max(64, limit + 1))
    while True:
        batch = query(cursor, batch_size)
        allowed = {item['id'] for item in visible(batch)}
        for item in batch:
            if item['id'] in allowed and matches(item):
                if len(items) == limit:
                    return items, True, cursor
                items.append(item)
            cursor += 1
        if len(batch) < batch_size:
            return items, False, cursor
