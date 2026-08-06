SQLITE_HEADER = b'SQLite format 3\x00'


def has_sqlite_header(file_path):
    """Check if file starts with SQLite database magic."""
    with open(file_path, 'rb') as f:
        return f.read(len(SQLITE_HEADER)) == SQLITE_HEADER
