import { PUBLIC_COPY, type ReaderLocale } from "../lib/locale";

type PublicSiteFooterProps = {
  copy: (typeof PUBLIC_COPY)[ReaderLocale];
  hideDisclaimerLink?: boolean;
};

export default function PublicSiteFooter({
  copy,
  hideDisclaimerLink = false,
}: PublicSiteFooterProps) {
  return (
    <footer className="public-site-footer">
      <div>
        <p className="public-kicker">{copy.disclaimerFooterKicker}</p>
        <p className="body-copy">{copy.disclaimerFooterBody}</p>
      </div>
      {hideDisclaimerLink ? null : (
        <a className="secondary-action" href="/disclaimer">
          {copy.disclaimerLinkLabel}
        </a>
      )}
    </footer>
  );
}
