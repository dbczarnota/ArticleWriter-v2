import { useT } from "../../i18n";

export function LandingFooter() {
  const t = useT();
  const f = t.landing.footer;

  return (
    <footer className="landing-footer">
      <div className="landing-container">
        <div className="landing-footer-inner">
          <div>
            <a href="#" className="landing-logo">
              <div className="landing-logo-bar" />
              <div className="landing-logo-stack">
                <div className="landing-logo-name"><span className="lt">headlines</span><span className="bd">forge</span></div>
                <div className="landing-logo-sub">AI Newsroom Platform</div>
              </div>
            </a>
            <p className="landing-footer-tagline">{f.tagline}</p>
          </div>
          <div className="landing-footer-col">
            <h4>{f.productH}</h4>
            <ul>
              <li><a href="#how">{f.productHowItWorks}</a></li>
              <li><a href="#features">{f.productFeatures}</a></li>
              <li><a href="#">{f.productDiscovery}</a></li>
              <li><a href="#">{f.productStreams}</a></li>
            </ul>
          </div>
          <div className="landing-footer-col">
            <h4>{f.newsroomsH}</h4>
            <ul>
              <li><a href="#">{f.newsroomsNews}</a></li>
              <li><a href="#">{f.newsroomsLifestyle}</a></li>
              <li><a href="#">{f.newsroomsSports}</a></li>
              <li><a href="#">{f.newsroomsBusiness}</a></li>
            </ul>
          </div>
          <div className="landing-footer-col">
            <h4>{f.companyH}</h4>
            <ul>
              <li><a href="#">{f.companyAbout}</a></li>
              <li><a href="mailto:hello@headlinesforge.com">{f.companyContact}</a></li>
              <li><a href="#">{f.companyPrivacy}</a></li>
            </ul>
          </div>
        </div>
        <div className="landing-footer-bottom">
          <p>{f.copyright}</p>
          <p>{f.tagline2}</p>
        </div>
      </div>
    </footer>
  );
}
