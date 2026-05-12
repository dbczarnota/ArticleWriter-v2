import { useT } from "../../i18n";
import { EyeIcon, BroadcastIcon, BookOpenIcon, FileTextIcon, UsersIcon, ShieldCheckIcon } from "./icons";

export function LandingFeatures() {
  const t = useT();
  const f = t.landing.features;

  const cards = [
    { icon: <EyeIcon width={22} height={22} />, h: f.sourcesH, p: f.sourcesP },
    { icon: <BroadcastIcon width={22} height={22} />, h: f.tvRadioH, p: f.tvRadioP },
    { icon: <BookOpenIcon width={22} height={22} />, h: f.voiceH, p: f.voiceP },
    { icon: <FileTextIcon width={22} height={22} />, h: f.readyH, p: f.readyP },
    { icon: <UsersIcon width={22} height={22} />, h: f.teamH, p: f.teamP },
    { icon: <ShieldCheckIcon width={22} height={22} />, h: f.controlH, p: f.controlP },
  ];

  return (
    <section id="features" className="landing-features">
      <div className="landing-container">
        <div className="landing-label-tag">{f.tag}</div>
        <h2 className="landing-section-h">{f.h2}</h2>
        <div className="landing-features-grid">
          {cards.map((c, i) => (
            <div key={i} className="landing-feat-card">
              <div className="landing-feat-icon">{c.icon}</div>
              <h3 className="landing-feat-h">{c.h}</h3>
              <p className="landing-feat-p">{c.p}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
