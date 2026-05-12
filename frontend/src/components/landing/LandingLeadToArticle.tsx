import { useT } from "../../i18n";
import { CheckIcon, BoltIcon, InstagramIcon, XIcon, YouTubeIcon, TikTokIcon } from "./icons";

export function LandingLeadToArticle() {
  const t = useT();
  const l = t.landing.lead;

  return (
    <section className="landing-lead">
      <div className="landing-container">
        <div className="landing-split">
          <div>
            <div className="landing-label-tag" style={{ color: "#fb923c" }}>{l.tag}</div>
            <h2 className="landing-section-h landing-on-dark-h">{l.h}</h2>
            <p className="landing-section-sub landing-on-dark-sub">{l.sub}</p>
            <div className="landing-points" style={{ marginTop: 28 }}>
              {([
                [l.point1Strong, l.point1],
                [l.point2Strong, l.point2],
                [l.point3Strong, l.point3],
                [l.point4Strong, l.point4],
                [l.point5Strong, l.point5],
                [l.point6Strong, l.point6],
              ] as [string, string][]).map(([strong, rest], i) => (
                <div className="landing-point" key={i}>
                  <div className="landing-point-check"><CheckIcon width={12} height={12} /></div>
                  <div className="landing-point-text"><strong>{strong}</strong>{rest}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="landing-lead-mock">
            <div className="landing-lead-mock-label">{l.mockLabel}</div>
            <div className="landing-lead-sources">
              <div className="landing-lead-source">
                <div className="landing-lead-source-icon" style={{ background: "linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045)" }}>
                  <InstagramIcon width={14} height={14} />
                </div>
                <div className="landing-lead-source-text">Instagram<small>{l.mockSourceIgSub}</small></div>
              </div>
              <div className="landing-lead-source">
                <div className="landing-lead-source-icon" style={{ background: "#000" }}>
                  <XIcon width={13} height={13} />
                </div>
                <div className="landing-lead-source-text">X<small>{l.mockSourceXSub}</small></div>
              </div>
              <div className="landing-lead-source">
                <div className="landing-lead-source-icon" style={{ background: "#ff0000" }}>
                  <YouTubeIcon width={14} height={14} />
                </div>
                <div className="landing-lead-source-text">YouTube<small>{l.mockSourceYtSub}</small></div>
              </div>
              <div className="landing-lead-source">
                <div className="landing-lead-source-icon" style={{ background: "#000" }}>
                  <TikTokIcon width={13} height={13} />
                </div>
                <div className="landing-lead-source-text">TikTok<small>{l.mockSourceTtSub}</small></div>
              </div>
            </div>

            <div className="landing-lead-arrow"><div className="landing-lead-arrow-line" /></div>

            <div className="landing-lead-output">
              <div className="landing-lead-output-label">
                <BoltIcon width={11} height={11} />
                {l.mockOutputLabel}
              </div>
              <div className="landing-lead-output-title">{l.mockOutputTitle}</div>
              <div className="landing-lead-output-line" />
              <div className="landing-lead-output-line" />

              <div className="landing-lead-output-divider" />

              <div className="landing-lead-output-section">
                <div className="landing-lead-output-section-label">{l.mockAltLabel}</div>
                <div className="landing-lead-alt-row">{l.mockAlt1}</div>
                <div className="landing-lead-alt-row">{l.mockAlt2}</div>
                <div className="landing-lead-alt-row">{l.mockAlt3}</div>
              </div>

              <div className="landing-lead-output-divider" />

              <div className="landing-lead-output-section">
                <div className="landing-lead-output-section-label">{l.mockFbLabel}</div>
                <div className="landing-lead-fb-text">{l.mockFbText}</div>
              </div>

              <div className="landing-lead-output-divider" />

              <div className="landing-lead-output-section">
                <div className="landing-lead-output-section-label">{l.mockMediaLabel}</div>
                <div className="landing-lead-media-row">
                  <div className="landing-lead-media-thumb" />
                  <div className="landing-lead-media-info">
                    <strong>{l.mockMediaLabel}</strong>
                    {l.mockMediaSub}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
