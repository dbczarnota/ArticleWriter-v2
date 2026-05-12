import { useEffect } from "react";
import { LandingNav } from "./landing/LandingNav";
import { LandingHero } from "./landing/LandingHero";
import { LandingHowItWorks } from "./landing/LandingHowItWorks";
import { LandingFeatures } from "./landing/LandingFeatures";
import { LandingDiscoverySpotlight } from "./landing/LandingDiscoverySpotlight";
import { LandingStreamsSpotlight } from "./landing/LandingStreamsSpotlight";
import { LandingLeadToArticle } from "./landing/LandingLeadToArticle";
import { LandingAudience } from "./landing/LandingAudience";
import { LandingNoPlagiat } from "./landing/LandingNoPlagiat";
import { LandingContact } from "./landing/LandingContact";
import { LandingCtaBottom } from "./landing/LandingCtaBottom";
import { LandingFooter } from "./landing/LandingFooter";

export function LandingPage() {
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    const el = document.getElementById(hash);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }, []);

  return (
    <div className="landing-root">
      <LandingNav />
      <LandingHero />
      <LandingHowItWorks />
      <LandingFeatures />
      <LandingDiscoverySpotlight />
      <LandingStreamsSpotlight />
      <LandingLeadToArticle />
      <LandingAudience />
      <LandingNoPlagiat />
      <LandingContact />
      <LandingCtaBottom />
      <LandingFooter />
    </div>
  );
}
