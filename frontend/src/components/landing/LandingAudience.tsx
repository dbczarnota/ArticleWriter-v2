import { useT } from "../../i18n";
import { NewspaperIcon, SparklesIcon, TrophyIcon, BriefcaseIcon } from "./icons";

export function LandingAudience() {
  const t = useT();
  const a = t.landing.audience;

  const cards = [
    { icon: <NewspaperIcon width={32} height={32} />, type: a.newsH, desc: a.newsP },
    { icon: <SparklesIcon width={32} height={32} />, type: a.lifestyleH, desc: a.lifestyleP },
    { icon: <TrophyIcon width={32} height={32} />, type: a.sportH, desc: a.sportP },
    { icon: <BriefcaseIcon width={32} height={32} />, type: a.businessH, desc: a.businessP },
  ];

  return (
    <section id="audience" className="landing-audience">
      <div className="landing-container">
        <div className="landing-label-tag">{a.tag}</div>
        <h2 className="landing-section-h">{a.h2}</h2>
        <p className="landing-section-sub">{a.sub}</p>
        <div className="landing-audience-grid">
          {cards.map((c, i) => (
            <div key={i} className="landing-audience-card">
              <div className="landing-audience-icon">{c.icon}</div>
              <div className="landing-audience-type">{c.type}</div>
              <div className="landing-audience-desc">{c.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
