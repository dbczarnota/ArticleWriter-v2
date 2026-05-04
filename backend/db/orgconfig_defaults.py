"""Default text values for new OrgConfig rows.

Used by `OrgConfig` field defaults (models.py) and by tests that assert what
a freshly-bootstrapped tenant sees on first login. Kept as module-level
constants so the long Polish strings don't bloat models.py.

Tone: generic editorial — gives a new user something usable to start from
without locking them into any particular publication's voice. They edit it
all in Settings.
"""

from textwrap import dedent

DEFAULT_DESCRIPTION = "Polski portal redakcyjny — opisz krótko styl i tematykę."

DEFAULT_GUIDELINES = dedent("""\
    # Wytyczne redakcyjne

    ## Ton i styl
    - Pisz konkretnie, krótkimi zdaniami. Akapity 3–5 zdań.
    - Aktywna strona, czas teraźniejszy gdy to możliwe.
    - Unikaj clickbaitu i frazesów ("warto wiedzieć", "to musisz zobaczyć").

    ## Struktura
    - H1: konkretny tytuł, max 15 słów, zawiera kluczowy fakt lub pytanie.
    - Lead (pierwszy akapit): kto, co, gdzie, kiedy. Nie powtarzaj H1.
    - H2: faktyczne podtytuły, jak rozdziały — nie teaser-bait.
    - Cytaty dosłowne — z atrybucją (kto, kiedy, w jakim kontekście).

    ## Faktualność
    - Każdy fakt musi pochodzić ze źródła. Bez halucynacji.
    - Liczby, daty, nazwiska — sprawdzaj dwa razy.
    - Jeśli źródła sobie przeczą, zaznacz to wprost.

    ## SEO (delikatnie)
    - Słowo kluczowe w H1, leadzie i jednym H2.
    - Linki wewnętrzne tam gdzie pasują tematycznie.
    """)

DEFAULT_HTML_FORMAT = dedent("""\
    <h1>Tytuł artykułu</h1>
    <p><strong>Lead</strong> — pierwszy akapit z konkretami: kto, co, gdzie, kiedy.</p>

    <h2>Pierwszy podrozdział</h2>
    <p>Treść akapitu z faktem ze źródła.</p>
    <p>Kolejny akapit rozwijający temat.</p>

    <h2>Drugi podrozdział</h2>
    <p>Treść.</p>
    <blockquote>Cytat dosłowny — atrybucja (kto, kiedy).</blockquote>

    <h2>Podsumowanie</h2>
    <p>Akapit zamykający.</p>
    """)
