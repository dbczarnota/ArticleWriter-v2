import logging
from contextvars import ContextVar
from rich.logging import RichHandler

current_article_topic = ContextVar("current_article_topic", default="")

class ArticleContextFilter(logging.Filter):
    def filter(self, record):
        topic = current_article_topic.get()
        if topic:
            if isinstance(record.msg, str):
                record.msg = f"[{topic}] {record.msg}"
        return True

_filter_instance = ArticleContextFilter()

def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, markup=True, show_time=False)],
        force=True # Ensures the configuration is re-applied even if called previously
    )
    root_logger = logging.getLogger()
    
    # Ensure our filter is only added once
    for handler in root_logger.handlers:
        is_filter_added = any(isinstance(f, ArticleContextFilter) for f in handler.filters)
        if not is_filter_added:
            handler.addFilter(_filter_instance)
