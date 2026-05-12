import { useT } from "../i18n";
import { useAuth } from "../lib/useAuth";

export function LandingPage() {
  const t = useT();
  const { login } = useAuth();

  return (
    <div className="landing-root">
      {/* Nav stub — full nav in Task 4 */}
      <nav className="landing-nav">
        <div className="landing-container">
          <div className="landing-nav-inner">
            <a href="#" className="landing-logo">
              <div className="landing-logo-bar" />
              <div className="landing-logo-stack">
                <div className="landing-logo-name"><span className="lt">headlines</span><span className="bd">forge</span></div>
                <div className="landing-logo-sub">AI Newsroom Platform</div>
              </div>
            </a>
            <div className="landing-nav-right">
              <button className="landing-nav-cta" onClick={() => login()}>
                {t.landing.nav.signin}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero stub */}
      <section className="landing-hero">
        <div className="landing-container">
          <h1 className="landing-hero-h">
            {t.landing.hero.h1Part1}
            <em>{t.landing.hero.h1Em}</em>
            {t.landing.hero.h1Part2}
          </h1>
          <p className="landing-hero-sub">{t.landing.hero.sub}</p>
          <button className="landing-btn-primary" onClick={() => login()}>
            {t.landing.hero.ctaPrimary}
          </button>
        </div>
      </section>
    </div>
  );
}
