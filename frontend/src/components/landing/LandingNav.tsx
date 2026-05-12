import { useT, useLang } from "../../i18n";
import { useAuth } from "../../lib/useAuth";

export function LandingNav() {
  const t = useT();
  const { lang, setLang } = useLang();
  const { login } = useAuth();

  return (
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
          <div className="landing-nav-links">
            <a href="#how">{t.landing.nav.how}</a>
            <a href="#features">{t.landing.nav.features}</a>
            <a href="#audience">{t.landing.nav.audience}</a>
          </div>
          <div className="landing-nav-right">
            <div className="landing-lang-toggle">
              <button className={lang === "pl" ? "active" : ""} onClick={() => setLang("pl")}>PL</button>
              <span className="landing-lang-sep">/</span>
              <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>EN</button>
            </div>
            <button className="landing-nav-cta" onClick={() => login()}>
              {t.landing.nav.signin}
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
