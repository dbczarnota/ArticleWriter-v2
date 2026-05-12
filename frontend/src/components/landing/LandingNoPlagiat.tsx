import { useT } from "../../i18n";
import { ShieldCheckIcon } from "./icons";

export function LandingNoPlagiat() {
  const t = useT();
  const n = t.landing.noPlagiat;

  return (
    <section className="landing-no-plagiat">
      <div className="landing-container">
        <div className="landing-plagiat-banner">
          <div className="landing-plagiat-icon">
            <ShieldCheckIcon width={32} height={32} strokeWidth={1.6} />
          </div>
          <div className="landing-plagiat-body">
            <div className="landing-plagiat-label">{n.label}</div>
            <div className="landing-plagiat-h">{n.h}</div>
            <div className="landing-plagiat-p">{n.p}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
