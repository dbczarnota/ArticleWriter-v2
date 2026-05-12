import { useT } from "../../i18n";
import { CheckIcon, BoltIcon } from "./icons";

export function LandingStreamsSpotlight() {
  const t = useT();
  const s = t.landing.streams;

  return (
    <section className="landing-streams">
      <div className="landing-container">
        <div className="landing-streams-grid">
          <div className="landing-streams-mock">
            <div className="landing-stream-bar">
              <div className="landing-stream-live">
                <div className="landing-stream-live-dot" /> LIVE
              </div>
              <span style={{ fontSize: 11, color: "#6b7280" }}>TVN24</span>
            </div>
            <div className="landing-stream-body">
              <div className="landing-stream-chunk">
                <div className="landing-stream-chunk-label">{s.mockChunkLabel}</div>
                <div className="landing-stream-chunk-text">{s.mockChunkText}</div>
              </div>
              <div className="landing-stream-topic">
                <div className="landing-stream-topic-label">
                  <BoltIcon width={11} height={11} />
                  {s.mockTopicLabel}
                </div>
                <div className="landing-stream-topic-title">{s.mockTopicTitle}</div>
              </div>
            </div>
          </div>

          <div>
            <div className="landing-label-tag">{s.tag}</div>
            <h2 className="landing-section-h">{s.h}</h2>
            <p className="landing-section-sub">{s.sub}</p>
            <div className="landing-points landing-points-light" style={{ marginTop: 24 }}>
              <div className="landing-point">
                <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                <div className="landing-point-text"><strong>{s.point1Strong}</strong>{s.point1}</div>
              </div>
              <div className="landing-point">
                <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                <div className="landing-point-text"><strong>{s.point2Strong}</strong>{s.point2}</div>
              </div>
              <div className="landing-point">
                <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                <div className="landing-point-text"><strong>{s.point3Strong}</strong>{s.point3}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
