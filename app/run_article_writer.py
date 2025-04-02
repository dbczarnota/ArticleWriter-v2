from article_writer import ArticleWriter

final_text = ArticleWriter.write_article(
    article_topic='Gdzie jechać, żeby zobaczyć żubry?',
    domains=[],
    number_of_queries=2,
    scraping_model="",
    max_search_results=4,
    search_days=900,
    extraction_mode="markdown",
)
print("FINAL ARTICLE:", final_text)
