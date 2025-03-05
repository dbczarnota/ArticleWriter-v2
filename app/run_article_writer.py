from article_writer import ArticleWriter

final_text = ArticleWriter.write_article(
    article_topic='Anja Rubik do samego końca wahała się, czy chce wziąć ślub. "Bałam się, że to jest rodzaj zakłamania". Z mężem rozstała się po pięciu latach',
    domains=["party.pl", "pudelek.pl", "styl.fm", "pomponik.pl"],
    number_of_queries=2,
    scraping_model="",
    max_search_results=4,
    search_days=14,
    extraction_mode="markdown",
)
print("FINAL ARTICLE:", final_text)
