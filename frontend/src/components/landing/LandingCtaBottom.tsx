import { useT } from "../../i18n";
import { useAuth } from "../../lib/useAuth";

export function LandingCtaBottom() {
  const t = useT();
  const { login } = useAuth();
  const c = t.landing.cta;

  return (
    <section id="cta-bottom" className="landing-cta-bottom">
      <div className="landing-container landing-cta-bottom-inner">
        <h2 className="landing-cta-h">{c.h}</h2>
        <p className="landing-cta-sub">{c.sub}</p>
        <div className="landing-cta-actions">
          <button
            className="landing-btn-primary"
            onClick={() => login()}
          >
            {c.ctaPrimary}
          </button>
          <a
            href="mailto:demo@headlinesforge.com"
            className="landing-btn-ghost"
          >
            {c.ctaGhost}
          </a>
        </div>
      </div>
    </section>
  );
}
