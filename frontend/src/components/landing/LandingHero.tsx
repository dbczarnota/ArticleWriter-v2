import { useT } from "../../i18n";

export function LandingHero() {
  const t = useT();

  return (
    <section id="hero" className="landing-hero">
      <div className="landing-container">
        <div className="landing-hero-badge">
          <span className="landing-badge-dot" />
          {t.landing.hero.badge}
        </div>
        <h1 className="landing-hero-h">
          {t.landing.hero.h1Part1}
          <em>{t.landing.hero.h1Em}</em>
          {t.landing.hero.h1Part2}
        </h1>
        <p className="landing-hero-sub">{t.landing.hero.sub}</p>
        <div className="landing-hero-ctas">
          <button className="landing-btn-primary" onClick={() => document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" })}>
            {t.landing.hero.ctaPrimary}
          </button>
          <a href="#how" className="landing-btn-ghost">
            {t.landing.hero.ctaGhost}
          </a>
        </div>
        <div className="landing-hero-stats">
          <div>
            <div className="landing-stat-num">{t.landing.hero.stat1Value} <span>{t.landing.hero.stat1Unit}</span></div>
            <div className="landing-stat-label">{t.landing.hero.stat1Label}</div>
          </div>
          <div>
            <div className="landing-stat-num">{t.landing.hero.stat2Value}<span>{t.landing.hero.stat2Unit}</span></div>
            <div className="landing-stat-label">{t.landing.hero.stat2Label}</div>
          </div>
          <div>
            <div className="landing-stat-num">{t.landing.hero.stat3Value}<span>{t.landing.hero.stat3Unit}</span></div>
            <div className="landing-stat-label">{t.landing.hero.stat3Label}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
