import { useState } from "react";
import { useT } from "../../i18n";

const FORMSPREE_ENDPOINT = "https://formspree.io/dczarnota@gmail.com";

type Status = "idle" | "submitting" | "success" | "error";

export function LandingContact() {
  const t = useT();
  const c = t.landing.contact;
  const [status, setStatus] = useState<Status>("idle");

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    const form = e.currentTarget;
    try {
      const res = await fetch(FORMSPREE_ENDPOINT, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
      });
      setStatus(res.ok ? "success" : "error");
    } catch {
      setStatus("error");
    }
  }

  return (
    <section id="contact" className="landing-contact">
      <div className="landing-container">
        <div className="landing-contact-inner">
          <div className="landing-contact-info">
            <div className="landing-label-tag">{c.tag}</div>
            <h2 className="landing-section-h landing-on-dark-h">{c.h}</h2>
            <p className="landing-section-sub landing-on-dark-sub">{c.sub}</p>
            <div className="landing-contact-info-row">
              <div className="landing-contact-info-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
                </svg>
              </div>
              <div>
                <div className="landing-contact-info-label">E-mail</div>
                <div className="landing-contact-info-value">{c.infoEmail}</div>
              </div>
            </div>
            <div className="landing-contact-info-row">
              <div className="landing-contact-info-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 10a5 5 0 0 1-5 5"/><path d="M3 10a9 9 0 0 0 9 9"/><path d="M21 10a9 9 0 0 0-9-9"/><circle cx="12" cy="10" r="3"/>
                </svg>
              </div>
              <div>
                <div className="landing-contact-info-label">Demo</div>
                <div className="landing-contact-info-value">{c.infoDemo}</div>
              </div>
            </div>
          </div>

          <div className="landing-contact-form">
            {status === "success" ? (
              <div className="landing-contact-success">
                <div style={{ fontSize: 40, marginBottom: 16 }}>✓</div>
                <div className="landing-contact-success-h">{c.successH}</div>
                <div className="landing-contact-success-p">{c.successP}</div>
              </div>
            ) : (
              <form onSubmit={handleSubmit}>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelName}</label>
                  <input name="name" type="text" required className="landing-contact-input" placeholder={c.placeholderName} />
                </div>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelEmail}</label>
                  <input name="email" type="email" required className="landing-contact-input" placeholder={c.placeholderEmail} />
                </div>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelCompany}</label>
                  <input name="company" type="text" className="landing-contact-input" placeholder={c.placeholderCompany} />
                </div>
                <div className="landing-contact-row">
                  <label className="landing-contact-label">{c.labelMessage}</label>
                  <textarea name="message" required className="landing-contact-textarea" placeholder={c.placeholderMessage} />
                </div>
                <button type="submit" className="landing-contact-submit" disabled={status === "submitting"}>
                  {status === "submitting" ? c.submitting : c.submit}
                </button>
                {status === "error" && <div className="landing-contact-error">{c.errorP}</div>}
              </form>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
