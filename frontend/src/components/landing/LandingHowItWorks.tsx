import { useT } from "../../i18n";
import { RadioTowerIcon, PenLineIcon, ArrowUpRightIcon } from "./icons";

export function LandingHowItWorks() {
  const t = useT();
  const h = t.landing.how;

  return (
    <section id="how" className="landing-how">
      <div className="landing-container">
        <div className="landing-label-tag">{h.tag}</div>
        <h2 className="landing-section-h">{h.h2}</h2>
        <p className="landing-section-sub">{h.sub}</p>

        <div className="landing-how-tracks">
          {/* Track A */}
          <div className="landing-track">
            <div className="landing-track-header">
              <div className="landing-track-icon" style={{ background: "#eff6ff", color: "#1d4ed8" }}>
                <RadioTowerIcon width={22} height={22} />
              </div>
              <div>
                <div className="landing-track-title">{h.trackATitle}</div>
                <div className="landing-track-sub">{h.trackASub}</div>
              </div>
            </div>
            <div className="landing-track-steps">
              <div className="landing-track-step">
                <div className="landing-track-step-dot" style={{ background: "#dbeafe", color: "#1d4ed8" }}>1</div>
                <div className="landing-track-step-body">
                  <div className="landing-track-step-h">{h.trackAStep1H}</div>
                  <div className="landing-track-step-p">{h.trackAStep1P}</div>
                  <div className="landing-step-pills">
                    <span className="landing-pill">{h.trackAStep1Pill1}</span>
                    <span className="landing-pill">{h.trackAStep1Pill2}</span>
                    <span className="landing-pill">{h.trackAStep1Pill3}</span>
                  </div>
                </div>
              </div>
              <div className="landing-track-step">
                <div className="landing-track-step-dot" style={{ background: "#dbeafe", color: "#1d4ed8" }}>2</div>
                <div className="landing-track-step-body">
                  <div className="landing-track-step-h">{h.trackAStep2H}</div>
                  <div className="landing-track-step-p">{h.trackAStep2P}</div>
                </div>
              </div>
              <div className="landing-track-step">
                <div className="landing-track-step-dot" style={{ background: "#dbeafe", color: "#1d4ed8" }}>3</div>
                <div className="landing-track-step-body">
                  <div className="landing-track-step-h">{h.trackAStep3H}</div>
                  <div className="landing-track-step-p">{h.trackAStep3P}</div>
                  <div className="landing-step-pills">
                    <span className="landing-pill accent">{h.trackAStep3Pill}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Track B */}
          <div className="landing-track">
            <div className="landing-track-header">
              <div className="landing-track-icon" style={{ background: "#fff7ed", color: "#ea580c" }}>
                <PenLineIcon width={22} height={22} />
              </div>
              <div>
                <div className="landing-track-title">{h.trackBTitle}</div>
                <div className="landing-track-sub">{h.trackBSub}</div>
              </div>
            </div>
            <div className="landing-track-steps">
              <div className="landing-track-step">
                <div className="landing-track-step-dot" style={{ background: "#fff7ed", color: "#ea580c" }}>1</div>
                <div className="landing-track-step-body">
                  <div className="landing-track-step-h">{h.trackBStep1H}</div>
                  <div className="landing-track-step-p">{h.trackBStep1P}</div>
                  <div className="landing-step-pills">
                    <span className="landing-pill">{h.trackBStep1Pill1}</span>
                    <span className="landing-pill">{h.trackBStep1Pill2}</span>
                    <span className="landing-pill">{h.trackBStep1Pill3}</span>
                  </div>
                </div>
              </div>
              <div className="landing-track-step">
                <div className="landing-track-step-dot" style={{ background: "#fff7ed", color: "#ea580c" }}>2</div>
                <div className="landing-track-step-body">
                  <div className="landing-track-step-h">{h.trackBStep2H}</div>
                  <div className="landing-track-step-p">{h.trackBStep2P}</div>
                  <div className="landing-step-pills">
                    <span className="landing-pill">{h.trackBStep2Pill1}</span>
                    <span className="landing-pill accent">{h.trackBStep2Pill2}</span>
                  </div>
                </div>
              </div>
              <div className="landing-track-step">
                <div className="landing-track-step-dot" style={{ background: "#fff7ed", color: "#ea580c" }}>3</div>
                <div className="landing-track-step-body">
                  <div className="landing-track-step-h">{h.trackBStep3H}</div>
                  <div className="landing-track-step-p">{h.trackBStep3P}</div>
                  <div className="landing-step-pills">
                    <span className="landing-pill accent">{h.trackBStep3Pill1}</span>
                    <span className="landing-pill">{h.trackBStep3Pill2}</span>
                    <span className="landing-pill">{h.trackBStep3Pill3}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Convergence */}
          <div className="landing-how-convergence">
            <div className="landing-conv-icon">
              <ArrowUpRightIcon width={22} height={22} />
            </div>
            <div className="landing-conv-body">
              <div className="landing-conv-label">{h.convLabel}</div>
              <div className="landing-conv-h">{h.convH}</div>
              <div className="landing-conv-p">{h.convP}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
