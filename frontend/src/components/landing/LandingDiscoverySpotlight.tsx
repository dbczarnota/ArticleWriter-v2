import { useT } from "../../i18n";
import { CheckIcon } from "./icons";

export function LandingDiscoverySpotlight() {
  const t = useT();
  const d = t.landing.discovery;

  return (
    <section className="landing-discovery">
      <div className="landing-container">
        <div className="landing-split">
          <div>
            <div className="landing-label-tag" style={{ color: "#fb923c" }}>{d.tag}</div>
            <h2 className="landing-section-h landing-on-dark-h">{d.h}</h2>
            <p className="landing-section-sub landing-on-dark-sub">{d.sub}</p>
            <div className="landing-points">
              <div className="landing-point">
                <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                <div className="landing-point-text"><strong>{d.point1Strong}</strong>{d.point1}</div>
              </div>
              <div className="landing-point">
                <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                <div className="landing-point-text"><strong>{d.point2Strong}</strong>{d.point2}</div>
              </div>
              <div className="landing-point">
                <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                <div className="landing-point-text"><strong>{d.point3Strong}</strong>{d.point3}</div>
              </div>
            </div>
          </div>

          <div className="landing-mock-panel">
            <div className="landing-mock-bar">
              <div className="landing-mock-dot" style={{ background: "#ef4444" }} />
              <div className="landing-mock-dot" style={{ background: "#f59e0b", margin: "0 4px" }} />
              <div className="landing-mock-dot" style={{ background: "#22c55e" }} />
              <span style={{ fontSize: 11, color: "#6b7280", marginLeft: 10 }}>{d.mockTitle}</span>
            </div>
            <div className="landing-mock-body">
              <div className="landing-mock-row hot">
                <div className="landing-mock-row-dot" style={{ background: "#ea580c" }} />
                <div className="landing-mock-row-title">{d.mockRow1}</div>
                <span className="landing-mock-badge hot">{d.mockRow1Count}</span>
              </div>
              <div className="landing-mock-row">
                <div className="landing-mock-row-dot" style={{ background: "#f59e0b" }} />
                <div className="landing-mock-row-title">{d.mockRow2}</div>
                <span className="landing-mock-badge neutral">{d.mockRow2Count}</span>
              </div>
              <div className="landing-mock-row">
                <div className="landing-mock-row-dot" style={{ background: "#6b7280" }} />
                <div className="landing-mock-row-title">{d.mockRow3}</div>
                <span className="landing-mock-badge neutral">{d.mockRow3Count}</span>
              </div>
              <div className="landing-mock-row">
                <div className="landing-mock-row-dot" style={{ background: "#6b7280" }} />
                <div className="landing-mock-row-title">{d.mockRow4}</div>
                <span className="landing-mock-badge neutral">{d.mockRow4Count}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
